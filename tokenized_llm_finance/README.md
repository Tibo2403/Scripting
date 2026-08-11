# Finance tokenisée pour agents LLM

Cette infrastructure mesure un appel LiteLLM, convertit sa consommation estimée en énergie puis en
euros tokenisés, régule le budget par PID et temporise le règlement avec Chainlink VRF v2.5.

## Invariants de sécurité

1. LiteLLM doit fournir des compteurs entiers et cohérents `prompt_tokens` et `completion_tokens`.
2. Une clé de métrologie distincte signe un reçu EIP-712. La preuve lie chaîne, coffre, agent,
   bénéficiaire, requête fournisseur, modèle, tarif versionné, hash de réponse, compteurs, énergie,
   montant, époque, nonce et expiration.
3. Le proposant met exactement ce reçu en file. Sa clé ne peut ni attester la mesure, ni annuler, ni
   exécuter en production.
4. VRF fixe `readyAt = callbackTime + minimumDelay + bruit`. L'exécution n'est permise que jusqu'à
   `executeBefore = readyAt + executionWindow`.
5. Une révocation de cible invalide également les opérations déjà mises en file. Une clé sémantique
   n'est utilisable qu'une fois, y compris après annulation, afin d'empêcher le grinding VRF.
6. Le coffre vérifie la signature, la fraîcheur, l'époque et le plafond PID avant le transfert ERC-20.

## Conversion entière

Toutes les valeurs économiques utilisent des entiers WAD (`10^18`) :

```text
J_WAD = prompt_tokens × J_prompt_token_WAD
      + completion_tokens × J_completion_token_WAD
kWh_WAD = floor(J_WAD / 3 600 000)
EUR_WAD = floor(kWh_WAD × tarif_EUR_kWh_WAD / 10^18)
```

`1 kWh = 3 600 000 joules`. Les divisions ont la même troncature en Python et Solidity. Le résultat
est exact pour les coefficients fournis, mais ces coefficients restent une estimation physique à
calibrer par matériel, modèle, PUE et méthode de mesure. Ils doivent être versionnés avec `tariff-id`.

Le PID applique la formule classique `Kp·e + Ki·∫e·dt + Kd·de/dt`. Il ajoute anti-windup, bornes de
gain et d'observation, intervalle minimum, rejet des données trop anciennes et limite de variation du
budget par mise à jour. Ces paramètres doivent être simulés puis revus par gouvernance.

## Installation et validation

Prérequis : Python 3.11+, Foundry, un RPC EVM et une souscription VRF v2.5 financée.

```powershell
cd tokenized_llm_finance
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
forge install OpenZeppelin/openzeppelin-contracts foundry-rs/forge-std --no-commit
$env:PYTHONPATH = (Resolve-Path python)
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m ruff check python tests
forge test
```

Mesure seule :

```powershell
python -m llm_energy_settlement.cli --model openai/gpt-4o-mini --prompt "résume ceci" `
  --prompt-joules-per-token 2.1 --completion-joules-per-token 3.7 --euro-per-kwh 0.22
```

## Déploiement en deux phases

Copier `.env.example`, renseigner des adresses non nulles et distinctes, puis déployer :

```powershell
forge script script/Deploy.s.sol:Deploy --rpc-url $env:RPC_URL --broadcast
```

Le déployeur conserve temporairement ses droits pour éviter un verrouillage irréversible. Vérifier les
adresses, le consumer VRF, les rôles, l'allowlist et la capacité de chaque multisig. Ensuite seulement :

```powershell
forge script script/FinalizeHandoff.s.sol:FinalizeHandoff --rpc-url $env:RPC_URL --broadcast
```

Le second script refuse l'abandon si la gouvernance ne possède pas tous les rôles critiques attendus.

## Workflow

`SETTLEMENT_TTL_SECONDS` ne doit pas depasser `MAXIMUM_USAGE_AGE_SECONDS`. Le client refuse aussi
une file d'attente dont la fenetre restante ne couvre pas le delai VRF maximal.

Le workflow utilise `SUPERVISOR_PRIVATE_KEY` pour proposer, `METERING_ATTESTOR_PRIVATE_KEY` pour
signer les mesures et, si demandé, `VELOCITY_ORACLE_PRIVATE_KEY` pour le PID. Les annulations et
exécutions exigent leurs clés distinctes dans le client. Les confirmations sont suivies jusqu'au seuil,
puis le reçu et son bloc canonique sont revérifiés. Un verrou de nonce inter-processus protège les
processus partageant accidentellement un même signataire.

```powershell
python -m llm_energy_settlement.workflow --model openai/gpt-4o-mini --prompt "analyse" `
  --agent 0x... --beneficiary 0x... --tariff-id datacenter-fr-v3 `
  --prompt-joules-per-token 2.1 --completion-joules-per-token 3.7 --euro-per-kwh 0.22
```

## Limites réglementaires et opérationnelles

- L'ERC-20 est un rail technique permissionné, pas une certification MiCA ni une MNBC. Réserves,
  remboursement, KYC/AML, gouvernance, reporting et droits des détenteurs restent à mettre en œuvre.
- Les adresses sont pseudonymes, pas anonymes. L'allowlist doit être reliée aux contrôles réglementaires.
- Des clés distinctes doivent être conservées dans HSM/coffres et idéalement portées par des services
  ou multisigs indépendants. Ne jamais committer une clé réelle.
- Le prix API LLM, le change, le gaz et les frais de rachat ne sont pas inclus dans la formule énergie.
- Une transaction annulée ne réutilise pas sa clé sémantique : une nouvelle attestation et un nouveau
  nonce sont nécessaires pour une nouvelle tentative.
- Faire auditer les contrats et tester les scénarios VRF, réorganisation, expiration et pause avant
  toute mise en production ou valeur réelle.
