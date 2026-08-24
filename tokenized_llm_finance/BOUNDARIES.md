# Frontiere imperative du projet

`tokenized_llm_finance/` est un prototype autonome. Sa frontiere est une propriete de securite :
aucun autre projet du depot ne doit devenir implicitement une dependance, une reserve, un oracle ou
un canal d'execution de ce prototype.

## Dans le perimetre

- mesurer des appels LLM et produire des recus EIP-712 auditables ;
- convertir des estimations d'energie et de cout fournisseur en unite de compte EUR WAD ;
- appliquer des budgets PID bornes et des reglements permissionnes ;
- temporiser, annuler, plafonner et interrompre les reglements techniques.

## Hors perimetre et interdit

- detenir ou gerer un portefeuille de Treasuries, en particulier de duration longue ;
- utiliser levier, repo, basis trade, rehypothecation ou transformation de maturite ;
- acheter ou vendre automatiquement des obligations depuis un signal brut de taux ou de marche ;
- promettre de stabiliser les taux longs americains, une devise ou la valeur du token ;
- presenter le token comme depot, stablecoin, fonds, titre financier ou garantie de remboursement ;
- importer du code d'execution de `scripts/`, `deploy/`, `pra/`, `litellm_scaleway_dispatching/` ou
  des projets OpenClaw voisins.

Une activite de reserve, de couverture obligataire ou d'intervention de marche exige un projet
distinct, sa propre gouvernance, un modele de risques, une analyse reglementaire et un audit. Elle ne
doit pas etre ajoutee a ce repertoire comme simple option de configuration.

## Gardes-fous executables

| Risque | Controle obligatoire |
|---|---|
| Cle operationnelle compromise | roles proposant, attestant, annulant et executant distincts |
| Incident ou oracle douteux | `PAUSER_ROLE` independant et arret immediat du vault |
| Gros reglement isole | `maximumSettlementWad`, immuable au deploiement |
| Fuite agregee | `maximumEpochOutflowWad`, immuable, commune a tous les agents et indexee sur l'epoque de reglement |
| Depassement individuel | budget PID par agent et par epoque |
| Insolvabilite technique | solde du vault controle avant mutation d'etat et transfert |
| Donnee de marche perimee | rejet ferme des donnees anciennes ou futures |
| Rejeu ou double paiement | nonce, digest EIP-712 et identifiant de requete consomme une seule fois |

Les plafonds immuables ne peuvent etre augmentes par une cle d'administration. Une augmentation
necessite un nouveau deploiement, une revue explicite et une migration controlee.

## Interfaces autorisees

Les seules entrees externes attendues sont les reponses LiteLLM, les sources de prix documentees, le
RPC EVM et Chainlink VRF. Les sorties sont des recus, journaux et appels aux contrats de ce projet.
Le test `tests/test_project_boundary.py` interdit les imports Python directs vers les autres projets
du depot. Les integrations nouvelles doivent passer par une interface documentee et des donnees
validees, jamais par un import transversal implicite.

## Condition avant valeur reelle

Audit des contrats, tests Foundry en CI, gestion HSM/multisig, procedures de pause et de reprise,
oracles de production, politique de reserves/remboursement, KYC/AML et analyse juridique restent
necessaires. Tant que ces conditions ne sont pas remplies, le projet demeure experimental.
