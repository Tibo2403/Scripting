# Scripting Toolkit

[![Validation des scripts](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml/badge.svg)](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml)

Ce dépôt rassemble des outils PowerShell, Bash et Python pour administrer des postes et des services, auditer un espace de travail et déployer des services d’IA.

## Premier essai

Depuis la racine du dépôt, choisissez une commande selon votre environnement.

**Sous Windows**, affichez les informations du poste avec PowerShell.

```powershell
.\scripts\powershell\Get-SystemInfo.ps1
```

**Sous Linux**, prévisualisez l’installation locale d’Ollama et d’Open WebUI.

```bash
bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model
```

La [matrice de compatibilité](docs/compatibility-matrix.md) précise les systèmes pris en charge, les dépendances, les privilèges et la disponibilité du mode simulation.

## Trouver un outil

| Je veux… | Point d’entrée |
|---|---|
| Administrer Windows ou Microsoft 365 | [Catalogue PowerShell](scripts/powershell/README.md) |
| Auditer un espace de travail Codex | [Guide du Workspace Doctor](docs/codex-workspace-doctor.md) |
| Administrer un hôte Linux | [Catalogue Linux](scripts/linux/README.md) |
| Installer une pile d’IA locale | [Guide Ollama et Open WebUI](docs/self-hosted-llm.md) |
| Explorer les scripts depuis un client MCP | [Outils Python](scripts/python/README.md) |
| Choisir un modèle selon le coût ou la disponibilité | [Modes de routage](docs/codex-routing-modes.md) · [Intégration Scaleway](litellm_scaleway_dispatching/README.md) |
| Déployer OpenClaw sur Akash | [Agent documentaire](deploy/akash-openclaw-doc-agent/README.md) · [Revue à deux agents](openclaw-akash-dual-agents/README.md) · [Passerelle Inkling](openclaw-inkling-akash/README.md) |
| Configurer Grok dans GitHub Actions, lancer Inkling dans Codespaces ou reproduire les contrôles CI | [Procédures et commandes](docs/workflows.md) |
| Préparer des entrées de démonstration | [Exemples](examples/README.md) |

## Prototypes expérimentaux

| Projet | Périmètre |
|---|---|
| [Reprise d’activité](pra/PRA_PME.md) | Plan pour PME et [procédure opérationnelle](pra/PRA_V2_Operationnel.md). Les connecteurs de l’orchestrateur restent à éprouver en exercice. |
| [Finance tokenisée](tokenized_llm_finance/README.md) | Prototype Python et Solidity indépendant des scripts d’administration. Les contrats sont non audités. Respecter les [limites du projet](tokenized_llm_finance/BOUNDARIES.md) et utiliser uniquement des valeurs de test. |

Le [catalogue de maturité](project-maturity.toml) consigne les validations et les limites de chaque projet. Les [critères de maturité](docs/project-maturity.md) expliquent le classement. Pour OpenClaw, la [validation des profils](scripts/openclaw/VALIDATION.md) couvre la construction des images et leur schéma de configuration. Le déploiement réel et les intégrations externes demandent une vérification opérateur.

## Exploitation et contribution

- Avant une installation chez un client, consulter la [grille de préinstallation](docs/client-preinstallation-audit.md).
- Pour présenter le dépôt, consulter le [portfolio](docs/portfolio/README.md) et le [plan de démonstration](docs/portfolio/demo-media.md).
- Pour proposer une modification, suivre le [guide de contribution](CONTRIBUTING.md) et les [commandes de validation](docs/workflows.md#validation). Les évolutions sont consignées dans le [journal des versions](CHANGELOG.md).
- Réserver les scripts de sécurité aux systèmes couverts par une autorisation écrite. Garder les identifiants, les cibles réelles et les résultats sensibles hors de Git. Pour signaler une vulnérabilité, consulter la [politique de sécurité](SECURITY.md).

[Licence MIT](LICENSE)
