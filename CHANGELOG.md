# Changelog

## 1.3.0 — 2026-09-08

### Compresser l'addon sur place
- Nouvelle option **« Remplacer l'addon d'origine »** : plus besoin de choisir
  un dossier de destination, l'addon source est remplacé par sa version
  compressée. En ligne de commande, `--in-place` (le chemin de sortie devient
  facultatif).
- **Les fichiers retirés disparaissent vraiment.** L'écriture en sortie dossier
  se contentait d'écrire les fichiers conservés, sans supprimer ceux que le
  compresseur avait retirés : écrire naïvement sur la source aurait laissé les
  C-Hands et les `.txt` en place, et l'addon n'aurait pas maigri.
- **Écriture par échange atomique** : le nouveau contenu est construit dans un
  dossier voisin, puis l'ancien est mis de côté et le nouveau prend sa place.
  Si quoi que ce soit échoue, l'ancien est remis — vérifié par un test qui
  provoque une panne au milieu de l'échange et compare les octets.
- **Confirmation obligatoire** dans l'interface avant d'écraser, indiquant
  clairement si une sauvegarde sera conservée ou non.
- Cochez **« Sauvegarder l'original »** pour garder une copie horodatée à côté.
- Compatible avec le mode lot : chaque addon du dossier est remplacé chez lui.
- Le mode aperçu ne touche à rien, comme partout ailleurs.
- **Message clair si le dossier est verrouillé** — le cas le plus probable sous
  Windows, quand l'explorateur, un antivirus ou Garry's Mod garde le dossier
  ouvert. L'outil dit quoi fermer et rappelle que l'addon n'a pas été touché,
  au lieu d'afficher `[Errno 13]` et un traceback Python. Si l'original se
  retrouvait bloqué sous un nom temporaire, son chemin exact est indiqué.
- Le journal n'affiche plus le dossier de transit, qui laissait croire que la
  sortie avait été écrite ailleurs.

## 1.2.1 — 2026-09-06

### L'outil s'appelle désormais Slimgma
- « Compressez PM GMod » était long, difficile à retenir et contenait une
  marque tierce. **Slimgma** (« slim » + `.gma`) dit ce que fait l'outil, sur
  le format que ses utilisateurs manipulent, et se comprend en français comme
  en anglais.
- L'exécutable devient `Slimgma.exe`, le script d'entrée `slimgma.py`, la
  commande `slimgma`, et le paquet Python `slimgma`.
- **Les préférences existantes sont migrées** : au premier lancement, l'app lit
  l'ancien dossier `CompressezPMGMod/` s'il existe et réécrit dans `Slimgma/`.
  Thème, langue, sources récentes et historique de nouveautés sont conservés.
- Le package interne reste `cpm/` : le renommer entrerait en conflit avec
  `slimgma.py` et obligerait à modifier la cible PyInstaller, non testable ici.

### Correction critique
- **Les textures sortaient entièrement noires.** srctools décode les pixels
  d'un `.vtf` à la demande : `VTF.read()` ne lit que l'en-tête, et il faut
  appeler `Frame.load()` avant de toucher aux pixels. `cpm/vtf.py` ne le
  faisait pas, redimensionnait donc un tampon vide et réencodait du noir. Tout
  addon compressé avec la 1.2.0 avait ses textures détruites — en jeu, le
  modèle apparaissait tout noir.
- **Pourquoi les tests ne l'ont pas vu** : ils vérifiaient les dimensions, le
  format, le nombre de mipmaps et la taille du fichier — jamais le contenu.
  Une texture entièrement noire produit un DXT1 parfaitement valide et bien
  plus léger, donc toutes les assertions passaient.
- Six tests ajoutés qui comparent les **pixels** avant/après : downscale,
  conversion de format, chaque format source, canal alpha, mipmaps générés, et
  sortie du compresseur. Vérifié : en réintroduisant le bug, cinq d'entre eux
  échouent.

### Deux défauts de la même famille, trouvés en cherchant celui-ci
- **La réflectivité de l'en-tête était écrasée à zéro.** Reconstruire le `.vtf`
  perdait `reflectivity` et `bumpmap_scale`, dont Source se sert pour
  l'éclairage. Ces champs sont désormais reportés, avec la miniature basse
  résolution et les métadonnées de sprite sheet.
- **Garde-fou à l'écriture** : avant d'enregistrer, l'outil compare la texture
  d'origine et la version redimensionnée. Si la source a de la couleur et que
  le résultat n'en a plus, il refuse et conserve l'original. Toute erreur
  pendant cette vérification conduit aussi à conserver l'original. Un bug de
  ce genre ne peut plus produire un fichier détruit — au pire, une texture non
  optimisée.

**Si vous avez compressé un addon avec la 1.2.0, repartez de l'original.**
Les fichiers produits ne sont pas récupérables.

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

