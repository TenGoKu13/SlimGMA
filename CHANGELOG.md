# Changelog

## 1.2.0 — 2026-08-12

### Refonte complète de l'affichage
- **Navigation latérale** : les onglets empilés laissent place à une barre
  latérale à cinq pages (Source, Options, Avancé, Journal, Rapport). Chaque page
  a son titre, son sous-titre et défile indépendamment si la fenêtre est petite.
- **Barre d'action permanente** : progression, pourcentage, statut,
  chronomètre, fichier courant et boutons Compresser / Annuler / Ouvrir le
  dossier / Ouvrir le rapport restent visibles depuis n'importe quelle page.
- **Bandeau d'étapes** : les 7 étapes du pipeline sont dessinées en pastilles
  numérotées reliées entre elles, cochées au fur et à mesure.
- **Mise en page en cartes** : options regroupées en cartes bordées de largeur
  égale, au lieu d'une colonne unique de cases à cocher.
- **Palette redessinée** : nouveaux thèmes sombre et clair, contraste renforcé,
  boutons, champs, curseurs, ascenseurs et info-bulles entièrement stylés.
- **Zone de dépôt agrandie** avec aperçu du nom de l'addon et de sa
  composition.
- **Compteur d'alertes** : le nombre d'avertissements ou d'erreurs s'affiche
  directement sur l'entrée « Journal » de la barre latérale.
- **Filtres de journal en segments** cliquables et fenêtre « À propos »
  redessinée, avec lien vers le dépôt.
- La page active est mémorisée entre deux lancements.

### Rapport d'analyse dans l'application
- **Le rapport HTML est supprimé.** Il fallait quitter l'app, retrouver un
  fichier sur le disque et l'ouvrir dans un navigateur pour lire l'analyse.
- **Nouvelle page « Rapport »** dans la barre latérale : synthèse (taille
  d'origine, taille finale, réduction, nombre de fichiers), rôles des textures
  en listes dépliables, fichiers inutilisés, doublons exacts et audit qualité.
- Bouton **Copier le rapport** : version texte prête à coller dans un ticket
  ou sur Discord.
- Le rapport suit le changement de langue (les libellés sont traduits à
  l'affichage, plus au moment de la compression).
- L'option « Générer un rapport HTML » et le drapeau CLI `--no-report`
  disparaissent : le rapport est désormais gratuit et toujours disponible.
  `cpm/report.py` est supprimé.

### Nouveautés dans l'application
- **Fenêtre « ✨ Nouveautés »** accessible depuis l'en-tête : les changements de
  chaque version y sont listés en FR/EN, étiquetés *Nouveau* / *Corrigé* /
  *Modifié*, avec lien vers ce fichier.
- Après une mise à jour, un point d'accent signale les versions non encore
  consultées ; il disparaît à l'ouverture de la fenêtre.
- Le contenu vit dans `cpm/changelog.py` (embarqué dans l'exécutable, donc
  lisible hors ligne). Un test refuse toute version publiée sans entrée.

### Corrections
- La ligne de détection des bibliothèques (`PIL : ✗`) n'est plus comptée comme
  une erreur dans le journal ni dans le compteur d'alertes.
- Le filtre du journal et l'état des étapes survivent au changement de thème ou
  de langue.
- L'ascenseur du journal suit désormais le thème au lieu de rester clair.

### Ouverture du code
- Ajout du fichier **LICENSE** (MIT) — la licence était annoncée dans le README
  sans jamais être présente dans le dépôt.
- Ajout de **CONTRIBUTING.md**, des modèles d'issue et de pull request.
- Ajout de **pyproject.toml** (métadonnées, extras, point d'entrée
  `compressez-pm`).

### Style du dépôt
- **Tous les commentaires et docstrings ont été retirés** du code Python
  (~280 lignes) : seuls les noms et les clés de traduction portent
  l'explication. Le shebang est conservé.
- Ajout de `tools/check_no_comments.py`, exécuté par la CI avant les tests pour
  empêcher toute réintroduction.
- Le fichier Lua généré ne contient plus d'en-tête de commentaires.

## 1.1.0 — 2026-07-17

### Corrections critiques
- **Support .gma réparé** : la classe `GMAFile` avait été tronquée lors du
  découpage en package (`load()` incomplet, `save()`/`_read_str`/`_write_str`
  manquants) — toute lecture/écriture de `.gma` plantait. Restaurée et couverte
  par des tests de round-trip.
- **Compression des sons réparée** : `subprocess` n'était plus importé dans
  `compressor.py` (NameError dès que ffmpeg était disponible).
- **« Ouvrir le dossier » réparé sur macOS/Linux** : `subprocess` n'était plus
  importé dans `gui.py`.
- **Fin de la corruption des `.tga`/`.bmp`** : les images non-VTF étaient
  réécrites en PNG sous leur extension d'origine (illisibles par le moteur
  Source). Elles sont désormais réencodées dans leur vrai format
  (TGA RLE / BMP).
- **Lua généré valide** : le hook c_hands appelait `ply:GetBodygroupsString()`,
  méthode inexistante dans l'API GMod (erreur Lua en jeu). Remplacé par
  l'enregistrement standard `player_manager.AddValidHands` +
  `list.Set("PlayerOptionsModel", …)` pour l'icône du menu Sandbox.
- **Les sons ne sont plus renommés** : la conversion forcée `.wav` → `.mp3`
  cassait les chemins codés en dur dans les scripts Lua. Chaque son est
  désormais réencodé dans son format d'origine (mp3 → mp3, ogg → ogg,
  wav → PCM 22 kHz) ; les formats que GMod ne joue pas sont laissés intacts.
