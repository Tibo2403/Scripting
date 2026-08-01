# Déploiement cloud

## Principe

Construisez l'image dans CI et poussez-la dans GHCR. Ne copiez jamais le compte
de service Google Chat dans l'image, une variable publique ou un manifeste Git.
Les volumes suivants doivent être persistants :

- `/home/node/.openclaw`
- `/var/lib/openclaw-crewai-admin`
- `/workspace/crewai`

Le secret Google doit être monté en lecture seule dans
`/run/secrets/googlechat-service-account.json`.

## AWS

La voie la plus simple et prévisible est une petite instance EC2 avec Docker
Compose, trois volumes EBS chiffrés (ou des répertoires sur un volume EBS) et un
Application Load Balancer HTTPS. Configurez l'ALB pour transmettre uniquement
`/googlechat*`; refusez la route par défaut. Conservez le JSON Google dans AWS
Secrets Manager et matérialisez-le avec permissions `0400` avant le démarrage.

Exécutez `install-vm.sh`, puis `install-secure-container.sh`. Limitez le Security
Group à SSH depuis votre IP et au trafic ALB vers le port 8080.

## Azure

Utilisez une VM Azure avec disque managé chiffré, ou Azure Container Apps avec
Azure Files pour les trois volumes persistants. Placez le JSON Google dans Key
Vault et montez-le comme secret fichier. L'ingress HTTPS doit cibler le port
8080 et la couche Front Door/Application Gateway doit autoriser uniquement
`/googlechat*`.

Pour une VM, exécutez `install-vm.sh`, puis le programme d'installation du kit.

## Akash

Le manifeste SDL est public : n'y placez jamais le JSON du compte de service,
une clé de modèle ou le jeton Gateway. N'utilisez Akash que si le fournisseur
choisi permet d'injecter un secret fichier hors SDL et fournit un stockage
persistant chiffré. Sans ces deux garanties, AWS ou Azure est préférable.

Le modèle `akash/deploy.yaml.example` contient uniquement les volumes, ressources
et port. Remplacez l'image par une référence GHCR immuable et injectez les
secrets séparément selon le fournisseur.

