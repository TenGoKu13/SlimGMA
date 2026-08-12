# Compressez PM GMod

[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![Tests & Build](https://github.com/TenGoKu13/Compressez-PM-gmod/actions/workflows/build.yml/badge.svg)](https://github.com/TenGoKu13/Compressez-PM-gmod/actions/workflows/build.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PRs bienvenues](https://img.shields.io/badge/PRs-bienvenues-brightgreen.svg)](CONTRIBUTING.md)

Outil de compression d'addons **Playermodel** pour Garry's Mod.
Disponible en **interface graphique** (GUI) et en **ligne de commande** (CLI).

**Logiciel libre sous licence [MIT](LICENSE)** — utilisez-le, modifiez-le,
redistribuez-le, y compris commercialement.

---

## Interface

La v1.2 remplace l'ancienne fenêtre à onglets empilés par une navigation
latérale à quatre pages, un bandeau d'étapes et une barre d'action fixe :

```
┌────────────┬──────────────────────────────────────────────┐
│  🗜 CPM    │  Source                                      │
│            │  ┌────────────────────────────────────────┐  │
│  ▸ Source  │  │      Déposez un addon ou un .gma       │  │
│    Options │  └────────────────────────────────────────┘  │
│    Avancé  │  Destination : …                             │
│    Journal │                                              │
│  ────────  ├──────────────────────────────────────────────┤
│  Pillow ●  │  ①─②─③─④─⑤─⑥─⑦   Textures                    │
│  vtflib ●  │  ▬▬▬▬▬▬▬▬▬▬▬ 58%      [⏹ Annuler] [▶ Compresser] │
└────────────┴──────────────────────────────────────────────┘
```

- **Source** — zone de dépôt, historique, type d'entrée et de sortie
- **Options** — profils rapides, nettoyage, textures, script Lua
- **Avancé** — sons, archive, sécurité, taille cible, compatibilité GMA
- **Journal** — trace filtrable, avec compteur d'avertissements dans le menu

L'en-tête donne accès au thème, à la langue, à « À propos » et à la fenêtre
**✨ Nouveautés**, qui liste les changements de chaque version et signale d'un
point ceux que vous n'avez pas encore lus.

Le bandeau d'étapes 1→7, la progression, le chronomètre et les boutons
d'action restent visibles depuis n'importe quelle page.

---

## Fonctionnalités

| Option | Description |
|--------|-------------|
| **Supprimer les C-Hands** | Retire les modèles de bras à la 1ʳᵉ personne (`c_arms`, `c_*`) |
| **Supprimer les fichiers inutiles** | Supprime `.txt`, `.md`, `.pdf`, `.psd`, `.log`, etc. |
| **Vérification des matériaux** | Détecte les textures référencées par les `.vmt` mais absentes de l'addon |
| **Rôle des textures** | Classe chaque texture par usage (tête, casque, corps, yeux, mains, cartes normales…) |
| **Graphe de dépendances** | Lit les `.mdl` pour relier modèles → `.vmt` → `.vtf` et repérer les orphelins |
| **Supprimer les textures inutilisées** | Repère les `.vtf`/`.vmt` orphelins et peut les supprimer |
| **Fusion des doublons (dédup)** | Fusionne les textures identiques en une copie unique et réécrit les `.vmt` — sans perte |
| **Whitelist GMA** | Signale (ou retire) les fichiers que GMod refuserait au montage du `.gma` |
| **Audit qualité** | Repère les textures surdimensionnées, non compressées ou non puissance de 2 |
| **Recompression DXT** | Convertit les `.vtf` RGBA/BGR volumineux en DXT (avec vtflib) |
| **Rapport HTML** | Récapitulatif visuel autonome (rôles, orphelins, doublons, audit) |
| **Optimiser les textures** | Redimensionne et recompresse `.vtf`, `.png`, `.jpg`, `.tga` — en parallèle (multi-thread) |
| **Résolution max des textures** | 256 / 512 / 1024 / 2048 / Aucune limite |
| **Qualité des textures** | Curseur de 10 % à 100 % |
| **Taille cible** | Ajuste automatiquement résolution/qualité pour atteindre une taille max donnée |
| **Compresser les sons** | Ré-encode chaque son dans son format d'origine via ffmpeg (les chemins Lua restent valides) |
| **`addon.json` automatique** | Généré s'il manque en sortie dossier (requis par gmad) |
| **Niveau de compression ZIP** | 1 (rapide) à 9 (maximum) |
| **Mode aperçu (dry-run)** | Affiche les changements sans rien écrire sur le disque |
| **Sauvegarde de l'original** | Crée une copie horodatée de la sortie avant écrasement |
| **Mode batch** | Traite plusieurs addons (sous-dossiers/.gma) en une seule fois |
| **Zone de dépôt** | Déposez un dossier ou un `.gma` (ou cliquez) — composition affichée (textures/sons/modèles) |
| **Bandeau d'étapes** | Pipeline 1→7 avec état en direct, chronomètre et fichier courant |
| **Sources récentes** | Historique persistant des derniers addons traités |
| **Raccourcis clavier** | Ctrl+O source • Ctrl+Entrée compresser • Échap annuler |
| **Info-bulles** | Explication au survol de chaque option (FR/EN) |
| **Thème clair / sombre** | Bascule depuis l'en-tête de la GUI |
| **Multilingue FR / EN** | Bascule la langue de l'interface et des messages |
| **Récapitulatif de fin** | Barres avant/après, durée, accès direct au dossier et au rapport HTML |
| **Nouveautés intégrées** | Fenêtre « ✨ Nouveautés » listant les changements de chaque version (FR/EN), signalées après une mise à jour |
| **Tolérance aux fichiers corrompus** | Une texture illisible est ignorée avec un avertissement, sans interrompre la compression |

### Formats supportés
- **Entrée** : dossier addon ou fichier `.gma`
- **Sortie** : dossier, fichier `.gma`, ou archive `.zip`

---

## Installation

```bash
git clone https://github.com/TenGoKu13/Compressez-PM-gmod.git
cd Compressez-PM-gmod
pip install -r requirements.txt
```

> **Optionnel – compression des sons** : installer [ffmpeg](https://ffmpeg.org/download.html) dans le PATH
>
> Les textures `.vtf` et le glisser-déposer fonctionnent directement, sans dépendance supplémentaire à installer.

---

## Utilisation

### Interface graphique (recommandée)

```bash
python compressez_pm.py
```

### Ligne de commande

```bash
python compressez_pm.py mon_addon/ sortie/

python compressez_pm.py mon_addon.gma sortie.gma --no-chands --quality 70

python compressez_pm.py mon_addon/ sortie.zip --format zip --max-res 512

python compressez_pm.py mon_addon/ sortie/ --compress-sounds --sound-quality 96k
```

#### Toutes les options CLI

```
source output               Chemins source et sortie
--format {folder,gma,zip}   Format de sortie (défaut : folder)
--no-chands                 Supprimer les C-Hands
--no-unused                 Supprimer les fichiers inutiles
--no-textures               Ne pas optimiser les textures
--quality 10-100            Qualité des textures (défaut : 85)
--max-res 256|512|1024|2048 Résolution max (défaut : 1024)
--compress-sounds           Compresser les sons (nécessite ffmpeg)
--sound-quality BITRATE     64k / 96k / 128k / 192k / 320k
--zip-level 1-9             Niveau ZIP (défaut : 6)
--no-lua                    Ne pas générer le fichier Lua PM
--no-lua-chands             Ne pas inclure les C-Hands dans le Lua généré
--no-check-materials        Ne pas vérifier les matériaux/textures manquants
--remove-unused-textures    Supprimer les .vtf référencés par aucun .vmt
--dedup-textures            Fusionner les textures identiques (réécrit les .vmt)
--strip-non-whitelisted     Retirer les fichiers refusés par la whitelist GMA
--no-convert-uncompressed   Ne pas recompresser les .vtf non compressés en DXT
--no-addon-json             Ne pas générer addon.json s'il manque (sortie dossier)
--no-report                 Ne pas générer le rapport HTML d'analyse
--target-size MO            Taille cible en Mo (ajuste résolution/qualité automatiquement)
--dry-run                   Mode aperçu : affiche les changements sans rien écrire
--backup                    Sauvegarde l'original avant écrasement
--batch                     Traite chaque sous-dossier/.gma de la source comme un addon distinct
--lang {fr,en}              Langue des messages (défaut : fr)
```

---

## Dépendances

| Bibliothèque | Utilité | Obligatoire |
|---|---|---|
| `Pillow` | Textures .png/.jpg/.tga | Non (recommandé) |
| `tkinterdnd2` | Glisser-déposer (GUI) | Non (inclus dans l'.exe) |
| `ffmpeg` | Sons .mp3/.wav/.ogg | Non |

Les fichiers `.vtf` sont compressés nativement (sans dépendance).
Sans `Pillow`/`ffmpeg`, les optimisations C-Hands, fichiers inutiles et ZIP fonctionnent toujours.

---

## Structure du projet

Le code est organisé en package `cpm/` (le fichier `compressez_pm.py` reste le
point d'entrée et ré-exporte l'API publique) :

```
compressez_pm.py   Point d'entrée (CLI + GUI)
cpm/
├── deps.py         Dépendances optionnelles (Pillow, vtflib, ffmpeg)
├── constants.py    Constantes globales
├── i18n.py         Traductions FR / EN
├── changelog.py    Nouveautés affichées dans l'application
├── gma.py          Lecteur / écrivain .gma
├── analysis.py     Moteur d'analyse (pur, testable)
├── report.py       Rapport HTML
├── compressor.py   Logique de compression
├── gui.py          Interface graphique tkinter
└── cli.py          Point d'entrée ligne de commande
tools/
└── check_no_comments.py   Vérification du style du dépôt (CI)
```

### Style du dépôt

Le code ne contient **aucun commentaire ni docstring** : les noms et les clés
de traduction portent l'explication. La CI refuse toute PR qui en réintroduit
(`python tools/check_no_comments.py .`). Voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Les tests couvrent le moteur d'analyse (parsing `.mdl`/`.vmt`/`.vtf`, graphe de
dépendances, doublons, dédup, whitelist GMA, audit, rapport HTML), le
round-trip `.gma` et la génération Lua — sans nécessiter d'interface graphique.
La CI exécute la suite avant chaque build de l'exécutable Windows.

---

## Contribuer

Les contributions sont bienvenues : voir [CONTRIBUTING.md](CONTRIBUTING.md)
pour l'installation, le style de code et l'ajout de traductions.

## Licence

[MIT](LICENSE) © 2026 TenGoKu13
