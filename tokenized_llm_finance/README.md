# Infrastructure tokenisée interbancaire et règlement d'agents LLM

> **Maturité : expérimental.** Les contrats sont compilés et testés avec Foundry en CI, mais ils ne sont pas audités. Ne pas utiliser avec de la valeur réelle.

Cette infrastructure combine désormais deux rails : un règlement bilatéral entre banques admises et
un sous-système qui mesure un appel LiteLLM, convertit sa consommation en euros tokenisés, régule le
budget par PID et temporise son règlement avec Chainlink VRF v2.5.

## Architecture interbancaire

- `BankRegistry` inscrit chaque établissement sous un identifiant stable, associe son compte de
  règlement et permet sa suspension immédiate. Les rôles d'inscription et de suspension sont séparés.
- `InterbankSettlement` crée une instruction irréutilisable de banque débitrice vers banque
  créditrice. La banque créditrice doit l'accepter avant le transfert atomique du jeton.
- Chaque instruction lie les deux banques, leurs comptes au moment de la création, le montant, une
  référence métier hachée et une expiration. Une rotation de compte invalide le règlement en attente.
- Une limite de sortie par banque et par époque borne la liquidité mobilisable. La pause globale et la
  suspension individuelle sont indépendantes.
- `EuroSettlementToken` demeure un actif privé permissionné libellé en euros. Il ne représente ni des
  réserves BCE, ni une MNBC, ni une créance automatiquement remboursable en monnaie commerciale.

Flux minimal d'un règlement :

```text
Gouvernance -> inscrit Banque A et Banque B dans BankRegistry
Compliance  -> autorise leurs comptes dans EuroSettlementToken
Liquidité   -> fixe la limite de sortie de Banque A
Banque A    -> approve InterbankSettlement puis crée l'instruction
Banque B    -> vérifie la référence et appelle acceptAndSettle
Contrat     -> transfère atomiquement A vers B et scelle l'instruction
```

L'identifiant BIC est stocké sous forme de hash pour l'intégrité, pas pour garantir sa confidentialité.
Une donnée sensible doit utiliser un engagement salé ou rester dans le registre réglementaire hors
chaîne. Les références de paiement peuvent pointer vers un message ISO 20022 conservé hors chaîne.

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
forge install OpenZeppelin/openzeppelin-contracts@c64a1edb67b6e3f4a15cca8909c9482ad33a02b0 --no-git
forge install foundry-rs/forge-std@77041d2ce690e692d6e03cc812b57d1ddaa4d505 --no-git
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

## Prix de marché auto-ajustés

```powershell
$env:ENTSOE_API_TOKEN = "charge-depuis-un-coffre"
python -m llm_energy_settlement.cli --model openai/gpt-4o-mini --prompt "résume ceci" `
  --prompt-joules-per-token 2.1 --completion-joules-per-token 3.7 `
  --auto-market-pricing
```

Ce mode lit le prix spot day-ahead ENTSO-E (EUR/MWh, converti en EUR/kWh), le taux de référence
ECB USD par EUR et le coût fournisseur estimé par LiteLLM. Il rejette les données anciennes ou
futures, applique un plancher/plafond et limite chaque variation par rapport au dernier snapshot
accepté. Le fichier d'état est écrit atomiquement. Les formules entières sont :

```text
electricite_EUR_WAD = floor(kWh_WAD * EUR_kWh_WAD / 10^18)
fournisseur_EUR_WAD = floor(fournisseur_USD_WAD * 10^18 / USD_par_EUR_WAD)
total_EUR_WAD       = electricite_EUR_WAD + fournisseur_EUR_WAD
```

Le reçu EIP-712 lie aussi `EUR/kWh`, le coût fournisseur USD et `USD/EUR`. Le coffre recalcule sur
chaîne chaque conversion avec `Math.mulDiv`, puis vérifie que le total signé est exactement la somme
des deux composantes.
Les taux ECB sont des références informatives et non des prix d'exécution. Un cache interne ne
remplace pas un oracle on-chain décentralisé pour une utilisation financière en production.

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

Le second script refuse l'abandon si la gouvernance et les opérateurs interbancaires ne possèdent pas
tous les rôles critiques attendus. Après le premier script, reporter aussi les adresses de
`BankRegistry` et `InterbankSettlement` dans `BANK_REGISTRY_ADDRESS` et
`INTERBANK_SETTLEMENT_ADDRESS` avant la finalisation.

## Exploitation du rail interbancaire

L'opérateur d'admission appelle `registerBank(bankId, bicHash, settlementAccount)`. Le responsable
compliance autorise séparément le compte dans `EuroSettlementToken`, puis le gestionnaire de
liquidité appelle `setOutgoingLimit(bankId, amountWad)`. Le compte débiteur doit enfin autoriser le
contrat par `approve` avant de créer une instruction.

La banque débitrice appelle `initiate(instructionId, creditorBankId, amountWad, referenceHash,
expiresAt)`. La banque créditrice règle avec `acceptAndSettle(instructionId)`. Le débiteur peut annuler
une instruction encore en attente et n'importe quel acteur peut la marquer expirée après l'échéance.
Un identifiant consommé ne redevient jamais disponible, y compris après annulation ou expiration.

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

Pour le workflow automatique, supprimer `--tariff-id` et `--euro-per-kwh`, puis ajouter
`--auto-market-pricing`. Les bornes, l'âge maximal et la variation maximale sont configurables avec
les variables `PRICE_*` documentées dans `.env.example`.

Si `--observed-network-velocity-wad` est aussi fourni, le workflow applique au signal PID une
surcharge unidirectionnelle lorsque le prix accepté dépasse `MARKET_PID_REFERENCE_EUR_PER_KWH` :

```text
prime_brute_bps = max(0, (prix - reference) * 10000 / reference)
prime_bps = min(prime_brute_bps * sensibilite_bps / 10000, prime_max_bps)
velocite_effective = velocite_observee * (10000 + prime_bps) / 10000
```

Une baisse du prix ne gonfle donc jamais le budget. La vélocité effective est plafonnée par
`maximumVelocityWad` lu directement dans le contrôleur on-chain. La sortie JSON expose le signal
brut, le signal effectif et la prime appliquée pour permettre l'audit de chaque décision.

## Limites réglementaires et opérationnelles

- L'ERC-20 est un rail technique permissionné, pas une certification MiCA ni une MNBC. Réserves,
  remboursement, KYC/AML, gouvernance, reporting et droits des détenteurs restent à mettre en œuvre.
- Le rail règle aujourd'hui la jambe espèces privée en brut. Il n'implémente pas encore le netting,
  la monnaie de banque centrale, la connexion TARGET/TIPS, le DvP/PvP, la gestion des files d'attente,
  le collatéral, la reprise après incident ni une passerelle ISO 20022 complète.
- Les adresses sont pseudonymes, pas anonymes. L'allowlist doit être reliée aux contrôles réglementaires.
- Des clés distinctes doivent être conservées dans HSM/coffres et idéalement portées par des services
  ou multisigs indépendants. Ne jamais committer une clé réelle.
- Le mode automatique inclut l'estimation du prix API LLM et le change. Le gaz, les spreads, les frais
  de rachat et les taxes ne sont pas inclus dans le règlement.
- Une transaction annulée ne réutilise pas sa clé sémantique : une nouvelle attestation et un nouveau
  nonce sont nécessaires pour une nouvelle tentative.
- Faire auditer les contrats et tester les scénarios VRF, réorganisation, expiration et pause avant
  toute mise en production ou valeur réelle.
