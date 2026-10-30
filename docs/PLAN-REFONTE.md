# Slimgma+ — cahier de construction

Ce document suffit à une nouvelle session Claude Code pour construire
Slimgma+ **de zéro**, dans le dépôt privé `TenGoKu13/SlimGMAPERSO`, sans
avoir lu la conversation qui l'a produit. Il dit quoi construire, avec quoi,
dans quel ordre, et comment savoir qu'une étape est finie.

> **À la session qui reprend :** lis tout ce fichier avant d'écrire une ligne.
> Construis phase par phase (§10). Ne passe à la phase suivante que quand les
> critères « Fini quand » de la phase en cours sont vrais. Dans le doute sur un
> choix produit, demande à l'utilisateur ; pour un choix technique, suis ce
> document.

---

## 0. En une phrase

On dépose un modèle 3D (FBX, XPS, PMX, OBJ…) ou un lien Workshop, et une IA
**locale** fait tout jusqu'au playermodel Garry's Mod compilé, léger, installé
et testable — l'utilisateur peut aussi tout faire à la main, module par module.

## 1. Décisions déjà prises (ne pas rediscuter)

| Sujet | Décision |
|---|---|
| Nom | **Slimgma+** (dépôt `TenGoKu13/SlimGMAPERSO`, privé) |
| Licence | **Code fermé** pour l'instant |
| Base | **Nouvelle base de zéro.** Rien n'est copié de l'ancien code Python : on reprend seulement la *logique* et les cas de test de SlimGMA |
| IA | **100 % locale**, aucune donnée ne quitte le PC (seul réseau : téléchargement unique du modèle IA, et Steam pour le Workshop) |
| Matériel | L'app **détecte** GPU/VRAM/RAM et choisit le modèle IA ; **VRAM + RAM partagées** (§6.3) |
| Blender | **Déjà installé** chez l'utilisateur : l'app le détecte, ne l'installe pas |
| Style | Celui du portfolio `tengoku-ch.vercel.app` (§4), avec ses 5 thèmes |
| Langues | Français par défaut, anglais |
| OS cible | **Windows 10/11 x64** (là où sont GMod et les utilisateurs). Le code reste portable mais on ne teste que Windows |
| Machine de référence | RTX 5080 (16 Go VRAM), 32 Go RAM |

## 2. Pile technique et pourquoi

