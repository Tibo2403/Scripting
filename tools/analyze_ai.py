import os
import pathlib
import requests

API_KEY = os.environ["INKLING_API_KEY"]
API_URL = os.environ["INKLING_API_URL"]

EXTENSIONS = {".py", ".js", ".ts", ".sh"}
EXCLUDED = {".git", "node_modules", ".venv", "venv"}

files = []

for path in pathlib.Path(".").rglob("*"):
    if not path.is_file():
        continue
    if any(part in EXCLUDED for part in path.parts):
        continue
    if path.suffix in EXTENSIONS:
        files.append(path)

print(f"🔎 {len(files)} fichiers trouvés")

report = []

for path in files:
    print(f"🤖 Analyse : {path}")

    code = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )[:30000]

    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "prompt":
                "Analyse ce code : bugs, sécurité, qualité et "
                "refactoring possible.\n\n"
                f"Fichier: {path}\n\n{code}"
        },
        timeout=120,
    )

    response.raise_for_status()

    report.append(
        f"# {path}\n\n{response.text}\n"
    )

pathlib.Path("AI_REPORT.md").write_text(
    "\n\n".join(report),
    encoding="utf-8"
)

print("\n✅ Rapport créé : AI_REPORT.md")
