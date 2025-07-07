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
├── setup_api.sh          # Installe Python, Ollama et un exemple d'API Flask
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
