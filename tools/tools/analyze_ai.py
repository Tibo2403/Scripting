import os
import sys
from pathlib import Path

from anthropic import Anthropic


API_KEY = os.getenv("INKLING_API")

if not API_KEY:
    raise SystemExit(
        "❌ Secret 'INKLING_API' introuvable.\n"
        "Ajoute-le aux Codespaces Secrets puis reconstruis/redémarre le Codespace."
    )

client = Anthropic(
    base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/anthropic/api",
    api_key=API_KEY,
    timeout=30.0,
)

MODEL = "thinkingmachines/Inkling"

EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".sh", ".json", ".yml", ".yaml",
}

EXCLUDED = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPOSITORY_ROOT / "AI_REPORT.md"


def is_text_file(path: Path) -> bool:
    try:
        return b"\x00" not in path.read_bytes()[:8192]
    except OSError:
        return False


MAX_FILES = 8
MAX_TOKENS = 300

files = sorted(
    (
        path for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file()
        and path.name != "AI_REPORT.md"
        and not any(part in EXCLUDED for part in path.parts)
        and is_text_file(path)
    ),
    key=lambda path: str(path),
)[:MAX_FILES]

print(f"🔎 {len(files)} fichiers texte trouvés (maximum {MAX_FILES})")

failed_files = []
report = [f"# Rapport d'analyse Inkling\nModèle : `{MODEL}`\n"]

for index, path in enumerate(files, 1):
    print(f"🤖 [{index}/{len(files)}] {path.relative_to(REPOSITORY_ROOT)}")

    try:
        code = path.read_text(encoding="utf-8", errors="ignore")

        prompt = f"""
Analyse entièrement ce fichier du dépôt.

FICHIER: {path.relative_to(REPOSITORY_ROOT)}

Identifie les bugs, problèmes de sécurité, erreurs de logique,
problèmes de performance et améliorations possibles.

Réponds avec les catégories CRITIQUE, IMPORTANT et AMELIORATION.

CODE:
{code}
"""

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        answer = "\n".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()

        if not answer:
            raise RuntimeError("Réponse Inkling vide")

        report.append(
            f"\n---\n\n## `{path.relative_to(REPOSITORY_ROOT)}`\n\n{answer}\n"
        )

    except Exception as exc:
        failed_files.append(path)
        print(f"⚠️ Erreur : {path}: {exc}", file=sys.stderr)

REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

if failed_files:
    raise SystemExit(1)

print()
print("===================================")
print("✅ ANALYSE TERMINÉE")
print("📄 Rapport : AI_REPORT.md")
print("===================================")
