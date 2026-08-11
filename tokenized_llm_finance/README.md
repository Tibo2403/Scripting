# Finance tokenisée pour agents LLM

Cette infrastructure mesure un appel LLM, transforme sa consommation en énergie puis en euros
tokenisés, limite la dépense par un PID on-chain et retarde tout règlement lourd à l'aide d'un
timelock réversible dont le bruit temporel provient de Chainlink VRF v2.5.

## Flux et invariants

1. `meter_completion` appelle `litellm.completion` et refuse tout résultat sans compteurs entiers
   `prompt_tokens` et `completion_tokens` cohérents.
2. Le superviseur produit un `usageDigest` unique et encode `AgentSettlementVault.settle`.
3. `ReversibleRandomTimelock.queue` demande un mot VRF. Le callback fixe
   `readyAt = callbackTime + minimumDelay + randomWord % (noiseWindow + 1)`.
4. Jusqu'à `execute`, le rôle `CANCELLER_ROLE` peut annuler l'opération, y compris avant le callback
   VRF. Une opération annulée ne peut jamais être exécutée.
5. À l'exécution, le coffre refuse les doublons et tout dépassement du plafond PID de l'époque,
   puis transfère le stablecoin ERC-20 au bénéficiaire allowlisté.

Les adresses restent pseudonymes sur la chaîne, mais le token est permissionné. L'émetteur doit
relier l'allowlist à ses contrôles KYC/AML hors chaîne. Le contrat fournit les primitives techniques
(émission contrôlée, pause, allowlist, traçabilité), mais **ne constitue pas à lui seul une
certification MiCA**, une preuve de réserves ni une MNBC émise par une banque centrale.

## Formules exactes

Toutes les valeurs économiques utilisent des entiers en base `10^18` (`WAD`). Aucun `float` Python
ni nombre à virgule Solidity n'est utilisé.

```text
J_WAD = prompt_tokens × J_prompt_token_WAD
      + completion_tokens × J_completion_token_WAD

kWh_WAD = floor(J_WAD / 3 600 000)

EUR_MiCA_WAD = floor(kWh_WAD × tarif_EUR_kWh_WAD / 10^18)
```

`1 kWh = 3 600 000 joules`. Les divisions tronquent seulement en dessous de `10^-18` unité et ont
exactement la même sémantique dans Python et Solidity. Les joules par token ne sont pas une constante
universelle : ils doivent provenir de mesures du matériel, du PUE du datacenter et du modèle concerné.
Le terme « exact » désigne donc le calcul à partir de coefficients mesurés, pas une estimation physique
universelle.

Le contrôleur applique, en secondes entières :

```text
e(t) = vélocité_cible - vélocité_observée
u(t) = Kp·e(t) + Ki·∫e(t)dt + Kd·de(t)/dt
budget(t) = clamp(budget(t-1) + u(t), budget_min, budget_max)
```

L'intégrale est bornée (anti-windup) et le budget est toujours borné. `Math.mulDiv` d'OpenZeppelin
préserve la précision des produits intermédiaires.

## Installation et tests

Prérequis : Python 3.11+, Foundry, une souscription VRF v2.5 financée et un nœud RPC EVM.

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

Exemple de mesure seule (les identifiants fournisseur LiteLLM restent dans l'environnement) :

```powershell
$env:OPENAI_API_KEY = "..."
python -m llm_energy_settlement.cli --model openai/gpt-4o-mini --prompt "résume ceci" `
  --prompt-joules-per-token 2.1 --completion-joules-per-token 3.7 --euro-per-kwh 0.22
```

Ajouter `tokenized_llm_finance/python` à `PYTHONPATH` si le module n'est pas installé en editable.

## Déploiement et câblage

Renseigner les variables attendues par `script/Deploy.s.sol`, puis :

```powershell
forge script script/Deploy.s.sol:Deploy --rpc-url $env:RPC_URL --broadcast
```

Après le déploiement :

- ajouter le timelock comme consumer de la souscription VRF;
- allowlister les bénéficiaires et approvisionner le coffre en EEST;
- configurer chaque agent dans `PIDBudgetController.configureAgent`;
- vérifier les rôles après déploiement (le script les abandonne automatiquement lorsque la
  gouvernance diffère du déployeur);
- conserver `SUPERVISOR_PRIVATE_KEY` dans un HSM ou un coffre de secrets, jamais dans `.env` commité;
- faire auditer les contrats et tester le réseau cible avant toute valeur réelle.

Le workflow intégré lit `RPC_URL`, `SUPERVISOR_PRIVATE_KEY`, `TIMELOCK_ADDRESS`, `VAULT_ADDRESS` et
`PID_CONTROLLER_ADDRESS`, exécute l'appel LiteLLM puis met le règlement en attente :

```powershell
python -m llm_energy_settlement.workflow --model openai/gpt-4o-mini --prompt "analyse" `
  --agent 0x... --beneficiary 0x... --prompt-joules-per-token 2.1 `
  --completion-joules-per-token 3.7 --euro-per-kwh 0.22 `
  --observed-network-velocity-wad 125000000000000000000
```

L'exécution et l'annulation sont exposées par `OnChainSupervisor.execute` et
`OnChainSupervisor.cancel`. Une politique autonome peut annuler si la vélocité, le prix de l'énergie,
le budget résiduel ou un signal de risque dépasse son seuil avant `readyAt`.
L'option de vélocité déclenche d'abord `updateBudget`; l'adresse signataire doit alors posséder
`ORACLE_ROLE`. Dans une séparation stricte des fonctions, omettre cette option et faire publier la
vélocité agrégée par un oracle distinct.

## Limites de sécurité

- Ne jamais remplacer VRF par `block.timestamp`, `blockhash` ou `prevrandao` pour un règlement à
  enjeu financier : un producteur de bloc pourrait influencer le délai.
- La vélocité est une donnée oracle. Séparer les rôles oracle, superviseur, conformité et gouvernance,
  et utiliser multisig/timelock administratif en production.
- L'allowlist réduit la confidentialité. Pour davantage de confidentialité réglementée, ajouter une
  couche ZK/KYC auditée plutôt que de prétendre à l'anonymat.
- Le coffre règle le coût énergétique calculé. Les frais API du fournisseur LLM, le change éventuel
  USD/EUR, le gaz et les frais de rachat du stablecoin doivent être ajoutés comme postes séparés si le
  modèle économique les facture.
