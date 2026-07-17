# Inkling on Akash

## Configuration optimale

Inkling compte 975 milliards de paramètres et nécessite un cluster de GPU spécialisés pour l'auto-hébergement. Une RTX 3090 de 24 GiB ne peut pas charger le modèle.

La solution la moins chère est donc, dans cet ordre :

1. appeler directement une API Inkling compatible OpenAI ;
2. si un endpoint privé et une clé client distincte sont nécessaires, déployer une petite passerelle LiteLLM CPU sur Akash ;
3. ne louer une RTX 3090 que pour un autre modèle local compatible, car elle ne sert à rien pour une passerelle API Inkling.

Le profil par défaut du script est désormais CPU-only :

- 0,5 vCPU ;
- 1 GiB de RAM ;
- 1 GiB de stockage éphémère ;
- aucune carte graphique ;
- plafond d'enchère de 25 uACT par bloc, soit environ 10,80 ACT par mois au maximum configuré. Le prix réel dépend de l'offre gagnante.

## Prérequis

- Un compte Akash financé.
- Le CLI `provider-services` configuré avec une clé Akash.
- Un endpoint Inkling compatible avec l'API OpenAI.
- Une clé API du fournisseur.

## Générer le SDL

```bash
export INKLING_API_BASE='https://provider.example/v1'
export INKLING_API_KEY='replace-me'
export LITELLM_MASTER_KEY="$(openssl rand -hex 32)"

bash scripts/bash/deploy_inkling_akash.sh --dry-run
bash scripts/bash/deploy_inkling_akash.sh --output deploy-inkling-akash.yaml
```

Le fichier SDL contient les secrets. Ne le commitez pas et supprimez-le après le déploiement.

## Déployer

```bash
export AKASH_KEY_NAME='your-akash-key'
bash scripts/bash/deploy_inkling_akash.sh --deploy
```

Après la création du déploiement, sélectionnez une offre fournisseur et envoyez le manifeste avec votre workflow Akash habituel. La passerelle expose une API compatible OpenAI sur le port 80.

## Tester

```bash
curl 'http://YOUR_AKASH_HOST/v1/chat/completions' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "inkling",
    "messages": [{"role": "user", "content": "Bonjour"}]
  }'
```

## Profil RTX 3090

Le profil historique reste disponible uniquement pour comparaison :

```bash
bash scripts/bash/deploy_inkling_akash.sh --profile rtx3090 --dry-run
```

Il affiche un avertissement, car le GPU reste inutilisé par la passerelle et peut ajouter plusieurs centaines de dollars par mois. Il ne permet pas d'auto-héberger Inkling.

## Réduction supplémentaire du coût

Pour un usage personnel ou un seul client, utilisez directement `INKLING_API_BASE` depuis l'application et ne déployez aucune passerelle. La passerelle Akash devient utile pour centraliser les clés, présenter un endpoint stable, appliquer des quotas ou connecter plusieurs applications.