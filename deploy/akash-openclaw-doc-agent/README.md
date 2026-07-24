# Agent de documentation privé sur Akash

Ce dossier prépare un agent OpenClaw spécialisé dans la documentation, exécuté sans privilèges avec Ollama et Llama 3.2 3B Q4. Le Gateway OpenClaw écoute uniquement sur `127.0.0.1:18789`. Akash exige néanmoins au moins un endpoint global : seul un endpoint minimal `/healthz` sur le port `8080` est publié. Il ne donne accès ni au Gateway, ni au modèle, ni aux fichiers.

## Ce que l'agent peut faire

- lire, créer et modifier des fichiers dans `/workspace` ;
- rédiger ou mettre à jour des README, guides d'installation et documentation d'API ;
- documenter des scripts Python, Bash et PowerShell ;
- produire des comptes rendus de modifications.

Il ne peut pas lancer de commande, ouvrir un navigateur, utiliser Docker, SSH ou un terminal, ni créer d'autres agents. Toute sortie doit être relue avant d'être intégrée. Un modèle 3B quantifié est économique mais moins robuste face aux instructions malveillantes et moins fiable qu'un modèle 8B.

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

Akash ne fournit pas de mécanisme natif de secret chiffré dans le SDL : les variables d'environnement du manifeste sont visibles par le fournisseur. Cette configuration ne place donc aucun secret dans `deploy.yaml`. Le token du Gateway est généré en mémoire au démarrage, n'est pas journalisé et le Gateway reste inaccessible hors du conteneur.

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

Le workflow [`.github/workflows/akash-openclaw-doc-agent.yml`](../../.github/workflows/akash-openclaw-doc-agent.yml) valide les règles de sécurité à chaque modification du dossier. Depuis l'onglet **Actions**, lancer manuellement **Akash OpenClaw documentation agent**, avec la version par défaut `2026.07.24-1`, pour publier :

```text
ghcr.io/tibo2403/scripting/akash-openclaw-doc-agent:2026.07.24-1
ghcr.io/tibo2403/scripting/akash-openclaw-ollama:2026.07.24-1
```

Rendre les deux packages GHCR accessibles au fournisseur Akash, ou configurer des identifiants de registre côté plateforme. Ne jamais ajouter de jeton GHCR dans le SDL.

## Déploiement contrôlé

1. Exécuter localement `python deploy/akash-openclaw-doc-agent/scripts/validate.py`.
2. Publier les images avec le workflow manuel.
3. Vérifier que les tags du fichier `deploy.yaml` correspondent aux images publiées.
4. Créer le déploiement depuis Akash Console avec `deploy.yaml`.
5. Comparer les offres au plafond de 50 uact/bloc, puis accepter une offre.
6. Vérifier uniquement `https://<URI_AKASH>/healthz` ; toute autre route doit renvoyer `404`.
7. Approvisionner `/workspace` par une procédure opérateur contrôlée, puis récupérer et relire les documents produits.

Le déploiement est volontairement **headless** : aucune interface d'administration et aucune API d'agent ne sont exposées. Pour piloter l'agent à distance, il faudrait ajouter un canal authentifié distinct ; ce dossier ne l'active pas afin de respecter l'exigence « URL publique : non ».

## Contrôles de sécurité

- images versionnées, sans tag `latest` ;
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
3. exécuter le validateur et construire localement ;
4. publier un nouveau tag immuable ;
5. tester un nouveau déploiement avant de fermer l'ancien.

Références : [Akash SDL](https://akash.network/docs/developers/deployment/akash-sdl/syntax-reference/), [secrets Akash](https://akash.network/docs/learn/core-concepts/environment-secrets/), [facturation GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Docker OpenClaw](https://docs.openclaw.ai/install/docker), [sécurité OpenClaw](https://docs.openclaw.ai/gateway/security/), [Ollama dans OpenClaw](https://docs.openclaw.ai/providers/ollama).
