# Compressez PM GMod

Outil de compression d'addons **Playermodel** pour Garry's Mod.  
Disponible en **interface graphique** (GUI) et en **ligne de commande** (CLI).

---

## Fonctionnalités

| Option | Description |
|--------|-------------|
| **Supprimer les C-Hands** | Retire les modèles de bras à la 1ʳᵉ personne (`c_arms`, `c_*`) |
| **Supprimer les fichiers inutiles** | Supprime `.txt`, `.md`, `.pdf`, `.psd`, `.log`, etc. |
| **Vérification des matériaux** | Détecte les textures référencées par les `.vmt` mais absentes de l'addon |
| **Optimiser les textures** | Redimensionne et recompresse `.vtf`, `.png`, `.jpg`, `.tga` |
| **Résolution max des textures** | 256 / 512 / 1024 / 2048 / Aucune limite |
| **Qualité des textures** | Curseur de 10 % à 100 % |
| **Taille cible** | Ajuste automatiquement résolution/qualité pour atteindre une taille max donnée |
| **Compresser les sons** | Re-encode en MP3 via ffmpeg |
| **Niveau de compression ZIP** | 1 (rapide) à 9 (maximum) |
| **Mode aperçu (dry-run)** | Affiche les changements sans rien écrire sur le disque |
| **Sauvegarde de l'original** | Crée une copie horodatée de la sortie avant écrasement |
| **Mode batch** | Traite plusieurs addons (sous-dossiers/.gma) en une seule fois |
| **Glisser-déposer** | Déposez un dossier ou un `.gma` dans la fenêtre (GUI, nécessite `tkinterdnd2`) |
| **Thème clair / sombre** | Bascule depuis l'en-tête de la GUI |
| **Multilingue FR / EN** | Bascule la langue de l'interface et des messages |

### Formats supportés
- **Entrée** : dossier addon ou fichier `.gma`
- **Sortie** : dossier, fichier `.gma`, ou archive `.zip`

---

## Installation

```bash
git clone https://github.com/tengoku13/compressez-pm-gmod.git
cd compressez-pm-gmod
pip install -r requirements.txt
```

> **Optionnel – support VTF natif** : `pip install vtflib`  
> **Optionnel – compression des sons** : installer [ffmpeg](https://ffmpeg.org/download.html) dans le PATH

---

## Utilisation

### Interface graphique (recommandée)

```bash
python compressez_pm.py
```

### Ligne de commande

```bash
# Dossier → dossier
python compressez_pm.py mon_addon/ sortie/

# Supprimer les C-Hands + qualité 70 %
python compressez_pm.py mon_addon.gma sortie.gma --no-chands --quality 70

# Sortie ZIP, résolution max 512 px
python compressez_pm.py mon_addon/ sortie.zip --format zip --max-res 512

# Avec compression des sons
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
| `vtflib` | Textures .vtf natif | Non |
| `ffmpeg` | Sons .mp3/.wav/.ogg | Non |
| `tkinterdnd2` | Glisser-déposer (GUI) | Non |

Sans ces dépendances, les optimisations C-Hands, fichiers inutiles et ZIP fonctionnent toujours.

---

## Licence

MIT
