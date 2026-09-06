# Deux agents OpenClaw sur Akash

Deux comptes Telegram interrogent deux modèles DeepInfra et lisent des dépôts GitHub. Cette version prend en charge la revue et les explications de code : les outils de modification, de shell et de publication sont désactivés. Les agents partagent le conteneur ; leurs espaces de travail distincts ne constituent pas une frontière de sécurité.

## Prérequis

Node.js 22 ou ultérieur, Docker avec moteur Linux, et Bash (Linux, WSL ou Git Bash sous Windows). Exécuter les commandes depuis la racine de ce dépôt. Le contexte de construction est désormais la racine, pas ce sous-dossier. L’image OpenClaw est fixée par version et digest dans le Dockerfile.

Préparer deux bots Telegram distincts, une clé DeepInfra et un jeton GitHub limité à la lecture des dépôts nécessaires. Choisir deux identifiants de modèles réellement disponibles dans le catalogue DeepInfra. REPOSITORIES attend une liste owner/name séparée par des virgules, sans suffixe .git.

## Configuration et démarrage local

```bash
cp openclaw-akash-dual-agents/.env.example openclaw-akash-dual-agents/.env
node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"
```

Reporter le jeton généré dans OPENCLAW_GATEWAY_TOKEN et compléter chaque valeur vide. Remplacer OPENCLAW_IMAGE par le nom versionné de votre image. Utiliser des valeurs littérales sans guillemets, sans export et sans substitution shell. Ne jamais exécuter le fichier .env. Celui-ci est ignoré par Git et exclu du contexte Docker.

```bash
node scripts/openclaw/render.mjs dual openclaw-akash-dual-agents/.env openclaw-akash-dual-agents/deploy.yaml
docker build -f openclaw-akash-dual-agents/Dockerfile -t openclaw-dual:local .
docker volume create openclaw-dual-data
docker run -d --name openclaw-dual --init --restart unless-stopped \
  --env-file openclaw-akash-dual-agents/.env \
  -p 127.0.0.1:18789:18789 -v openclaw-dual-data:/data \
  openclaw-dual:local
docker logs openclaw-dual
```

Le générateur refuse les paramètres manquants, les placeholders et les images latest. Il refuse d’écraser un manifeste existant ; ajouter --force pour un remplacement volontaire. Le manifeste contient vos secrets : garder les permissions locales restrictives et ne pas le partager. Les permissions POSIX 0600 ne remplacent pas les ACL Windows.

Au démarrage, la configuration est validée par OpenClaw, les deux modèles sont vérifiés dans le catalogue DeepInfra, puis les dépôts sont clonés sous /data/repos/OWNER/NAME. Toute erreur arrête le démarrage. Les redémarrages récupèrent les références Git sans modifier la copie de travail. Pour actualiser celle-ci, effectuer manuellement un git pull --ff-only dans le clone concerné. Un ancien clone sous /data/repos/NAME reste intact : sauvegarder puis migrer explicitement si nécessaire.

Envoyer un message privé à chaque bot puis approuver le code de pairing depuis le conteneur avec la commande OpenClaw pairing (voir docker exec openclaw-dual openclaw pairing approve --help pour les paramètres du compte). Les groupes sont désactivés. Demander ensuite une explication d’un fichier précis sous /data/repos/OWNER/NAME.

Les tâches cron, heartbeats et recherches mémoire sont désactivés. Les échanges demandés par l’utilisateur peuvent être facturés ; les scripts ne fixent aucun budget chez le fournisseur.

## Persistance, diagnostic et mises à jour

La configuration est régénérée à chaque démarrage depuis les variables d’environnement. Modifier .env puis recréer le conteneur en conservant le volume pour appliquer un changement ; une modification manuelle de openclaw.json sera remplacée. L’état de pairing et les conversations persistent dans le volume. Les fichiers d’instructions existants sont conservés ; pour adopter les nouvelles instructions de lecture seule, sauvegarder puis remplacer SOUL.md, TOOLS.md et HEARTBEAT.md dans les deux workspaces.

```bash
docker exec openclaw-dual openclaw config validate
docker restart openclaw-dual
docker logs --tail 100 openclaw-dual
```

Une erreur de configuration, d’autorisation ou de réseau apparaît dans les logs et produit un code de sortie non nul. Ne pas publier les logs bruts sans les relire. Sauvegarder le volume avant une mise à jour ; arrêter le conteneur, sauvegarder ses données, puis conserver l’ancienne image pour permettre le retour arrière. Réutiliser le même volume avec l’ancienne image seulement si le format d’état reste compatible.

## Akash

Construire et publier votre image versionnée dans le registre indiqué par OPENCLAW_IMAGE, puis générer le manifeste. Vérifier les prix, la classe de stockage et les capacités du fournisseur avant de créer une offre. Le port reste privé (global: false) : prévoir un accès privé ou un tunnel pour le client ; aucun service HTTP public n’est configuré. Le volume persistant doit être sauvegardé indépendamment du fournisseur. Le manifeste n’achète ni ne déploie rien à lui seul.

## Validation et limites

Les [résultats de validation](../scripts/openclaw/VALIDATION.md) distinguent les tests réussis des vérifications Docker et externes restantes.

```bash
node --test scripts/openclaw/tests/*.test.mjs
bash scripts/openclaw/tests/smoke.sh
```

La CI dédiée exécute ces tests et construit les deux images pour valider le schéma avec la version épinglée. Les tests locaux couvrent les paramètres invalides, la génération littérale du manifeste, la protection contre l’écrasement et les échecs de démarrage. Aucun test automatisé ne dépense de crédits de modèles ni ne crée de déploiement Akash. Les connexions réelles Telegram/GitHub/DeepInfra et l’exploitation Akash exigent un essai opérateur avant des données importantes. Une CI configurée ne constitue pas une exécution réussie : vérifier son résultat sur votre branche.
