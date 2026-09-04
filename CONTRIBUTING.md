# Contribuer à Slimgma

Merci de vouloir aider ! Ce projet est un logiciel libre sous licence MIT :
toute contribution est la bienvenue, du signalement de bug à la traduction.

## Signaler un bug

Ouvrez une [issue](https://github.com/TenGoKu13/Compressez-PM-gmod/issues) en
précisant :

- votre système (Windows / Linux / macOS) et la version de l'outil ;
- l'addon concerné (dossier ou `.gma`) et les options cochées ;
- le journal complet — le bouton **💾 Enregistrer** de l'onglet *Journal*
  produit un fichier texte à joindre.

## Proposer un changement

```bash
git clone https://github.com/TenGoKu13/Compressez-PM-gmod.git
cd Compressez-PM-gmod
pip install -r requirements-dev.txt
python -m pytest -q
```

Python 3.10 minimum (le code utilise la syntaxe `X | None`). Les tests
d'interface ont besoin d'un serveur X : sans écran ils se sautent tout seuls,
sous Linux lancez-les avec `xvfb-run -a pytest -q`.

1. Créez une branche depuis `main`.
2. Faites votre modification, avec un test quand c'est possible.
3. Vérifiez que `python -m pytest -q` passe.
4. Ouvrez une pull request en décrivant le problème résolu.

La CI rejoue la suite de tests puis construit l'exécutable Windows à chaque
push : une PR rouge ne sera pas fusionnée.

## Style de code

Ce dépôt applique une règle simple et volontaire : **le code ne contient aucun
commentaire ni docstring**. Les noms de fonctions, de variables et les clés de
traduction doivent porter l'explication à eux seuls. Si un passage a besoin
d'un commentaire pour être compris, c'est le passage qu'il faut réécrire.

Le reste suit la PEP 8 : 4 espaces d'indentation, lignes de moins de 100
caractères, `snake_case` pour les fonctions et variables, `PascalCase` pour les
classes.

## Ajouter une traduction

Toutes les chaînes affichées vivent dans `cpm/i18n.py`, dans le dictionnaire
`STRINGS` (clé → `{'fr': …, 'en': …}`). Une nouvelle langue se résume à ajouter
son code à chaque entrée ; `t()` retombe automatiquement sur le français pour
les clés manquantes.

## Organisation du code

```
slimgma.py         Point d'entrée (CLI + GUI)
cpm/                Package interne (le nom historique est conservé :
│                   le renommer entrerait en conflit avec slimgma.py)
├── deps.py         Dépendances optionnelles (Pillow, srctools, ffmpeg)
├── constants.py    Constantes globales
├── i18n.py         Traductions FR / EN
├── gma.py          Lecteur / écrivain .gma
├── vtf.py          Redimensionnement et recompression DXT des .vtf
├── analysis.py     Moteur d'analyse (pur, testable)
├── compressor.py   Logique de compression
├── gui.py          Interface graphique tkinter
└── cli.py          Point d'entrée ligne de commande
```

`analysis.py` et `vtf.py` sont des modules purs, sans dépendance à tkinter :
c'est là que les nouveaux tests sont les plus faciles à écrire.

## Code de conduite

Le projet suit un [code de conduite](CODE_OF_CONDUCT.md) court : soyez corrects
les uns envers les autres.

## Licence des contributions

En proposant une contribution, vous acceptez qu'elle soit distribuée sous la
[licence MIT](LICENSE) du projet.
