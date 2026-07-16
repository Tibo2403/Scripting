# TOOLS — agent-deepseek

Les permissions réelles sont définies dans `openclaw.json`; ce fichier décrit leur usage autorisé.

## Outils autorisés
- `read`, `write`, `edit`: notes de triage et synthèses locales.
- `exec`, `process`: commandes Git/GitHub en lecture et scripts de collecte contrôlés.
- `web_fetch`, `web_search`: documentation officielle et vérification de dépendances publiques.
- `message`: notifications vers le compte Telegram lié à cet agent.

## GitHub natif via `gh`
Token recommandé :
- Metadata: Read-only
- Contents: Read-only
- Issues: Read and write uniquement si l'ajout de labels/commentaires est souhaité
- Pull requests: Read-only
- Actions: Read-only

Commandes permises : `gh issue list/view`, `gh pr list/view/checks/diff`, `gh api` en GET, recherche de doublons et lecture des workflows.

Écritures permises seulement après autorisation humaine explicite : ajout de label, commentaire de triage, assignation. Toujours proposer avant d'appliquer.

Interdits : fermeture automatique, fusion, push de code, suppression, modification de secrets, branches protégées, workflows, collaborateurs ou paramètres du dépôt.
