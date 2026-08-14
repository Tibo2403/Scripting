"""Validate the repository project-maturity catalog."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {"experimental", "usable"}
IGNORED_ROOTS = {".git", ".github", ".pytest_cache", ".ruff_cache", "docs", "examples"}
REQUIRED_TEXT_FIELDS = ("path", "name", "status", "summary", "documentation")


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    """Load a TOML maturity catalog."""
    with catalog_path.open("rb") as catalog_file:
        return tomllib.load(catalog_file)


def discover_project_roots(repository_root: Path) -> set[str]:
    """Return top-level directories that must be classified."""
    return {
        path.name
        for path in repository_root.iterdir()
        if path.is_dir() and path.name not in IGNORED_ROOTS and not path.name.startswith(".")
    }


def validate_catalog(catalog: dict[str, Any], repository_root: Path) -> list[str]:
    """Return every catalog validation error without changing the repository."""
    errors: list[str] = []
    if catalog.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    projects = catalog.get("projects")
    if not isinstance(projects, list):
        return [*errors, "projects must be an array of tables"]

    classified_roots: set[str] = set()
    for index, project in enumerate(projects, start=1):
        label = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{label} must be a table")
            continue

        for field in REQUIRED_TEXT_FIELDS:
            if not isinstance(project.get(field), str) or not project[field].strip():
                errors.append(f"{label}.{field} must be a non-empty string")

        project_path_value = project.get("path")
        if isinstance(project_path_value, str) and project_path_value:
            project_path = Path(project_path_value)
            if project_path.is_absolute() or ".." in project_path.parts:
                errors.append(f"{label}.path must stay inside the repository")
            elif not (repository_root / project_path).is_dir():
                errors.append(f"{label}.path does not exist: {project_path_value}")
            elif len(project_path.parts) != 1:
                errors.append(f"{label}.path must identify a top-level project directory")
            elif project_path_value in classified_roots:
                errors.append(f"duplicate project path: {project_path_value}")
            else:
                classified_roots.add(project_path_value)

        documentation = project.get("documentation")
        if isinstance(documentation, str) and documentation:
            documentation_path = Path(documentation)
            if documentation_path.is_absolute() or ".." in documentation_path.parts:
                errors.append(f"{label}.documentation must stay inside the repository")
            elif not (repository_root / documentation_path).is_file():
                errors.append(f"{label}.documentation does not exist: {documentation}")

        status = project.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{label}.status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}")

        validation = project.get("validation")
        if not isinstance(validation, list) or not validation or not all(
            isinstance(command, str) and command.strip() for command in validation
        ):
            errors.append(f"{label}.validation must contain at least one command")

        limitations = project.get("limitations")
        if status == "experimental" and (
            not isinstance(limitations, list)
            or not limitations
            or not all(isinstance(item, str) and item.strip() for item in limitations)
        ):
            errors.append(f"{label}.limitations must explain why the project is experimental")

    discovered_roots = discover_project_roots(repository_root)
    missing = discovered_roots - classified_roots
    unexpected = classified_roots - discovered_roots
    if missing:
        errors.append(f"unclassified project roots: {', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"catalog paths are not project roots: {', '.join(sorted(unexpected))}")
    return errors


def main() -> int:
    """Validate the catalog and return a process-friendly exit code."""
    repository_root = Path(__file__).resolve().parents[2]
    catalog_path = repository_root / "project-maturity.toml"
    try:
        catalog = load_catalog(catalog_path)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"Unable to read {catalog_path}: {exc}", file=sys.stderr)
        return 1

    errors = validate_catalog(catalog, repository_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Project maturity catalog valid: {len(catalog['projects'])} projects classified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