### Textures .vtf : la recompression DXT fonctionne enfin
- **La dépendance `vtflib` n'existait pas sur PyPI.** `pip install vtflib`
  échoue — donc `VTFLIB_AVAILABLE` était toujours faux, l'option
  « Recompresser les textures en DXT » ne faisait **rien**, et les `.vtf`
  n'étaient réduits que par troncature de mipmaps.
- Remplacée par **`srctools`**, qui lit et écrit réellement le format VTF (DXT
  compilé, aucune DLL externe). Ajoutée à `requirements.txt`, à `pyproject.toml`
  et à l'exécutable Windows.
- Nouveau module `cpm/vtf.py` : rééchantillonnage bilinéaire par halvings
  successifs, régénération de la chaîne de mipmaps, et conversion vers **DXT1
  ou DXT5 selon la transparence réellement utilisée** (une texture opaque ne
  part plus en DXT5, deux fois trop lourd).
- Cubemaps, textures multi-frames et fichiers illisibles sont laissés
  intacts. La troncature de mipmaps reste le repli si `srctools` est absent.
- Mesuré sur un addon de test de 26,7 Mo : **1,7 Mo en sortie (-93,6 %)**.

### Mode batch
- **Un batch réussi s'affichait comme un échec** : `_run_batch()` ne
  renseignait ni `final_size`, ni `reduction`, ni le rapport, si bien que la
  GUI montrait une pastille rouge, aucun récapitulatif et les boutons de fin
  désactivés — alors que les addons étaient bien compressés.
- Les totaux sont désormais agrégés et le rapport liste chaque addon traité
  avec sa taille finale et son gain.

### Ligne de commande
- **`--no-chands` et `--no-unused` faisaient l'inverse de leur nom** : ils
  *activaient* la suppression. La CLI ne supprimait donc rien par défaut, là où
  la GUI supprimait les deux — même addon, deux résultats.
- Les défauts s'alignent sur la GUI : C-Hands et fichiers inutiles sont
  supprimés par défaut. **`--keep-chands` et `--keep-unused`** désactivent.
- Les anciens drapeaux restent acceptés et affichent un avertissement de
  dépréciation. Un script qui utilisait `--no-chands` obtient le même résultat
  qu'avant ; un script qui ne l'utilisait **pas** verra désormais les C-Hands
  supprimés.
- `--gen-lua` supprimé : `store_true` avec `default=True`, il ne pouvait rien
  faire et doublonnait `--no-lua`.

### Tests de l'interface
- La GUI (~2 000 lignes) n'était couverte par **aucun test**. Ajout de
  `tests/test_gui.py` : construction des cinq pages, bascule thème/langue avec
  conservation de l'état, profils, compression complète, mode batch, rapport,
  changelog. Ils se sautent sans serveur X et tournent sous `xvfb-run` en CI.
- Ajout de `tests/test_vtf.py` pour le pipeline VTF.
- Suite : 29 → 57 tests.

### Corrections
- Le récapitulatif de fin en mode aperçu utilise la fenêtre redessinée au lieu
  d'une boîte de dialogue système.
- La ligne de détection des bibliothèques (`PIL : ✗`) n'est plus comptée comme
  une erreur dans le journal ni dans le compteur d'alertes.
- Le filtre du journal et l'état des étapes survivent au changement de thème ou
  de langue.
- L'ascenseur du journal suit désormais le thème au lieu de rester clair.

### Ouverture du code
- Ajout du fichier **LICENSE** (MIT) — la licence était annoncée dans le README
  sans jamais être présente dans le dépôt.
- Ajout de **CONTRIBUTING.md**, **CODE_OF_CONDUCT.md**, des modèles d'issue et
  de pull request, et de **dependabot.yml**.
- Ajout de **pyproject.toml** (métadonnées, extras, point d'entrée
  `compressez-pm`).
- **Publication automatique des releases** : pousser un tag `v*` construit
  l'exécutable Windows, vérifie qu'il démarre, extrait les notes de ce fichier
  et publie le tout en GitHub Release. Avant, l'`.exe` restait un artefact
  Actions expirant au bout de 90 jours et inaccessible sans compte GitHub.
- **README refait** pour les moddeurs plutôt que pour les développeurs :
  captures d'écran, parcours en trois étapes, FAQ, et détails techniques
  repliés dans une section dépliable.
- `requires-python` corrigé de `>=3.9` à `>=3.10` (le code utilise `X | None`,
  évalué à l'import) et CI étendue à 3.10 / 3.11 / 3.12.

### Performance
- **Mode taille cible 5× plus rapide** sur les addons sans images non-VTF : le
  curseur de qualité n'affecte que les `.png`/`.jpg`/`.tga`, l'outil essayait
  malgré tout cinq qualités différentes par résolution — cinq passes de
  recompression identiques. Les variantes de qualité ne sont plus tentées
  quand l'addon n'a que des `.vtf`.

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
