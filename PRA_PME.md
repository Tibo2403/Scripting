# Plan de Reprise d’Activité (PRA) — PME

## 1) Objectif
Ce document définit les actions à mener pour rétablir rapidement les services critiques de l’entreprise après un incident majeur (panne serveur, ransomware, erreur humaine, crash applicatif, coupure réseau).

## 2) Périmètre
Systèmes couverts :
- Messagerie (Microsoft 365 / Google Workspace)
- Serveur de fichiers
- ERP / CRM
- Site web vitrine ou e-commerce
- Postes utilisateurs
- Réseau (pare-feu, switch, accès internet)

## 3) Rôles et responsabilités
- **Responsable PRA (Direction / DSI)** : déclenchement du plan, pilotage global.
- **Référent IT interne / prestataire MSP** : diagnostic, restauration technique.
- **Référent métier** : validation fonctionnelle (ERP, facturation, ventes).
- **Communication** : information salariés, clients, partenaires.

## 4) Criticité et priorités (RTO / RPO)
- **Niveau 1 (critique)** : ERP, fichiers comptables, messagerie  
  - RTO : 4h  
  - RPO : 1h
- **Niveau 2 (important)** : CRM, intranet  
  - RTO : 8h  
  - RPO : 4h
- **Niveau 3 (support)** : site institutionnel, outils secondaires  
  - RTO : 24h  
  - RPO : 24h

## 5) Conditions de déclenchement
Le PRA est activé si :
- indisponibilité > 30 min d’un service critique,
- suspicion d’attaque (ransomware, compromission),
- perte de données avérée,
- panne matérielle empêchant l’activité.

**Décisionnaire de déclenchement :** [Nom / Fonction / Téléphone]

## 6) Procédure d’urgence (H0 à H4)
1. **Sécuriser**
   - Isoler les machines compromises du réseau.
   - Couper les accès externes non essentiels (VPN, RDP).
2. **Qualifier**
   - Identifier la nature de l’incident (matériel, logiciel, cyber).
   - Évaluer les impacts métiers.
3. **Alerter**
   - Informer cellule de crise (direction + IT + métiers).
   - Ouvrir ticket incident prioritaire.
4. **Restaurer le socle**
   - Vérifier disponibilité sauvegardes (locale + hors ligne + cloud).
   - Restaurer en priorité services Niveau 1.
5. **Valider**
   - Tests techniques (accès, performance, logs).
   - Tests métiers (facture test, envoi mail test, accès dossiers).

## 7) Check-list restauration
- [ ] Accès annuaire (AD / Entra ID) opérationnel
- [ ] Messagerie fonctionnelle
- [ ] Partages fichiers restaurés
- [ ] ERP/CRM accessible et cohérent
- [ ] Sauvegarde relancée post-restauration
- [ ] Antivirus/EDR actif et à jour
- [ ] Journal d’incident complété

## 8) Communication de crise (modèle court)
**Message interne :**  
“Un incident IT est en cours. Le PRA est activé depuis [heure]. Les équipes techniques travaillent au rétablissement prioritaire des services. Prochain point d’information à [heure].”

**Message client (si impact) :**  
“Nous rencontrons un incident technique affectant [service]. Nos équipes sont mobilisées pour un rétablissement rapide. Merci de votre compréhension.”

## 9) Retour à la normale
- Confirmer stabilité 24h.
- Clôturer cellule de crise.
- Réaliser RETEX sous 5 jours :
  - causes racines,
  - délais réels vs objectifs RTO/RPO,
  - actions correctives,
  - mise à jour du PRA.