- **Plus de fenêtres console fantômes** : les appels ffmpeg utilisent
  `CREATE_NO_WINDOW` sous Windows (l'exe « windowed » faisait clignoter des
  consoles).
- **Fermeture propre pendant une compression** : fermer la fenêtre n'entraîne
  plus d'erreurs `RuntimeError` du thread de travail ; la compression est
  annulée proprement.

### Nouvelles fonctionnalités
- **Fusion des textures identiques (dédup)** : les `.vtf` au contenu strictement
  identique sont fusionnés en une seule copie, les `.vmt` sont réécrits vers
  celle-ci (préférence à la copie déjà référencée). Sans perte.
- **Whitelist GMA** : en sortie `.gma`, les fichiers que GMod refuserait au
  montage (mêmes règles que gmad) sont signalés, avec option de retrait
  automatique — fini les addons qui ne montent pas.
- **`addon.json` auto** : généré s'il manque en sortie dossier (requis par
  gmad pour republier), à partir des métadonnées du `.gma` source.
- **Textures en parallèle** : optimisation multi-thread (jusqu'à 8 threads),
  avec verrou de sécurité autour de VTFLib (état global de la DLL).
- **CLI** : nouveaux drapeaux `--dedup-textures`, `--strip-non-whitelisted`,
  `--no-addon-json`.

### Interface graphique (refonte)
- **Zone de dépôt visuelle** : déposez un dossier/.gma ou cliquez pour
  parcourir ; affiche le nom et la composition de la source
  (textures / sons / modèles).
- **Indicateur d'étapes** : 7 pastilles qui suivent le pipeline en direct
  (en cours = accent, terminé = vert).
- **Info-bulles** sur toutes les options (FR/EN).
- **Journal amélioré** : filtres (tout / avertissements / erreurs), boutons
  Copier et Enregistrer.
- **Récapitulatif graphique** : barres avant/après, durée, accès direct au
  rapport HTML et au dossier de sortie (+ bouton rapport dans la fenêtre
  principale).
- **Sources récentes** (bouton 🕘, persistées), **raccourcis clavier**
  (Ctrl+O source, Ctrl+Entrée compresser, Échap annuler), **chronomètre**.
- Les boutons d'action restent visibles quelle que soit la taille de la
  fenêtre ; onglet Avancé réorganisé en 3 colonnes.
- Les profils rapides activent désormais la dédup automatiquement.

### Qualité
- Suite de tests étendue : 16 → 29 tests (round-trip GMA, whitelist, dédup,
  génération Lua, formats).
- CI : job de tests (pytest) avant le build Windows ; `--collect-all
  tkinterdnd2` pour un drag & drop fonctionnel dans l'exe.

## 1.0.0

Version initiale.
