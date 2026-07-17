# OpenClaw + Inkling sur Akash

Ce dossier fournit une image OpenClaw configurée avec un fournisseur Inkling compatible avec l'API OpenAI, ainsi qu'un modèle SDL Akash.

## Prérequis

- Docker
- un registre d'images public, par exemple GHCR
- une clé `INKLING_API_KEY`
- Akash Console ou Akash CLI
- `envsubst` (`gettext-base`) pour générer le SDL

## 1. Configuration

```bash
cd openclaw-inkling-akash
cp .env.example .env
openssl rand -hex 32
```

Place le résultat dans `OPENCLAW_GATEWAY_TOKEN`, puis renseigne l'image et la clé API dans `.env`.

Le réglage par défaut utilise :

- URL : `https://ai-gateway.vercel.sh/v1`
- modèle : `thinkingmachines/inkling`

Ces deux valeurs sont surchargeables dans `.env` si ton endpoint Inkling est différent.

## 2. Construction et publication de l'image

```bash
set -a
source .env
set +a

docker build -t "$OPENCLAW_IMAGE" .
docker push "$OPENCLAW_IMAGE"
```

## 3. Génération du SDL Akash

```bash
chmod +x render-deploy.sh
./render-deploy.sh
```

Le script produit `deploy.yaml`. Ce fichier contient les secrets injectés : ne le committe pas et supprime-le après le déploiement.

## 4. Déploiement

Importe `deploy.yaml` dans Akash Console, ou utilise la CLI Akash selon ton environnement. Le service expose le port `18789` et protège la gateway avec `OPENCLAW_GATEWAY_TOKEN`.

## Vérification locale

```bash
docker run --rm -p 18789:18789 \
  --env-file .env \
  "$OPENCLAW_IMAGE"
```

Puis vérifie que le conteneur reste actif et consulte ses journaux :

```bash
docker ps
docker logs <container-id>
```

## Sécurité

- Ne committe jamais `.env` ni `deploy.yaml`.
- Utilise un token gateway long et aléatoire.
- Limite l'exposition publique ou ajoute un proxy TLS/authentifié devant OpenClaw pour un usage Internet.
