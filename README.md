# Compressez PM GMod

Outil de compression d'addons **Playermodel** pour Garry's Mod.  
Disponible en **interface graphique** (GUI) et en **ligne de commande** (CLI).

---

## Fonctionnalités

| Option | Description |
|--------|-------------|
| **Supprimer les C-Hands** | Retire les modèles de bras à la 1ʳᵉ personne (`c_arms`, `c_*`) |
| **Supprimer les fichiers inutiles** | Supprime `.txt`, `.md`, `.pdf`, `.psd`, `.log`, etc. |
| **Optimiser les textures** | Redimensionne et recompresse `.vtf`, `.png`, `.jpg`, `.tga` |
| **Résolution max des textures** | 256 / 512 / 1024 / 2048 / Aucune limite |
| **Qualité des textures** | Curseur de 10 % à 100 % |
| **Compresser les sons** | Re-encode en MP3 via ffmpeg |
| **Niveau de compression ZIP** | 1 (rapide) à 9 (maximum) |

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
```

---

## Dépendances

| Bibliothèque | Utilité | Obligatoire |
|---|---|---|
| `Pillow` | Textures .png/.jpg/.tga | Non (recommandé) |
| `vtflib` | Textures .vtf natif | Non |
| `ffmpeg` | Sons .mp3/.wav/.ogg | Non |

Sans ces dépendances, les optimisations C-Hands, fichiers inutiles et ZIP fonctionnent toujours.

---

## Licence

MIT
