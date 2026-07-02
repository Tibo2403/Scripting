# PRA V2 Opérationnel (PME) — Exécution PowerShell + Backup standard

## 1. Objectif
Permettre à une PME de redémarrer ses services critiques rapidement après crash (matériel, logiciel, cyber), avec une procédure semi-automatisée via PowerShell et un backup standard robuste.

## 2. Hypothèses techniques
- Environnement Windows Server / postes Windows.
- Script exécuté avec privilèges administrateur.
- Outil de backup existant (Veeam, Acronis, Nakivo, Windows Server Backup, etc.) pilotable par CLI/API ou tâches planifiées.
- Sauvegardes disponibles localement + hors site (règle 3-2-1).

## 3. Politique de sauvegarde standard (3-2-1)
- **3 copies** : 1 prod + 2 sauvegardes.
- **2 supports différents** : NAS + stockage objet/cloud.
- **1 copie hors ligne / immuable** : disque déconnecté OU bucket immutability/WORM.

### 3.1 Fréquences recommandées
- **Critique (ERP, fichiers compta, AD, DB métier)**  
  - Incrémental : toutes les 1h  
  - Full : quotidien (nuit)
- **Important (CRM, fichiers projets)**  
  - Incrémental : toutes les 4h  
  - Full : quotidien
- **Standard (partages secondaires)**  
  - Incrémental : quotidien  
  - Full : hebdomadaire

### 3.2 Rétention recommandée
- Quotidien : 30 jours
- Hebdomadaire : 8 semaines
- Mensuel : 12 mois
- (Option conformité) annuel : 3 à 10 ans selon obligations légales

## 4. RTO / RPO cibles
- **Niveau 1** : RTO 4h, RPO 1h
- **Niveau 2** : RTO 8h, RPO 4h
- **Niveau 3** : RTO 24h, RPO 24h

## 5. Procédure opérationnelle (Runbook)
### Phase A — Détection & qualification (0–30 min)
1. Ouvrir incident critique.
2. Identifier périmètre touché (serveur, VM, DB, partages, AD).
3. Décider activation PRA (Direction/IT).

### Phase B — Confinement (30–60 min)
1. Isoler les hôtes compromis (VLAN quarantaine / coupure réseau).
2. Désactiver accès externes non essentiels (RDP, VPN non maîtrisé).
3. Geler changements infra non urgents.

### Phase C — Restauration prioritaire (H1–H4)
1. Vérifier chaîne backup (catalogue, dépôt, intégrité).
2. Restaurer services Niveau 1 dans l’ordre :
   - Identité (AD/Entra connectivité locale si besoin)
   - Stockage fichiers critiques
   - Base de données métier
   - Application ERP/CRM
3. Lancer tests techniques + métiers.

### Phase D — Retour maîtrisé (H4–H24)
1. Réactiver flux réseau progressivement.
2. Renforcer surveillance (EDR, logs, SIEM, alertes backup).
3. Générer rapport d’incident + RETEX sous 5 jours.

## 6. Script PowerShell PRA (orchestrateur)
Le script `Invoke-PRA.ps1` :
- charge une config JSON,
- crée un dossier de logs horodaté,
- exécute des checks préalables,
- lance les étapes de restauration (placeholders adaptables à l’outil),
- exécute des tests de validation,
- produit un rapport final.

## 7. Commandes d’exploitation
```powershell
# Test à blanc (sans actions destructives)
.\Invoke-PRA.ps1 -ConfigPath .\backup-config.json -WhatIfMode

# Exécution réelle
.\Invoke-PRA.ps1 -ConfigPath .\backup-config.json
```

## 8. Contrôles minimum à imposer
- Test de restauration **mensuel** (au moins un service critique).
- Test PRA complet **trimestriel**.
- Double validation humaine avant restauration en production.
- Journalisation centralisée des logs PRA.
- Rotation des secrets/comptes de service après incident cyber.

## 9. Critères d’acceptation V2
- Le script retourne `exit 0` en succès et `exit != 0` en échec.
- Un log horodaté est généré à chaque exécution.
- Les services critiques sont restaurés dans l’ordre défini.
- Les tests de validation passent avant déclaration de retour à la normale.
- Les objectifs RTO/RPO sont mesurés et reportés.

## 10. Prochaines améliorations (V3)
- Connecteurs natifs Veeam/Acronis/Nakivo.
- Notification Teams/Slack/Email en fin d’exécution.
- Tableau de bord KPI PRA (temps de reprise réel, taux de succès restauration).
- Mode “ransomware” dédié (forensic + clean-room restore).
