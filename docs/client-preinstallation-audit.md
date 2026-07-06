# Feuille d'audit pre-installation client

Support standard a completer avant toute installation d'une solution IA privee, LiteLLM, Ollama, Open WebUI ou gateway LLM chez un client en Belgique.

> Objectif : verifier la faisabilite technique, les risques securite, les contraintes RGPD / AI Act et les prerequis d'exploitation avant de deployer une solution IA chez un client.
>
> Ce document est un support operationnel. Il ne remplace pas un avis juridique, un DPIA officiel, ni une validation DPO lorsque le contexte l'exige.

---

## 1. Informations client

| Champ | Reponse |
| --- | --- |
| Nom de l'organisation |  |
| Secteur d'activite |  |
| Adresse / site concerne |  |
| Personne de contact |  |
| Responsable IT |  |
| DPO / responsable RGPD |  |
| Date de l'audit |  |
| Auditeur |  |
| Version du document |  |

---

## 2. Objectif du projet

### Objectif principal

- [ ] IA interne privee
- [ ] Gateway IA multi-fournisseurs
- [ ] Reduction des couts d'inference
- [ ] Centralisation des acces IA
- [ ] Self-hosting de modeles locaux
- [ ] Securisation des usages ChatGPT / API
- [ ] Automatisation metier
- [ ] Assistance developpeur / code review
- [ ] Autre :

### Cas d'usage envisages

| Cas d'usage | Service concerne | Donnees utilisees | Validation humaine requise ? |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

### Type de donnees manipulees

- [ ] Donnees publiques
- [ ] Donnees internes
- [ ] Donnees personnelles
- [ ] Donnees sensibles
- [ ] Donnees medicales
- [ ] Donnees RH
- [ ] Donnees financieres
- [ ] Code source
- [ ] Documents clients
- [ ] Secrets techniques / credentials

Commentaires :

```text

```

---

## 3. Conformite Belgique / UE

### RGPD

- [ ] Base legale identifiee
- [ ] Finalite du traitement documentee
- [ ] Registre de traitement a mettre a jour
- [ ] DPA / contrat sous-traitant necessaire
- [ ] Donnees minimisees
- [ ] Duree de conservation definie
- [ ] Logs contenant des donnees personnelles verifies
- [ ] Droit d'acces / rectification / suppression pris en compte
- [ ] DPIA necessaire
- [ ] DPO consulte

Commentaires RGPD :

```text

```

### AI Act / gouvernance IA

- [ ] Usage faible risque
- [ ] Usage potentiellement a haut risque
- [ ] Usage RH / recrutement / evaluation de personnes
- [ ] Usage medical ou sante
- [ ] Usage financier / scoring / decision automatisee
- [ ] Usage uniquement assistant interne
- [ ] Validation humaine prevue
- [ ] Tracabilite des reponses prevue
- [ ] Politique d'usage IA a prevoir

Commentaires AI Act :

```text

```

### NIS2 / cybersecurite

- [ ] Organisation potentiellement concernee par NIS2
- [ ] Mesures de securite documentees
- [ ] Gestion des incidents prevue
- [ ] Controle des acces prevu
- [ ] Sauvegardes et continuite prevues
- [ ] Journalisation securisee prevue

Commentaires NIS2 / securite :

```text

```

---

## 4. Infrastructure existante

### Environnement

- [ ] On-premise
- [ ] Cloud
- [ ] Hybride
- [ ] VPS
- [ ] Datacenter
- [ ] Poste local / mini serveur
- [ ] Environnement de test disponible
- [ ] Environnement de production separe

### Systemes

- [ ] Windows Server
- [ ] Linux
- [ ] Docker disponible
- [ ] Docker Compose disponible
- [ ] Kubernetes disponible
- [ ] VMware / Hyper-V
- [ ] NAS / stockage reseau
- [ ] Git disponible
- [ ] CI/CD disponible

### Reseau

- [ ] VLAN disponible
- [ ] Reverse proxy
- [ ] VPN
- [ ] Firewall
- [ ] DNS interne
- [ ] Certificats TLS
- [ ] Acces distant securise
- [ ] Proxy sortant / filtrage web
- [ ] Monitoring reseau

### Capacite technique

| Ressource | Valeur actuelle | Besoin estime | Commentaire |
| --- | --- | --- | --- |
| CPU |  |  |  |
| RAM |  |  |  |
| GPU |  |  |  |
| Stockage |  |  |  |
| Bande passante |  |  |  |
| OS cible |  |  |  |
| Backup |  |  |  |

Contraintes techniques :

```text

```

---

## 5. Architecture IA proposee

### Composants envisages

- [ ] LiteLLM Proxy
- [ ] Ollama
- [ ] Open WebUI
- [ ] Modeles locaux
- [ ] OpenAI / Azure OpenAI
- [ ] Anthropic
- [ ] Google Gemini
- [ ] Mistral
- [ ] Qwen
- [ ] Redis / cache
- [ ] Base de logs
- [ ] Monitoring
- [ ] Dashboard couts / tokens
- [ ] Authentification par cles API
- [ ] Reverse proxy HTTPS
- [ ] Backup configuration

### Mode de fonctionnement

- [ ] 100 % local
- [ ] Cloud uniquement
- [ ] Hybride local + cloud
- [ ] Routage selon cout
- [ ] Routage selon latence
- [ ] Routage selon disponibilite
- [ ] Fallback automatique
- [ ] Limites par utilisateur / equipe
- [ ] Separation test / production

