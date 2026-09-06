# OpenClaw avec un fournisseur Inkling

Passerelle OpenClaw pour un modèle explicitement choisi sur une API HTTPS compatible OpenAI Chat Completions. Le nom Inkling désigne ce profil de configuration : il ne garantit ni l’existence d’un modèle particulier ni son accès avec votre clé. Les outils utilisent le profil minimal.

## Prérequis

Node.js 22 ou ultérieur, Docker avec moteur Linux, et Bash (Linux, WSL ou Git Bash sous Windows). Exécuter les commandes depuis la racine de ce dépôt. Le contexte de construction est désormais la racine, pas ce sous-dossier. L’image OpenClaw est fixée par version et digest dans le Dockerfile.

Préparer la clé et l’identifiant exact du modèle chez votre fournisseur. INKLING_BASE_URL doit utiliser HTTPS, sans identifiants ni paramètres dans l’URL. La valeur fournie cible Vercel AI Gateway ; la clé et le modèle doivent être autorisés sur cet endpoint. Choisir un modèle acceptant au moins 32 768 tokens de contexte et 4 096 tokens de sortie.

## Configuration et démarrage local

```bash
cp openclaw-inkling-akash/.env.example openclaw-inkling-akash/.env
node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"
```

Reporter le jeton généré dans OPENCLAW_GATEWAY_TOKEN et compléter chaque valeur vide. Remplacer OPENCLAW_IMAGE par le nom versionné de votre image. Utiliser des valeurs littérales sans guillemets, sans export et sans substitution shell. Ne jamais exécuter le fichier .env. Celui-ci est ignoré par Git et exclu du contexte Docker.

```bash
node scripts/openclaw/render.mjs inkling openclaw-inkling-akash/.env openclaw-inkling-akash/deploy.yaml
docker build -f openclaw-inkling-akash/Dockerfile -t openclaw-inkling:local .
docker volume create openclaw-inkling-data
docker run -d --name openclaw-inkling --init --restart unless-stopped \
  --env-file openclaw-inkling-akash/.env \
  -p 127.0.0.1:18789:18789 -v openclaw-inkling-data:/home/node/.openclaw \
  openclaw-inkling:local
docker logs openclaw-inkling
```

Le générateur refuse les paramètres manquants, les placeholders et les images latest. Il refuse d’écraser un manifeste existant ; ajouter --force pour un remplacement volontaire. Le manifeste contient vos secrets : garder les permissions locales restrictives et ne pas le partager. Les permissions POSIX 0600 ne remplacent pas les ACL Windows.

Utiliser un client OpenClaw compatible avec la passerelle locale ws://127.0.0.1:18789, authentifié avec OPENCLAW_GATEWAY_TOKEN. L’interface de contrôle web est désactivée. La validation du schéma ne vérifie pas le droit d’accès au modèle : effectuer une première requête courte avec votre client avant tout usage régulier.

Le client en ligne de commande est déjà dans le conteneur. Premier appel manuel (consomme les crédits du fournisseur) :

```bash
docker exec openclaw-inkling openclaw agent --agent main --session-id premier-essai --message "Reponds simplement : bonjour." --timeout 60
```

Les tâches cron, heartbeats et recherches mémoire sont désactivés. Les échanges demandés par l’utilisateur peuvent être facturés ; les scripts ne fixent aucun budget chez le fournisseur.

## Persistance, diagnostic et mises à jour

La configuration est régénérée à chaque démarrage depuis les variables d’environnement. Modifier .env puis recréer le conteneur en conservant le volume pour appliquer un changement ; une modification manuelle de openclaw.json sera remplacée. L’état de pairing et les conversations persistent dans le volume.

```bash
docker exec openclaw-inkling openclaw config validate
docker restart openclaw-inkling
docker logs --tail 100 openclaw-inkling
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

La CI dédiée exécute ces tests et construit les deux images pour valider le schéma avec la version épinglée. Les tests locaux couvrent les paramètres invalides, la génération littérale du manifeste, la protection contre l’écrasement et les échecs de démarrage. Aucun test automatisé ne dépense de crédits de modèles ni ne crée de déploiement Akash. Les connexions réelles au fournisseur Inkling et l’exploitation Akash exigent un essai opérateur avant des données importantes. Une CI configurée ne constitue pas une exécution réussie : vérifier son résultat sur votre branche.
