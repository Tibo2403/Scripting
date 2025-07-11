# PowerShell Scripts Repository

Ce dépôt contient une collection de scripts PowerShell utiles pour l'administration système et l'automatisation de tâches courantes.

## 📂 Structure du dépôt

```
scripts/
├── DiskUsageReport.ps1   # Rapport d'utilisation des disques locaux
├── Get-SystemInfo.ps1    # Informations système de base
├── ManageServices.ps1    # Démarrer/Arrêter/Redémarrer un service Windows
├── VMManagement.ps1      # Gérer les machines virtuelles Hyper-V
├── LinkCrawler.ps1       # Vérifier les liens d'un site web
├── TeamsManagement.ps1   # Gérer Microsoft Teams
├── ExchangeOnlineManagement.ps1   # Gérer Exchange Online
├── setup_api.sh          # Installe Python, Ollama et un exemple d'API Flask
├── pentest_discovery.sh   # Phase de découverte (Nmap complet + scripts vuln, options)
├── pentest_verification.sh   # Phase de vérification des vulnérabilités
├── pentest_exploitation.sh   # Phase d'exploitation (facultative)
└── UserManagement.ps1    # Gestion des comptes utilisateurs locaux
```

## ⚙️ Utilisation rapide

Les scripts peuvent être lancés via PowerShell :

```powershell
# Exemple : afficher les informations système
.\scripts\Get-SystemInfo.ps1

# Exemple : vérifier l'état d'un service
.\scripts\ManageServices.ps1 -Action status -ServiceName spooler

# Exemple : lister les machines virtuelles Hyper-V
.\scripts\VMManagement.ps1 -Action list

# Exemple : démarrer une machine virtuelle
.\scripts\VMManagement.ps1 -Action start -VMName "TestVM"
# Exemple : lister les equipes Teams
.\scripts\TeamsManagement.ps1 -Action list
# Exemple : lister les boîtes aux lettres Exchange Online
.\scripts\ExchangeOnlineManagement.ps1 -Action list
```
> **Note :** `ManageServices.ps1` et `UserManagement.ps1` doivent être exécutés dans une session PowerShell élevée.
> **Exemple :** cherchez "PowerShell" dans le menu Démarrer, faites un clic droit puis sélectionnez "Exécuter en tant qu'administrateur".

Chacun des scripts possède des paramètres décrits en début de fichier.

```bash
# Installation de l'API Mistral
bash scripts/setup_api.sh
# Puis lancer l'API
python3 ~/mistral_api.py
```

### Scripts Kali Linux

Le script de découverte crée par défaut un dossier `pentest_results_DATE` et
un lien symbolique `pentest_results_latest` vers celui‑ci.

```bash
# Phase de découverte (scan complet et scripts de vulnérabilités)
bash scripts/pentest_discovery.sh -t targets.txt -o mon_dossier
# Phase de vérification des vulnérabilités
bash scripts/pentest_verification.sh -d mon_dossier
# Phase d'exploitation (si autorisée)
bash scripts/pentest_exploitation.sh -d mon_dossier
```
