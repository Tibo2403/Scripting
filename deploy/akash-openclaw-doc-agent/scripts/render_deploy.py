"""Render an Akash SDL with immutable OCI image references."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATTERN = re.compile(
    r"^[a-z0-9.-]+(?::[0-9]+)?/"
    r"[a-z0-9._/-]+:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"
    r"@sha256:[0-9a-f]{64}$"
)
PLACEHOLDERS = {
    "__AGENT_IMAGE__": "agent",
    "__OLLAMA_IMAGE__": "ollama",
}


def validate_image_reference(reference: str) -> None:
    """Reject references that are not tag-and-digest pinned OCI images."""
    if not IMAGE_PATTERN.fullmatch(reference):
        raise ValueError(
            "image reference must include a registry, repository, non-latest tag, "
            "and sha256 digest"
        )
    tag = reference.rsplit("@", maxsplit=1)[0].rsplit(":", maxsplit=1)[1]
    if tag.lower() == "latest":
        raise ValueError("the latest tag is forbidden")


def render(template: Path, output: Path, agent_image: str, ollama_image: str) -> None:
    """Render *template* to *output* after validating all substitutions."""
    validate_image_reference(agent_image)
    validate_image_reference(ollama_image)
    content = template.read_text(encoding="utf-8")
    replacements = {
        "__AGENT_IMAGE__": agent_image,
        "__OLLAMA_IMAGE__": ollama_image,
    }
    for placeholder, role in PLACEHOLDERS.items():
        if content.count(placeholder) != 1:
            raise ValueError(f"template must contain exactly one {role} image placeholder")
        content = content.replace(placeholder, replacements[placeholder])
    if "__" in content:
        raise ValueError("unresolved template placeholder detected")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-image", required=True)
    parser.add_argument("--ollama-image", required=True)
    parser.add_argument("--template", type=Path, default=ROOT / "deploy.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "deploy.resolved.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        render(args.template, args.output, args.agent_image, args.ollama_image)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Rendered immutable Akash SDL: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