| Couche | Choix | Pourquoi ce choix et pas un autre |
|---|---|---|
| Coquille d'app | **Tauri 2** | `.exe` ~10 Mo (Electron ~100 Mo), WebView2 déjà dans Windows, installateur NSIS + mise à jour auto intégrés, beaucoup moins de faux positifs antivirus que PyInstaller (le problème Brave de SlimGMA) |
| Cœur | **Rust** (stable) | GMA/VTF/compression rapides et multi-thread (`rayon`), binaire unique, pas d'interpréteur à embarquer |
| Interface | **React 19 + TypeScript + Vite** | L'utilisateur connaît déjà React/Next (tous ses sites) |
| Style | **CSS à variables** (pas Tailwind) | Le portfolio fonctionne déjà comme ça : on recopie les blocs `[data-theme]` tels quels |
| État UI | **Zustand** | Simple, sans boilerplate |
| 3D | **three.js** via `@react-three/fiber` + `@react-three/drei` | Visionneuse, repères, avant/après |
| Animations | **framer-motion** | Déjà utilisé dans `WebApp/mission-interne` |
| Import 3D, rig, export | **Blender** en arrière-plan (`blender -b --python …`) | Meilleur importeur FBX/glTF/OBJ gratuit ; aucun code maison ne fera mieux |
| Compilation | **studiomdl.exe** de GMod (`GarrysMod/bin/studiomdl.exe`) | L'outil officiel |
| Paquet/Workshop | **gmad.exe / gmpublish.exe** de GMod | Les outils officiels |
| IA (texte + vision) | **llama.cpp `llama-server`** lancé en sidecar par Tauri | API compatible OpenAI avec appel d'outils et images, CUDA + Vulkan, répartition GPU/CPU déjà gérée |
| Repères du squelette | **MediaPipe Pose Landmarker** (`@mediapipe/tasks-vision`) dans la WebView | L'utilisateur l'a déjà fait marcher dans `WebApp/psl` (visage) : même technique, version corps |
| Tests | `cargo test` (Rust), **Vitest** (UI), **Playwright** (bout en bout sur l'app) | |

### Crates Rust prévues
`tauri` 2, `serde`/`serde_json`, `tokio`, `rayon`, `thiserror`, `anyhow`
(binaire seulement), `image` (redimensionnement Lanczos3), `texpresso`
(compression DXT1/DXT5), `crc32fast` (GMA), `walkdir`, `sysinfo` (RAM/CPU),
`nvml-wrapper` (VRAM NVIDIA), `windows` (DXGI, VRAM AMD/Intel ; registre),
`keyvalues-parser` (fichiers VDF de Steam), `reqwest` (téléchargement du modèle IA,
API Steam), `sha2` (vérifier les téléchargements), `tracing` (journaux).

Ne pas ajouter d'autre dépendance sans raison écrite dans le commit.

## 3. Architecture

```
SlimGMAPERSO/
├── CLAUDE.md                 consignes pour Claude (§12)
├── PLAN.md                   ce document
├── crates/
│   └── core/                 tout le métier, SANS Tauri : testable seul
│       └── src/
│           ├── gma.rs        lire/écrire .gma
│           ├── vtf.rs        lire/écrire/optimiser .vtf
│           ├── vmt.rs        lire les .vmt (références de textures)
│           ├── mdl.rs        lire les matériaux référencés par un .mdl
│           ├── analysis.rs   graphe de dépendances, doublons, inutilisés
│           ├── compress.rs   le pipeline de compression (ex-SlimGMA)
│           ├── blender.rs    trouver Blender, lancer un script, lire son JSON
│           ├── steam.rs      trouver Steam, GMod, studiomdl, gmad
│           ├── studiomdl.rs  écrire le .qc, compiler, traduire les erreurs
│           ├── workshop.rs   lien Workshop → .gma (steamcmd)
│           ├── hardware.rs   GPU, VRAM, RAM, CPU
│           ├── project.rs    projets, instantanés, annulation
│           └── tools.rs      LE registre d'outils (§5)
├── src-tauri/                l'app : commandes Tauri = outils du registre
│   ├── src/ (main.rs, commands.rs, agent.rs, llm.rs, jobs.rs)
│   ├── resources/blender/    scripts Python exécutés DANS Blender
│   └── binaries/             llama-server (sidecar), steamcmd
├── ui/                       React
│   └── src/
│       ├── styles/ (tokens.css, themes.css, base.css)
│       ├── themes.ts         copie adaptée de portofolio/src/data/themes.js
│       ├── i18n/ (fr.ts, en.ts)
│       ├── pages/ (Accueil, Projet, Compression, Import, Workshop, Reglages)
│       ├── components/ (Viewer3D, Landmarks, StepList, Journal, ChatIA…)
│       └── store/
└── tests/fixtures/           addons de test (repris de SlimGMA/tests)
```

### Règles d'architecture
1. **`crates/core` ne connaît ni Tauri ni l'UI.** Toute fonction métier y vit
   et se teste avec `cargo test`.
2. **Un seul registre d'outils** (`tools.rs`). Chaque action de l'app
   (« compresser », « créer le squelette »…) est un outil avec un nom, une
   description, un schéma JSON d'entrée, une fonction. **Les boutons de
   l'UI et l'IA appellent exactement les mêmes outils.** C'est ce qui permet à
   l'IA de « tout faire dans l'app ».
3. **Travaux longs = jobs** : chaque outil lourd tourne hors du fil UI et
   émet des évènements Tauri `job://progress` (étape, %, fichier courant,
   message) et `job://done`. Annulable.
4. **Projets** : chaque travail est un dossier projet
   (`%APPDATA%/Slimgma+/projets/<id>/`) contenant `source/` (copie
   intouchable de l'original), `travail/`, `instantanes/` et `projet.json`.
   **Avant chaque outil qui modifie `travail/`, on prend un instantané** :
   l'annulation = restaurer le dernier. L'original de l'utilisateur n'est
   jamais modifié, sauf export final explicite.
5. **Tout fichier de config** : `%APPDATA%/Slimgma+/config.json`.

## 4. Design (copié du portfolio)

Source de vérité : `TenGoKu13/WebApp`, fichiers
`portofolio/src/app/themes.css` et `portofolio/src/data/themes.js`.
**Recopier les blocs de variables tels quels** dans `ui/src/styles/themes.css`.

Thème « Défaut » (valeurs relevées sur le site en ligne) :

```css
:root {
  --bg:#0a0b12; --bg-2:#0f111b; --surface:#131626; --surface-2:#1a1e33;
  --line:rgba(165,172,214,.13); --line-strong:rgba(165,172,214,.26);
  --text:#eef0fa; --text-strong:#fff; --text-2:#b8bdd6; --text-3:#8e94b2;
  --accent:#9d9aff; --accent-2:#5ee39a; --fill:#8f8cff; --fill-hover:#a7a5ff;
  --on-fill:#0b0a1f; --ok:#5ee39a; --danger:#ff7a85; --star:#ffc857;
  --radius:20px; --radius-sm:12px; --radius-pill:999px;
  --shadow:0 24px 60px -30px rgba(3,4,8,.9);
  --ring:0 0 0 3px rgba(157,154,255,.45);
  --ease:cubic-bezier(0.16,1,0.3,1);
  --font-display:"Space Grotesk",Inter,system-ui,sans-serif;
  --font-body:Inter,system-ui,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,monospace;
}
```

Autres thèmes à recopier : **GMod** (orange `#ff9c1a`, Oswald, rayons 5px),
**Cyberpunk** (jaune `#fcee0a` + cyan `#00f0ff`, rayons 0, coins coupés via
`--clip`, Rajdhani), **Resident Evil** (rouge `#e05a5a`, Cinzel + Courier
Prime), **Chainsaw Man** (orange `#ff7a5c` + rose `#ff8ccf`, Anton).

Règles (les mêmes que le site) :
- **Aucune couleur en dur** dans les composants : uniquement `var(--…)`.
- Un thème = une entrée dans `themes.ts` + un bloc `[data-theme="…"]`.
- Polices **embarquées** dans l'app (fichiers `.woff2` dans `ui/public/fonts`),
  pas de Google Fonts : l'app doit marcher hors-ligne.
- Halos d'ambiance flous en fond (`.ambient-glow` du site), animations avec
  `--ease`, respecter `prefers-reduced-motion`.
- Fenêtre sans barre Windows (`decorations: false`) avec une barre de titre
  maison aux couleurs du thème.

### Écrans
1. **Accueil** : tuiles (Importer un playermodel · Compresser un addon ·
   Réparer un addon · Depuis le Workshop · Publier) + projets récents +
   barre « Dis à l'IA ce que tu veux faire ».
2. **Projet** : à gauche la liste d'étapes (comme la capture « Étapes » :
   ✓ fait, ● en cours, ○ à venir), au centre la **visionneuse 3D**, à droite
   le **panneau IA** (conversation + actions qu'elle fait, chacune annulable).
   En bas : journal repliable.
3. **Repères** : vue de face du modèle, points déplaçables (menton,
   entrejambe, poignet, coude, genou, épaule, cheville ; côté droit en miroir),
   pré-placés par MediaPipe.
4. **Rapport** : avant/après (taille, textures), problèmes trouvés.
5. **Réglages** : thème, langue, chemins (Blender, GMod), niveau d'IA, mode
   IA (auto / pas à pas).

## 5. Le registre d'outils (contrat UI ⇄ IA)

Chaque outil : `nom`, `description` (écrite pour l'IA, en français clair),
`schéma d'entrée` (JSON Schema), `danger` (`lecture` | `modifie_projet` |
`hors_projet`), `fn`. Les outils `hors_projet` (écrire dans GMod, publier,
écraser l'original) **demandent toujours confirmation** à l'utilisateur,
même en mode automatique.

Liste minimale (la compléter au fil des phases) :

| Outil | Danger | Ce qu'il fait |
|---|---|---|
| `projet_ouvrir` | lecture | Ouvre/crée un projet depuis un fichier, dossier, .gma |
| `addon_analyser` | lecture | Graphe de dépendances, doublons, inutilisés, liste blanche |
| `addon_compresser` | modifie_projet | Pipeline de compression (§7.2) avec options |
| `modele_importer` | modifie_projet | Blender : importe FBX/OBJ/glTF/PMX/XPS, normalise échelle et axes |
| `modele_inspecter` | lecture | Os, meshes, matériaux, nombre de triangles, présence d'un squelette |
| `vue_rendre` | lecture | Rend une image du modèle (face/profil/3-4) → renvoyée à l'IA (vision) |
| `reperes_detecter` | lecture | MediaPipe sur le rendu de face → positions des repères |
| `squelette_creer` | modifie_projet | Crée un squelette ValveBiped à partir des repères + poids automatiques |
| `os_renommer` | modifie_projet | Fait correspondre un squelette existant à ValveBiped |
| `jigglebone_regler` | modifie_projet | Ajoute/ajuste un os à ressort (cheveux, vêtements) |
| `bodygroup_definir` | modifie_projet | Regroupe des meshes en bodygroups |
| `materiaux_convertir` | modifie_projet | PBR/PNG → VMT/VTF Source |
| `texture_optimiser` | modifie_projet | Redimensionne/compresse une texture précise |
| `qc_ecrire` | modifie_projet | Génère le .qc |
| `compiler` | modifie_projet | studiomdl → .mdl, erreurs traduites en clair |
| `lua_playermodel_ecrire` | modifie_projet | Fichier `player_manager.AddValidModel` |
| `gmod_installer` | hors_projet | Copie l'addon dans `garrysmod/addons/` |
| `gmod_lancer` | hors_projet | Lance GMod sur une map de test |
| `workshop_telecharger` | lecture | Lien Workshop → .gma ouvert en projet |
| `workshop_publier` | hors_projet | gmad + gmpublish |
| `instantane_annuler` | modifie_projet | Revient à l'instantané précédent |

## 6. L'IA

### 6.1 Ce qu'elle est
Un **agent** : modèle de langage local avec appel d'outils. Boucle :
1. reçoit la demande (« fais-moi un playermodel léger, cheveux qui bougent »)
   + l'état du projet (résumé de `modele_inspecter`, étapes faites) ;
2. planifie et l'écrit à l'utilisateur en 3-6 lignes ;
3. appelle un outil, lit le résultat (texte + image si `vue_rendre`) ;
4. vérifie (rend une vue, relit les erreurs), corrige, recommence ;
5. s'arrête quand c'est fini, ou après **40 appels d'outils** maximum, ou si
   l'utilisateur l'arrête ; résume ce qu'elle a fait.

Modes : **Automatique** (elle enchaîne) ou **Pas à pas** (chaque outil
`modifie_projet` attend un clic « OK »). Les outils `hors_projet` attendent
toujours un clic.

Le prompt système (dans `src-tauri/src/agent.rs`) contient : son rôle, les
règles (agir seulement via les outils, ne jamais inventer un résultat,
annoncer avant d'agir), un **mémo GMod/Source** (`resources/ia/memo.md` :
noms des os ValveBiped, structure d'un .qc, erreurs studiomdl fréquentes et
leurs causes, limites — 128 os, 32 matériaux par modèle conseillés, etc.).

### 6.2 Modèles
Format **GGUF**, téléchargés au premier lancement depuis Hugging Face dans
`%APPDATA%/Slimgma+/modeles/`, vérifiés par SHA-256, reprise du
téléchargement si coupé. Le choix exact des modèles est à faire en phase 3
en testant l'appel d'outils sur nos tâches ; candidats : famille **Qwen3**
(texte, bon appel d'outils) et **Qwen2.5-VL / Qwen3-VL** (vision, via
`--mmproj` de llama-server).

### 6.3 Détection du matériel et répartition VRAM + RAM
Au premier lancement (et bouton « Re-détecter ») :
1. `hardware.rs` lit : GPU(s), **VRAM totale et libre** (NVML pour NVIDIA,
   DXGI `QueryVideoMemoryInfo` sinon), RAM totale/libre, nombre de cœurs.
2. Choix du niveau :

| VRAM | Modèle texte visé | Vision |
|---|---|---|
| aucune / < 4 Go | ~1-2B, sur CPU | désactivée par défaut |
| 4-6 Go | ~4B | petite, chargée à la demande |
| 8-12 Go | ~8B | oui |
| ≥ 16 Go | ~14B, ou MoE ~30B (A3B) en partage VRAM+RAM | oui, chargée en même temps |

3. **Partage VRAM + RAM** : llama-server découpe le modèle en couches.
   L'app calcule combien de couches tiennent dans la VRAM libre **moins une
   marge de 2 Go** (Blender et l'affichage en ont besoin) et passe
   `--n-gpu-layers N` ; le reste va en RAM. Pour un modèle MoE, garder les
   couches d'attention sur GPU et envoyer les « experts » en RAM
   (`--n-cpu-moe` / `--override-tensor`, selon la version de llama.cpp
   embarquée). Garder aussi une marge RAM de 4 Go.
4. Le niveau reste modifiable dans Réglages.

Les seuils ci-dessus sont des **estimations à recaler** en phase 3 sur la
machine de référence.

### 6.4 Version 2 : la rendre spécialiste (phase 6)
Chaque session réussie est enregistrée (demande, appels d'outils, corrections
faites à la main par l'utilisateur) dans `donnees-ia/` **uniquement si
l'utilisateur l'a activé**. Ces données servent à **affiner (LoRA)** le
modèle texte sur la RTX 5080 (Unsloth ou axolotl, hors de l'app), puis on
livre l'adaptateur LoRA avec l'app. On n'entraîne **jamais** un modèle de
zéro : hors de portée.

## 7. Les modules en détail

### 7.1 Trouver les outils externes (`steam.rs`, `blender.rs`)
- **Steam** : registre `HKCU\Software\Valve\Steam\SteamPath`, puis
  `steamapps/libraryfolders.vdf` pour toutes les bibliothèques ; GMod =
  appid **4000** (`steamapps/common/GarrysMod`).
- **Outils GMod** : `GarrysMod/bin/studiomdl.exe`, `gmad.exe`,
  `gmpublish.exe` (vérifier qu'ils existent, sinon le dire clairement).
- **Blender** : `HKLM\SOFTWARE\BlenderFoundation`, `C:\Program Files\Blender
  Foundation\Blender */blender.exe` (prendre la plus récente), Steam (appid
  365670), sinon demander le chemin. Version minimale **4.2**.
- Tout chemin trouvé est montré dans Réglages et modifiable.

### 7.2 Compression (portage de SlimGMA)
Lire dans **`TenGoKu13/SlimGMA`** : `cpm/compressor.py` (les 7 étapes),
`cpm/analysis.py`, `cpm/vtf.py`, `cpm/gma.py`, `cpm/constants.py`, et
**tous les tests de `tests/`** : ils deviennent les tests Rust (mêmes
entrées, mêmes résultats attendus). Comportements à garder :
- retirer les c_hands quand demandé (motifs dans `constants.py`), les
  fichiers inutiles (`.psd`, `.txt`…), les textures non référencées ;
- dédupliquer les textures identiques et réécrire les `.vmt` ;
- VTF : redimensionner à la résolution max, DXT1 sans alpha / DXT5 avec
  alpha, garder les cubemaps et les drapeaux, régénérer les mipmaps ;
- respecter la liste blanche GMA ;
- compression sur place ou vers un dossier de sortie ;
- profils Équilibré / Qualité / Minimal / Partage (valeurs dans
  `cpm/gui.py`, `App.PRESETS`).
Ajout : l'IA peut choisir la résolution **par texture** (visage net, semelle
réduite) grâce à `vue_rendre` + le graphe de dépendances.

### 7.3 Import playermodel (Blender)
Chaque étape = un script dans `src-tauri/resources/blender/`, lancé par
`blender -b <fichier.blend> --python <script>.py -- <args JSON>`, qui écrit
son résultat en JSON sur la dernière ligne de stdout (`@@RESULT@@{…}`).
1. **Import** : FBX/OBJ/glTF natifs. **PMX** via l'addon `mmd_tools`,
   **XPS** via `XNALaraMesh` : si absents, l'app propose de les installer
   dans le dossier d'addons de Blender de l'utilisateur.
2. **Normaliser** : échelle (taille humaine ≈ 72 unités Source), axe Z
   en haut, appliquer les transformations, fusionner les doublons de
   sommets.
3. **Squelette** : si le modèle a des os → `os_renommer` vers ValveBiped
   (table de correspondance + comparaison de noms : Mixamo, MMD, XPS, VRM) ;
   sinon → rendu de face → MediaPipe → écran Repères → `squelette_creer`
   (squelette ValveBiped posé sur les repères, poids automatiques de Blender).
4. **Bodygroups / jigglebones / flexes** proposés par l'IA, validés par
   l'utilisateur.
5. **Matériaux** : textures → VTF (même code que 7.2), `.vmt` générés
   (`VertexLitGeneric`, phong si carte de spéculaire).
6. **Export SMD** : écrire **notre propre exporteur SMD** (format texte
   simple) dans le script Blender, pour ne pas dépendre de l'addon Blender
   Source Tools. Physique : mesh simplifié par os principal.
7. **QC + compilation** : `.qc` généré (modèle, matériaux, `$includemodel`
   des animations `m_anm.mdl`/`f_anm.mdl`, `$definebone`, jigglebones,
   bodygroups), `studiomdl -game <GarrysMod/garrysmod> <fichier.qc>`.
   Lire la sortie, traduire les erreurs connues en français clair.
8. **Lua** : `lua/autorun/<nom>.lua` avec `player_manager.AddValidModel` et
   `AddValidHands` si bras c_hands générés.

### 7.4 Workshop
Reprendre la logique de **`TenGoKu13/WebApp`, dossier `support/workshop/`**
(`serveur.py`, `gma.py`) : identifiant tiré du lien → API Steam
`ISteamRemoteStorage/GetPublishedFileDetails` (refuser si pas GMod, privé,
> 300 Mo) → `steamcmd +login anonymous +workshop_download_item 4000 <id>`
(steamcmd téléchargé au premier usage) → ancien format LZMA géré → ouvrir le
`.gma` comme projet.

### 7.5 Envoyer vers le serveur de l'utilisateur
Dépôt **`TenGoKu13/gmod`** : les skins sont déclarés dans
`serveur/lua/autorun/…` (`CustomSkins.SkinPacks`, `CustomSkins.WorkshopIDs`,
voir `sv_customskins.lua`) et le contenu lourd vit dans l'addon Workshop
« Server Content ». Module (phase 5) : ajouter le modèle à « Server
Content », publier la mise à jour, et produire la ligne de config à coller
dans `SkinPacks`. **Ne jamais écrire de SteamID dans un addon publié.**

### 7.6 Réparation
Textures manquantes (chemins de `.vmt`/`.mdl` sans fichier), fichiers hors
liste blanche, doublons, conflits de chemin avec les autres addons installés
dans `garrysmod/addons`.

## 8. Distribution
- Installateur **NSIS** de Tauri, mise à jour automatique (`tauri-plugin-updater`)
  depuis les releases GitHub du dépôt privé (ou un stockage dédié, à décider
  avec l'utilisateur car un dépôt privé n'est pas lisible sans jeton).
- **Signature de code** : reprendre la démarche SignPath de SlimGMA
  (`docs/signing.md` de `TenGoKu13/SlimGMA`). Attention : le programme
  gratuit SignPath est réservé à l'**open source** ; en code fermé il faudra
  un certificat payant (à dire à l'utilisateur au moment de la phase 0).
- `llama-server` : embarquer la build **CUDA 12.8+** (obligatoire pour les
  RTX 50) et la build **Vulkan** (AMD/Intel/CPU) ; choisir au lancement.
- Les modèles IA ne sont **pas** dans l'installateur (plusieurs Go).

## 9. Qualité
- `cargo fmt`, `cargo clippy -D warnings`, `cargo test` ; `npm run lint`,
  `npm test`, `npm run build`.
- CI GitHub Actions sur `windows-latest` : les commandes ci-dessus + build
  Tauri à chaque push ; release sur tag `v*`.
- Fixtures : copier l'addon de test de `SlimGMA/tests` dans `tests/fixtures`.
- Tests bout en bout Playwright sur les parcours : compresser un addon,
  importer un FBX de test, annuler une étape.
- Les scripts Blender ont leurs propres tests (lancés seulement si Blender
  est présent sur la machine de CI : sinon ignorés avec un message).

## 10. Feuille de route (chaque phase livre une version utilisable)

### Phase 0 — Fondations
- Dépôt, `CLAUDE.md` (§12), Tauri 2 + React + Vite + TS, `crates/core`.
- Thèmes (§4) avec sélecteur, polices embarquées, barre de titre maison,
  FR/EN, écran d'accueil à tuiles (tuiles inactives = « bientôt »).
- Visionneuse 3D qui affiche un `.glb` de test.
- Détection Steam/GMod/Blender/matériel affichée dans Réglages.
- CI + build de l'installateur.

**Fini quand** : l'installateur s'installe sur Windows, l'app s'ouvre, les
5 thèmes changent toute l'interface, Réglages montre les chemins et la
VRAM détectés, la CI est verte.

### Phase 1 — Compression (remplace SlimGMA)
- `gma.rs`, `vtf.rs`, `vmt.rs`, `mdl.rs`, `analysis.rs`, `compress.rs`.
- Tous les tests de SlimGMA portés et verts.
- Module Compression complet dans l'UI (profils, progression, rapport).

**Fini quand** : sur l'addon de test, Slimgma+ obtient une taille finale
≤ celle de SlimGMA 1.3.0 avec le même profil, l'addon se charge dans GMod
sans texture manquante.

### Phase 2 — Import playermodel manuel
- Scripts Blender (§7.3), écran Repères (placement à la main d'abord),
  compilation, Lua, installation dans GMod, instantanés/annulation.

**Fini quand** : un FBX Mixamo et un modèle **sans squelette** deviennent
des playermodels sélectionnables et animés en jeu.

### Phase 3 — Agent IA
- Sidecar llama-server, téléchargement des modèles, niveaux (§6.3), boucle
  d'agent, panneau IA, modes auto / pas à pas, mémo GMod.
- Choisir et figer les modèles GGUF après essais.

**Fini quand** : la phrase « compresse cet addon au maximum sans abîmer le
visage » et « fais un playermodel de ce FBX » aboutissent sans clic (sauf
confirmations `hors_projet`) sur la machine de référence.

### Phase 4 — Vision et automatisation
- MediaPipe pour pré-placer les repères, `vue_rendre` branché sur la vision,
  propositions de jigglebones/bodygroups, choix de résolution par texture.

**Fini quand** : un modèle sans squelette passe de l'import au jeu en mode
automatique, l'utilisateur n'ayant qu'à valider les repères.

### Phase 5 — Workshop, réparation, serveur
- §7.4, §7.5, §7.6, publication Workshop.

### Phase 6 — IA spécialiste
- Collecte opt-in, affinage LoRA, livraison de l'adaptateur.

## 11. Risques connus
| Risque | Parade |
|---|---|
| MediaPipe est entraîné sur de vraies personnes, pas des personnages 3D en T-pose | Toujours montrer l'écran Repères pour validation ; rendre en éclairage neutre, fond uni |
| Modèles locaux faibles en appel d'outils sur les petits niveaux | Outils peu nombreux et bien décrits ; sur < 8 Go, mode pas à pas par défaut |
| Addons Blender PMX/XPS absents | Les installer avec l'accord de l'utilisateur ; FBX/OBJ/glTF marchent sans |
| Antivirus / SmartScreen | Tauri + signature (§8) |
| studiomdl : erreurs obscures | Table d'erreurs connues dans le mémo IA + traduction dans l'UI |

## 12. `CLAUDE.md` à créer en phase 0 (contenu)
- Ce dépôt est **privé et fermé** : ne jamais le rendre public ni copier son
  code dans un dépôt public.
- Lire `PLAN.md` avant toute tâche ; une tâche = une phase ou une partie de phase.
- Métier dans `crates/core`, jamais dans `src-tauri` ni `ui`.
- Toute nouvelle action = un outil du registre (§5), utilisé par l'UI **et** l'IA.
- Aucune couleur en dur dans l'UI ; tout passe par les variables de thème.
- Textes d'interface en français et en anglais (`ui/src/i18n`).
- Avant de pousser : `cargo fmt`, `cargo clippy`, `cargo test`, `npm test`,
  `npm run build`.
- L'original de l'utilisateur n'est jamais modifié sans confirmation.
- L'IA n'envoie rien sur Internet.

## 13. Dépôts de référence de l'utilisateur
| Dépôt | À lire pour |
|---|---|
| `TenGoKu13/SlimGMA` (public) | Logique et tests de compression (§7.2), signature (§8) |
| `TenGoKu13/WebApp` (privé) | `portofolio/` : thèmes (§4) ; `support/workshop/` : Workshop (§7.4) ; `psl/` : MediaPipe ; `.claude/skills/` : skills design à copier |
| `TenGoKu13/gmod` (privé) | Serveur de l'utilisateur, système de skins (§7.5) |
