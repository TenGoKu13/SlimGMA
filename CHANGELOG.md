# Changelog

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
