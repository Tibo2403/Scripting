# Scripts Bash pour Linux

Ce dossier regroupe les scripts destinés aux systèmes GNU/Linux.

- `check_dependencies.sh` – vérifie la présence des outils requis. Options : `--install` pour installer, `--dry-run` pour simuler, `--prefix DIR` pour une installation utilisateur et `--help` pour afficher l'usage (compatible avec `apt-get`, `yum`, `dnf` et `pacman`).
- `setup_api.sh` – installe et configure l'API Mistral.
- `pentest_discovery.sh` – phase de découverte lors d'un pentest.
- `pentest_verification.sh` – vérification des vulnérabilités détectées.
- `pentest_exploitation.sh` – exploitation des vulnérabilités.
- `scan_wifi.sh` – analyse des réseaux Wi-Fi.
  Le script consigne désormais toutes les actions et erreurs dans `wifi_captures/scan_wifi.log`.
- `stealth_post.sh` – exfiltration basique des informations.

Les scripts utilisent `targets.txt` situé à la racine du dépôt pour définir les cibles de test.
