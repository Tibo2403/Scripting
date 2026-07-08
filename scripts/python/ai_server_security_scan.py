"""Authorized server security scanner with optional AI-assisted reporting.

The scanner is intentionally non-destructive: it performs TCP connect checks,
light banner/header collection, TLS certificate inspection, and local risk
summaries. An optional OpenAI-compatible API call can turn the structured
findings into a prioritized remediation plan.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PORTS = "22,25,53,80,110,143,443,445,465,587,993,995,1433,1521,2375,2376,3306,3389,5432,5601,5900,6379,8000,8080,8443,9200,9300,11211,27017"
COMMON_SERVICE_RISKS = {
    21: ("medium", "FTP is often cleartext. Prefer SFTP or disable if unused."),
    22: ("info", "SSH is exposed. Enforce keys, MFA where available, and fail2ban or equivalent."),
    23: ("high", "Telnet is cleartext and should be disabled."),
    25: ("medium", "SMTP is exposed. Confirm relay restrictions and TLS policy."),
    80: ("info", "HTTP is exposed. Redirect to HTTPS when possible."),
    110: ("medium", "POP3 is exposed. Prefer TLS-only access."),
    143: ("medium", "IMAP is exposed. Prefer TLS-only access."),
    445: ("high", "SMB is exposed. Restrict to private networks and patch aggressively."),
    1433: ("high", "SQL Server is exposed. Restrict by firewall and require strong authentication."),
    2375: ("critical", "Docker API without TLS is commonly dangerous. Do not expose it."),
    3306: ("high", "MySQL is exposed. Restrict by firewall and disable public access."),
    3389: ("high", "RDP is exposed. Require VPN, MFA, NLA, and lockout policy."),
    5432: ("high", "PostgreSQL is exposed. Restrict by firewall and require TLS/auth hardening."),
    5900: ("high", "VNC is exposed. Require VPN and strong authentication."),
    6379: ("critical", "Redis should not be internet-exposed without strict controls."),
    9200: ("high", "Elasticsearch is exposed. Require auth, TLS, and network restrictions."),
    11211: ("critical", "Memcached should not be internet-exposed."),
    27017: ("critical", "MongoDB is exposed. Require auth, TLS, and network restrictions."),
}
HTTP_PORTS = {80, 8000, 8080}
HTTPS_PORTS = {443, 8443}
SECURITY_HEADERS = {
    "strict-transport-security": "Add HSTS on HTTPS responses.",
    "content-security-policy": "Add a Content-Security-Policy appropriate for the app.",
    "x-content-type-options": "Add X-Content-Type-Options: nosniff.",
    "x-frame-options": "Add clickjacking protection or CSP frame-ancestors.",
    "referrer-policy": "Add Referrer-Policy.",
}
SEVERITY_SCORE = {"info": 10, "low": 25, "medium": 50, "high": 75, "critical": 95}
ADMIN_PORTS = {22, 2375, 2376, 3389, 5900}
DATASTORE_PORTS = {1433, 1521, 3306, 5432, 6379, 9200, 9300, 11211, 27017}
MAIL_PORTS = {25, 110, 143, 465, 587, 993, 995}


@dataclass
class PortObservation:
    port: int
    status: str
    service_hint: str = ""
    banner: str = ""
    risk: str = "info"
    notes: list[str] = field(default_factory=list)


def parse_ports(raw: str) -> list[int]:
    ports: set[int] = set()
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        if "-" in value:
            start_raw, end_raw = value.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                raise ValueError(f"Invalid port range: {value}")
            ports.update(range(start, end + 1))
        else:
            ports.add(int(value))
    invalid = [port for port in ports if port < 1 or port > 65535]
    if invalid:
        raise ValueError(f"Invalid TCP ports: {invalid}")
    return sorted(ports)


def normalize_target(target: str) -> tuple[str, str | None]:
    target = target.strip()
    if not target:
        raise ValueError("Target is required.")
    if any(marker in target for marker in ("*", " ")):
        raise ValueError("Only one explicit host, IP, or URL is supported. No ranges or wildcards.")

    parsed = urllib.parse.urlparse(target if "://" in target else f"//{target}")
    if parsed.path and not parsed.scheme:
        raise ValueError("Only one explicit host, IP, or URL is supported. No ranges or wildcards.")
    host = parsed.hostname
    scheme = parsed.scheme if parsed.scheme else None
    if not host:
        raise ValueError(f"Could not parse target: {target}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
            raise ValueError(f"Unexpected target hostname: {host}")
    return host, scheme


def connect_port(host: str, port: int, timeout: float) -> PortObservation:
    observation = PortObservation(port=port, status="closed")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            observation.status = "open"
            observation.service_hint = service_name(port)
            sock.settimeout(timeout)
            try:
                banner = sock.recv(160)
                observation.banner = banner.decode("utf-8", errors="replace").strip()
            except (OSError, TimeoutError):
                observation.banner = ""
    except (OSError, TimeoutError):
        observation.status = "closed"

    if observation.status == "open":
        severity, note = COMMON_SERVICE_RISKS.get(
            port, ("info", "Open port. Confirm it is required and access-controlled.")
        )
        observation.risk = severity
        observation.notes.append(note)
    return observation


def service_name(port: int) -> str:
    try:
        return socket.getservbyport(port, "tcp")
    except OSError:
        return ""


def fetch_http_headers(host: str, port: int, tls: bool, timeout: float) -> dict[str, Any]:
    scheme = "https" if tls else "http"
    url = f"{scheme}://{host}:{port}/"
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "Scripting-AI-Security-Scanner/1.0"},
    )
    try:
        context = ssl.create_default_context() if tls else None
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return {
                "url": url,
                "status": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001 - report probe failure, do not crash scan.
        return {"url": url, "status": None, "headers": {}, "error": str(exc)}


def inspect_tls(host: str, port: int, timeout: float) -> dict[str, Any]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as wrapped:
                cert = wrapped.getpeercert()
                not_after = cert.get("notAfter")
                expires_at = None
                days_remaining = None
                if not_after:
                    expires_at = dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                        tzinfo=dt.UTC
                    )
                    days_remaining = (expires_at - dt.datetime.now(dt.UTC)).days
                return {
                    "port": port,
                    "protocol": wrapped.version(),
                    "cipher": wrapped.cipher()[0] if wrapped.cipher() else None,
                    "subject": cert.get("subject", []),
                    "issuer": cert.get("issuer", []),
                    "expires_at": expires_at.isoformat() + "Z" if expires_at else None,
                    "days_remaining": days_remaining,
                    "error": "",
                }
    except Exception as exc:  # noqa: BLE001 - TLS failures are findings.
        return {"port": port, "error": str(exc)}


def local_findings(
    ports: list[PortObservation], http_results: list[dict[str, Any]], tls_results: list[dict[str, Any]]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for observation in ports:
        if observation.status != "open":
            continue
        severity = observation.risk
        note = " ".join(observation.notes)
        findings.append(
            {
                "severity": severity,
                "title": f"Open TCP port {observation.port}",
                "evidence": f"Service hint: {observation.service_hint or 'unknown'}",
                "recommendation": note,
            }
        )

    for result in http_results:
        if result.get("error"):
            findings.append(
                {
                    "severity": "low",
                    "title": f"HTTP probe failed for {result['url']}",
                    "evidence": result["error"],
                    "recommendation": "Confirm whether the service requires GET, SNI, authentication, or firewall access.",
                }
            )
            continue
        headers = result.get("headers", {})
        for header, recommendation in SECURITY_HEADERS.items():
            if header not in headers:
                findings.append(
                    {
                        "severity": "medium" if header == "strict-transport-security" else "low",
                        "title": f"Missing HTTP security header: {header}",
                        "evidence": result["url"],
                        "recommendation": recommendation,
                    }
                )

    for result in tls_results:
        if result.get("error"):
            findings.append(
                {
                    "severity": "medium",
                    "title": f"TLS inspection failed on port {result['port']}",
                    "evidence": result["error"],
                    "recommendation": "Check certificate validity, supported TLS versions, and SNI configuration.",
                }
            )
            continue
        days = result.get("days_remaining")
        if isinstance(days, int) and days < 30:
            findings.append(
                {
                    "severity": "high" if days < 7 else "medium",
                    "title": f"TLS certificate expires soon on port {result['port']}",
                    "evidence": f"{days} days remaining",
                    "recommendation": "Renew the certificate and verify automated renewal.",
                }
            )
    return findings


def classify_finding(finding: dict[str, str], exposure: str) -> dict[str, Any]:
    title = finding.get("title", "")
    evidence = finding.get("evidence", "")
    severity = finding.get("severity", "info")
    score = SEVERITY_SCORE.get(severity, 10)
    tags: list[str] = []

    port_match = re.search(r"\bport (\d+)\b", title, flags=re.IGNORECASE)
    port = int(port_match.group(1)) if port_match else None
    if port in ADMIN_PORTS:
        tags.append("remote-admin")
        score += 12
    if port in DATASTORE_PORTS:
        tags.append("data-store")
        score += 15
    if port in MAIL_PORTS:
        tags.append("mail-service")
        score += 6
    if "missing http security header" in title.lower():
        tags.append("web-hardening")
    if "tls" in title.lower():
        tags.append("tls")
    if exposure == "internet":
        score += 10
        tags.append("internet-exposed")
    elif exposure == "internal":
        score -= 8
        tags.append("internal-only")
    if "unknown" in evidence.lower():
        tags.append("needs-owner-confirmation")

    score = max(0, min(100, score))
    if score >= 85:
        effort = "same-day containment"
        first_day_action = "Restrict exposure immediately, then validate service ownership."
    elif score >= 65:
        effort = "same-day fix"
        first_day_action = "Apply firewall or configuration hardening before expanding the pilot."
    elif score >= 40:
        effort = "planned quick win"
        first_day_action = "Schedule a short hardening task and capture before/after evidence."
    else:
        effort = "monitor"
        first_day_action = "Confirm the service is expected and keep it in the evidence log."

    enriched = dict(finding)
    enriched.update(
        {
            "priority_score": score,
            "triage_tags": sorted(set(tags)),
            "day_one_action": first_day_action,
            "estimated_effort": effort,
            "verification": "Re-run this scanner and compare the JSON/Markdown output after remediation.",
        }
    )
    return enriched


def enrich_findings(findings: list[dict[str, str]], exposure: str) -> list[dict[str, Any]]:
    enriched = [classify_finding(finding, exposure) for finding in findings]
    return sorted(enriched, key=lambda item: (-int(item["priority_score"]), item["title"]))


def build_ai_triage(report: dict[str, Any]) -> dict[str, Any]:
    findings = report.get("findings", [])
    critical_or_high = [
        finding
        for finding in findings
        if finding.get("severity") in {"critical", "high"} or finding.get("priority_score", 0) >= 75
    ]
    quick_wins = [
        finding
        for finding in findings
        if finding.get("estimated_effort") in {"same-day fix", "planned quick win"}
    ][:5]
    open_ports = [item["port"] for item in report.get("ports", []) if item.get("status") == "open"]
    return {
        "risk_posture": "needs immediate containment" if critical_or_high else "manageable with hardening",
        "open_port_count": len(open_ports),
        "open_ports": open_ports,
        "top_risks": critical_or_high[:5],
        "quick_wins": quick_wins,
        "recommended_next_scan": "Run again after firewall/header/TLS changes and compare priority_score deltas.",
    }


def build_local_remediation_plan(report: dict[str, Any]) -> str:
    triage = report.get("ai_triage", {})
    findings = report.get("findings", [])
    if not findings:
        return "No local findings from the selected checks. Keep the evidence and rerun after any infrastructure change."

    lines = [
        f"Local AI-style triage: {triage.get('risk_posture', 'unknown')}.",
        "Day-one remediation order:",
    ]
    for index, finding in enumerate(findings[:7], start=1):
        tags = ", ".join(finding.get("triage_tags", [])) or "general"
        lines.append(
            f"{index}. [{finding.get('priority_score', 0)}/100] "
            f"{finding['title']} ({tags}) - {finding['day_one_action']}"
        )
    lines.append("Verification: rerun the scanner with the same ports and attach the before/after reports.")
    return "\n".join(lines)


def build_ai_prompt(report: dict[str, Any]) -> str:
    compact = json.dumps(report, indent=2, sort_keys=True)[:12000]
    return textwrap.dedent(
        f"""
        You are a defensive cybersecurity analyst. Review this authorized,
        non-destructive server scan and produce a concise remediation plan.

        Rules:
        - Do not provide exploit instructions.
        - Prioritize business risk, quick wins, and verification steps.
        - Mention assumptions and missing evidence.
        - Keep recommendations practical for an SMB.
        - Use the local priority_score and triage_tags, but correct them if the
          evidence suggests a safer interpretation.
        - Output sections: Executive summary, Day-one fixes, Follow-up backlog,
          Evidence to collect, Verification commands.

        Scan JSON:
        {compact}
        """
    ).strip()


def call_ai(endpoint: str, api_key: str | None, model: str, prompt: str, timeout: float) -> str:
    base = endpoint.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write defensive security remediation plans."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def render_markdown(report: dict[str, Any]) -> str:
    findings = report["findings"]
    lines = [
        f"# AI-Assisted Security Scan: {report['target']['host']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Authorization confirmed: {report['authorization_confirmed']}",
        f"- Exposure: {report.get('context', {}).get('exposure', 'unknown')}",
        f"- Business context: {report.get('context', {}).get('business_context', 'unknown')}",
        f"- Data class: {report.get('context', {}).get('data_class', 'unknown')}",
        f"- AI analysis: {'enabled' if report.get('ai_analysis') else 'disabled'}",
        f"- Local triage: {report.get('ai_triage', {}).get('risk_posture', 'not available')}",
        "",
        "## Open Ports",
        "",
        "| Port | Status | Service | Risk | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for observation in report["ports"]:
        if observation["status"] == "open":
            notes = "<br>".join(observation.get("notes", []))
            lines.append(
                f"| {observation['port']} | {observation['status']} | "
                f"{observation.get('service_hint', '')} | {observation.get('risk', '')} | {notes} |"
            )
    if not any(observation["status"] == "open" for observation in report["ports"]):
        lines.append("| - | No open scanned ports | - | - | - |")

    lines.extend(["", "## Findings", ""])
    if findings:
        lines.extend(
            [
                "| Score | Severity | Finding | Tags | Day-one action |",
                "| ---: | --- | --- | --- | --- |",
            ]
        )
        for finding in findings:
            tags = ", ".join(finding.get("triage_tags", []))
            lines.append(
                f"| {finding.get('priority_score', '')} | {finding['severity']} | "
                f"{finding['title']} | {tags} | {finding.get('day_one_action', '')} |"
            )
        lines.append("")
        for finding in findings:
            lines.extend(
                [
                    f"### {finding['severity'].upper()}: {finding['title']}",
                    "",
                    f"- Evidence: {finding['evidence']}",
                    f"- Recommendation: {finding['recommendation']}",
                    f"- Verification: {finding.get('verification', 'Re-run the scanner.')}",
                    "",
                ]
            )
    else:
        lines.append("No findings from the selected checks.")

    if report.get("local_remediation_plan"):
        lines.extend(["", "## Local Remediation Plan", "", report["local_remediation_plan"], ""])

    if report.get("ai_analysis"):
        lines.extend(["", "## AI Remediation Plan", "", report["ai_analysis"], ""])
    elif report.get("ai_error"):
        lines.extend(["", "## AI Analysis Error", "", report["ai_error"], ""])

    return "\n".join(lines).rstrip() + "\n"


def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    host, scheme = normalize_target(args.target)
    ports = parse_ports(args.ports)
    if args.dry_run:
        return {
            "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "target": {"host": host, "input": args.target, "scheme": scheme},
            "context": {
                "business_context": args.business_context,
                "data_class": args.data_class,
                "exposure": args.exposure,
            },
            "authorization_confirmed": bool(args.yes_i_am_authorized),
            "dry_run": True,
            "planned_ports": ports,
            "planned_ai": not args.no_ai,
        }

    observations = [connect_port(host, port, args.timeout) for port in ports]
    open_ports = {observation.port for observation in observations if observation.status == "open"}
    http_results = [
        fetch_http_headers(host, port, tls=False, timeout=args.timeout)
        for port in sorted(open_ports & HTTP_PORTS)
    ]
    https_results = [
        fetch_http_headers(host, port, tls=True, timeout=args.timeout)
        for port in sorted(open_ports & HTTPS_PORTS)
    ]
    tls_results = [inspect_tls(host, port, args.timeout) for port in sorted(open_ports & HTTPS_PORTS)]
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "target": {"host": host, "input": args.target, "scheme": scheme},
        "context": {
            "business_context": args.business_context,
            "data_class": args.data_class,
            "exposure": args.exposure,
        },
        "authorization_confirmed": bool(args.yes_i_am_authorized),
        "dry_run": False,
        "ports": [observation.__dict__ for observation in observations],
        "http": http_results + https_results,
        "tls": tls_results,
    }
    report["findings"] = enrich_findings(
        local_findings(observations, report["http"], tls_results),
        exposure=args.exposure,
    )
    report["ai_triage"] = build_ai_triage(report)
    report["local_remediation_plan"] = build_local_remediation_plan(report)

    if not args.no_ai:
        api_key = os.getenv(args.ai_api_key_env) if args.ai_api_key_env else None
        try:
            report["ai_analysis"] = call_ai(
                endpoint=args.ai_endpoint,
                api_key=api_key,
                model=args.ai_model,
                prompt=build_ai_prompt(report),
                timeout=args.ai_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - local report is still useful.
            report["ai_error"] = str(exc)
    return report


def write_outputs(report: dict[str, Any], outdir: Path, markdown: bool) -> tuple[Path, Path | None]:
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    safe_host = re.sub(r"[^A-Za-z0-9_.-]+", "_", report["target"]["host"])
    json_path = outdir / f"ai_security_scan_{safe_host}_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path = None
    if markdown:
        markdown_path = json_path.with_suffix(".md")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authorized non-destructive server scanner with optional AI remediation.",
    )
    parser.add_argument("--target", required=True, help="Single authorized host, IP, or URL to scan.")
    parser.add_argument("--ports", default=DEFAULT_PORTS, help="Comma-separated ports or ranges.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Network timeout in seconds.")
    parser.add_argument("--outdir", default="security_scan_results", help="Output directory.")
    parser.add_argument("--markdown", action="store_true", help="Also write a Markdown report.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned checks without scanning.")
    parser.add_argument(
        "--business-context",
        default="smb",
        help="Short context for the AI/local triage, for example smb, production, pilot, or lab.",
    )
    parser.add_argument(
        "--data-class",
        default="unknown",
        help="Data class handled by the server, for example public, internal, confidential, personal-data.",
    )
    parser.add_argument(
        "--exposure",
        choices=("internet", "private", "internal"),
        default="internet",
        help="Network exposure used to adjust local AI-style risk scoring.",
    )
    parser.add_argument(
        "--yes-i-am-authorized",
        action="store_true",
        help="Confirm you are authorized to scan the target.",
    )
    parser.add_argument("--no-ai", action="store_true", help="Skip AI API analysis.")
    parser.add_argument(
        "--ai-endpoint",
        default=os.getenv("AI_SECURITY_API_BASE", "http://127.0.0.1:4000/v1"),
        help="OpenAI-compatible API base URL or /chat/completions URL.",
    )
    parser.add_argument(
        "--ai-model",
        default=os.getenv("AI_SECURITY_MODEL", "codex-default"),
        help="Model name for the OpenAI-compatible API.",
    )
    parser.add_argument(
        "--ai-api-key-env",
        default="LITELLM_API_KEY",
        help="Environment variable containing the AI API key.",
    )
    parser.add_argument("--ai-timeout", type=float, default=30.0, help="AI API timeout in seconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.dry_run and not args.yes_i_am_authorized:
        parser.error("Refusing to scan without --yes-i-am-authorized. Use --dry-run to preview.")

    try:
        report = run_scan(args)
    except ValueError as exc:
        parser.error(str(exc))
    if report.get("dry_run"):
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    json_path, markdown_path = write_outputs(report, Path(args.outdir), args.markdown)
    print(f"Wrote JSON report: {json_path}")
    if markdown_path:
        print(f"Wrote Markdown report: {markdown_path}")
    if report.get("ai_error"):
        print(f"AI analysis skipped or failed: {report['ai_error']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
