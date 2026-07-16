# TOOLS — agent-qwen

Les permissions réelles sont définies dans `openclaw.json`; ce fichier décrit leur usage autorisé.

## Outils autorisés
- `read`, `write`, `edit`: inspection et modification du workspace et des clones autorisés.
- `exec`, `process`: Git, GitHub CLI, tests, linters, builds et scripts du dépôt.
- `web_fetch`, `web_search`: documentation officielle et dépendances, jamais pour transmettre du code privé.

## GitHub natif via `gh`
Le conteneur doit recevoir `GITHUB_TOKEN` avec permissions minimales :
- Contents: Read and write
- Pull requests: Read and write
- Metadata: Read-only
- Issues: Read-only
- Actions: Read-only

Commandes permises : `gh repo view`, `gh issue list/view`, `gh pr list/view/create`, `gh api`, `git fetch/status/diff/switch/add/commit/push`.

Interdits sans validation humaine : `gh pr merge`, suppression de branche distante, release, modification de secrets, règles de branche, Actions, environnements ou collaborateurs.

## Isolation
- Cloner uniquement les dépôts listés dans `REPOSITORIES` sous `/data/repos`.
- Une branche par tâche; aucune écriture sur `main`, `master` ou branche protégée.
- Ne jamais inclure `.env`, tokens, fichiers d'état OpenClaw, logs bruts ou données clients dans un commit.
