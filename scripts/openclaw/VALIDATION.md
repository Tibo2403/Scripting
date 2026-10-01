# Validation des deux profils OpenClaw

Date : 2026-09-06. Perimetre utilisable : configuration, generation SDL et demarrage documente ; revue de code en lecture seule pour dual, conversation avec un fournisseur compatible pour inkling. Validation Docker et schema confirmee par la CI, verifiee le 2026-09-07. Aucun deploiement Akash n'a ete effectue.

## What Problem This Solves

Les prototypes employaient une configuration OpenClaw obsolete, une generation de manifeste executant le fichier d'environnement, et des chemins de demarrage qui pouvaient masquer les erreurs externes. Les clones de depots portant le meme nom pouvaient entrer en collision.

## Why This Change Was Made

Les deux profils partagent un validateur et un generateur sans evaluation shell. La configuration utilise le schema de la version 2026.5.26, epinglee par digest dans les images. Les clones utilisent OWNER/NAME, les erreurs interrompent le demarrage, et les instructions personnalisees persistent au redemarrage. Les manifestes generes et fichiers .env sont ignores par Git et exclus du contexte de construction.

## User Impact

Le contexte Docker est maintenant la racine du depot. Il faut renseigner les modeles et secrets dans .env. Les valeurs par defaut desactivent les appels periodiques, les groupes Telegram et les outils de modification. Le port Akash reste prive. La configuration est regeneree au demarrage ; les donnees et instructions conservent leur volume. Les guides de chaque projet decrivent la migration et le premier appel manuel.

## Evidence

- Before : configuration dual supprimee incompatible avec le schema epingle ; validation des modeles et gestion des erreurs de clonage insuffisantes ; ancien renderer Inkling utilisant le fichier .env comme code shell.
- Tests : `node --test scripts/openclaw/tests/config.test.mjs` : 6/6 reussis. Entrees invalides, secrets non journalises, generation litterale et ecriture atomique sans ecrasement implicite.
- Tests : `bash scripts/openclaw/tests/smoke.sh` : reussi avec Node et jq reels, fournisseurs/OpenClaw/Git simules. Couvre les deux demarrages, clones homonymes, conservation des instructions, erreurs Git/reseau/catalogue/schema, les deux wrappers de generation, refus d'ecrasement et remplacement explicite.
- Checks : `openclaw config validate` accepte les deux configurations avec le paquet npm exact `openclaw@2026.5.26`, installe temporairement avec `--ignore-scripts`. Secrets factices, aucun appel aux modeles.
- Checks : syntaxe Bash des scripts modifies reussie ; `python -m compileall -q .` reussi ; `python scripts/python/check_project_maturity.py` reussi (7 projets) ; `git diff --check` reussi sur le perimetre.
- Checks : PSScriptAnalyzer indisponible ; aucun fichier PowerShell modifie par ce travail.
- Checks : [CI OpenClaw deployment profiles #34033503411](https://github.com/Tibo2403/Scripting/actions/runs/34033503411) : **success**, du 2026-09-06 12:34:24 UTC au 12:35:15 UTC, commit `ee6a379d63847528248625e7d597de6bf777867e`. Le job `validate` confirme les tests Node, le smoke Bash, la construction de `dual:test` et `inkling:test`, puis `docker-schema.sh` dans les deux images avec `--network none`.
- Correspondance verifiee le 2026-09-07 : `git diff ee6a379d63847528248625e7d597de6bf777867e 13706da98fc69a2855367d7a082b919d42f2bedc -- openclaw-akash-dual-agents openclaw-inkling-akash scripts/openclaw .github/workflows/openclaw-deployments.yml` ne montre aucune difference. La preuve couvre donc les fichiers executables actuels ; cette mise a jour documentaire ne change pas les images.
- Execution locale du 2026-09-07 : moteur Docker Desktop Linux arrete (pipe absent), aucune nouvelle construction locale revendiquee. La preuve de construction des images vient du runner Linux GitHub, pas de hello-world.
- Autoreview : revue manuelle du code effectuee ; pas d'autoreview independante. Verifications : pas de `source .env`, substitutions shell conservees comme texte, URL HTTPS validee, jeton de passerelle obligatoire, permissions POSIX restrictives, erreurs non ignorees, aucun reset Git ni publication automatique. Les espaces de travail partages ne sont pas une isolation de securite ; l'outil read peut lire les fichiers accessibles au processus. Ne pas monter d'autres secrets dans ce conteneur.

## Reproduire la validation complete

Depuis la racine, avec Node 22+, Bash, jq et Docker Linux :

```bash
node --test scripts/openclaw/tests/config.test.mjs
bash scripts/openclaw/tests/smoke.sh
docker build -f openclaw-akash-dual-agents/Dockerfile -t dual:test .
docker build -f openclaw-inkling-akash/Dockerfile -t inkling:test .
bash scripts/openclaw/tests/docker-schema.sh
```

Le dernier test valide le schema dans chaque image sans reseau. Il ne demarre pas les integrations distantes. La CI ci-dessus satisfait la verification Docker/schema de la promotion. Avant exploitation, effectuer le premier appel manuel documente avec ses propres identifiants, verifier le pairing Telegram et tester le stockage chez le fournisseur Akash. Ces essais externes ne sont pas presentes comme reussis ici.
