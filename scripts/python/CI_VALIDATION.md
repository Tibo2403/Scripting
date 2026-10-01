# Validation et dependances CI

Le workflow principal execute Python 3.11 et 3.12 sur Windows et Ubuntu.
Les tests PowerShell restent dans un job Windows. Les dependances propres a
Windows portent un marqueur de plateforme dans les contraintes.

Depuis la racine du depot, dans un environnement virtuel :

```powershell
python -m pip install -r scripts/python/requirements-ci.txt
python -m unittest discover -s scripts/python/tests -v
python -m ruff check --config scripts/python/ruff.toml scripts/python
python -m compileall -q scripts/python
```

Ruff couvre progressivement les routeurs et les outils de selection CI listes
dans `ruff.toml`. ShellCheck et PSScriptAnalyzer bloquent les erreurs existantes,
ainsi que les avertissements des scripts modifies sous `scripts/`.
PSScriptAnalyzer est fixe a 1.25.0.

Les fichiers `requirements-ci.txt` et `constraints-ci.txt` de `scripts/python/`
et `tokenized_llm_finance/` fixent les versions directes et transitives utilisees
par ces deux workflows. Les plages des requirements utilisateur restent
disponibles pour les installations hors CI. Les contraintes ne sont pas un
verrouillage cryptographique des distributions.

Pour une mise a jour, partir d'un environnement virtuel neuf, installer les
requirements utilisateur (ou `requirements-dev.txt` pour le prototype) et les
outils de lint, puis regenerer les contraintes avec `python -m pip freeze`.
Conserver les marqueurs de plateforme, notamment celui de `pywin32`, et
reinstaller via `requirements-ci.txt` dans un second environnement neuf.
Soumettre ensemble les contraintes et les eventuelles adaptations du code.
Les PR Dependabot hebdomadaires passent par les memes tests ; verifier les
quatre combinaisons de la matrice avant de fusionner.

Le prototype ajoute `python -m pytest`, `python -m ruff check python tests`
depuis son dossier, et les tests Foundry decrits dans son README. Foundry et
ses deux bibliotheques Solidity sont fixes a une version ou un commit explicite.
Le PRA ajoute `./pra/tests/Test-PraRecovery.ps1`, sans infrastructure externe.
