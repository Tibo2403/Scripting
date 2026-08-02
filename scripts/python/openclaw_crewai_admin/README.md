# OpenClaw ↔ CrewAI depuis Google Chat

Ce kit permet à OpenClaw de gérer les tâches CrewAI en langage naturel depuis
Google Chat, via un serveur MCP local. Les écritures utilisent un flux en deux
temps : proposition, puis application avec un jeton de confirmation.

## Installation sécurisée avec Docker

L'image inclut OpenClaw, le serveur MCP CrewAI et un proxy minimal. Le port
public ne dessert que `POST /googlechat` et `GET /healthz`; le tableau de bord
OpenClaw écoute uniquement sur la boucle locale du conteneur.

```bash
chmod +x install-secure-container.sh
./install-secure-container.sh \
  /chemin/absolu/projet-crewai \
  /chemin/absolu/googlechat-service-account.json \
  https://bot.example.com/googlechat \
  users/1234567890
```

Le port est lié à `127.0.0.1:8080` par défaut. Placez-le derrière un proxy TLS
qui ne publie que `/googlechat`. Pour un cloud avec terminaison TLS intégrée,
changez `BIND_ADDRESS` uniquement après avoir configuré les restrictions
d'entrée de la plateforme.

Le script refuse les emails comme allowlist Google Chat : utilisez l'identifiant
stable `users/<nombre>`.

## Prérequis

- Linux, macOS ou WSL2
- Python 3.11+
- OpenClaw déjà installé
- Un projet CrewAI contenant `config/tasks.yaml`; `config/agents.yaml` est requis
  pour consulter les agents avec les outils MCP dédiés.

## Installation

```bash
chmod +x setup.sh
./setup.sh /chemin/vers/votre/projet-crewai
```

Le script crée `.venv`, installe les dépendances et génère `.env` ainsi que
`openclaw-mcp.json5`. Il ne modifie pas la configuration OpenClaw existante.

Ajoutez ensuite le serveur MCP à OpenClaw :

```bash
openclaw mcp add crewai-admin \
  --command "$(pwd)/.venv/bin/python" \
  --arg "$(pwd)/crewai_admin_mcp.py"
openclaw mcp status
openclaw mcp probe crewai-admin
```

Si votre version utilise l'édition JSON5, copiez le bloc de
`openclaw-mcp.json5` dans la section `mcp.servers` de la configuration.

## Outils exposés à OpenClaw

- `list_tasks` : affiche les tâches CrewAI.
- `get_task` : affiche une tâche précise.
- `list_agents` : affiche les agents CrewAI et leurs rôles.
- `get_agent` : affiche la définition d'un agent précis.
- `propose_task_update` : prépare un changement et renvoie un jeton.
- `apply_task_update` : applique une proposition confirmée.
- `rollback_last_change` : restaure la sauvegarde précédente.

Exemple de conversation dans Google Chat :

> Liste les tâches CrewAI.

> Montre-moi la configuration de l'agent `coder_agent`.

> Propose de limiter `market_research` à dix lignes et d'exiger des sources.

> Montre-moi le changement exact, sans l'appliquer.

> J'approuve la proposition `<jeton>` ; applique-la.

## Agent codeur d'exemple

Le dossier `sample-crewai/config` contient désormais un `coder_agent` et une
tâche `code_change`. L'agent produit uniquement une proposition de patch et les
commandes de validation : l'exécution de code, la délégation et la publication
automatique sont désactivées. Lancez la tâche avec une entrée explicite, par
exemple `coding_request="Ajoute une validation du fichier de configuration"`.

## Google Chat

Google Chat reste le canal d'entrée. Configurez l'application Google Chat et
son webhook HTTPS selon la documentation OpenClaw, puis liez ce compte à
l'agent ayant accès au serveur MCP `crewai-admin`.

Ne publiez pas le tableau de bord OpenClaw sur Internet. N'exposez que le chemin
webhook Google Chat et conservez l'authentification du Gateway.

## Sécurité

- Les écritures sont limitées à `tasks.yaml`; `agents.yaml` reste en lecture seule.
- Une proposition expire après 15 minutes.
- L'application exige le jeton exact avant toute écriture.
- Chaque écriture crée une sauvegarde horodatée.
- Le YAML est validé avant remplacement atomique.
- Le serveur MCP ne lance ni CrewAI, ni commande shell, ni déploiement.
- Le conteneur abandonne toutes les capabilities Linux et interdit l'élévation.
- Le système de fichiers racine est en lecture seule; seuls l'état et CrewAI
  sont montés en écriture.
- Aucun secret n'est inclus dans l'image ou le dépôt.

Pour la production, exécutez le serveur sous un utilisateur système dédié,
limitez l'accès OpenClaw à ce seul MCP et conservez le projet CrewAI dans Git.

Voir [`deploy/README.md`](deploy/README.md) pour AWS, Azure et Akash.