Schema cible ou notes d'architecture :

```text

```

---

## 6. Securite

### Acces

- [ ] Utilisateurs identifies
- [ ] Groupes / roles definis
- [ ] Cles API separees
- [ ] Rotation des secrets prevue
- [ ] MFA disponible
- [ ] Acces admin limite
- [ ] Acces service separe
- [ ] Procedure de revocation prevue

### Protection des donnees

- [ ] Chiffrement TLS
- [ ] Chiffrement disque
- [ ] Isolation Docker
- [ ] Pas de secrets dans GitHub
- [ ] Pas de logs excessifs
- [ ] Masquage des donnees sensibles
- [ ] Politique de retention des logs
- [ ] Sauvegardes chiffrees
- [ ] Segmentation reseau

### Risques principaux identifies

- [ ] Fuite de donnees vers fournisseur externe
- [ ] Prompt injection
- [ ] Exfiltration via documents
- [ ] Mauvaise gestion des cles API
- [ ] Couts non controles
- [ ] Hallucinations IA
- [ ] Decision automatisee non validee
- [ ] Dependance a un fournisseur
- [ ] Exposition reseau non maitrisee
- [ ] Donnees client presentes dans les logs

Mesures de reduction des risques :

```text

```

---

## 7. Besoins metier

### Utilisateurs prevus

- [ ] Direction
- [ ] IT
- [ ] RH
- [ ] Finance
- [ ] Juridique
- [ ] Commercial
- [ ] Support client
- [ ] Developpeurs
- [ ] Autre :

### Fonctions attendues

- [ ] Chat interne
- [ ] Analyse de documents
- [ ] Resume automatique
- [ ] Generation d'e-mails
- [ ] Assistance code
- [ ] Extraction d'informations
- [ ] Automatisation scripts
- [ ] Reporting
- [ ] RAG / base documentaire
- [ ] API pour applications internes

Priorites metier :

```text

```

---

## 8. Donnees et documents

### Sources possibles

- [ ] Fichiers PDF
- [ ] Word / Excel
- [ ] SharePoint
- [ ] Google Drive
- [ ] Base SQL
- [ ] ERP / Odoo
- [ ] CRM
- [ ] E-mails
- [ ] Tickets support
- [ ] Code GitHub / GitLab
- [ ] NAS / fichiers reseau

### Questions a valider

| Question | Reponse |
| --- | --- |
| Les donnees peuvent-elles quitter l'infrastructure client ? |  |
| Certaines donnees doivent-elles rester en Belgique / UE ? |  |
| Les documents contiennent-ils des donnees personnelles ? |  |
| Une anonymisation est-elle necessaire ? |  |
| Qui peut consulter les reponses generees ? |  |
| Les prompts doivent-ils etre conserves ? |  |
| Les reponses doivent-elles etre auditees ? |  |

Notes :

```text

```

---

## 9. Monitoring et exploitation

### Elements a prevoir

- [ ] Logs techniques
- [ ] Logs d'usage
- [ ] Suivi des tokens
- [ ] Suivi des couts
- [ ] Alertes erreurs
- [ ] Alertes quotas
- [ ] Sauvegarde configuration
- [ ] Procedure de restauration
- [ ] Documentation d'exploitation
- [ ] Formation administrateur
- [ ] Procedure de mise a jour
- [ ] Plan de rollback

### Indicateurs utiles

| Indicateur | Requis ? | Remarque |
| --- | --- | --- |
| Nombre de requetes |  |  |
| Tokens consommes |  |  |
| Cout par fournisseur |  |  |
| Latence moyenne |  |  |
| Taux d'erreur |  |  |
| Modeles les plus utilises |  |  |
| Utilisateurs actifs |  |  |
| Requetes bloquees |  |  |

---

## 10. Decision d'installation

### Evaluation globale

| Critere | Niveau |
| --- | --- |
| Maturite client | Faible / Moyen / Bon / Tres bon |
| Risque technique | Faible / Moyen / Eleve / Critique |
| Risque RGPD | Faible / Moyen / Eleve / Critique |
| Risque securite | Faible / Moyen / Eleve / Critique |
| Faisabilite installation | Faible / Moyenne / Bonne / Immediate |

### Decision

- [ ] Installation possible immediatement
- [ ] Installation possible avec adaptations
- [ ] POC recommande avant production
- [ ] Audit securite complementaire necessaire
- [ ] Validation DPO / juridique necessaire
- [ ] Installation deconseillee a ce stade

### Points bloquants

```text

```

### Actions avant installation

```text

```

---

## 11. Livrables recommandes

- [ ] Schema d'architecture
- [ ] Inventaire des modeles utilises
- [ ] Fichier de configuration LiteLLM
- [ ] Procedure d'installation
- [ ] Procedure de backup
- [ ] Politique de logs
- [ ] Documentation utilisateur
- [ ] Documentation administrateur
- [ ] Rapport d'audit pre-installation
- [ ] Plan de tests
- [ ] Plan de rollback

---

## 12. Conclusion

### Synthese

```text

```

### Recommandation finale

```text

```

| Validation | Nom | Date | Signature |
| --- | --- | --- | --- |
| Auditeur |  |  |  |
| Client |  |  |  |
