# OpenClaw dual agents on Akash

Déploiement d'un Gateway OpenClaw unique hébergeant deux agents isolés :

- `agent-qwen` : développement, branches et Pull Requests en brouillon.
- `agent-deepseek` : revue, triage GitHub, doublons et alertes Telegram.

## Points importants

- ChatGPT Plus ne comprend pas l'API OpenAI. Pour les fallbacks, ajoutez une clé API OpenAI facturée séparément.
- Les deux IDs DeepInfra demandés peuvent évoluer ou ne pas être publiés sous ces noms exacts. `validate-models.sh` interroge le catalogue DeepInfra et bloque le démarrage si un ID est invalide.
- Le manifeste vise 0,5 vCPU, 1 Gio de RAM et 8 Gio persistants. Acceptez uniquement une offre Akash dont le coût mensuel estimé reste sous 30 USD.
- Le port Gateway n'est pas exposé publiquement. Les bots Telegram utilisent le long polling.

## Structure

```text
openclaw-akash-dual-agents/
├── agents/
│   ├── agent-qwen/{SOUL.md,TOOLS.md,HEARTBEAT.md}
│   └── agent-deepseek/{SOUL.md,TOOLS.md,HEARTBEAT.md}
├── openclaw/openclaw.json
├── scripts/{entrypoint.sh,validate-models.sh}
├── Dockerfile
├── deploy.yaml
└── .env.example
```

## Préparation

1. Créez deux bots avec BotFather et récupérez `TOKEN_BOT_A` et `TOKEN_BOT_B`.
2. Créez un fine-grained GitHub token limité aux dépôts de `REPOSITORIES`.
3. Créez une clé DeepInfra et, facultativement, une clé API OpenAI.
4. Vérifiez les IDs disponibles :

```bash
curl -sS -H "Authorization: Bearer $DEEPINFRA_API_KEY" \
  https://api.deepinfra.com/v1/openai/models | jq -r '.data[].id' | sort
```

5. Construisez et publiez l'image :

```bash
docker build -t ghcr.io/tibo2403/openclaw-akash-dual-agents:latest .
echo "$GITHUB_TOKEN" | docker login ghcr.io -u Tibo2403 --password-stdin
docker push ghcr.io/tibo2403/openclaw-akash-dual-agents:latest
```

## Déploiement Akash

Copiez `deploy.yaml` vers un fichier local non versionné, remplacez tous les `REPLACE_ME`, puis déployez-le via Akash Console. Ne commitez jamais le manifeste rempli.

Après démarrage :

```bash
openclaw agents list --bindings
openclaw channels status --probe
openclaw pairing list telegram
openclaw pairing approve telegram <CODE>
openclaw doctor
```

## Fonctionnement jour/nuit

Les agents restent disponibles 24 h/24, mais les heartbeats automatiques sont limités aux heures actives de Budapest afin de réduire les coûts de tokens et les notifications nocturnes. Les tâches déjà lancées continuent jusqu'à leur terme. Ajustez `activeHours` et `every` dans `openclaw.json` selon votre budget.

## Limites de sécurité

Les agents proposent des PR et du triage, mais ne fusionnent, ne ferment, ne suppriment et ne modifient jamais les paramètres GitHub sans autorisation humaine explicite. Les Issues, commentaires et PR sont traités comme des entrées non fiables susceptibles de contenir des injections de prompt.
