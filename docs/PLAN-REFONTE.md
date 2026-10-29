# Plan de refonte totale

Objectif : une application pro où l'on dépose un modèle 3D (FBX, XPS…) et où
une IA embarquée fait tout le travail jusqu'au playermodel prêt dans Garry's
Mod — avec plusieurs modules (import, compression, réparation, Workshop…).

---

## 1. La nouvelle base technique

| Couche | Choix | Pourquoi |
|---|---|---|
| Application | **Tauri 2** | `.exe` de ~10 Mo (contre ~100 Mo Electron), rapide, installateur + mises à jour automatiques intégrés, beaucoup moins de faux positifs antivirus qu'un PyInstaller |
| Cœur (traitements) | **Rust** | GMA, VTF, compression, analyse : rapide, sûr, multi-thread sans effort |
| Interface | **React + TypeScript + Tailwind** | Interface moderne de niveau pro, animations, thèmes |
| Visionneuse 3D | **three.js** (react-three-fiber) | Voir le modèle en direct, placer/valider les repères, avant/après |
| Import 3D et rig | **Blender en arrière-plan** (piloté par script) | Meilleur importeur FBX/PMX/XPS au monde, gratuit ; aucun code maison ne fera mieux |
| Compilation | **studiomdl** (fourni avec GMod) | L'outil officiel Source |
| IA locale | **llama.cpp** embarqué (Rust) | Tourne hors-ligne, sur GPU ou CPU, sans serveur |

Ce qui est récupéré de SlimGMA : la *logique* (règles de compression, analyse
des dépendances VMT/MDL, déduplication, liste blanche GMA) et **les tests**,
réécrits en Rust. Le code Python est abandonné.

---

## 2. Les modules de l'application

L'accueil propose des tuiles ; chaque module est aussi un « outil » que l'IA
peut utiliser (voir §3).

### 2.1 Import Playermodel (le module phare)
- Formats : FBX, OBJ, GLB/GLTF, XPS, PMX (MMD), VRM, `.blend`
- Squelette : détection et renommage automatique vers **ValveBiped**, ou
  création d'un squelette si le modèle n'en a pas (repères placés par l'IA)
- Poids (skinning), doigts, échelle et orientation corrigées
- Bodygroups, skins, jigglebones (cheveux, vêtements), flexes (visage)
- Bras en vue première personne (c_hands)
- Physique du ragdoll (modèle de collision)
- Matériaux : conversion PBR → Source (VMT/VTF, phong, normal maps)
- Fichier Lua `player_manager`, icône, compilation `studiomdl`
- Aperçu 3D avant/après chaque étape

### 2.2 Compression (SlimGMA)
Tout ce que fait SlimGMA aujourd'hui, en plus rapide, plus le choix des
résolutions guidé par l'IA (le visage garde sa netteté, la semelle non).

### 2.3 Réparation / analyse d'addon
- Textures manquantes (damier violet/noir), chemins cassés, erreurs de
  compilation expliquées en clair
- Fichiers inutiles, doublons, conflits avec d'autres addons installés

### 2.4 Installation et test
- Détection automatique de GMod (Steam), installation dans `addons/`
- Lancement de GMod directement sur le modèle pour tester

### 2.5 Publication Workshop
- Empaquetage `.gma`, miniature générée, envoi au Workshop, mise à jour

### 2.6 Plus tard
- Particules, armes (SWEP), NPC à partir du même playermodel

### Socle commun
- Projets : chaque travail est un projet avec historique et **annulation**
- On travaille toujours sur une copie : l'original n'est jamais modifié
- Journal clair, rapport final, français / anglais

---

## 3. L'IA : un vrai agent, pas un réglage par défaut

### Ce qu'elle est
Un **agent** : un modèle de langage local qui comprend la demande
(« fais-moi un playermodel léger avec les cheveux qui bougent »), **planifie**,
puis **agit lui-même** dans l'app en appelant ses outils, regarde le résultat,
corrige, et recommence jusqu'à ce que ce soit bon.

Chaque fonction de l'app est un outil qu'elle peut appeler :
`importer_modele`, `rendre_vue`, `placer_reperes`, `creer_squelette`,
`renommer_os`, `regler_jigglebone`, `convertir_materiaux`, `compiler`,
`compresser`, `installer_dans_gmod`, `lire_erreurs`, etc.
L'IA peut donc **tout faire** dans l'app, comme un utilisateur expert —
l'interface et l'IA utilisent exactement les mêmes outils.

### Ses « sens »
- **Texte** : modèle de langage local (ex. Qwen 3 / Llama, 4 à 8 milliards
  de paramètres, quantifié) avec appel d'outils
- **Vision** : modèle vision-langage local qui *regarde* les rendus du modèle
  et les textures (« ceci est un visage », « le bras est tordu après le rig »)
- **Spécialistes** : détection de pose (repères menton/coude/genou placés
  automatiquement), classement des textures, choix des os qui doivent bouger

### Les garde-fous
- Elle n'agit que via les outils, sur la copie du projet
- Toute action est visible dans le journal et **annulable**
- Elle demande confirmation avant d'écraser un fichier ou de publier
- Mode « automatique » (elle fait tout) ou « pas à pas » (elle propose, tu
  valides)

### La rendre « à nous »
1. **Version 1** : modèles ouverts existants + une base de connaissances
   GMod/Source intégrée (doc studiomdl, QC, erreurs connues)
2. **Version 2** : **entraînement (fine-tuning LoRA)** sur nos propres
   données — les sessions réussies, les corrections faites à la main, les
   erreurs résolues. C'est là qu'elle devient spécialiste de GMod.
   Entraîner un modèle *à partir de zéro* n'est pas réaliste (des millions
   d'euros de calcul) ; affiner un modèle ouvert l'est, sur un seul GPU.

### Matériel
- Avec carte graphique ≥ 6 Go de VRAM : modèle 7-8B, fluide
- Sans : modèle plus petit sur CPU, plus lent
- Option : brancher une IA en ligne (clé API) pour les PC trop faibles

---

## 4. Feuille de route

| Phase | Contenu | Résultat |
|---|---|---|
| 0 | Squelette Tauri + React, accueil à tuiles, visionneuse 3D, CI, signature | L'app s'ouvre, est signée, se met à jour seule |
| 1 | Compression portée en Rust + tests SlimGMA portés | Remplace SlimGMA |
| 2 | Import playermodel manuel (Blender + studiomdl), étape par étape | Un FBX devient un playermodel jouable |
| 3 | Agent IA local + outils | L'IA fait l'import et la compression seule |
| 4 | Vision + repères automatiques + jigglebones/bodygroups proposés | Zéro clic sur un modèle standard |
| 5 | Réparation, installation/test GMod, Workshop | Chaîne complète jusqu'à la publication |
| 6 | Fine-tuning sur nos données | IA spécialiste GMod |

Chaque phase se termine par une version utilisable : on ne reste jamais des
mois sans rien qui marche.

---

## 5. Questions à trancher

1. **Nom** de l'app (on garde Slimgma ou nouveau nom ?)
2. **Même dépôt** (SlimGMA devient la nouvelle app) ou **nouveau dépôt** ?
3. **Blender obligatoire** : l'installateur le télécharge, ou on demande à
   l'utilisateur de l'avoir ?
4. **IA** : 100 % locale, ou locale + option en ligne ?
5. **Ta config PC** (carte graphique, VRAM) pour calibrer le modèle IA
6. Open source (MIT) comme aujourd'hui, ou fermé ?
