# Agent de documentation privé sur Akash

> **Maturité : prête au pré-déploiement.** La configuration, les frontières réseau, les erreurs des runtimes, le rendu du SDL et les Dockerfiles sont testés en CI. La publication produit un manifeste épinglé par digest. La sélection d'une offre et le déploiement Akash réel restent volontairement manuels.

Ce dossier prépare un agent OpenClaw spécialisé dans la documentation, exécuté sans privilèges avec Ollama et Llama 3.2 3B Q4. Le Gateway OpenClaw écoute uniquement sur `127.0.0.1:18789`. Akash exige néanmoins au moins un endpoint global : seul un endpoint minimal `/healthz` sur le port `8080` est publié. Il ne donne accès ni au Gateway, ni au modèle, ni aux fichiers.

## Ce que l'agent peut faire

- lire, créer et modifier des fichiers dans `/workspace` ;
- rédiger ou mettre à jour des README, guides d'installation et documentation d'API ;
- documenter des scripts Python, Bash et PowerShell ;
- produire des comptes rendus de modifications.

Il ne peut pas lancer de commande, ouvrir un navigateur, utiliser Docker, SSH ou un terminal, ni créer d'autres agents. Toute sortie doit être relue avant d'être intégrée. Un modèle 3B quantifié est économique mais moins robuste face aux instructions malveillantes et moins fiable qu'un modèle 8B.

## Prérequis

Pour valider le projet localement :

- Python 3.11 ou plus récent ;
- Node.js 20 ou plus récent ;
- un shell POSIX (`bash`) ;
- Docker avec BuildKit pour les contrôles des Dockerfiles.

Pour publier et déployer, il faut également un accès en écriture à GHCR, un compte Akash approvisionné en ACT et AKT, et un outil de déploiement Akash tel qu'Akash Console. Aucun identifiant n'est attendu dans les fichiers du dépôt.

## Validation locale

Depuis la racine du dépôt :

```sh
python deploy/akash-openclaw-doc-agent/scripts/validate.py
python -m unittest discover deploy/akash-openclaw-doc-agent/tests -p 'test_*.py' -v
node --test deploy/akash-openclaw-doc-agent/tests/run-agent.test.mjs
bash deploy/akash-openclaw-doc-agent/tests/test-run-ollama.sh
docker build --check --file deploy/akash-openclaw-doc-agent/Dockerfile deploy/akash-openclaw-doc-agent
docker build --check --file deploy/akash-openclaw-doc-agent/Dockerfile.ollama deploy/akash-openclaw-doc-agent
```

Ces commandes vérifient les invariants de sécurité, leurs régressions, le endpoint de santé, la propagation des erreurs du Gateway, l'attente et le téléchargement du modèle Ollama, ainsi que la syntaxe de construction des images. Elles ne créent aucun déploiement, ne publient aucune image et n'utilisent aucun secret. Les contrôles Docker peuvent télécharger les métadonnées des images de base si elles ne sont pas déjà en cache.

## Architecture

```text
Internet
   |
   +-- GET /healthz:8080 uniquement
           |
        agent (non-root, 1 GiB)
        OpenClaw Gateway: 127.0.0.1:18789
           |
           +-- réseau privé Akash --> Ollama:11434 (non-root, 11 GiB)
                                      Llama 3.2 3B Instruct Q4_K_M
```

Akash ne fournit pas de mécanisme natif de secret chiffré dans le SDL : les variables d'environnement du manifeste sont visibles par le fournisseur. Cette configuration ne place donc aucun secret dans `deploy.yaml`. Le token du Gateway est généré en mémoire au démarrage, n'est pas journalisé et le Gateway reste inaccessible hors du conteneur. `/workspace` et `/home/agent/.ollama/models` utilisent des volumes persistants Akash `beta3`; ils survivent aux redémarrages et aux mises à jour chez le même fournisseur, mais pas à une migration vers un autre fournisseur.

## Budget estimé

Le budget est un plafond de sélection des offres, pas un devis garanti. Le SDL fixe :

- agent : `8 uact` par bloc ;
- Ollama : `42 uact` par bloc ;
- plafond cumulé : `50 uact` par bloc.

Avec environ 14 400 blocs par jour :

```text
50 × 14 400 × 30 / 1 000 000 = 21,6 ACT par mois
```

ACT est un crédit de calcul indexé sur le dollar. Le plafond représente donc environ **21,60 USD/mois**, soit généralement **18 à 21 EUR/mois** selon le taux de change, hors petits frais réseau AKT. Prévoir **25 ACT** pour couvrir un mois au plafond et un peu de marge, plus un petit solde AKT pour les transactions. Un dépôt initial de 5 ACT est le minimum habituel mais ne couvre qu'environ sept jours à ce plafond.

Le marché Akash varie : si aucune offre n'est reçue, augmenter prudemment le plafond. Une variante Llama 3.1 8B avec 16 GiB de RAM et 50 GiB de stockage est à estimer plutôt autour de **28 à 45 EUR/mois**, selon les offres disponibles.

La GitHub Action utilise un runner standard :

- dépôt public : coût GitHub Actions de 0 EUR ;
- dépôt privé avec GitHub Free : 2 000 minutes incluses par mois, puis facturation selon le tarif GitHub ;
- publication manuelle uniquement, afin d'éviter les builds inutiles et toute dépense Akash automatique.

