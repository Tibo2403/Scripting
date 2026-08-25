#!/usr/bin/env python3
"""Serveur MCP minimal pour administrer config/tasks.yaml de CrewAI."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml
from filelock import FileLock
from mcp.server import MCPServer


def load_dotenv() -> None:
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

PROJECT_DIR_RAW = os.environ.get("CREWAI_PROJECT_DIR", "").strip()
if not PROJECT_DIR_RAW:
    raise RuntimeError("CREWAI_PROJECT_DIR est obligatoire; exécutez setup.sh")
PROJECT_DIR = Path(PROJECT_DIR_RAW).expanduser().resolve()
TASKS_RELATIVE = Path(os.environ.get("CREWAI_TASKS_FILE", "config/tasks.yaml"))
TTL_SECONDS = int(os.environ.get("CREWAI_PROPOSAL_TTL", "900"))

if str(PROJECT_DIR) == "/":
    raise RuntimeError("CREWAI_PROJECT_DIR doit désigner un projet précis")
if TASKS_RELATIVE.is_absolute() or ".." in TASKS_RELATIVE.parts:
    raise RuntimeError("CREWAI_TASKS_FILE doit être un chemin relatif sûr")

TASKS_FILE = (PROJECT_DIR / TASKS_RELATIVE).resolve()
if PROJECT_DIR not in TASKS_FILE.parents:
    raise RuntimeError("Le fichier de tâches doit rester dans le projet CrewAI")

STATE_DIR = Path(
    os.environ.get("CREWAI_ADMIN_STATE_DIR", str(Path(__file__).with_name(".state")))
).expanduser().resolve()
PROPOSALS_DIR = STATE_DIR / "proposals"
BACKUPS_DIR = STATE_DIR / "backups"
LOCK_FILE = STATE_DIR / "tasks.lock"
for directory in (PROPOSALS_DIR, BACKUPS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

mcp = MCPServer("crewai-admin")


def read_tasks() -> dict[str, Any]:
    if not TASKS_FILE.is_file():
        raise RuntimeError(f"Fichier de tâches introuvable: {TASKS_FILE}")
    data = yaml.safe_load(TASKS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("tasks.yaml doit contenir un objet YAML à la racine")
    return data


def validate_task(task_name: str, task: dict[str, Any]) -> None:
    if not task_name or any(char in task_name for char in "/\\\n\r"):
        raise ValueError("Nom de tâche invalide")
    if not isinstance(task, dict):
        raise ValueError("La définition de tâche doit être un objet")
    for field in ("description", "expected_output", "agent"):
        if field in task and not isinstance(task[field], str):
            raise ValueError(f"Le champ {field} doit être une chaîne")


def canonical_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def proposal_path(token: str) -> Path:
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("Jeton de proposition invalide")
    return PROPOSALS_DIR / f"{token}.json"


@mcp.tool()
def list_tasks() -> dict[str, Any]:
    """Lister les tâches CrewAI et leurs agents associés, sans les modifier."""
    tasks = read_tasks()
    return {
        "tasks_file": str(TASKS_RELATIVE),
        "tasks": [
            {"name": name, "agent": value.get("agent") if isinstance(value, dict) else None}
            for name, value in tasks.items()
        ],
    }


@mcp.tool()
def get_task(task_name: str) -> dict[str, Any]:
    """Afficher la définition complète d'une tâche CrewAI."""
    tasks = read_tasks()
    if task_name not in tasks:
        raise ValueError(f"Tâche inconnue: {task_name}")
    return {"name": task_name, "definition": tasks[task_name]}


@mcp.tool()
def propose_task_update(
    task_name: str,
    definition: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Préparer la création ou modification d'une tâche sans écrire tasks.yaml."""
    validate_task(task_name, definition)
    if not reason.strip():
        raise ValueError("Une raison est obligatoire")

    tasks = read_tasks()
    before = tasks.get(task_name)
    token = secrets.token_hex(16)
    proposal = {
        "token": token,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + TTL_SECONDS,
        "base_hash": canonical_hash(tasks),
        "task_name": task_name,
        "before": before,
        "after": definition,
        "reason": reason.strip(),
    }
    proposal_path(token).write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": "awaiting_confirmation",
        "confirmation_token": token,
        "expires_at": proposal["expires_at"],
        "task_name": task_name,
        "before": before,
        "after": definition,
        "reason": proposal["reason"],
    }


@mcp.tool()
def apply_task_update(confirmation_token: str) -> dict[str, Any]:
    """Appliquer exactement une proposition préalablement confirmée par l'utilisateur."""
    path = proposal_path(confirmation_token)
    if not path.is_file():
        raise ValueError("Proposition inconnue ou déjà utilisée")
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if int(time.time()) > proposal["expires_at"]:
        path.unlink(missing_ok=True)
        raise ValueError("La proposition a expiré")

    with FileLock(str(LOCK_FILE), timeout=10):
        tasks = read_tasks()
        if canonical_hash(tasks) != proposal["base_hash"]:
            raise RuntimeError("tasks.yaml a changé; créez une nouvelle proposition")

        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        backup = BACKUPS_DIR / f"tasks-{timestamp}-{confirmation_token[:8]}.yaml"
        shutil.copy2(TASKS_FILE, backup)
        tasks[proposal["task_name"]] = proposal["after"]
        validate_task(proposal["task_name"], proposal["after"])

        serialized = yaml.safe_dump(tasks, allow_unicode=True, sort_keys=False)
        yaml.safe_load(serialized)
        fd, temporary_name = tempfile.mkstemp(prefix="tasks-", suffix=".yaml", dir=TASKS_FILE.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, TASKS_FILE)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

        path.unlink(missing_ok=True)
        return {
            "status": "applied",
            "task_name": proposal["task_name"],
            "backup": backup.name,
            "reason": proposal["reason"],
        }


@mcp.tool()
def rollback_last_change(confirm: bool = False) -> dict[str, Any]:
    """Restaurer la sauvegarde la plus récente; exige confirm=true."""
    backups = sorted(BACKUPS_DIR.glob("tasks-*.yaml"), reverse=True)
    if not backups:
        raise RuntimeError("Aucune sauvegarde disponible")
    latest = backups[0]
    if not confirm:
        return {
            "status": "awaiting_confirmation",
            "backup": latest.name,
            "instruction": "Rappeler rollback_last_change avec confirm=true après accord explicite.",
        }
    with FileLock(str(LOCK_FILE), timeout=10):
        current = read_tasks()
        restored = yaml.safe_load(latest.read_text(encoding="utf-8"))
        if not isinstance(restored, dict):
            raise RuntimeError("Sauvegarde invalide")
        emergency = BACKUPS_DIR / f"pre-rollback-{int(time.time())}.yaml"
        shutil.copy2(TASKS_FILE, emergency)
        shutil.copy2(latest, TASKS_FILE)
        return {
            "status": "rolled_back",
            "restored": latest.name,
            "previous_hash": canonical_hash(current),
            "current_hash": canonical_hash(restored),
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
