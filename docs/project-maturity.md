# Maturite des projets du monorepo

Ce depot reste un monorepo. Chaque dossier de projet doit etre declare dans
[`project-maturity.toml`](../project-maturity.toml) avec un des deux niveaux suivants.

## Utilisable

Un projet **utilisable** possede une entree documentee, des valeurs par defaut prudentes, une
validation reproductible executee en CI et des limites connues. Il peut etre utilise dans le cadre
decrit par sa documentation. Ce niveau ne signifie pas « certifie pour la production » : les acces,
secrets, couts, sauvegardes et impacts metier restent sous la responsabilite de l'operateur.

## Experimental

Un projet **experimental** sert a apprendre, prototyper ou valider une architecture. Son interface
peut changer sans migration. Certaines integrations externes, validations de securite ou simulations
de panne peuvent manquer. Il ne doit pas recevoir de secrets ou de donnees reelles, ni piloter un
systeme critique ou de la valeur reelle sans revue et validation complementaires.

## Passer un projet a « utilisable »

La promotion se fait dans le meme depot et exige une pull request qui apporte les preuves suivantes :

1. un README avec prerequis, exemple minimal, entrees, sorties, effets de bord et limites ;
2. des valeurs par defaut non destructives et aucune donnee secrete versionnee ;
3. une commande de validation locale reproductible ;
4. des tests CI couvrant les chemins d'execution principaux ;
5. un test d'echec ou de repli pour les dependances externes critiques ;
6. une revue securite adaptee au risque ;
7. la mise a jour de `project-maturity.toml` et du tableau du README.

Si une garantie n'est plus vraie, le projet repasse a **experimental** jusqu'a sa restauration. Les
fonctionnalites experimentales placees dans un projet utilisable doivent etre nommees et signalees
comme telles dans leur documentation ; elles n'heritent pas automatiquement du niveau du dossier.

## Controle anti-derive

La commande suivante verifie que tous les dossiers de projet a la racine sont classes, que leur
documentation existe et que les projets experimentaux expliquent leurs limites :

```bash
python scripts/python/check_project_maturity.py
```

Ce controle verifie la coherence du catalogue, pas la fiabilite fonctionnelle des projets. Les
commandes listees dans le manifeste et les workflows de CI fournissent les preuves fonctionnelles.