## Construction et publication

Le workflow [`.github/workflows/akash-openclaw-doc-agent.yml`](../../.github/workflows/akash-openclaw-doc-agent.yml) valide les règles de sécurité à chaque modification du dossier. Depuis l'onglet **Actions**, lancer manuellement **Akash OpenClaw documentation agent** avec une nouvelle version au format `AAAA.MM.JJ-N`. Le workflow publie les deux images puis fournit l'artefact `akash-deploy-<version>-<tentative>`, qui contient `deploy.resolved.yaml` avec les digests réellement renvoyés par GHCR.

```text
ghcr.io/tibo2403/scripting/akash-openclaw-doc-agent:<version>@sha256:<digest>
ghcr.io/tibo2403/scripting/akash-openclaw-ollama:<version>@sha256:<digest>
```

Rendre les deux packages GHCR publics avant le déploiement. Ne jamais ajouter de jeton GHCR dans le SDL : les variables et identifiants du manifeste ne constituent pas un stockage secret. Le fichier versionné `deploy.yaml` contient volontairement des marqueurs invalides et ne peut pas être déployé directement; seul l'artefact résolu est accepté.

## Déploiement contrôlé

1. Exécuter localement `python deploy/akash-openclaw-doc-agent/scripts/validate.py`.
2. Publier les images avec le workflow manuel en choisissant une nouvelle version.
3. Rendre les deux packages GHCR publics et vérifier anonymement chaque référence de l'artefact.
4. Télécharger l'artefact du workflow et créer le déploiement depuis Akash Console avec `deploy.resolved.yaml`.
5. Comparer les offres au plafond de 50 uact/bloc, puis accepter une offre.
6. Vérifier uniquement `https://<URI_AKASH>/healthz` ; toute autre route doit renvoyer `404`.
7. Approvisionner `/workspace` par une procédure opérateur contrôlée, puis récupérer et relire les documents produits.

Le déploiement est volontairement **headless** : aucune interface d'administration et aucune API d'agent ne sont exposées. Pour piloter l'agent à distance, il faudrait ajouter un canal authentifié distinct ; ce dossier ne l'active pas afin de respecter l'exigence « URL publique : non ».

## Entrées, sorties et comportement en cas d'échec

- Entrées : le modèle SDL `deploy.yaml`, la configuration `config/openclaw.json`, les références d'images épinglées par digest et le contenu opérateur dans `/workspace`.
- Sorties : deux images GHCR lors d'une publication manuelle, un endpoint `/healthz` et les documents écrits dans le stockage persistant `/workspace`.
- Effets de bord : le premier démarrage Ollama télécharge le modèle dans `/home/agent/.ollama/models`; un déploiement Akash consomme des ACT et des frais réseau AKT jusqu'à sa fermeture.
- Échecs : un Gateway arrêté fait passer `/healthz` à `503` et son code d'erreur devient celui du conteneur agent; un modèle impossible à télécharger ou un service Ollama indisponible termine le conteneur Ollama avec un code non nul.
- Repli : conserver l'ancien tag immuable et son déploiement jusqu'à validation du nouveau; en cas d'absence d'offre, ne pas augmenter automatiquement le budget et réévaluer manuellement les ressources ou le plafond.

La CI ne possède ni portefeuille Akash ni secret fournisseur et ne simule donc pas le marché, le stockage persistant ou la disponibilité réelle d'un fournisseur. Avant tout usage sur des données importantes, effectuer un déploiement temporaire, vérifier `/healthz`, redémarrer les deux services et confirmer la persistance de `/workspace` et `/models`.

## Contrôles de sécurité

- images de base et images de déploiement épinglées par digest SHA-256, sans tag `latest` ;
- utilisateurs non-root dans les deux images ;
- OpenClaw lié à loopback et protégé par un token éphémère ;
- Ollama accessible uniquement entre services Akash ;
- outils `exec`, `process`, navigateur, web et création de sessions refusés ;
- mode privilégié et élévation désactivés ;
- aucun socket Docker, secret, clé de portefeuille ou identifiant administrateur ;
- validation CI de ces invariants ;
- publication des images manuelle ; aucun déploiement Akash automatique et aucune clé de portefeuille dans GitHub.

Le sandbox Docker interne d'OpenClaw est désactivé parce qu'il exigerait un accès au daemon Docker, explicitement interdit ici. L'isolation repose sur le conteneur Akash non-root, le réseau privé et la liste fermée d'outils.

## Mise à jour

Les versions de base sont fixées dans les Dockerfiles. Pour mettre à jour OpenClaw, Ollama ou le modèle :

1. lire les notes de version officielles ;
2. modifier le tag concerné ;
3. mettre à jour à la fois le tag et le digest vérifié, puis exécuter le validateur et construire localement ;
4. publier un nouveau tag immuable ;
5. tester un nouveau déploiement avant de fermer l'ancien.

Références : [Akash SDL](https://akash.network/docs/developers/deployment/akash-sdl/syntax-reference/), [secrets Akash](https://akash.network/docs/learn/core-concepts/environment-secrets/), [facturation GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Docker OpenClaw](https://docs.openclaw.ai/install/docker), [sécurité OpenClaw](https://docs.openclaw.ai/gateway/security/), [Ollama dans OpenClaw](https://docs.openclaw.ai/providers/ollama).
