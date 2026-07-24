#!/usr/bin/env python3
"""Audit an Akash SDL for a small, defensible production security baseline.

The optional sanitized copy is suitable for source control review. It is not
deployable until every REDACTED value is replaced outside the repository.
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SENSITIVE_NAME = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9._-]{12,}\b")
MAX_BODY_BYTES = 10 * 1024 * 1024
MAX_TIMEOUT_MS = 60_000


@dataclass(frozen=True)
class Finding:
    severity: str
    location: str
    message: str


def _env_pairs(service: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for entry in service.get("env", []) or []:
        if isinstance(entry, str) and "=" in entry:
            name, value = entry.split("=", 1)
            pairs.append((name, value))
    return pairs


def _is_pinned(image: str) -> bool:
    if "@sha256:" in image:
        return True
    final_component = image.rsplit("/", 1)[-1]
    return ":" in final_component and "latest" not in final_component.rsplit(":", 1)[-1].lower()


def audit(document: dict[str, Any], public_service: str) -> list[Finding]:
    findings: list[Finding] = []
    services = document.get("services")
    if not isinstance(services, dict) or not services:
        return [Finding("ERROR", "services", "SDL has no service definitions")]

    globally_exposed: set[str] = set()
    for name, raw_service in services.items():
        location = f"services.{name}"
        if not isinstance(raw_service, dict):
            findings.append(Finding("ERROR", location, "service definition is not a mapping"))
            continue
        service = raw_service
        image = service.get("image")
        if not isinstance(image, str) or not _is_pinned(image):
            findings.append(
                Finding("ERROR", f"{location}.image", "pin an explicit version or sha256 digest; do not use latest")
            )
        elif "@sha256:" not in image:
            findings.append(
                Finding("WARN", f"{location}.image", "version tag is acceptable, but a sha256 digest is immutable")
            )

        for env_name, env_value in _env_pairs(service):
            if SENSITIVE_NAME.search(env_name) and env_value and env_value != "REDACTED":
                findings.append(
                    Finding(
                        "WARN",
                        f"{location}.env.{env_name}",
                        "secret is embedded in the SDL/provider manifest; sanitize before source control",
                    )
                )
            elif SECRET_VALUE.search(env_value):
                findings.append(
                    Finding(
                        "WARN",
                        f"{location}.env.{env_name}",
                        "secret-like token is embedded inline in the SDL/provider manifest; sanitize before source control",
                    )
                )

        for field in ("command", "args"):
            value = service.get(field)
            entries = [value] if isinstance(value, str) else value if isinstance(value, list) else []
            for index, entry in enumerate(entries):
                if isinstance(entry, str) and SECRET_VALUE.search(entry):
                    suffix = "" if isinstance(value, str) else f"[{index}]"
                    findings.append(
                        Finding(
                            "WARN",
                            f"{location}.{field}{suffix}",
                            "secret-like token is embedded inline in the SDL/provider manifest; sanitize before source control",
                        )
                    )

        for index, exposure in enumerate(service.get("expose", []) or []):
            if not isinstance(exposure, dict):
                continue
            targets = exposure.get("to", []) or []
            is_global = any(isinstance(target, dict) and target.get("global") is True for target in targets)
            if not is_global:
                continue
            globally_exposed.add(str(name))
            exposure_location = f"{location}.expose[{index}]"
            options = exposure.get("http_options")
            if not isinstance(options, dict):
                findings.append(Finding("ERROR", exposure_location, "global HTTP port needs http_options limits"))
                continue
            body_size = options.get("max_body_size")
            if not isinstance(body_size, int) or body_size > MAX_BODY_BYTES:
                findings.append(Finding("ERROR", exposure_location, "max_body_size must be at most 10 MiB"))
            for field in ("read_timeout", "send_timeout"):
                timeout = options.get(field)
                if not isinstance(timeout, int) or timeout > MAX_TIMEOUT_MS:
                    findings.append(Finding("ERROR", exposure_location, f"{field} must be at most 60000 ms"))

    if public_service not in services:
        findings.append(Finding("ERROR", "services", f"expected public gateway {public_service!r} is absent"))
    unexpected = globally_exposed - {public_service}
    for name in sorted(unexpected):
        findings.append(Finding("ERROR", f"services.{name}.expose", "backend is globally exposed"))
    if public_service not in globally_exposed:
        findings.append(Finding("ERROR", f"services.{public_service}.expose", "gateway is not globally exposed"))

    return findings


def sanitize(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for service in (result.get("services") or {}).values():
        if not isinstance(service, dict):
            continue
        cleaned_env: list[Any] = []
        for entry in service.get("env", []) or []:
            if isinstance(entry, str) and "=" in entry:
                name, value = entry.split("=", 1)
                if SENSITIVE_NAME.search(name):
                    entry = f"{name}=REDACTED"
                else:
                    entry = f"{name}={SECRET_VALUE.sub('REDACTED', value)}"
            cleaned_env.append(entry)
        if "env" in service:
            service["env"] = cleaned_env
        for field in ("command", "args"):
            value = service.get(field)
            if isinstance(value, str):
                service[field] = SECRET_VALUE.sub("REDACTED", value)
            elif isinstance(value, list):
                service[field] = [SECRET_VALUE.sub("REDACTED", item) if isinstance(item, str) else item for item in value]
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdl", type=Path, help="Akash deploy.yaml to audit")
    parser.add_argument("--public-service", default="litellm", help="only service allowed global exposure")
    parser.add_argument("--sanitized-output", type=Path, help="write a secret-redacted review copy")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        loaded = yaml.safe_load(args.sdl.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR {args.sdl}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(loaded, dict):
        print(f"ERROR {args.sdl}: root document must be a mapping", file=sys.stderr)
        return 2

    findings = audit(loaded, args.public_service)
    for finding in findings:
        print(f"{finding.severity} {finding.location}: {finding.message}")
    if args.sanitized_output:
        args.sanitized_output.parent.mkdir(parents=True, exist_ok=True)
        args.sanitized_output.write_text(
            yaml.safe_dump(sanitize(loaded), sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        print(f"SANITIZED {args.sanitized_output}")

    errors = any(finding.severity == "ERROR" for finding in findings)
    warnings = any(finding.severity == "WARN" for finding in findings)
    if not findings:
        print("PASS minimum Akash security baseline")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
