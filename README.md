# PowerShell Scripts Repository

Ce dépôt contient une collection de scripts PowerShell utiles pour l'administration système et l'automatisation de tâches courantes.

## 📂 Structure du dépôt

```
scripts/
├── DiskUsageReport.ps1   # Rapport d'utilisation des disques locaux
├── Get-SystemInfo.ps1    # Informations système de base
├── ManageServices.ps1    # Démarrer/Arrêter/Redémarrer un service Windows
└── UserManagement.ps1    # Gestion des comptes utilisateurs locaux
```

## ⚙️ Utilisation rapide

Les scripts peuvent être lancés via PowerShell :

```powershell
# Exemple : afficher les informations système
.\scripts\Get-SystemInfo.ps1

# Exemple : vérifier l'état d'un service
.\scripts\ManageServices.ps1 -Action status -ServiceName spooler
```

Chacun des scripts possède des paramètres décrits en début de fichier.
