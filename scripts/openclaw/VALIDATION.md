# Validation des deux profils OpenClaw

Date : 2026-09-06. Perimetre utilisable : configuration, generation SDL et demarrage documente ; revue de code en lecture seule pour dual, conversation avec un fournisseur compatible pour inkling. La promotion dans le catalogue reste a confirmer par la CI avant integration. Aucun deploiement Akash n'a ete effectue.

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
- Checks : CI ajoutee dans `.github/workflows/openclaw-deployments.yml`, resultat a verifier sur GitHub. Apres reparation des sockets locales, le moteur Docker Linux 29.6.1 repond et `docker run --rm hello-world` reussit (2026-09-06). Construction et tests des images de ces projets NON executes localement. La validation npm et hello-world ne remplacent pas la validation des images OpenClaw.
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

Le dernier test valide le schema dans chaque image sans reseau. Il ne demarre pas les integrations distantes. Avant integration de la promotion, obtenir une CI verte ; avant exploitation, effectuer le premier appel manuel documente avec ses propres identifiants, verifier le pairing Telegram et tester le stockage chez le fournisseur Akash. Ces essais externes ne sont pas presentes comme reussis ici.
