#!/usr/bin/env python3
# Requires Python 3.9+ (Windows 64-bit compatible)
"""
Compressez PM GMod
Outil de compression d'addons Playermodel pour Garry's Mod
"""
from __future__ import annotations

import os
import sys
import struct
import json
import shutil
import zipfile
import threading
import time
import re
import binascii
import subprocess
import tempfile
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ─── Dépendances optionnelles ────────────────────────────────────────────────

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import vtflib
    VTFLIB_AVAILABLE = True
except ImportError:
    VTFLIB_AVAILABLE = False

def _check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False

FFMPEG_AVAILABLE = _check_ffmpeg()

# ─── Constantes ──────────────────────────────────────────────────────────────

VERSION = "1.0.0"


def _config_path() -> Path:
    """Chemin du fichier de préférences utilisateur (multiplateforme)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return base / 'CompressezPMGMod' / 'config.json'


CONFIG_PATH = _config_path()

# Patterns de fichiers C-Hands (bras à la première personne)
CHAND_PATTERNS = [
    r"models/weapons/c_.*",
    r"materials/models/weapons/c_.*",
    r"models/weapons/cstrike/c_.*",
    r"materials/models/weapons/cstrike/c_.*",
    r"models/weapons/v_.*_c\..*",
]

# Extensions de fichiers inutiles (documentation, sources PSD, etc.)
USELESS_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.nfo', '.log',
    '.bat', '.sh', '.psd', '.xcf', '.ai', '.eps',
}

# Extensions de textures supportées
TEXTURE_EXTENSIONS = {'.vtf', '.png', '.jpg', '.jpeg', '.tga', '.bmp'}

# Extensions de sons supportées
SOUND_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aif', '.aiff'}

# Formats d'image VTF : id -> (nom, octets/pixel ou octets/bloc 4x4, bloc compressé ?)
VTF_FORMAT_SIZES = {
    0:  ('RGBA8888', 4, False),
    1:  ('ABGR8888', 4, False),
    2:  ('RGB888', 3, False),
    3:  ('BGR888', 3, False),
    4:  ('RGB565', 2, False),
    5:  ('I8', 1, False),
    6:  ('IA88', 2, False),
    7:  ('P8', 1, False),
    8:  ('A8', 1, False),
    9:  ('RGB888_BLUESCREEN', 3, False),
    10: ('BGR888_BLUESCREEN', 3, False),
    11: ('ARGB8888', 4, False),
    12: ('BGRA8888', 4, False),
    13: ('DXT1', 8, True),
    14: ('DXT3', 16, True),
    15: ('DXT5', 16, True),
    16: ('BGRX8888', 4, False),
    17: ('BGR565', 2, False),
    18: ('BGRX5551', 2, False),
    19: ('BGRA4444', 2, False),
    20: ('DXT1_ONEBITALPHA', 8, True),
    21: ('BGRA5551', 2, False),
    22: ('UV88', 2, False),
    23: ('UVWQ8888', 4, False),
    24: ('RGBA16161616F', 8, False),
    25: ('RGBA16161616', 8, False),
    26: ('UVLX8888', 4, False),
    27: ('R32F', 4, False),
    28: ('RGB323232F', 12, False),
    29: ('RGBA32323232F', 16, False),
}


def _vtf_format_size(fmt: int, w: int, h: int) -> int | None:
    info = VTF_FORMAT_SIZES.get(fmt)
    if info is None:
        return None
    _, unit, is_block = info
    if is_block:
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        return bw * bh * unit
    return w * h * unit


# Clés de matériaux VMT faisant référence à des fichiers .vtf
VMT_TEXTURE_KEYS = {
    'basetexture', 'basetexture2', 'bumpmap', 'bumpmap2', 'normalmap',
    'normalmap2', 'envmapmask', 'detail', 'blendmodulatetexture',
    'phongexponenttexture', 'phongwarptexture', 'lightwarptexture',
    'selfillummask', 'ambientocclusiontexture', 'tooltexture', 'texture2',
    'iris', 'corneatexture', 'displacementmap', 'blendmask',
}

# Rôle d'une texture déterminé par des mots-clés dans son nom de fichier.
# L'ordre compte : les rôles les plus spécifiques doivent passer en premier.
# Clé de rôle -> liste de mots-clés (FR/EN) recherchés dans le chemin.
TEXTURE_ROLE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ('role_eye_effect', ('eyeglow', 'eyeball', 'glowing_eye', 'eye_glow')),
    ('role_eyes',       ('eye', 'iris', 'cornea', 'oeil', 'yeux', 'pupil')),
    ('role_helmet',     ('helmet', 'casque', 'hat', 'chapeau', 'cap', 'mask', 'masque', 'hood', 'capuche')),
    ('role_hair',       ('hair', 'cheveux', 'beard', 'barbe', 'brow', 'lash', 'sourcil')),
    ('role_mouth',      ('mouth', 'teeth', 'tooth', 'bouche', 'dent', 'tongue', 'langue', 'lip', 'levre')),
    ('role_head',       ('head', 'face', 'tete', 'visage', 'skin_head', 'faceskin')),
    ('role_hands',      ('hand', 'arm', 'glove', 'main', 'bras', 'gant', 'c_arms', 'fist', 'finger')),
    ('role_legs',       ('leg', 'foot', 'feet', 'boot', 'shoe', 'pant', 'jambe', 'pied', 'botte', 'chaussure', 'thigh')),
    ('role_body',       ('body', 'torso', 'chest', 'corps', 'torse', 'suit', 'shirt', 'jacket', 'vest', 'cloth', 'outfit', 'skin')),
    ('role_accessory',  ('accessor', 'bag', 'belt', 'ceinture', 'strap', 'pouch', 'badge', 'patch', 'weapon', 'gun')),
]

# Suffixes de nom indiquant une carte technique plutôt qu'un rôle visuel.
NORMALMAP_HINTS = ('_normal', '_n', '_nrm', '_bump', '_ddn')
EFFECTMAP_HINTS = ('_phong', '_spec', '_exp', '_gloss', '_ao', '_mask', '_illum', '_detail')


# ─── Internationalisation (FR/EN) ────────────────────────────────────────────

STRINGS: dict[str, dict[str, str]] = {
    # CLI
    'cli_header': {'fr': "Compressez PM GMod v{version} – mode CLI\n", 'en': "Compressez PM GMod v{version} – CLI mode\n"},

    # Pipeline général
    'loading_files':   {'fr': "Chargement des fichiers…", 'en': "Loading files…"},
    'err_no_files':    {'fr': "✗ ERREUR : Aucun fichier trouvé dans la source.", 'en': "✗ ERROR: No files found in source."},
    'files_loaded':    {'fr': "▶ {n} fichier(s) chargé(s)", 'en': "▶ {n} file(s) loaded"},
    'original_size':   {'fr': "  Taille originale : {size}", 'en': "  Original size: {size}"},
    'disabled':        {'fr': "  (désactivé)", 'en': "  (disabled)"},
    'removed_n':       {'fr': "  ✓ {n} fichier(s) supprimé(s)", 'en': "  ✓ {n} file(s) removed"},

    'step_chands':     {'fr': "▶ Étape {n}/{total} — C-Hands", 'en': "▶ Step {n}/{total} — C-Hands"},
    'status_chands':   {'fr': "Suppression des C-Hands…", 'en': "Removing C-Hands…"},

    'step_unused':     {'fr': "▶ Étape {n}/{total} — Fichiers inutiles", 'en': "▶ Step {n}/{total} — Unused files"},
    'status_unused':   {'fr': "Suppression des fichiers inutiles…", 'en': "Removing unused files…"},

    'step_materials':  {'fr': "▶ Étape {n}/{total} — Vérification des matériaux", 'en': "▶ Step {n}/{total} — Material check"},
    'status_materials':{'fr': "Vérification des matériaux…", 'en': "Checking materials…"},

    'step_textures':   {'fr': "▶ Étape {n}/{total} — Textures", 'en': "▶ Step {n}/{total} — Textures"},
    'status_textures': {'fr': "Optimisation des textures…", 'en': "Optimizing textures…"},

    'step_sounds':     {'fr': "▶ Étape {n}/{total} — Sons", 'en': "▶ Step {n}/{total} — Sounds"},
    'status_sounds':   {'fr': "Compression des sons…", 'en': "Compressing sounds…"},
    'ffmpeg_missing':  {'fr': "  ⚠ ffmpeg introuvable dans le PATH, étape ignorée", 'en': "  ⚠ ffmpeg not found in PATH, step skipped"},

    'step_lua':        {'fr': "▶ Étape {n}/{total} — Fichier Lua PM", 'en': "▶ Step {n}/{total} — Lua PM file"},
    'status_lua':      {'fr': "Génération du fichier Lua…", 'en': "Generating Lua file…"},

    'step_write':      {'fr': "▶ Étape {n}/{total} — Écriture de la sortie", 'en': "▶ Step {n}/{total} — Writing output"},
    'status_write':    {'fr': "Écriture de la sortie…", 'en': "Writing output…"},

    'final_size':      {'fr': "✓ Taille finale  : {size}", 'en': "✓ Final size    : {size}"},
    'final_reduction': {'fr': "✓ Réduction      : {pct}%", 'en': "✓ Reduction     : {pct}%"},
    'success':         {'fr': "✓ Compression terminée avec succès !", 'en': "✓ Compression completed successfully!"},
    'status_done':     {'fr': "Terminé !", 'en': "Done!"},
    'cancelled':       {'fr': "\n⚠ Compression annulée.", 'en': "\n⚠ Compression cancelled."},
    'status_cancelled':{'fr': "Annulé", 'en': "Cancelled"},
    'error_generic':   {'fr': "\n✗ ERREUR : {e}", 'en': "\n✗ ERROR: {e}"},
    'status_error':    {'fr': "Erreur !", 'en': "Error!"},

    # C-Hands / fichiers inutiles
    'removed_chand':       {'fr': "  Supprimé C-Hand : {path}", 'en': "  Removed C-Hand: {path}"},
    'removed_unused_file': {'fr': "  Supprimé inutile : {path}", 'en': "  Removed unused file: {path}"},

    # Textures
    'no_textures':     {'fr': "  Aucune texture trouvée.", 'en': "  No textures found."},
    'textures_found':  {'fr': "  {n} texture(s) trouvée(s)…", 'en': "  {n} texture(s) found…"},
    'no_res_limit':    {'fr': "  Résolution max : aucune limite (les .vtf seront copiés tels quels)", 'en': "  Max resolution: no limit (.vtf files copied as-is)"},
    'no_vtflib':       {'fr': "  vtflib non installé : réduction des .vtf par troncature de mipmaps (résolution max {max_res}px)", 'en': "  vtflib not installed: .vtf reduced via mipmap truncation (max resolution {max_res}px)"},
    'texture_saving':  {'fr': "  {path} : -{size}", 'en': "  {path}: -{size}"},
    'textures_reduced':{'fr': "  Textures réduites : {reduced}/{total}", 'en': "  Textures reduced: {reduced}/{total}"},
    'vtf_unchanged':   {'fr': "  .vtf inchangés : {n} (déjà sous la résolution max, ou format/structure non pris en charge)", 'en': "  .vtf unchanged: {n} (already under max resolution, or unsupported format/structure)"},
    'texture_error':   {'fr': "  ⚠ Texture ignorée (illisible) : {path} — {e}", 'en': "  ⚠ Texture skipped (unreadable): {path} — {e}"},
    'no_limit':        {'fr': "Aucune limite", 'en': "No limit"},

    # Sons
    'no_sounds':    {'fr': "  Aucun son trouvé.", 'en': "  No sounds found."},
    'sounds_found': {'fr': "  {n} son(s) trouvé(s)…", 'en': "  {n} sound(s) found…"},
    'sound_saving': {'fr': "  {path} → {new_path} : -{size}", 'en': "  {path} → {new_path}: -{size}"},
    'sound_error':  {'fr': "  Erreur son {path}: {e}", 'en': "  Sound error {path}: {e}"},

    # Lua
    'lua_no_models_player': {'fr': "  Lua : aucun .mdl dans models/player/, utilisation des modèles trouvés ailleurs dans models/", 'en': "  Lua: no .mdl in models/player/, using models found elsewhere in models/"},
    'lua_no_models':        {'fr': "  Lua : aucun .mdl trouvé dans models/ – ignoré", 'en': "  Lua: no .mdl found in models/ – skipped"},
    'lua_model_detected':   {'fr': "  Lua : modèle détecté → {path}", 'en': "  Lua: model detected → {path}"},
    'lua_models_found':     {'fr': "  Lua : {n} modèle(s) trouvé(s)", 'en': "  Lua: {n} model(s) found"},
    'lua_updated':          {'fr': "  Lua mis à jour : {path}", 'en': "  Lua updated: {path}"},
    'lua_created':          {'fr': "  Lua créé : {path}", 'en': "  Lua created: {path}"},

    # Écriture
    'write_folder': {'fr': "  Dossier : {path}/", 'en': "  Folder: {path}/"},
    'write_gma':    {'fr': "  GMA : {path}", 'en': "  GMA: {path}"},
    'write_zip':    {'fr': "  ZIP : {path}", 'en': "  ZIP: {path}"},

    # Mode aperçu (dry-run)
    'dry_run_active':             {'fr': "  🔍 Mode aperçu activé : aucune modification ne sera écrite sur le disque", 'en': "  🔍 Dry-run mode enabled: nothing will be written to disk"},
    'dry_run_would_write_folder': {'fr': "  [APERÇU] Aurait écrit le dossier : {path}/ ({n} fichier(s))", 'en': "  [DRY-RUN] Would write folder: {path}/ ({n} file(s))"},
    'dry_run_would_write_gma':    {'fr': "  [APERÇU] Aurait écrit le GMA : {path}", 'en': "  [DRY-RUN] Would write GMA: {path}"},
    'dry_run_would_write_zip':    {'fr': "  [APERÇU] Aurait écrit le ZIP : {path}", 'en': "  [DRY-RUN] Would write ZIP: {path}"},

    # Sauvegarde de l'original
    'backup_created': {'fr': "  ✓ Sauvegarde de l'original créée : {path}", 'en': "  ✓ Backup of original created: {path}"},
    'backup_failed':  {'fr': "  ⚠ Sauvegarde impossible : {e}", 'en': "  ⚠ Backup failed: {e}"},

    # Mode taille cible
    'step_target_size':   {'fr': "  ▶ Mode taille cible — objectif : {size}", 'en': "  ▶ Target size mode — goal: {size}"},
    'target_attempt':     {'fr': "    Tentative {n} : résolution={res}, qualité={q} → {size}", 'en': "    Attempt {n}: resolution={res}, quality={q} → {size}"},
    'target_reached':     {'fr': "  ✓ Taille cible atteinte : {size} ≤ {target}", 'en': "  ✓ Target size reached: {size} ≤ {target}"},
    'target_not_reached': {'fr': "  ⚠ Taille cible non atteinte ({size} > {target}), réglages les plus agressifs appliqués", 'en': "  ⚠ Target size not reached ({size} > {target}), most aggressive settings applied"},

    # Détection de matériaux/textures manquants
    'no_vmt':                  {'fr': "  Aucun fichier .vmt trouvé.", 'en': "  No .vmt file found."},
    'missing_texture':         {'fr': "  ⚠ Texture manquante : {texture} (référencée dans {vmt})", 'en': "  ⚠ Missing texture: {texture} (referenced in {vmt})"},
    'missing_textures_none':   {'fr': "  ✓ Aucune texture manquante détectée ({n} .vmt vérifié(s))", 'en': "  ✓ No missing textures detected ({n} .vmt checked)"},
    'missing_textures_found':  {'fr': "  ⚠ {n} texture(s) manquante(s) détectée(s)", 'en': "  ⚠ {n} missing texture(s) detected"},

    # Classification et rôles des textures
    'classify_header':     {'fr': "  ── Rôle des textures ──", 'en': "  ── Texture roles ──"},
    'classify_line':       {'fr': "  {role} : {n} texture(s)", 'en': "  {role}: {n} texture(s)"},
    'classify_item':       {'fr': "      • {path}", 'en': "      • {path}"},
    'classify_none':       {'fr': "  Aucune texture à classer.", 'en': "  No texture to classify."},
    'role_head':           {'fr': "Tête / Visage", 'en': "Head / Face"},
    'role_helmet':         {'fr': "Casque / Chapeau", 'en': "Helmet / Hat"},
    'role_hair':           {'fr': "Cheveux", 'en': "Hair"},
    'role_eyes':           {'fr': "Yeux", 'en': "Eyes"},
    'role_mouth':          {'fr': "Bouche / Dents", 'en': "Mouth / Teeth"},
    'role_body':           {'fr': "Corps / Torse", 'en': "Body / Torso"},
    'role_hands':          {'fr': "Mains / Bras", 'en': "Hands / Arms"},
    'role_legs':           {'fr': "Jambes / Pieds", 'en': "Legs / Feet"},
    'role_accessory':      {'fr': "Accessoires", 'en': "Accessories"},
    'role_normalmap':      {'fr': "Cartes normales / bump", 'en': "Normal / bump maps"},
    'role_effectmap':      {'fr': "Cartes d'effet (phong, spéculaire…)", 'en': "Effect maps (phong, specular…)"},
    'role_eye_effect':     {'fr': "Effets (yeux brillants, œil…)", 'en': "Eye effects (glow, eyeball…)"},
    'role_other':          {'fr': "Autre / Non classé", 'en': "Other / Unclassified"},

    # Textures inutilisées
    'unused_tex_header':   {'fr': "  ── Textures inutilisées ──", 'en': "  ── Unused textures ──"},
    'unused_tex_item':     {'fr': "  ⚠ Inutilisée (aucun .vmt) : {path} ({size})", 'en': "  ⚠ Unused (no .vmt): {path} ({size})"},
    'unused_tex_removed':  {'fr': "  🗑 Supprimée : {path} ({size})", 'en': "  🗑 Removed: {path} ({size})"},
    'unused_tex_none':     {'fr': "  ✓ Aucune texture inutilisée détectée.", 'en': "  ✓ No unused texture detected."},
    'unused_tex_found':    {'fr': "  ⚠ {n} texture(s) inutilisée(s) — {size} (activez la suppression pour les retirer)", 'en': "  ⚠ {n} unused texture(s) — {size} (enable removal to strip them)"},
    'unused_tex_deleted':  {'fr': "  🗑 {n} texture(s) inutilisée(s) supprimée(s) — {size} libéré(s)", 'en': "  🗑 {n} unused texture(s) removed — {size} freed"},
    'unused_tex_no_vmt':   {'fr': "  Aucun .vmt : classement des textures inutilisées ignoré.", 'en': "  No .vmt: unused-texture check skipped."},

    # Matériaux (.vmt) orphelins — non référencés par un .mdl
    'orphan_vmt_header':   {'fr': "  ── Matériaux orphelins ──", 'en': "  ── Orphan materials ──"},
    'orphan_vmt_item':     {'fr': "  ⚠ Orphelin (aucun .mdl) : {path} ({size})", 'en': "  ⚠ Orphan (no .mdl): {path} ({size})"},
    'orphan_vmt_removed':  {'fr': "  🗑 Supprimé : {path} ({size})", 'en': "  🗑 Removed: {path} ({size})"},
    'orphan_vmt_found':    {'fr': "  ⚠ {n} matériau(x) orphelin(s) — {size}", 'en': "  ⚠ {n} orphan material(s) — {size}"},
    'orphan_vmt_deleted':  {'fr': "  🗑 {n} matériau(x) orphelin(s) supprimé(s) — {size} libéré(s)", 'en': "  🗑 {n} orphan material(s) removed — {size} freed"},

    # Doublons de textures
    'dup_header':          {'fr': "  ── Doublons de textures ──", 'en': "  ── Duplicate textures ──"},
    'dup_group':           {'fr': "  ⧉ {n} copies identiques ({size} chacune) :", 'en': "  ⧉ {n} identical copies ({size} each):"},
    'dup_item':            {'fr': "      • {path}", 'en': "      • {path}"},
    'dup_none':            {'fr': "  ✓ Aucun doublon exact détecté.", 'en': "  ✓ No exact duplicate detected."},
    'dup_summary':         {'fr': "  ⧉ {groups} groupe(s) de doublons — {size} récupérable(s) par déduplication", 'en': "  ⧉ {groups} duplicate group(s) — {size} recoverable via dedup"},

    # Audit des textures
    'audit_header':        {'fr': "  ── Audit des textures ──", 'en': "  ── Texture audit ──"},
    'audit_oversized':     {'fr': "  ⚠ Surdimensionnée : {path} ({detail})", 'en': "  ⚠ Oversized: {path} ({detail})"},
    'audit_uncompressed':  {'fr': "  ⚠ Non compressée : {path} (format {detail} → DXT recommandé)", 'en': "  ⚠ Uncompressed: {path} (format {detail} → DXT recommended)"},
    'audit_npot':          {'fr': "  ⚠ Non puissance de 2 : {path} ({detail})", 'en': "  ⚠ Not power-of-two: {path} ({detail})"},
    'audit_none':          {'fr': "  ✓ Aucun problème de texture détecté.", 'en': "  ✓ No texture issue detected."},
    'audit_summary':       {'fr': "  ⚠ {n} avertissement(s) d'audit", 'en': "  ⚠ {n} audit warning(s)"},

    # Rapport HTML
    'report_written':      {'fr': "▶ Rapport HTML généré : {path}", 'en': "▶ HTML report generated: {path}"},
    'report_title':        {'fr': "Rapport d'analyse — {name}", 'en': "Analysis report — {name}"},
    'report_subtitle':     {'fr': "Compressez PM GMod — analyse de l'addon", 'en': "Compressez PM GMod — addon analysis"},
    'report_sum_original': {'fr': "Taille d'origine", 'en': "Original size"},
    'report_sum_final':    {'fr': "Taille finale", 'en': "Final size"},
    'report_sum_saved':    {'fr': "Réduction", 'en': "Reduction"},
    'report_sum_files':    {'fr': "Fichiers", 'en': "Files"},
    'report_sec_roles':    {'fr': "Rôle des textures", 'en': "Texture roles"},
    'report_sec_orphans':  {'fr': "Fichiers inutilisés", 'en': "Unused files"},
    'report_sec_dups':     {'fr': "Doublons exacts", 'en': "Exact duplicates"},
    'report_sec_audit':    {'fr': "Audit qualité", 'en': "Quality audit"},
    'report_col_texture':  {'fr': "Texture", 'en': "Texture"},
    'report_col_issue':    {'fr': "Problème", 'en': "Issue"},
    'report_col_detail':   {'fr': "Détail", 'en': "Detail"},
    'report_removed_badge':{'fr': "supprimé(s)", 'en': "removed"},
    'report_kept_badge':   {'fr': "conservé(s)", 'en': "kept"},
    'report_empty':        {'fr': "Rien à signaler.", 'en': "Nothing to report."},
    'report_audit_oversized':    {'fr': "Surdimensionnée", 'en': "Oversized"},
    'report_audit_uncompressed': {'fr': "Non compressée", 'en': "Uncompressed"},
    'report_audit_npot':         {'fr': "Non puissance de 2", 'en': "Not power-of-two"},
    'report_open':         {'fr': "📄 Ouvrir le rapport", 'en': "📄 Open report"},
    'chk_report':          {'fr': "Générer un rapport HTML", 'en': "Generate HTML report"},
    'desc_report':         {'fr': "  Récapitulatif visuel (rôles, orphelins, audit)", 'en': "  Visual summary (roles, orphans, audit)"},
    'chk_convert':         {'fr': "Recompresser les textures non compressées (DXT)", 'en': "Recompress uncompressed textures (DXT)"},
    'desc_convert':        {'fr': "  Convertit les .vtf RGBA/BGR volumineux en DXT", 'en': "  Converts bulky RGBA/BGR .vtf files to DXT"},

    # Mode batch
    'batch_none':           {'fr': "✗ ERREUR : Aucun addon trouvé pour le mode batch (sous-dossiers ou .gma attendus dans la source).", 'en': "✗ ERROR: No addon found for batch mode (subfolders or .gma files expected in source)."},
    'batch_found':          {'fr': "▶ Mode batch : {n} addon(s) détecté(s) dans {path}", 'en': "▶ Batch mode: {n} addon(s) detected in {path}"},
    'batch_processing':     {'fr': "▶ ─── Addon {i}/{n} : {name} ───", 'en': "▶ ─── Addon {i}/{n}: {name} ───"},
    'batch_summary_header': {'fr': "▶ ═══ Résumé du traitement par lot ═══", 'en': "▶ ═══ Batch processing summary ═══"},
    'batch_summary_line':   {'fr': "  {name} : {size}  ({pct}%)", 'en': "  {name}: {size}  ({pct}%)"},
    'batch_done':           {'fr': "✓ Traitement par lot terminé : {n} addon(s)", 'en': "✓ Batch processing completed: {n} addon(s)"},

    # ─── Interface graphique ────────────────────────────────────────────────
    'app_tagline':         {'fr': "Compresseur d'addons Playermodel pour Garry's Mod", 'en': "Playermodel addon compressor for Garry's Mod"},
    'io_section':          {'fr': " 📁 Entrée / Sortie ", 'en': " 📁 Input / Output "},
    'label_source':        {'fr': "Source :", 'en': "Source:"},
    'label_output':        {'fr': "Sortie :", 'en': "Output:"},
    'btn_browse':          {'fr': "📂 Parcourir", 'en': "📂 Browse"},
    'label_source_type':   {'fr': "Type source :", 'en': "Source type:"},
    'radio_folder':        {'fr': "Dossier", 'en': "Folder"},
    'radio_gma_file':      {'fr': "Fichier .gma", 'en': ".gma file"},
    'label_output_format': {'fr': "Format sortie :", 'en': "Output format:"},
    'drop_hint':           {'fr': "  (glissez-déposez un dossier ou .gma ici)", 'en': "  (drag & drop a folder or .gma here)"},

    'dialog_select_gma':    {'fr': "Sélectionner un fichier GMA", 'en': "Select a GMA file"},
    'dialog_select_folder': {'fr': "Sélectionner le dossier de l'addon", 'en': "Select the addon folder"},
    'dialog_output_folder': {'fr': "Dossier de sortie", 'en': "Output folder"},
    'dialog_save_gma':      {'fr': "Enregistrer le GMA", 'en': "Save GMA"},
    'dialog_save_zip':      {'fr': "Enregistrer l'archive ZIP", 'en': "Save ZIP archive"},
    'filetype_gma':         {'fr': "Fichiers GMA", 'en': "GMA files"},
    'filetype_all':         {'fr': "Tous les fichiers", 'en': "All files"},
    'filetype_zip':         {'fr': "Archives ZIP", 'en': "ZIP archives"},

    'stats_source':      {'fr': "Source : {count} fichier(s) — {size}", 'en': "Source: {count} file(s) — {size}"},
    'stats_source_file': {'fr': "Fichier source : {size}", 'en': "Source file: {size}"},
    'stats_analyzing':   {'fr': "Analyse de la source…", 'en': "Analyzing source…"},
    'stats_done':        {'fr': "✓ Terminé : {before} → {after}  (-{pct}%)", 'en': "✓ Done: {before} → {after}  (-{pct}%)"},

    'label_profile':    {'fr': "Profil rapide :", 'en': "Quick profile:"},
    'profile_hint':     {'fr': "  Ajuste automatiquement les réglages ci-dessous", 'en': "  Automatically adjusts the settings below"},
    'profile_custom':   {'fr': "Personnalisé", 'en': "Custom"},
    'profile_balanced': {'fr': "Équilibré (recommandé)", 'en': "Balanced (recommended)"},
    'profile_quality':  {'fr': "Qualité maximale", 'en': "Maximum quality"},
    'profile_minimal':  {'fr': "Taille minimale", 'en': "Minimum size"},
    'profile_share':    {'fr': "Partage rapide (Discord…)", 'en': "Quick share (Discord…)"},

    'tab_general':  {'fr': " ⚙ Général ", 'en': " ⚙ General "},
    'tab_advanced': {'fr': " 🛠 Avancé ", 'en': " 🛠 Advanced "},

    'chk_chands':  {'fr': "Supprimer les C-Hands", 'en': "Remove C-Hands"},
    'desc_chands': {'fr': "  Retire les bras à la 1ʳᵉ personne (c_arms, c_*)", 'en': "  Removes first-person arms (c_arms, c_*)"},
    'chk_unused':  {'fr': "Supprimer les fichiers inutiles", 'en': "Remove unused files"},
    'desc_unused': {'fr': "  .txt, .md, .pdf, .psd, .log…", 'en': "  .txt, .md, .pdf, .psd, .log…"},

    'chk_remove_unused_tex':  {'fr': "Supprimer les textures inutilisées", 'en': "Remove unused textures"},
    'desc_remove_unused_tex': {'fr': "  Retire les .vtf référencées par aucun .vmt", 'en': "  Strips .vtf files no .vmt references"},

    'chk_textures':  {'fr': "Optimiser les textures", 'en': "Optimize textures"},
    'label_max_res': {'fr': "Résolution max :", 'en': "Max resolution:"},
    'label_quality': {'fr': "Qualité :", 'en': "Quality:"},
    'pillow_hint':   {'fr': "⚠  pip install Pillow  pour les images non-VTF", 'en': "⚠  pip install Pillow  for non-VTF images"},

    'chk_lua':         {'fr': "Générer le fichier Lua PM", 'en': "Generate Lua PM file"},
    'desc_lua':        {'fr': "  Crée/met à jour lua/autorun/sh_*_pm.lua", 'en': "  Creates/updates lua/autorun/sh_*_pm.lua"},
    'chk_lua_chands':  {'fr': "Inclure les C-Hands dans le Lua", 'en': "Include C-Hands in Lua"},
    'desc_lua_chands': {'fr': "  Ajoute le hook PlayerSetHandsModel si\n  les c_arms sont présents", 'en': "  Adds the PlayerSetHandsModel hook if\n  c_arms are present"},

    'chk_sounds':         {'fr': "Compresser les sons", 'en': "Compress sounds"},
    'ffmpeg_ok':          {'fr': "✓ ffmpeg détecté", 'en': "✓ ffmpeg detected"},
    'ffmpeg_missing_lbl': {'fr': "⚠  ffmpeg introuvable dans le PATH", 'en': "⚠  ffmpeg not found in PATH"},
    'label_bitrate':      {'fr': "Bitrate :", 'en': "Bitrate:"},
    'label_zip_level':    {'fr': "Niveau de compression ZIP :", 'en': "ZIP compression level:"},
    'zip_fast':           {'fr': "Rapide", 'en': "Fast"},
    'zip_max':            {'fr': "Max", 'en': "Max"},
    'libs_detected':      {'fr': "Bibliothèques détectées :", 'en': "Detected libraries:"},
    'lib_pillow':         {'fr': "Pillow (.png/.jpg/.tga)", 'en': "Pillow (.png/.jpg/.tga)"},
    'lib_vtflib':         {'fr': "vtflib (.vtf natif)", 'en': "vtflib (native .vtf)"},
    'lib_ffmpeg':         {'fr': "ffmpeg (sons)", 'en': "ffmpeg (sounds)"},
    'vtf_note':           {'fr': "\nSans vtflib, les .vtf sont réduits par\ntroncature de mipmaps (résolution\nmax respectée, sans dépendance).",
                            'en': "\nWithout vtflib, .vtf files are reduced\nvia mipmap truncation (max resolution\nrespected, no dependency)."},

    # Nouvelles options (onglet Avancé)
    'chk_check_materials': {'fr': "Vérifier les matériaux/textures manquants", 'en': "Check for missing materials/textures"},
    'chk_dry_run':         {'fr': "Mode aperçu (dry-run)", 'en': "Dry-run (preview) mode"},
    'desc_dry_run':        {'fr': "  Affiche les changements sans rien écrire", 'en': "  Shows changes without writing anything"},
    'chk_backup':          {'fr': "Sauvegarder l'original avant écrasement", 'en': "Back up original before overwrite"},
    'desc_backup':         {'fr': "  Copie de sécurité horodatée", 'en': "  Timestamped safety copy"},
    'chk_target_size':     {'fr': "Taille cible :", 'en': "Target size:"},
    'label_mb':            {'fr': "Mo", 'en': "MB"},
    'desc_target_size':    {'fr': "  Ajuste résolution/qualité pour atteindre\n  la taille visée", 'en': "  Adjusts resolution/quality to reach\n  the target size"},
    'chk_batch':           {'fr': "Mode batch (plusieurs addons)", 'en': "Batch mode (multiple addons)"},
    'desc_batch':          {'fr': "  Source = dossier contenant plusieurs\n  sous-dossiers/.gma à traiter", 'en': "  Source = folder containing multiple\n  subfolders/.gma to process"},

    'progress_section': {'fr': " 📊 Progression ", 'en': " 📊 Progress "},
    'status_ready':     {'fr': "Prêt", 'en': "Ready"},

    'log_section': {'fr': " 📜 Journal ", 'en': " 📜 Log "},

    'btn_clear_log':   {'fr': "🗑 Effacer journal", 'en': "🗑 Clear log"},
    'btn_open_output': {'fr': "📂 Ouvrir le dossier de sortie", 'en': "📂 Open output folder"},
    'btn_cancel':      {'fr': "⏹ Annuler", 'en': "⏹ Cancel"},
    'btn_run':         {'fr': "▶  Compresser  ", 'en': "▶  Compress  "},
    'btn_theme_light': {'fr': "☀ Thème clair", 'en': "☀ Light theme"},
    'btn_theme_dark':  {'fr': "🌙 Thème sombre", 'en': "🌙 Dark theme"},

    'msg_source_missing_title':   {'fr': "Source manquante", 'en': "Missing source"},
    'msg_source_missing_body':    {'fr': "Veuillez sélectionner un dossier ou fichier source.", 'en': "Please select a source folder or file."},
    'msg_output_missing_title':   {'fr': "Sortie manquante", 'en': "Missing output"},
    'msg_output_missing_body':    {'fr': "Veuillez indiquer un chemin de sortie.", 'en': "Please specify an output path."},
    'msg_source_not_found_title': {'fr': "Source introuvable", 'en': "Source not found"},
    'msg_source_not_found_body':  {'fr': "Le chemin n'existe pas :\n{src}", 'en': "Path does not exist:\n{src}"},
    'msg_error_title':             {'fr': "Erreur", 'en': "Error"},
    'msg_open_folder_error':       {'fr': "Impossible d'ouvrir le dossier :\n{e}", 'en': "Could not open folder:\n{e}"},
    'msg_invalid_target_size_title': {'fr': "Taille cible invalide", 'en': "Invalid target size"},
    'msg_invalid_target_size_body':  {'fr': "Veuillez entrer un nombre valide pour la taille cible (Mo).", 'en': "Please enter a valid number for the target size (MB)."},

    'summary_title':   {'fr': "Compression terminée 🎉", 'en': "Compression complete 🎉"},
    'summary_body':    {'fr': "Avant :   {before}\nAprès :   {after}\nGagné :   {saved}  (-{pct}%)",
                        'en': "Before:  {before}\nAfter:   {after}\nSaved:   {saved}  (-{pct}%)"},
    'summary_open_q':  {'fr': "Ouvrir le dossier de sortie ?", 'en': "Open the output folder?"},
    'summary_open_folder': {'fr': "📂 Ouvrir le dossier", 'en': "📂 Open folder"},
    'summary_close':   {'fr': "Fermer", 'en': "Close"},
    'summary_dry_run': {'fr': "Mode aperçu : aucun fichier n'a réellement été écrit.", 'en': "Dry-run mode: no file was actually written."},

    # À propos
    'btn_about':       {'fr': "ℹ À propos", 'en': "ℹ About"},
    'about_title':     {'fr': "À propos", 'en': "About"},
    'about_body':      {'fr': "Compressez PM GMod  v{version}\n\nCompresseur d'addons Playermodel pour Garry's Mod.\nRéduit la taille des textures, sons et fichiers inutiles\ntout en préservant le rendu en jeu.\n\nLicence : MIT\n\nBibliothèques détectées :\n{libs}",
                        'en': "Compressez PM GMod  v{version}\n\nPlayermodel addon compressor for Garry's Mod.\nReduces texture, sound and junk-file size while\npreserving the in-game look.\n\nLicense: MIT\n\nDetected libraries:\n{libs}"},
    'about_lib_yes':   {'fr': "  ✓ {lib}", 'en': "  ✓ {lib}"},
    'about_lib_no':    {'fr': "  ✗ {lib} (absent)", 'en': "  ✗ {lib} (missing)"},

    'log_app_version':    {'fr': "Compressez PM GMod  v{version}", 'en': "Compressez PM GMod  v{version}"},
    'log_install_pillow': {'fr': "→ pip install Pillow   (optimisation .png/.jpg/.tga)", 'en': "→ pip install Pillow   (.png/.jpg/.tga optimization)"},
}


def t(key: str, lang: str = 'fr', **kwargs) -> str:
    """Traduit une clé STRINGS dans la langue demandée (repli sur le français)."""
    entry = STRINGS.get(key, {})
    text = entry.get(lang, entry.get('fr', key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


# ─── Lecteur/Écrivain GMA ────────────────────────────────────────────────────

class GMAFile:
    """Gestion du format d'addon Garry's Mod (.gma)"""

    MAGIC = b'GMAD'

    def __init__(self):
        self.name = ""
        self.description = ""
        self.author = ""
        self.files: dict[str, bytes] = {}

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as f:
            if f.read(4) != self.MAGIC:
                raise ValueError("Fichier GMA invalide (magic bytes incorrects)")

            version = struct.unpack('B', f.read(1))[0]
            f.read(8)   # steamid (ignoré)
            f.read(8)   # timestamp (ignoré)

            if version > 1:
                while self._read_str(f):
                    pass  # required content, obsolète

            self.name = self._read_str(f)
            raw_desc = self._read_str(f)
            try:
                desc_obj = json.loads(raw_desc)
                self.description = desc_obj.get('description', raw_desc)
            except (json.JSONDecodeError, TypeError):
                self.description = raw_desc
            self.author = self._read_str(f)
            f.read(4)   # addon version int

            # Index des fichiers
            file_index = []
            while True:
                num = struct.unpack('<I', f.read(4))[0]
                if num == 0:
                    break
                name = self._read_str(f)
                size = struct.unpack('<q', f.read(8))[0]
                crc  = struct.unpack('<I', f.read(4))[0]
                file_index.append((name, size, crc))

            # Lecture des données binaires
            for name, size, _ in file_index:
                self.files[name] = f.read(size)

    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('B', 3))                    # version GMA 3
            f.write(struct.pack('<Q', 0))                   # steamid
            f.write(struct.pack('<Q', int(time.time())))    # timestamp
            f.write(b'\x00')                                # required content vide

            self._write_str(f, self.name)
            desc_json = json.dumps({
                "description": self.description,
                "type": "playermodel",
                "tags": [],
            })
            self._write_str(f, desc_json)
            self._write_str(f, self.author)
            f.write(struct.pack('<i', 1))  # addon version

            file_list = list(self.files.items())
            for i, (name, data) in enumerate(file_list, 1):
                f.write(struct.pack('<I', i))
                self._write_str(f, name)
                f.write(struct.pack('<q', len(data)))
                f.write(struct.pack('<I', binascii.crc32(data) & 0xFFFFFFFF))
            f.write(struct.pack('<I', 0))  # fin de l'index

            for _, data in file_list:
                f.write(data)

    @staticmethod
    def _read_str(f) -> str:
        buf = bytearray()
        while True:
            c = f.read(1)
            if c in (b'\x00', b''):
                break
            buf.extend(c)
        return buf.decode('utf-8', errors='replace')

    @staticmethod
    def _write_str(f, s: str) -> None:
        f.write(s.encode('utf-8') + b'\x00')


# ─── Moteur d'analyse (fonctions pures, testables sans GUI) ──────────────────
#
# Ce bloc contient toute la logique d'analyse d'un addon sous forme de
# fonctions autonomes : parsing des .mdl/.vmt/.vtf, graphe de dépendances,
# détection d'orphelins et de doublons, audit des textures. Elles ne
# dépendent ni de tkinter ni de la classe Compressor, ce qui les rend
# facilement testables (voir tests/test_analysis.py).

# Suffixes de fichiers « compagnons » d'un modèle .mdl (même nom de base).
MODEL_COMPANION_SUFFIXES = (
    '.vvd', '.vtx', '.dx90.vtx', '.dx80.vtx', '.sw.vtx',
    '.phy', '.ani', '.mdl',
)


def norm_key(path: str) -> str:
    """Normalise un chemin d'addon (slashs avant, minuscules, sans slash initial)."""
    return path.replace('\\', '/').lower().lstrip('/')


def resolve_material_ref(ref: str) -> str:
    """Transforme une référence de texture VMT en chemin `materials/....vtf`."""
    ref = ref.strip().strip('"\'').replace('\\', '/').lower().lstrip('/')
    if not ref:
        return ''
    if not ref.endswith('.vtf'):
        ref += '.vtf'
    if not ref.startswith('materials/'):
        ref = 'materials/' + ref
    return ref


_VMT_KV_RE = re.compile(r'\$(\w+)"?\s+"?([^"\r\n{}]+)"?', re.IGNORECASE)


def parse_vmt_refs(text: str) -> dict[str, str]:
    """Retourne {clé_matériau: chemin_vtf_résolu} pour un contenu .vmt."""
    refs: dict[str, str] = {}
    for m in _VMT_KV_RE.finditer(text):
        key = m.group(1).lower()
        if key not in VMT_TEXTURE_KEYS:
            continue
        raw = m.group(2).strip()
        if not raw or raw.lower() == 'env_cubemap':
            continue
        resolved = resolve_material_ref(raw)
        if resolved:
            refs[key] = resolved
    return refs


def _read_cstr(data: bytes, offset: int, limit: int = 260) -> str:
    """Lit une chaîne C (terminée par \\0) à partir de `offset`."""
    if offset < 0 or offset >= len(data):
        return ''
    end = data.find(b'\x00', offset, offset + limit)
    if end == -1:
        end = min(offset + limit, len(data))
    return data[offset:end].decode('latin-1', errors='replace')


def parse_mdl_materials(data: bytes) -> tuple[list[str], list[str]]:
    """Extrait (noms_de_matériaux, dossiers_cdmaterials) d'un binaire .mdl.

    Renvoie deux listes vides si l'en-tête n'est pas exploitable."""
    if len(data) < 224 or data[:4] != b'IDST':
        return [], []
    try:
        numtextures    = struct.unpack_from('<i', data, 204)[0]
        textureindex   = struct.unpack_from('<i', data, 208)[0]
        numcdtextures  = struct.unpack_from('<i', data, 212)[0]
        cdtextureindex = struct.unpack_from('<i', data, 216)[0]

        # Garde-fous contre des en-têtes corrompus.
        if not (0 <= numtextures < 4096 and 0 <= numcdtextures < 512):
            return [], []

        names: list[str] = []
        for i in range(numtextures):
            struct_off = textureindex + i * 64
            if struct_off + 4 > len(data):
                break
            sznameindex = struct.unpack_from('<i', data, struct_off)[0]
            name = _read_cstr(data, struct_off + sznameindex)
            if name:
                names.append(name.replace('\\', '/').strip('/').lower())

        dirs: list[str] = []
        for i in range(numcdtextures):
            ptr_off = cdtextureindex + i * 4
            if ptr_off + 4 > len(data):
                break
            str_off = struct.unpack_from('<i', data, ptr_off)[0]
            d = _read_cstr(data, str_off)
            if d:
                d = d.replace('\\', '/').lower().strip('/')
                dirs.append(d + '/' if d and not d.endswith('/') else d)
        return names, dirs
    except (struct.error, IndexError):
        return [], []


def read_vtf_info(data: bytes) -> dict | None:
    """Lit l'en-tête d'un .vtf : dimensions, format, mipmaps, version, flags."""
    if len(data) < 63 or data[:4] != b'VTF\x00':
        return None
    try:
        ver_maj, ver_min = struct.unpack_from('<II', data, 4)
        width, height = struct.unpack_from('<HH', data, 16)
        flags = struct.unpack_from('<I', data, 20)[0]
        frames = struct.unpack_from('<H', data, 24)[0]
        high_fmt = struct.unpack_from('<i', data, 52)[0]
        mipmaps = data[56]
        fmt_name = VTF_FORMAT_SIZES.get(high_fmt, (f'UNKNOWN_{high_fmt}',))[0]
        return {
            'version': (ver_maj, ver_min),
            'width': width, 'height': height,
            'format': high_fmt, 'format_name': fmt_name,
            'mipmaps': mipmaps, 'flags': flags, 'frames': frames,
        }
    except (struct.error, IndexError):
        return None


def build_dependency_graph(files: dict) -> dict:
    """Construit le graphe d'usage d'un addon.

    Renvoie un dict :
      reachable            : ensemble des fichiers considérés comme utilisés
      referenced_vtf       : .vtf référencés par au moins un .vmt
      referenced_vmt       : .vmt référencés par au moins un .mdl (si parsable)
      orphan_vtf           : .vtf référencés par aucun .vmt
      orphan_vmt           : .vmt référencés par aucun .mdl
      mdl_materials_parsed : True si au moins un .mdl a livré ses matériaux
    """
    keys = {k for k in files if k != '__meta__'}
    vmt_keys = {k for k in keys if k.endswith('.vmt')}
    vtf_keys = {k for k in keys if k.endswith('.vtf')}

    # 1) .vtf référencés par les .vmt
    referenced_vtf: set[str] = set()
    for vk in vmt_keys:
        try:
            text = files[vk].decode('utf-8', errors='replace')
        except Exception:
            continue
        for resolved in parse_vmt_refs(text).values():
            referenced_vtf.add(resolved)

    # 2) .vmt référencés par les .mdl (via cdmaterials + noms de matériaux)
    referenced_vmt: set[str] = set()
    mdl_materials_parsed = False
    for mk in (k for k in keys if k.endswith('.mdl')):
        names, dirs = parse_mdl_materials(files[mk])
        if names:
            mdl_materials_parsed = True
        search_dirs = dirs or ['']
        for name in names:
            for d in search_dirs:
                cand = norm_key('materials/' + d + name + '.vmt')
                if cand in vmt_keys:
                    referenced_vmt.add(cand)
                    break
            else:
                # Repli : chercher n'importe quel .vmt au nom de base identique.
                base = name.rsplit('/', 1)[-1]
                for vk in vmt_keys:
                    if vk.rsplit('/', 1)[-1] == base + '.vmt':
                        referenced_vmt.add(vk)
                        break

    orphan_vtf = sorted(vtf_keys - referenced_vtf)
    # On ne signale des .vmt orphelins que si l'on a réellement pu lire des
    # matériaux dans au moins un .mdl (sinon risque de faux positifs).
    orphan_vmt = sorted(vmt_keys - referenced_vmt) if mdl_materials_parsed else []

    reachable = set(keys)
    reachable -= set(orphan_vtf)
    reachable -= set(orphan_vmt)

    return {
        'reachable': reachable,
        'referenced_vtf': referenced_vtf,
        'referenced_vmt': referenced_vmt,
        'orphan_vtf': orphan_vtf,
        'orphan_vmt': orphan_vmt,
        'mdl_materials_parsed': mdl_materials_parsed,
    }


def find_duplicate_textures(files: dict) -> list[list[str]]:
    """Groupe les textures dont le contenu binaire est strictement identique."""
    import hashlib
    by_hash: dict[str, list[str]] = {}
    for k, v in files.items():
        if k == '__meta__' or Path(k).suffix.lower() not in TEXTURE_EXTENSIONS:
            continue
        h = hashlib.sha1(v).hexdigest()
        by_hash.setdefault(h, []).append(k)
    return [sorted(g) for g in by_hash.values() if len(g) > 1]


# Formats VTF non compressés (gaspilleurs) que l'on recommande de recompresser.
VTF_UNCOMPRESSED_FORMATS = {
    'RGBA8888', 'ABGR8888', 'ARGB8888', 'BGRA8888', 'BGRX8888',
    'RGB888', 'BGR888', 'UVLX8888',
}


def audit_textures(files: dict, max_res: int | None = 1024) -> list[dict]:
    """Repère les textures problématiques (surdimensionnées, non compressées…).

    Chaque entrée : {path, issue, detail}. `issue` est une clé de traduction."""
    issues: list[dict] = []
    for k, v in files.items():
        if k == '__meta__' or not k.endswith('.vtf'):
            continue
        info = read_vtf_info(v)
        if not info:
            continue
        w, h = info['width'], info['height']
        if max_res and max(w, h) > max_res:
            issues.append({'path': k, 'issue': 'audit_oversized',
                           'detail': f"{w}×{h} > {max_res}px"})
        if info['format_name'] in VTF_UNCOMPRESSED_FORMATS:
            issues.append({'path': k, 'issue': 'audit_uncompressed',
                           'detail': info['format_name']})
        if w and h and ((w & (w - 1)) or (h & (h - 1))):
            issues.append({'path': k, 'issue': 'audit_npot',
                           'detail': f"{w}×{h}"})
    return issues


def build_html_report(report: dict) -> str:
    """Construit un rapport HTML autonome (thème clair/sombre) à partir d'un
    dict `report` déjà traduit. Fonction pure et testable."""
    import html as _html

    def esc(s) -> str:
        return _html.escape(str(s))

    title = report.get('title', 'Rapport')
    subtitle = report.get('subtitle', '')
    s = report.get('summary', {})
    parts: list[str] = []

    # Cartes de synthèse
    cards = [
        (report['labels']['original'], s.get('original', '—')),
        (report['labels']['final'],    s.get('final', '—')),
        (report['labels']['saved'],    s.get('reduction', '—')),
        (report['labels']['files'],    s.get('files', '—')),
    ]
    cards_html = ''.join(
        f'<div class="card"><div class="k">{esc(k)}</div>'
        f'<div class="v">{esc(v)}</div></div>' for k, v in cards)
    parts.append(f'<div class="cards">{cards_html}</div>')

    # Rôles des textures
    roles = report.get('roles', [])
    if roles:
        blocks = []
        for label, items in roles:
            lis = ''.join(f'<li>{esc(p)}</li>' for p in items)
            blocks.append(
                f'<details open><summary>{esc(label)} '
                f'<span class="badge">{len(items)}</span></summary>'
                f'<ul class="files">{lis}</ul></details>')
        parts.append(_section(report['labels']['sec_roles'], ''.join(blocks)))

    # Orphelins
    orphans = report.get('orphans', [])
    if orphans:
        badge = report['labels']['removed'] if report.get('removed') else report['labels']['kept']
        lis = ''.join(f'<li>{esc(p)}</li>' for p in orphans)
        body = (f'<p class="tag {"del" if report.get("removed") else "keep"}">'
                f'{esc(badge)}</p><ul class="files">{lis}</ul>')
        parts.append(_section(report['labels']['sec_orphans'], body))

    # Doublons
    dups = report.get('duplicates', [])
    if dups:
        blocks = []
        for group in dups:
            lis = ''.join(f'<li>{esc(p)}</li>' for p in group)
            blocks.append(f'<details><summary>{len(group)}×</summary>'
                          f'<ul class="files">{lis}</ul></details>')
        parts.append(_section(report['labels']['sec_dups'], ''.join(blocks)))

    # Audit
    audit = report.get('audit', [])
    if audit:
        rows = ''.join(
            f'<tr><td>{esc(a["path"])}</td><td>{esc(a["label"])}</td>'
            f'<td>{esc(a["detail"])}</td></tr>' for a in audit)
        lbl = report['labels']
        table = (f'<table><thead><tr><th>{esc(lbl["col_texture"])}</th>'
                 f'<th>{esc(lbl["col_issue"])}</th>'
                 f'<th>{esc(lbl["col_detail"])}</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table>')
        parts.append(_section(lbl['sec_audit'], table))

    body = '\n'.join(parts) or f'<p>{esc(report["labels"]["empty"])}</p>'
    return _HTML_TEMPLATE.format(
        title=esc(title), subtitle=esc(subtitle), body=body)


def _section(title: str, inner: str) -> str:
    import html as _html
    return (f'<section><h2>{_html.escape(title)}</h2>{inner}</section>')


_HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg:#f4f6fb; --fg:#1b2430; --sub:#5b6675; --card:#ffffff;
    --accent:#3b82f6; --border:#e2e8f0; --del:#ef4444; --keep:#10b981;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0f141b; --fg:#e6edf3; --sub:#93a1b0; --card:#161d26;
      --accent:#60a5fa; --border:#26313d; --del:#f87171; --keep:#34d399;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:32px; background:var(--bg); color:var(--fg);
    font-family:'Segoe UI',system-ui,sans-serif; line-height:1.5; }}
  header {{ margin-bottom:24px; }}
  h1 {{ margin:0; font-size:22px; }}
  .sub {{ color:var(--sub); font-size:14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
    gap:12px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:14px 16px; }}
  .card .k {{ color:var(--sub); font-size:12px; text-transform:uppercase;
    letter-spacing:.04em; }}
  .card .v {{ font-size:22px; font-weight:700; margin-top:4px; }}
  section {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:16px 20px; margin-bottom:18px; }}
  h2 {{ margin:0 0 12px; font-size:16px; border-left:3px solid var(--accent);
    padding-left:10px; }}
  details {{ margin:6px 0; }}
  summary {{ cursor:pointer; font-weight:600; }}
  .badge {{ background:var(--accent); color:#fff; border-radius:10px;
    padding:1px 8px; font-size:12px; margin-left:6px; }}
  ul.files {{ margin:8px 0 8px 4px; padding-left:18px; }}
  ul.files li {{ font-family:ui-monospace,monospace; font-size:12.5px;
    color:var(--sub); word-break:break-all; }}
  .tag {{ display:inline-block; padding:2px 10px; border-radius:8px;
    font-size:12px; font-weight:700; }}
  .tag.del {{ background:var(--del); color:#fff; }}
  .tag.keep {{ background:var(--keep); color:#04231a; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--border);
    word-break:break-all; }}
  th {{ color:var(--sub); font-weight:600; }}
</style>
</head>
<body>
  <header><h1>{title}</h1><div class="sub">{subtitle}</div></header>
  {body}
</body>
</html>
"""


# ─── Compresseur ─────────────────────────────────────────────────────────────

class Compressor:
    """Logique de compression principale"""

    TOTAL_STEPS = 7

    def __init__(self, opts: dict, log_fn, progress_fn, status_fn, current_file_fn=None):
        self.opts        = opts
        self.log         = log_fn
        self.set_progress = progress_fn
        self.set_status  = status_fn
        self.set_current_file = current_file_fn or (lambda *_: None)
        self.cancel_flag = threading.Event()
        self.original_size: int | None = None
        self.final_size: int | None = None
        self.reduction: float | None = None
        self.analysis: dict = {}
        self.report_path: str | None = None
        self._tex_cache: dict = {}
        self.lang        = opts.get('lang', 'fr')

    def t(self, key: str, **kwargs) -> str:
        return t(key, self.lang, **kwargs)

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        if self.opts.get('batch'):
            self._run_batch()
            return

        try:
            src = Path(self.opts['source'])
            T = self.TOTAL_STEPS

            self.set_status(self.t('loading_files'))
            files = self._load_files(src)

            if not files:
                self.log(self.t('err_no_files'))
                return

            self.log(self.t('files_loaded', n=len(files)))
            original_size = sum(len(v) for v in files.values())
            self.original_size = original_size
            self.log(self.t('original_size', size=self._fmt_size(original_size)))
            self.log("")

            if self.opts.get('dry_run'):
                self.log(self.t('dry_run_active'))
                self.log("")

            # ── Étape 1 : C-Hands ──────────────────────────────────────────
            self.log(self.t('step_chands', n=1, total=T))
            if self.opts.get('remove_chands') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_chands'))
                removed = self._remove_chands(files)
                self.log(self.t('removed_n', n=removed))
            else:
                self.log(self.t('disabled'))
            self.set_progress(15)

            # ── Étape 2 : Fichiers inutiles ────────────────────────────────
            self.log(self.t('step_unused', n=2, total=T))
            if self.opts.get('remove_unused') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_unused'))
                removed = self._remove_unused(files)
                self.log(self.t('removed_n', n=removed))
            else:
                self.log(self.t('disabled'))
            self.set_progress(25)

            # ── Étape 3 : Vérification des matériaux ───────────────────────
            self.log(self.t('step_materials', n=3, total=T))
            if self.opts.get('check_materials', True) and not self.cancel_flag.is_set():
                self.set_status(self.t('status_materials'))
                self._check_missing_textures(files)
                self._analyze_texture_usage(files)
            else:
                self.log(self.t('disabled'))
            self.set_progress(30)

            # ── Étape 4 : Textures ─────────────────────────────────────────
            self.log(self.t('step_textures', n=4, total=T))
            if self.opts.get('compress_textures') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_textures'))
                if self.opts.get('target_size_mb'):
                    original_files = dict(files)
                    self._run_target_size_mode(files, original_files)
                else:
                    max_res_str = self.opts.get('max_resolution', '1024')
                    quality     = self.opts.get('texture_quality', 85)
                    max_res     = int(max_res_str) if str(max_res_str).isdigit() else None
                    self._optimize_textures(files, max_res, quality)
            else:
                self.log(self.t('disabled'))
            self.set_progress(60)

            # ── Étape 5 : Sons ─────────────────────────────────────────────
            self.log(self.t('step_sounds', n=5, total=T))
            if self.opts.get('compress_sounds') and not self.cancel_flag.is_set():
                if FFMPEG_AVAILABLE:
                    self.set_status(self.t('status_sounds'))
                    self._compress_sounds(files)
                else:
                    self.log(self.t('ffmpeg_missing'))
            else:
                self.log(self.t('disabled'))
            self.set_progress(75)

            # ── Étape 6 : Lua PM ───────────────────────────────────────────
            self.log(self.t('step_lua', n=6, total=T))
            if self.opts.get('gen_lua') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_lua'))
                self._generate_lua(files, Path(self.opts['source']).stem)
            else:
                self.log(self.t('disabled'))
            self.set_progress(85)

            # ── Étape 7 : Écriture ─────────────────────────────────────────
            self.log(self.t('step_write', n=7, total=T))
            if not self.cancel_flag.is_set():
                self.set_status(self.t('status_write'))
                self._write_output(files, src)
            self.set_progress(100)
            self.set_current_file("")

            if not self.cancel_flag.is_set():
                final_size = sum(len(v) for v in files.values())
                reduction  = (1 - final_size / original_size) * 100 if original_size > 0 else 0
                self.final_size = final_size
                self.reduction  = reduction
                self.log("")
                self.log(self.t('final_size', size=self._fmt_size(final_size)))
                self.log(self.t('final_reduction', pct=f"{reduction:.1f}"))
                if self.opts.get('gen_report', True):
                    self._write_html_report(files, src)
                self.log(self.t('success'))
                self.set_status(self.t('status_done'))
            else:
                self.log(self.t('cancelled'))
                self.set_status(self.t('status_cancelled'))

        except Exception as e:
            import traceback
            self.log(self.t('error_generic', e=e))
            self.log(traceback.format_exc())
            self.set_status(self.t('status_error'))

    # ── Chargement ───────────────────────────────────────────────────────────

    def _load_files(self, src: Path) -> dict:
        files = {}
        if self.opts.get('source_type') == 'gma':
            gma = GMAFile()
            gma.load(str(src))
            files['__meta__'] = json.dumps({
                'name': gma.name,
                'description': gma.description,
                'author': gma.author,
            }).encode()
            for name, data in gma.files.items():
                files[name.replace('\\', '/').lower()] = data
        else:
            for fp in src.rglob('*'):
                if fp.is_file():
                    key = str(fp.relative_to(src)).replace('\\', '/').lower()
                    files[key] = fp.read_bytes()
        return files

    # ── Filtres ───────────────────────────────────────────────────────────────

    def _remove_chands(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            for pattern in CHAND_PATTERNS:
                if re.match(pattern, path, re.IGNORECASE):
                    to_remove.append(path)
                    self.log(self.t('removed_chand', path=path))
                    break
        for p in to_remove:
            del files[p]
        return len(to_remove)

    def _remove_unused(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            if Path(path).suffix.lower() in USELESS_EXTENSIONS:
                to_remove.append(path)
                self.log(self.t('removed_unused_file', path=path))
        for p in to_remove:
            del files[p]
        return len(to_remove)

    # ── Vérification des matériaux ───────────────────────────────────────────

    @staticmethod
    def _resolve_vtf_path(ref: str) -> str:
        return resolve_material_ref(ref)

    def _check_missing_textures(self, files: dict) -> None:
        vmt_files = {k: v for k, v in files.items() if k.endswith('.vmt')}
        if not vmt_files:
            self.log(self.t('no_vmt'))
            return

        existing = set(files.keys())
        pattern = re.compile(r'\$(\w+)"?\s+"([^"]*)"', re.IGNORECASE)
        missing_total = 0
        checked = 0

        for vmt_path, data in vmt_files.items():
            if self.cancel_flag.is_set():
                break
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                continue
            checked += 1
            seen_refs = set()
            for m in pattern.finditer(text):
                key = m.group(1).lower()
                if key not in VMT_TEXTURE_KEYS:
                    continue
                ref = m.group(2).strip()
                if not ref or ref.lower() == 'env_cubemap':
                    continue
                tex_path = self._resolve_vtf_path(ref)
                if not tex_path or tex_path in seen_refs:
                    continue
                seen_refs.add(tex_path)
                if tex_path not in existing:
                    self.log(self.t('missing_texture', texture=tex_path, vmt=vmt_path))
                    missing_total += 1

        if missing_total == 0:
            self.log(self.t('missing_textures_none', n=checked))
        else:
            self.log(self.t('missing_textures_found', n=missing_total))

    # ── Classification / rôles des textures ──────────────────────────────────

    @staticmethod
    def _classify_texture_role(path: str) -> str:
        """Devine le rôle d'une texture d'après son nom de fichier."""
        name = path.lower()
        # Cartes techniques : prioritaires car elles peuvent contenir un mot-clé
        # de rôle (ex. head_normal) mais restent avant tout des cartes.
        stem = name.rsplit('/', 1)[-1]
        stem = stem.rsplit('.', 1)[0]
        if stem.endswith(NORMALMAP_HINTS):
            return 'role_normalmap'
        if stem.endswith(EFFECTMAP_HINTS):
            return 'role_effectmap'
        for role, keywords in TEXTURE_ROLE_KEYWORDS:
            if any(kw in name for kw in keywords):
                return role
        return 'role_other'

    def _analyze_texture_usage(self, files: dict) -> None:
        """Analyse complète : rôles, orphelins (.vtf/.vmt), doublons et audit.

        Remplit self.analysis (consommé par le rapport HTML) et applique les
        suppressions si l'option remove_unused_textures est active."""
        tex_files = {k: v for k, v in files.items()
                     if k != '__meta__' and Path(k).suffix.lower() in TEXTURE_EXTENSIONS}
        if not tex_files:
            self.log(self.t('classify_none'))
            self.analysis = {}
            return

        # ── 1) Classement par rôle ──
        by_role: dict[str, list[str]] = {}
        for path in sorted(tex_files):
            by_role.setdefault(self._classify_texture_role(path), []).append(path)

        self.log(self.t('classify_header'))
        role_order = [r for r, _ in TEXTURE_ROLE_KEYWORDS]
        role_order += ['role_normalmap', 'role_effectmap', 'role_other']
        for role in role_order:
            items = by_role.get(role)
            if not items:
                continue
            self.log(self.t('classify_line', role=self.t(role), n=len(items)))
            for path in items:
                self.log(self.t('classify_item', path=path))

        remove = self.opts.get('remove_unused_textures', False)
        graph = build_dependency_graph(files)

        # ── 2) Textures .vtf inutilisées ──
        if not any(k.endswith('.vmt') for k in files):
            self.log(self.t('unused_tex_no_vmt'))
            orphan_vtf = []
        else:
            orphan_vtf = graph['orphan_vtf']
            if not orphan_vtf:
                self.log(self.t('unused_tex_none'))
            else:
                size_total = sum(len(files[k]) for k in orphan_vtf)
                self.log(self.t('unused_tex_header'))
                for path in orphan_vtf:
                    size = self._fmt_size(len(files[path]))
                    key = 'unused_tex_removed' if remove else 'unused_tex_item'
                    self.log(self.t(key, path=path, size=size))
                if remove:
                    for path in orphan_vtf:
                        del files[path]
                    self.log(self.t('unused_tex_deleted', n=len(orphan_vtf),
                                     size=self._fmt_size(size_total)))
                else:
                    self.log(self.t('unused_tex_found', n=len(orphan_vtf),
                                     size=self._fmt_size(size_total)))

        # ── 3) Matériaux .vmt orphelins (non référencés par un .mdl) ──
        orphan_vmt = graph['orphan_vmt']
        if orphan_vmt:
            size_total = sum(len(files[k]) for k in orphan_vmt if k in files)
            self.log(self.t('orphan_vmt_header'))
            for path in orphan_vmt:
                if path not in files:
                    continue
                size = self._fmt_size(len(files[path]))
                key = 'orphan_vmt_removed' if remove else 'orphan_vmt_item'
                self.log(self.t(key, path=path, size=size))
            if remove:
                for path in orphan_vmt:
                    files.pop(path, None)
                self.log(self.t('orphan_vmt_deleted', n=len(orphan_vmt),
                                 size=self._fmt_size(size_total)))
            else:
                self.log(self.t('orphan_vmt_found', n=len(orphan_vmt),
                                 size=self._fmt_size(size_total)))

        # ── 4) Doublons exacts ──
        duplicates = find_duplicate_textures(files)
        if not duplicates:
            self.log(self.t('dup_none'))
        else:
            self.log(self.t('dup_header'))
            recoverable = 0
            for group in duplicates:
                each = len(files[group[0]])
                recoverable += each * (len(group) - 1)
                self.log(self.t('dup_group', n=len(group), size=self._fmt_size(each)))
                for path in group:
                    self.log(self.t('dup_item', path=path))
            self.log(self.t('dup_summary', groups=len(duplicates),
                             size=self._fmt_size(recoverable)))

        # ── 5) Audit qualité ──
        max_res_str = self.opts.get('max_resolution', '1024')
        max_res = int(max_res_str) if str(max_res_str).isdigit() else None
        issues = audit_textures(files, max_res)
        if not issues:
            self.log(self.t('audit_none'))
        else:
            self.log(self.t('audit_header'))
            for it in issues:
                self.log(self.t(it['issue'], path=it['path'], detail=it['detail']))
            self.log(self.t('audit_summary', n=len(issues)))

        # Résultats structurés pour le rapport HTML.
        self.analysis = {
            'roles': {r: list(by_role.get(r, [])) for r in role_order if by_role.get(r)},
            'orphan_vtf': list(orphan_vtf),
            'orphan_vmt': list(orphan_vmt),
            'duplicates': duplicates,
            'audit': issues,
            'removed': remove,
        }

    # ── Rapport HTML ──────────────────────────────────────────────────────────

    def _build_report_dict(self, files: dict, addon_name: str) -> dict:
        a = self.analysis or {}
        audit_lbl = {
            'audit_oversized':    self.t('report_audit_oversized'),
            'audit_uncompressed': self.t('report_audit_uncompressed'),
            'audit_npot':         self.t('report_audit_npot'),
        }
        roles = [(self.t(role), items) for role, items in a.get('roles', {}).items()]
        orphans = list(a.get('orphan_vtf', [])) + list(a.get('orphan_vmt', []))
        audit = [{'path': it['path'], 'label': audit_lbl.get(it['issue'], it['issue']),
                  'detail': it['detail']} for it in a.get('audit', [])]

        reduction = f"-{self.reduction:.1f}%" if self.reduction is not None else '—'
        return {
            'title': self.t('report_title', name=addon_name),
            'subtitle': self.t('report_subtitle'),
            'removed': a.get('removed', False),
            'summary': {
                'original': self._fmt_size(self.original_size or 0),
                'final': self._fmt_size(self.final_size or 0),
                'reduction': reduction,
                'files': str(sum(1 for k in files if k != '__meta__')),
            },
            'roles': roles,
            'orphans': orphans,
            'duplicates': a.get('duplicates', []),
            'audit': audit,
            'labels': {
                'original': self.t('report_sum_original'),
                'final': self.t('report_sum_final'),
                'saved': self.t('report_sum_saved'),
                'files': self.t('report_sum_files'),
                'sec_roles': self.t('report_sec_roles'),
                'sec_orphans': self.t('report_sec_orphans'),
                'sec_dups': self.t('report_sec_dups'),
                'sec_audit': self.t('report_sec_audit'),
                'col_texture': self.t('report_col_texture'),
                'col_issue': self.t('report_col_issue'),
                'col_detail': self.t('report_col_detail'),
                'removed': self.t('report_removed_badge'),
                'kept': self.t('report_kept_badge'),
                'empty': self.t('report_empty'),
            },
        }

    def _write_html_report(self, files: dict, src: Path) -> None:
        if self.opts.get('dry_run'):
            return
        try:
            out = Path(self.opts['output'])
            fmt = self.opts.get('output_format', 'folder')
            if fmt == 'folder':
                out.mkdir(parents=True, exist_ok=True)
                report_path = out / 'rapport_compression.html'
            else:
                stem = out.stem or 'addon'
                report_path = out.parent / (stem + '_rapport.html')
            html = build_html_report(self._build_report_dict(files, src.stem))
            report_path.write_text(html, encoding='utf-8')
            self.report_path = str(report_path)
            self.log(self.t('report_written', path=report_path))
        except Exception:
            pass  # le rapport ne doit jamais faire échouer la compression

    # ── Textures ──────────────────────────────────────────────────────────────

    def _optimize_textures(self, files: dict, max_res, quality: int, quiet: bool = False) -> None:
        tex_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in TEXTURE_EXTENSIONS and k != '__meta__'}

        if not tex_files:
            if not quiet:
                self.log(self.t('no_textures'))
            return

        if not quiet:
            self.log(self.t('textures_found', n=len(tex_files)))
            if max_res is None:
                self.log(self.t('no_res_limit'))
            elif not VTFLIB_AVAILABLE:
                self.log(self.t('no_vtflib', max_res=max_res))

        total = len(tex_files)
        reduced = 0
        unchanged_vtf = 0

        for i, (path, data) in enumerate(tex_files.items()):
            if self.cancel_flag.is_set():
                break

            if not quiet:
                self.set_current_file(path)
            ext = Path(path).suffix.lower()
            new_data = None

            # Cache mémoire : deux textures identiques (doublons) ou les
            # multiples passes du mode « taille cible » ne sont traitées qu'une
            # fois pour un jeu de paramètres donné.
            cache_key = (hash(data), ext, max_res, quality)
            if cache_key in self._tex_cache:
                new_data = self._tex_cache[cache_key]
            else:
                try:
                    if ext == '.vtf':
                        new_data = self._process_vtf(path, data, max_res, quality)
                    elif PIL_AVAILABLE and ext in {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}:
                        new_data = self._process_image_pil(path, data, ext, max_res, quality)
                except Exception as e:
                    # Un fichier corrompu ou non pris en charge ne doit jamais
                    # interrompre toute la compression : on le conserve tel quel.
                    if not quiet:
                        self.log(self.t('texture_error', path=path, e=e))
                    new_data = None
                self._tex_cache[cache_key] = new_data

            if new_data and len(new_data) < len(data):
                savings = len(data) - len(new_data)
                if not quiet:
                    self.log(self.t('texture_saving', path=path, size=self._fmt_size(savings)))
                files[path] = new_data
                reduced += 1
            elif ext == '.vtf':
                unchanged_vtf += 1

            if not quiet:
                self.set_progress(30 + (i / total) * 30)

        if not quiet:
            self.log(self.t('textures_reduced', reduced=reduced, total=total))
            if unchanged_vtf:
                self.log(self.t('vtf_unchanged', n=unchanged_vtf))

    # ── Mode taille cible ────────────────────────────────────────────────────

    def _target_size_steps(self) -> list[tuple[int | None, int]]:
        max_res_str = self.opts.get('max_resolution', '1024')
        quality     = int(self.opts.get('texture_quality', 85))
        base_res    = int(max_res_str) if str(max_res_str).isdigit() else None

        all_res = [2048, 1024, 512, 256, 128]
        res_list = [r for r in all_res if base_res is None or r <= base_res]
        if base_res is not None and base_res not in res_list:
            res_list.insert(0, base_res)
        if not res_list:
            res_list = [128]

        qual_list = sorted({q for q in (quality, 75, 60, 45, 30) if 10 <= q <= 100}, reverse=True)

        steps: list[tuple[int | None, int]] = []
        for res in res_list:
            for q in qual_list:
                if (res, q) not in steps:
                    steps.append((res, q))
        return steps

    def _run_target_size_mode(self, files: dict, original_files: dict) -> None:
        target_bytes = int(self.opts['target_size_mb'] * 1024 * 1024)
        self.log(self.t('step_target_size', size=self._fmt_size(target_bytes)))

        steps = self._target_size_steps()
        chosen = steps[-1]
        chosen_size = None

        for i, (res, quality) in enumerate(steps, 1):
            if self.cancel_flag.is_set():
                return
            trial = dict(original_files)
            self._optimize_textures(trial, res, quality, quiet=True)
            size = sum(len(v) for v in trial.values())
            res_label = f"{res}px" if res else self.t('no_limit')
            self.log(self.t('target_attempt', n=i, res=res_label, q=quality, size=self._fmt_size(size)))
            chosen, chosen_size = (res, quality), size
            if size <= target_bytes:
                break

        files.clear()
        files.update(original_files)
        self._optimize_textures(files, chosen[0], chosen[1])

        if chosen_size is not None and chosen_size <= target_bytes:
            self.log(self.t('target_reached', size=self._fmt_size(chosen_size), target=self._fmt_size(target_bytes)))
        else:
            self.log(self.t('target_not_reached', size=self._fmt_size(chosen_size or 0), target=self._fmt_size(target_bytes)))

    def _process_vtf(self, path: str, data: bytes, max_res, quality: int) -> bytes:
        if VTFLIB_AVAILABLE:
            try:
                return self._process_vtf_vtflib(data, max_res, quality)
            except Exception:
                pass
        # Sans VTFLib : réduction de résolution par troncature des mipmaps
        return self._process_vtf_mipstrip(data, max_res)

    def _process_vtf_vtflib(self, data: bytes, max_res, quality: int) -> bytes:
        lib = vtflib.VTFLib()
        lib.image_load_lump(data)
        w, h = lib.width(), lib.height()
        if max_res and (w > max_res or h > max_res):
            new_w = min(w, max_res)
            new_h = min(h, max_res)
            lib.image_resize(new_w, new_h)

        # Recompression de format : un .vtf stocké en RGBA8888/BGR888… pèse
        # 4 à 6× un DXT équivalent, sans différence visible en jeu. On tente la
        # conversion de façon défensive (l'API vtflib varie selon les versions).
        if self.opts.get('convert_uncompressed', True):
            self._try_convert_dxt(lib, data)

        return bytes(lib.image_save_lump())

    @staticmethod
    def _try_convert_dxt(lib, original: bytes) -> None:
        """Convertit une texture non compressée vers DXT1/DXT5 si possible.

        Best-effort : toute incompatibilité d'API laisse l'image inchangée."""
        info = read_vtf_info(original)
        if not info or info['format_name'] not in VTF_UNCOMPRESSED_FORMATS:
            return
        try:
            fmt_enum = getattr(vtflib, 'VTFImageFormat', None)
            convert = getattr(lib, 'image_convert', None)
            if fmt_enum is None or convert is None:
                return
            # Alpha présent -> DXT5 (préserve la transparence), sinon DXT1.
            has_alpha = bool(getattr(lib, 'image_has_alpha', lambda: True)())
            target_name = 'IMAGE_FORMAT_DXT5' if has_alpha else 'IMAGE_FORMAT_DXT1'
            target = getattr(fmt_enum, target_name, None)
            if target is not None:
                convert(target)
        except Exception:
            # On ne compromet jamais la compression pour un échec de conversion.
            pass

    def _process_vtf_mipstrip(self, data: bytes, max_res) -> bytes:
        """Réduit la résolution d'un VTF en supprimant les mipmaps les plus
        grands, sans dépendance externe. Ne touche pas aux fichiers dont la
        structure n'est pas reconnue (cubemaps, multi-frames, etc.)."""
        if max_res is None:
            return data
        try:
            if data[:4] != b'VTF\x00' or len(data) < 80:
                return data

            ver_maj, ver_min, header_size = struct.unpack_from('<III', data, 4)
            if ver_maj != 7:
                return data

            width, height = struct.unpack_from('<HH', data, 16)
            flags = struct.unpack_from('<I', data, 20)[0]
            frames = struct.unpack_from('<H', data, 24)[0]
            high_fmt = struct.unpack_from('<i', data, 52)[0]
            mipmap_count = data[56]
            low_fmt = struct.unpack_from('<i', data, 57)[0]
            low_w, low_h = data[61], data[62]

            TEXTUREFLAGS_ENVMAP = 0x4000
            if frames != 1 or (flags & TEXTUREFLAGS_ENVMAP):
                return data  # cubemaps / multi-frames : trop risqué
            if width == 0 or height == 0 or mipmap_count <= 1:
                return data
            if max(width, height) <= max_res:
                return data  # déjà sous la limite
            if high_fmt not in VTF_FORMAT_SIZES:
                return data

            depth = 1
            if (ver_maj, ver_min) >= (7, 2) and len(data) >= 65:
                depth = struct.unpack_from('<H', data, 63)[0] or 1
            if depth != 1:
                return data

            # Localiser le début des données haute résolution
            if (ver_maj, ver_min) >= (7, 3):
                if len(data) < 72:
                    return data
                num_res = struct.unpack_from('<I', data, 68)[0]
                high_res_offset = None
                for i in range(num_res):
                    off = 72 + i * 8
                    if off + 8 > len(data):
                        return data
                    tag = data[off:off + 3]
                    if tag == b'\x30\x00\x00':
                        high_res_offset = struct.unpack_from('<I', data, off + 4)[0]
                if high_res_offset is None:
                    return data
            else:
                low_size = 0
                if low_fmt != -1 and low_w and low_h:
                    low_size = _vtf_format_size(low_fmt, low_w, low_h) or 0
                high_res_offset = header_size + low_size

            if high_res_offset >= len(data):
                return data

            # Taille de chaque mip, du plus petit au plus grand (ordre de stockage)
            mip_sizes = []
            for m in range(mipmap_count - 1, -1, -1):
                mw = max(1, width >> m)
                mh = max(1, height >> m)
                sz = _vtf_format_size(high_fmt, mw, mh)
                if sz is None:
                    return data
                mip_sizes.append((m, mw, mh, sz))

            total_high_res = len(data) - high_res_offset
            if sum(s for _, _, _, s in mip_sizes) != total_high_res:
                return data  # structure inattendue : on ne touche pas au fichier

            # Trouver le plus grand mip qui respecte max_res
            keep = 0
            target = None
            for m, mw, mh, sz in mip_sizes:
                if max(mw, mh) > max_res:
                    break
                keep += sz
                target = (m, mw, mh, keep)

            if target is None or target[0] == 0:
                return data  # pas de réduction utile

            new_mip_level, new_w, new_h, new_high_res_size = target
            new_mipmap_count = mipmap_count - new_mip_level

            out = bytearray(data[:high_res_offset + new_high_res_size])
            struct.pack_into('<HH', out, 16, new_w, new_h)
            out[56] = new_mipmap_count
            return bytes(out)

        except (struct.error, IndexError):
            return data

    def _process_image_pil(self, path: str, data: bytes, ext: str,
                            max_res, quality: int) -> bytes:
        try:
            import io
            img = Image.open(io.BytesIO(data))
            if max_res and (img.width > max_res or img.height > max_res):
                img.thumbnail((max_res, max_res), Image.LANCZOS)
            buf = io.BytesIO()
            if ext in ('.jpg', '.jpeg'):
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(buf, format='JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                compress_level = max(0, min(9, int((100 - quality) / 11)))
                img.save(buf, format='PNG', compress_level=compress_level, optimize=True)
            else:
                img.save(buf, format='PNG', optimize=True)
            return buf.getvalue()
        except Exception:
            return data

    # ── Sons ─────────────────────────────────────────────────────────────────

    def _compress_sounds(self, files: dict) -> None:
        bitrate = self.opts.get('sound_quality', '128k')
        snd_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in SOUND_EXTENSIONS and k != '__meta__'}

        if not snd_files:
            self.log(self.t('no_sounds'))
            return

        self.log(self.t('sounds_found', n=len(snd_files)))

        for path, data in snd_files.items():
            if self.cancel_flag.is_set():
                break
            self.set_current_file(path)
            ext = Path(path).suffix.lower()
            # Toujours convertir en .mp3 avec le bitrate choisi
            out_ext = '.mp3'
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                tf.write(data)
                tmp_in = tf.name
            tmp_out = tmp_in + out_ext
            try:
                result = subprocess.run(
                    ['ffmpeg', '-y', '-i', tmp_in, '-b:a', bitrate,
                     '-map_metadata', '-1', tmp_out],
                    capture_output=True, timeout=60,
                )
                if result.returncode == 0:
                    new_data = Path(tmp_out).read_bytes()
                    if len(new_data) < len(data):
                        new_key = path.rsplit('.', 1)[0] + out_ext
                        del files[path]
                        files[new_key] = new_data
                        savings = len(data) - len(new_data)
                        self.log(self.t('sound_saving', path=path, new_path=new_key, size=self._fmt_size(savings)))
            except Exception as e:
                self.log(self.t('sound_error', path=path, e=e))
            finally:
                for tmp in (tmp_in, tmp_out):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    # ── Génération Lua ────────────────────────────────────────────────────────

    def _generate_lua(self, files: dict, addon_stem: str) -> None:
        """Génère ou met à jour le fichier Lua d'enregistrement du playermodel."""

        # 1. Trouver les .mdl candidats (hors armes et LOD), de préférence
        #    dans models/player/ ; sinon n'importe où ailleurs dans models/
        def is_mdl(p):
            return (p.startswith('models/') and p.endswith('.mdl')
                    and not p.startswith('models/weapons/')
                    and not re.search(r'_lod\d+\.mdl$', p))

        all_mdls = sorted(p for p in files if is_mdl(p))
        pm_models = [p for p in all_mdls if p.startswith('models/player/')]

        if not pm_models and all_mdls:
            self.log(self.t('lua_no_models_player'))
            pm_models = all_mdls

        if not pm_models:
            self.log(self.t('lua_no_models'))
            return

        for p in pm_models:
            self.log(self.t('lua_model_detected', path=p))

        self.log(self.t('lua_models_found', n=len(pm_models)))

        # 2. Trouver les c_hands encore présents dans les fichiers
        chand_mdls = [
            p for p in files
            if re.match(r'models/weapons/c_.*\.mdl', p, re.IGNORECASE)
        ]
        include_chands = self.opts.get('lua_chands', True) and bool(chand_mdls)

        # 3. Vérifier s'il existe déjà un fichier Lua avec AddValidModel
        existing_path: str | None = None
        for path, data in files.items():
            if not path.endswith('.lua'):
                continue
            try:
                if b'AddValidModel' in data or b'player_manager' in data:
                    existing_path = path
                    break
            except Exception:
                pass

        # 4. Construire le contenu Lua
        safe_stem = re.sub(r'[^a-z0-9]', '_', addon_stem.lower()).strip('_') or 'pm'
        lines: list[str] = [
            '-- Généré automatiquement par Compressez PM GMod',
            f'-- Addon : {addon_stem}',
            '',
        ]

        for mdl in pm_models:
            display = Path(mdl).stem.replace('_', ' ').replace('-', ' ').title()
            var      = re.sub(r'[^A-Z0-9]', '_', Path(mdl).stem.upper()).strip('_')
            lines += [
                f'local MDL_{var} = "{mdl}"',
                f'player_manager.AddValidModel("{display}", MDL_{var})',
            ]

            if include_chands:
                # Chercher le c_hands le plus proche par nom
                stem = Path(mdl).stem.lower()
                match = next(
                    (c for c in chand_mdls
                     if stem in c or c.replace('models/weapons/c_arms_', '').split('.')[0] in stem),
                    chand_mdls[0] if chand_mdls else None,
                )
                if match:
                    lines += [
                        '',
                        'if CLIENT then',
                        f'    hook.Add("PlayerSetHandsModel", "chands_{var}", function(ply, ent)',
                        f'        if ply:GetModel() == MDL_{var} then',
                        f'            ent:SetModel("{match}")',
                        f'            ent:SetSkin(ply:GetSkin())',
                        f'            ent:SetBodyGroups(ply:GetBodygroupsString())',
                        f'        end',
                        f'    end)',
                        'end',
                    ]

            lines.append('')

        lua_bytes = '\n'.join(lines).encode('utf-8')

        if existing_path:
            files[existing_path] = lua_bytes
            self.log(self.t('lua_updated', path=existing_path))
        else:
            new_path = f'lua/autorun/sh_{safe_stem}_pm.lua'
            files[new_path] = lua_bytes
            self.log(self.t('lua_created', path=new_path))

    # ── Écriture ─────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_output_path(output: Path, fmt: str) -> Path:
        if fmt == 'gma':
            return output if output.suffix == '.gma' else output.with_suffix('.gma')
        if fmt == 'zip':
            return output if output.suffix == '.zip' else output.with_suffix('.zip')
        return output

    def _backup_existing(self, output: Path, fmt: str) -> None:
        target = self._resolve_output_path(output, fmt)
        if not target.exists():
            return

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        try:
            if target.is_dir():
                backup_path = target.parent / f"{target.name}_backup_{timestamp}"
                shutil.copytree(target, backup_path)
            else:
                backup_path = target.with_name(f"{target.stem}_backup_{timestamp}{target.suffix}")
                shutil.copy2(target, backup_path)
            self.log(self.t('backup_created', path=backup_path))
        except Exception as e:
            self.log(self.t('backup_failed', e=e))

    def _write_output(self, files: dict, src: Path) -> None:
        output  = Path(self.opts['output'])
        fmt     = self.opts.get('output_format', 'folder')
        zip_lvl = self.opts.get('zip_level', 6)

        meta = None
        if '__meta__' in files:
            try:
                meta = json.loads(files['__meta__'].decode())
            except Exception:
                pass
        out_files = {k: v for k, v in files.items() if k != '__meta__'}

        if self.opts.get('dry_run'):
            if fmt == 'folder':
                self.log(self.t('dry_run_would_write_folder', path=output, n=len(out_files)))
            elif fmt == 'gma':
                self.log(self.t('dry_run_would_write_gma', path=self._resolve_output_path(output, fmt)))
            elif fmt == 'zip':
                self.log(self.t('dry_run_would_write_zip', path=self._resolve_output_path(output, fmt)))
            return

        if self.opts.get('backup_original'):
            self._backup_existing(output, fmt)

        if fmt == 'folder':
            output.mkdir(parents=True, exist_ok=True)
            for path, data in out_files.items():
                dest = output / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            self.log(self.t('write_folder', path=output))

        elif fmt == 'gma':
            gma = GMAFile()
            if meta:
                gma.name        = meta.get('name', src.stem)
                gma.description = meta.get('description', '')
                gma.author      = meta.get('author', '')
            else:
                gma.name = src.stem
                if 'addon.json' in out_files:
                    try:
                        info = json.loads(out_files['addon.json'].decode())
                        gma.name        = info.get('title', src.stem)
                        gma.description = info.get('description', '')
                    except Exception:
                        pass
            # Le format GMA utilise des forward slashes même sur Windows
            gma.files = out_files
            out_path = self._resolve_output_path(output, fmt)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gma.save(str(out_path))
            self.log(self.t('write_gma', path=out_path))

        elif fmt == 'zip':
            out_path = self._resolve_output_path(output, fmt)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(out_path), 'w',
                                 zipfile.ZIP_DEFLATED,
                                 compresslevel=zip_lvl) as zf:
                for path, data in out_files.items():
                    zf.writestr(path, data)
            self.log(self.t('write_zip', path=out_path))

    # ── Mode batch ───────────────────────────────────────────────────────────

    def _run_batch(self) -> None:
        src = Path(self.opts['source'])

        addons: list[tuple[str, Path]] = []
        if src.is_dir():
            for item in sorted(src.iterdir()):
                if item.is_dir():
                    addons.append(('folder', item))
                elif item.suffix.lower() == '.gma':
                    addons.append(('gma', item))

        if not addons:
            self.log(self.t('batch_none'))
            return

        self.log(self.t('batch_found', n=len(addons), path=src))
        self.log("")

        output_root = Path(self.opts['output'])
        fmt = self.opts.get('output_format', 'folder')
        n = len(addons)
        results: list[tuple[str, int, float]] = []

        for i, (stype, path) in enumerate(addons, 1):
            if self.cancel_flag.is_set():
                break

            name = path.stem
            self.log(self.t('batch_processing', i=i, n=n, name=name))

            sub_opts = dict(self.opts)
            sub_opts['source'] = str(path)
            sub_opts['source_type'] = stype
            sub_opts['batch'] = False
            if fmt == 'folder':
                sub_opts['output'] = str(output_root / name)
            else:
                ext = '.gma' if fmt == 'gma' else '.zip'
                sub_opts['output'] = str(output_root / (name + ext))

            def progress_wrap(v, i=i):
                self.set_progress((i - 1 + v / 100) / n * 100)

            sub = Compressor(
                sub_opts,
                log_fn=self.log,
                progress_fn=progress_wrap,
                status_fn=self.set_status,
                current_file_fn=self.set_current_file,
            )
            sub.run()
            if sub.final_size is not None:
                results.append((name, sub.final_size, sub.reduction or 0.0))
            self.log("")

        self.set_progress(100)
        self.set_current_file("")

        if results:
            self.log(self.t('batch_summary_header'))
            for name, size, reduction in results:
                self.log(self.t('batch_summary_line', name=name,
                                 size=self._fmt_size(size), pct=f"{reduction:.1f}"))
            self.log("")

        self.log(self.t('batch_done', n=len(results)))
        self.set_status(self.t('status_done'))

    # ── Utilitaires ──────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} To"


# ─── Interface graphique ──────────────────────────────────────────────────────

# Palettes de thème : Catppuccin Mocha (sombre) / Catppuccin Latte (clair)
THEMES = {
    'dark': {
        'BG': '#1e1e2e', 'FG': '#cdd6f4', 'ACCENT': '#89b4fa', 'SUB': '#6c7086',
        'SURFACE': '#313244', 'GREEN': '#a6e3a1', 'RED': '#f38ba8', 'YELLOW': '#f9e2af',
        'LOG_BG': '#11111b', 'ACCENT_ACTIVE': '#74c7ec', 'BTN_ACTIVE': '#45475a',
    },
    'light': {
        'BG': '#eff1f5', 'FG': '#4c4f69', 'ACCENT': '#1e66f5', 'SUB': '#8c8fa1',
        'SURFACE': '#ccd0da', 'GREEN': '#40a02b', 'RED': '#d20f39', 'YELLOW': '#df8e1d',
        'LOG_BG': '#e6e9ef', 'ACCENT_ACTIVE': '#7287fd', 'BTN_ACTIVE': '#bcc0cc',
    },
}


class App:

    # Profils rapides : ajustent automatiquement les options ci-dessous
    PRESETS: dict[str, dict | None] = {
        'custom': None,
        'balanced': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '1024', 'quality': 85, 'compress_sounds': False,
            'sound_quality': '128k', 'zip_level': 6,
        },
        'quality': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': 'none', 'quality': 100, 'compress_sounds': False,
            'sound_quality': '320k', 'zip_level': 4,
        },
        'minimal': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '512', 'quality': 60, 'compress_sounds': True,
            'sound_quality': '96k', 'zip_level': 9,
        },
        'share': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '256', 'quality': 50, 'compress_sounds': True,
            'sound_quality': '64k', 'zip_level': 9,
        },
    }

    def __init__(self):
        saved = self._load_config()
        self.lang = saved.get('lang', 'fr') if saved else 'fr'
        self.theme_name = saved.get('theme_name', 'dark') if saved else 'dark'
        self._apply_palette()

        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title(f"Compressez PM GMod  v{VERSION}")
        self.root.geometry("820x950")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)
        self.root.minsize(700, 760)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._compressor: Compressor | None = None
        self._thread: threading.Thread | None = None

        self._setup_styles()
        self._build_ui()
        if saved:
            self._restore_state(saved)
        self._log_header()

    # ── Internationalisation / thème ──────────────────────────────────────────

    def t(self, key: str, **kwargs) -> str:
        return t(key, self.lang, **kwargs)

    def _apply_palette(self):
        palette = THEMES[self.theme_name]
        for k, v in palette.items():
            setattr(self, k, v)

    def _profile_label(self, pid: str) -> str:
        return self.t(f'profile_{pid}')

    # ── Styles ───────────────────────────────────────────────────────────────

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use('clam')

        s.configure('.', background=self.BG, foreground=self.FG,
                    bordercolor=self.SURFACE, relief='flat')
        s.configure('TFrame',          background=self.BG)
        s.configure('TLabel',          background=self.BG, foreground=self.FG)
        s.configure('TLabelframe',     background=self.BG, bordercolor=self.SURFACE)
        s.configure('TLabelframe.Label', background=self.BG, foreground=self.ACCENT,
                    font=('Segoe UI', 9, 'bold'))
        s.configure('TCheckbutton',    background=self.BG, foreground=self.FG)
        s.configure('TRadiobutton',    background=self.BG, foreground=self.FG)
        s.configure('TEntry',          fieldbackground=self.SURFACE, foreground=self.FG,
                    bordercolor=self.SURFACE, insertcolor=self.FG)
        s.configure('TButton',         background=self.SURFACE, foreground=self.FG,
                    bordercolor=self.SURFACE, padding=(8, 4))
        s.configure('TCombobox',       fieldbackground=self.SURFACE, foreground=self.FG,
                    selectbackground=self.ACCENT, selectforeground=self.BG)
        s.configure('TScale',          background=self.BG, troughcolor=self.SURFACE)
        s.configure('TProgressbar',    background=self.ACCENT, troughcolor=self.SURFACE,
                    bordercolor=self.SURFACE, thickness=12)
        s.configure('Accent.TButton',  background=self.ACCENT, foreground=self.BG,
                    font=('Segoe UI', 9, 'bold'), padding=(14, 5))
        s.configure('TNotebook',       background=self.BG, bordercolor=self.SURFACE)
        s.configure('TNotebook.Tab',   background=self.SURFACE, foreground=self.FG,
                    padding=(12, 5), font=('Segoe UI', 9))

        s.map('Accent.TButton',  background=[('active', self.ACCENT_ACTIVE)])
        s.map('TButton',         background=[('active', self.BTN_ACTIVE)])
        s.map('TCheckbutton',    background=[('active', self.BG)])
        s.map('TRadiobutton',    background=[('active', self.BG)])
        s.map('TCombobox',       fieldbackground=[('readonly', self.SURFACE)])
        s.map('TNotebook.Tab',   background=[('selected', self.ACCENT)],
                                  foreground=[('selected', self.BG)])

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        # En-tête
        hdr = tk.Frame(self.root, bg=self.SURFACE, pady=10)
        hdr.pack(fill='x')

        title_box = tk.Frame(hdr, bg=self.SURFACE)
        title_box.pack(side='left', padx=14)

        title_row = tk.Frame(title_box, bg=self.SURFACE)
        title_row.pack(anchor='w')
        tk.Label(title_row, text="🗜️", bg=self.SURFACE, fg=self.ACCENT,
                 font=('Segoe UI', 16)).pack(side='left', padx=(0, 6))
        tk.Label(title_row, text="Compressez PM GMod",
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        tk.Label(title_row, text=f"  v{VERSION}",
                 bg=self.SURFACE, fg=self.SUB,
                 font=('Segoe UI', 9)).pack(side='left')

        tk.Label(title_box, text=self.t('app_tagline'),
                 bg=self.SURFACE, fg=self.SUB,
                 font=('Segoe UI', 8)).pack(anchor='w')

        theme_key = 'btn_theme_light' if self.theme_name == 'dark' else 'btn_theme_dark'
        ttk.Button(hdr, text=self.t(theme_key), command=self._toggle_theme,
                   width=14).pack(side='right', padx=(0, 14))
        lang_text = "English" if self.lang == 'fr' else "Français"
        ttk.Button(hdr, text=lang_text, command=self._toggle_language,
                   width=10).pack(side='right', padx=(0, 6))
        ttk.Button(hdr, text=self.t('btn_about'), command=self._show_about,
                   width=11).pack(side='right', padx=(0, 6))

        tk.Frame(self.root, bg=self.ACCENT, height=2).pack(fill='x')

        # Corps principal avec scroll
        main = ttk.Frame(self.root, padding=(10, 8, 10, 10))
        main.pack(fill='both', expand=True)

        self._build_io_section(main)
        self._build_options_section(main)
        self._build_progress_section(main)
        self._build_log_section(main)
        self._build_buttons(main)

    def _build_io_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('io_section'), padding=8)
        frm.pack(fill='x', pady=(0, 6))

        # Source
        r = ttk.Frame(frm)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text=self.t('label_source'), width=9).pack(side='left')
        self.source_var = tk.StringVar()
        src_entry = ttk.Entry(r, textvariable=self.source_var)
        src_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r, text=self.t('btn_browse'), command=self._browse_source, width=10).pack(side='right')

        if DND_AVAILABLE:
            src_entry.drop_target_register(DND_FILES)
            src_entry.dnd_bind('<<Drop>>', self._on_drop_source)

        # Output
        r2 = ttk.Frame(frm)
        r2.pack(fill='x', pady=2)
        ttk.Label(r2, text=self.t('label_output'), width=9).pack(side='left')
        self.output_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.output_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r2, text=self.t('btn_browse'), command=self._browse_output, width=10).pack(side='right')

        # Types
        types_row = ttk.Frame(frm)
        types_row.pack(fill='x', pady=(5, 0))

        ttk.Label(types_row, text=self.t('label_source_type')).pack(side='left')
        self.src_type = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text=self.t('radio_folder'),   variable=self.src_type, value='folder').pack(side='left', padx=(4, 10))
        ttk.Radiobutton(types_row, text=self.t('radio_gma_file'), variable=self.src_type, value='gma').pack(side='left', padx=(0, 20))

        ttk.Label(types_row, text=self.t('label_output_format')).pack(side='left')
        self.out_fmt = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text=self.t('radio_folder'), variable=self.out_fmt, value='folder').pack(side='left', padx=(4, 8))
        ttk.Radiobutton(types_row, text=".gma",                 variable=self.out_fmt, value='gma').pack(side='left', padx=(0, 8))
        ttk.Radiobutton(types_row, text=".zip",                 variable=self.out_fmt, value='zip').pack(side='left')

        if DND_AVAILABLE:
            ttk.Label(frm, text=self.t('drop_hint'),
                      foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        # Statistiques de la source (mises à jour après sélection)
        self.stats_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.stats_var,
                  foreground=self.ACCENT, font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(4, 0))

    def _build_options_section(self, parent):
        # ── Profil rapide ───────────────────────────────────────────────────
        profile_frm = ttk.Frame(parent)
        profile_frm.pack(fill='x', pady=(0, 6))
        ttk.Label(profile_frm, text=self.t('label_profile')).pack(side='left')
        self._profile_label_to_id = {self._profile_label(pid): pid for pid in self.PRESETS}
        self.profile_var = tk.StringVar(value=self._profile_label('custom'))
        profile_combo = ttk.Combobox(profile_frm, textvariable=self.profile_var, width=26,
                                      values=list(self._profile_label_to_id.keys()), state='readonly')
        profile_combo.pack(side='left', padx=4)
        profile_combo.bind('<<ComboboxSelected>>', self._apply_profile)
        ttk.Label(profile_frm, text=self.t('profile_hint'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(side='left')

        # ── Onglets Général / Avancé ────────────────────────────────────────
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='x', pady=(0, 6))

        general_tab  = ttk.Frame(notebook, padding=8)
        advanced_tab = ttk.Frame(notebook, padding=8)
        notebook.add(general_tab,  text=self.t('tab_general'))
        notebook.add(advanced_tab, text=self.t('tab_advanced'))

        # ════════════════════ Onglet Général ════════════════════
        left  = ttk.Frame(general_tab)
        left.pack(side='left', fill='both', expand=True)
        right = ttk.Frame(general_tab)
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # C-Hands
        self.rem_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_chands'),
                        variable=self.rem_chands).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_chands'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Fichiers inutiles
        self.rem_unused = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_unused'),
                        variable=self.rem_unused).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_unused'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Vérification des matériaux
        self.check_materials = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_check_materials'),
                        variable=self.check_materials).pack(anchor='w', pady=(0, 5))

        # Suppression des textures inutilisées
        self.rem_unused_tex = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, text=self.t('chk_remove_unused_tex'),
                        variable=self.rem_unused_tex).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_remove_unused_tex'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Textures
        self.comp_tex = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text=self.t('chk_textures'),
                        variable=self.comp_tex,
                        command=self._toggle_tex).pack(anchor='w')

        self.tex_sub = ttk.Frame(right)
        self.tex_sub.pack(anchor='w', padx=(16, 0), pady=(2, 0))

        r1 = ttk.Frame(self.tex_sub)
        r1.pack(anchor='w', pady=1)
        ttk.Label(r1, text=self.t('label_max_res')).pack(side='left')
        self.max_res = tk.StringVar(value='1024')
        ttk.Combobox(r1, textvariable=self.max_res, width=14,
                     values=['256', '512', '1024', '2048', self.t('no_limit')],
                     state='readonly').pack(side='left', padx=4)

        r2 = ttk.Frame(self.tex_sub)
        r2.pack(anchor='w', pady=1)
        ttk.Label(r2, text=self.t('label_quality')).pack(side='left')
        self.tex_qual = tk.IntVar(value=85)
        ttk.Scale(r2, from_=10, to=100, variable=self.tex_qual,
                  orient='h', length=110).pack(side='left', padx=4)
        self.qual_lbl = ttk.Label(r2, text="85%", width=5)
        self.qual_lbl.pack(side='left')
        self.tex_qual.trace_add('write', lambda *_: self.qual_lbl.config(
            text=f"{self.tex_qual.get()}%"))

        if not PIL_AVAILABLE and not VTFLIB_AVAILABLE:
            ttk.Label(self.tex_sub,
                      text=self.t('pillow_hint'),
                      foreground=self.YELLOW, font=('Segoe UI', 8)).pack(anchor='w', pady=(2, 0))

        # Génération Lua
        ttk.Separator(right, orient='horizontal').pack(fill='x', pady=(10, 4))

        self.gen_lua = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text=self.t('chk_lua'),
                        variable=self.gen_lua,
                        command=self._toggle_lua).pack(anchor='w')
        ttk.Label(right, text=self.t('desc_lua'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 3))

        self.lua_sub = ttk.Frame(right)
        self.lua_sub.pack(anchor='w', padx=(16, 0))

        self.lua_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.lua_sub, text=self.t('chk_lua_chands'),
                        variable=self.lua_chands).pack(anchor='w')
        ttk.Label(self.lua_sub,
                  text=self.t('desc_lua_chands'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        # ════════════════════ Onglet Avancé ════════════════════
        row1 = ttk.Frame(advanced_tab)
        row1.pack(fill='x')
        aleft  = ttk.Frame(row1)
        aleft.pack(side='left', fill='both', expand=True)
        aright = ttk.Frame(row1)
        aright.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # Sons
        self.comp_snd = tk.BooleanVar(value=False)
        ttk.Checkbutton(aleft, text=self.t('chk_sounds'),
                        variable=self.comp_snd,
                        command=self._toggle_snd).pack(anchor='w')
        snd_status = (self.t('ffmpeg_ok') if FFMPEG_AVAILABLE
                      else self.t('ffmpeg_missing_lbl'))
        snd_color = self.GREEN if FFMPEG_AVAILABLE else self.YELLOW
        ttk.Label(aleft, text=f"  {snd_status}",
                  foreground=snd_color, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        self.snd_sub = ttk.Frame(aleft)
        self.snd_sub.pack(anchor='w', padx=(16, 0))

        rs = ttk.Frame(self.snd_sub)
        rs.pack(anchor='w')
        ttk.Label(rs, text=self.t('label_bitrate')).pack(side='left')
        self.snd_qual = tk.StringVar(value='128k')
        ttk.Combobox(rs, textvariable=self.snd_qual, width=8,
                     values=['64k', '96k', '128k', '192k', '320k'],
                     state='readonly').pack(side='left', padx=4)

        # Niveau ZIP
        ttk.Label(aleft, text=self.t('label_zip_level'),
                  foreground=self.FG).pack(anchor='w', pady=(12, 2))
        zr = ttk.Frame(aleft)
        zr.pack(anchor='w')
        ttk.Label(zr, text=self.t('zip_fast')).pack(side='left')
        self.zip_lvl = tk.IntVar(value=6)
        ttk.Scale(zr, from_=1, to=9, variable=self.zip_lvl,
                  orient='h', length=100).pack(side='left', padx=4)
        ttk.Label(zr, text=self.t('zip_max')).pack(side='left')

        # Infos dépendances (côté droit de l'onglet avancé)
        ttk.Label(aright, text=self.t('libs_detected'),
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        for label, ok in (
            (self.t('lib_pillow'), PIL_AVAILABLE),
            (self.t('lib_vtflib'), VTFLIB_AVAILABLE),
            (self.t('lib_ffmpeg'), FFMPEG_AVAILABLE),
        ):
            mark  = "✓" if ok else "✗"
            color = self.GREEN if ok else self.SUB
            ttk.Label(aright, text=f"  {mark}  {label}",
                      foreground=color, font=('Segoe UI', 8)).pack(anchor='w')
        ttk.Label(aright,
                  text=self.t('vtf_note'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(6, 0))

        # ── Sécurité / modes spéciaux ────────────────────────────────────────
        ttk.Separator(advanced_tab, orient='horizontal').pack(fill='x', pady=8)

        row2 = ttk.Frame(advanced_tab)
        row2.pack(fill='x')
        a2left  = ttk.Frame(row2)
        a2left.pack(side='left', fill='both', expand=True)
        a2right = ttk.Frame(row2)
        a2right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # Mode aperçu (dry-run)
        self.dry_run = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2left, text=self.t('chk_dry_run'),
                        variable=self.dry_run).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_dry_run'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Sauvegarde de l'original
        self.backup = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2left, text=self.t('chk_backup'),
                        variable=self.backup).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_backup'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Recompression DXT des textures non compressées
        self.convert_uncompressed = tk.BooleanVar(value=True)
        ttk.Checkbutton(a2left, text=self.t('chk_convert'),
                        variable=self.convert_uncompressed).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_convert'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Rapport HTML d'analyse
        self.gen_report = tk.BooleanVar(value=True)
        ttk.Checkbutton(a2left, text=self.t('chk_report'),
                        variable=self.gen_report).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_report'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Taille cible
        self.target_size_enabled = tk.BooleanVar(value=False)
        ts_row = ttk.Frame(a2right)
        ts_row.pack(anchor='w')
        ttk.Checkbutton(ts_row, text=self.t('chk_target_size'),
                        variable=self.target_size_enabled,
                        command=self._toggle_target_size).pack(side='left')
        self.target_size_mb = tk.StringVar(value='10')
        self.target_size_entry = ttk.Entry(ts_row, textvariable=self.target_size_mb, width=6)
        self.target_size_entry.pack(side='left', padx=4)
        ttk.Label(ts_row, text=self.t('label_mb')).pack(side='left')
        ttk.Label(a2right, text=self.t('desc_target_size'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Mode batch
        self.batch = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2right, text=self.t('chk_batch'),
                        variable=self.batch).pack(anchor='w')
        ttk.Label(a2right, text=self.t('desc_batch'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()

    def _build_progress_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('progress_section'), padding=8)
        frm.pack(fill='x', pady=(0, 6))

        bar_row = ttk.Frame(frm)
        bar_row.pack(fill='x')

        self.prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bar_row, variable=self.prog_var, maximum=100).pack(side='left', fill='x', expand=True)

        self.prog_pct_var = tk.StringVar(value="0%")
        ttk.Label(bar_row, textvariable=self.prog_pct_var, width=5, anchor='e',
                  foreground=self.ACCENT, font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(8, 0))

        status_row = ttk.Frame(frm)
        status_row.pack(fill='x', pady=(3, 0))

        self.status_dot_lbl = tk.Label(status_row, text="●", bg=self.BG, fg=self.SUB,
                                        font=('Segoe UI', 10))
        self.status_dot_lbl.pack(side='left', padx=(0, 4))

        self.status_var = tk.StringVar(value=self.t('status_ready'))
        ttk.Label(status_row, textvariable=self.status_var,
                  foreground=self.SUB).pack(side='left')

        self.file_var = tk.StringVar(value="")
        ttk.Label(status_row, textvariable=self.file_var,
                  foreground=self.SUB, font=('Consolas', 8)).pack(side='right')

    def _build_log_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('log_section'), padding=8)
        frm.pack(fill='both', expand=True, pady=(0, 8))

        self.log_box = scrolledtext.ScrolledText(
            frm, height=9,
            bg=self.LOG_BG, fg=self.FG,
            insertbackground=self.FG,
            font=('Consolas', 9),
            state='disabled',
            relief='flat', borderwidth=0,
            selectbackground=self.ACCENT,
            selectforeground=self.BG,
        )
        self.log_box.pack(fill='both', expand=True)

        self.log_box.tag_configure('header',  foreground=self.ACCENT, font=('Consolas', 9, 'bold'))
        self.log_box.tag_configure('success', foreground=self.GREEN)
        self.log_box.tag_configure('warning', foreground=self.YELLOW)
        self.log_box.tag_configure('error',   foreground=self.RED)
        self.log_box.tag_configure('info',    foreground=self.FG)

    def _build_buttons(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill='x')

        ttk.Button(row, text=self.t('btn_clear_log'),
                   command=self._clear_log).pack(side='left')

        self.open_btn = ttk.Button(row, text=self.t('btn_open_output'),
                                   command=self._open_output, state='disabled')
        self.open_btn.pack(side='left', padx=(6, 0))

        self.stop_btn = ttk.Button(row, text=self.t('btn_cancel'),
                                   command=self._cancel, state='disabled')
        self.stop_btn.pack(side='right', padx=(4, 0))

        self.run_btn = ttk.Button(row, text=self.t('btn_run'),
                                  command=self._start, style='Accent.TButton')
        self.run_btn.pack(side='right')

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _toggle_tex(self):
        self._set_sub_state(self.tex_sub, self.comp_tex.get())

    def _toggle_snd(self):
        self._set_sub_state(self.snd_sub, self.comp_snd.get())

    def _toggle_lua(self):
        self._set_sub_state(self.lua_sub, self.gen_lua.get())

    @staticmethod
    def _set_sub_state(frame, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        for widget in frame.winfo_children():
            children = widget.winfo_children()
            targets = children if children else [widget]
            for w in targets:
                try:
                    w.configure(state=state)
                except tk.TclError:
                    pass

    def _apply_profile(self, _event=None):
        pid = self._profile_label_to_id.get(self.profile_var.get())
        preset = self.PRESETS.get(pid)
        if preset is None:
            return
        self.rem_chands.set(preset['remove_chands'])
        self.rem_unused.set(preset['remove_unused'])
        self.comp_tex.set(preset['compress_textures'])
        max_res = preset['max_res']
        self.max_res.set(self.t('no_limit') if max_res == 'none' else max_res)
        self.tex_qual.set(preset['quality'])
        self.comp_snd.set(preset['compress_sounds'] and FFMPEG_AVAILABLE)
        self.snd_qual.set(preset['sound_quality'])
        self.zip_lvl.set(preset['zip_level'])
        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()

    def _scan_source(self):
        src = self.source_var.get().strip()
        if not src or not Path(src).exists():
            self.stats_var.set("")
            return
        self.stats_var.set(self.t('stats_analyzing'))
        threading.Thread(target=self._scan_source_thread, args=(src,), daemon=True).start()

    def _scan_source_thread(self, src: str):
        try:
            p = Path(src)
            if p.is_file():
                text = self.t('stats_source_file', size=Compressor._fmt_size(p.stat().st_size))
            else:
                count = 0
                total = 0
                for fp in p.rglob('*'):
                    if fp.is_file():
                        count += 1
                        total += fp.stat().st_size
                text = self.t('stats_source', count=count, size=Compressor._fmt_size(total))
        except OSError:
            text = ""
        self.root.after(0, lambda: self.stats_var.set(text))

    def _browse_source(self):
        if self.src_type.get() == 'gma':
            path = filedialog.askopenfilename(
                title=self.t('dialog_select_gma'),
                filetypes=[(self.t('filetype_gma'), "*.gma"), (self.t('filetype_all'), "*.*")],
            )
        else:
            path = filedialog.askdirectory(title=self.t('dialog_select_folder'))
        if path:
            self.source_var.set(path)
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.parent / (p.stem + '_compressed')))
            self._scan_source()

    def _browse_output(self):
        fmt = self.out_fmt.get()
        if fmt == 'folder':
            path = filedialog.askdirectory(title=self.t('dialog_output_folder'))
        elif fmt == 'gma':
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_gma'),
                defaultextension='.gma',
                filetypes=[(self.t('filetype_gma'), "*.gma")],
            )
        else:
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_zip'),
                defaultextension='.zip',
                filetypes=[(self.t('filetype_zip'), "*.zip")],
            )
        if path:
            self.output_var.set(path)

    def _start(self):
        src = self.source_var.get().strip()
        out = self.output_var.get().strip()

        if not src:
            messagebox.showwarning(self.t('msg_source_missing_title'),
                                   self.t('msg_source_missing_body'))
            return
        if not out:
            messagebox.showwarning(self.t('msg_output_missing_title'),
                                   self.t('msg_output_missing_body'))
            return
        if not Path(src).exists():
            messagebox.showerror(self.t('msg_source_not_found_title'),
                                 self.t('msg_source_not_found_body', src=src))
            return

        target_size_mb = None
        if self.target_size_enabled.get():
            try:
                target_size_mb = float(self.target_size_mb.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning(self.t('msg_invalid_target_size_title'),
                                       self.t('msg_invalid_target_size_body'))
                return

        opts = {
            'source':            src,
            'output':            out,
            'source_type':       self.src_type.get(),
            'output_format':     self.out_fmt.get(),
            'remove_chands':     self.rem_chands.get(),
            'remove_unused':     self.rem_unused.get(),
            'compress_textures': self.comp_tex.get(),
            'max_resolution':    self.max_res.get(),
            'texture_quality':   self.tex_qual.get(),
            'compress_sounds':   self.comp_snd.get() and FFMPEG_AVAILABLE,
            'sound_quality':     self.snd_qual.get(),
            'zip_level':         int(self.zip_lvl.get()),
            'gen_lua':           self.gen_lua.get(),
            'lua_chands':        self.lua_chands.get(),
            'check_materials':   self.check_materials.get(),
            'remove_unused_textures': self.rem_unused_tex.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
            'gen_report':        self.gen_report.get(),
            'target_size_mb':    target_size_mb,
            'dry_run':           self.dry_run.get(),
            'backup_original':   self.backup.get(),
            'batch':             self.batch.get(),
            'lang':              self.lang,
        }

        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.open_btn.configure(state='disabled')
        self.prog_var.set(0)
        self.prog_pct_var.set("0%")
        self.file_var.set("")
        self.status_dot_lbl.configure(fg=self.ACCENT)

        self._compressor = Compressor(
            opts,
            log_fn=self._log,
            progress_fn=self._set_prog,
            status_fn=self._set_status,
            current_file_fn=self._set_current_file,
        )
        self._thread = threading.Thread(target=self._run_compressor, daemon=True)
        self._thread.start()

    def _run_compressor(self):
        self._compressor.run()
        self.root.after(0, self._on_done)

    def _on_done(self):
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.file_var.set("")
        comp = self._compressor
        if comp and comp.final_size is not None:
            self.open_btn.configure(state='normal')
            before = Compressor._fmt_size(comp.original_size)
            after = Compressor._fmt_size(comp.final_size)
            self.stats_var.set(self.t('stats_done', before=before, after=after, pct=f"{comp.reduction:.1f}"))
            self.status_dot_lbl.configure(fg=self.GREEN)
            self._show_summary(comp, before, after)
        elif comp and comp.cancel_flag.is_set():
            self.status_dot_lbl.configure(fg=self.YELLOW)
        else:
            self.status_dot_lbl.configure(fg=self.RED)

    def _show_summary(self, comp: 'Compressor', before: str, after: str):
        """Affiche un récapitulatif convivial à la fin d'une compression réussie."""
        saved = Compressor._fmt_size(max(0, (comp.original_size or 0) - (comp.final_size or 0)))
        pct = f"{comp.reduction:.1f}"
        body = self.t('summary_body', before=before, after=after, saved=saved, pct=pct)
        if comp.opts.get('dry_run'):
            messagebox.showinfo(self.t('summary_title'), body + "\n\n" + self.t('summary_dry_run'))
            return

        report_path = getattr(comp, 'report_path', None)

        win = tk.Toplevel(self.root)
        win.title(self.t('summary_title'))
        win.configure(bg=self.BG)
        win.transient(self.root)
        win.resizable(False, False)

        wrap = tk.Frame(win, bg=self.BG, padx=24, pady=20)
        wrap.pack(fill='both', expand=True)

        tk.Label(wrap, text=self.t('summary_title'), bg=self.BG, fg=self.ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(wrap, text=body, bg=self.BG, fg=self.FG, justify='left',
                 font=('Segoe UI', 10)).pack(anchor='w', pady=(10, 16))

        btn_row = tk.Frame(wrap, bg=self.BG)
        btn_row.pack(fill='x')
        ttk.Button(btn_row, text=self.t('summary_open_folder'),
                   style='Accent.TButton',
                   command=lambda: (win.destroy(), self._open_output())
                   ).pack(side='left')
        if report_path and Path(report_path).exists():
            ttk.Button(btn_row, text=self.t('report_open'),
                       command=lambda: self._open_path(report_path)
                       ).pack(side='left', padx=(8, 0))
        ttk.Button(btn_row, text=self.t('summary_close'),
                   command=win.destroy).pack(side='right')

        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.grab_set()

    def _cancel(self):
        if self._compressor:
            self._compressor.cancel()

    def _open_output(self):
        out = Path(self.output_var.get().strip())
        target = out if out.is_dir() else out.parent
        self._open_path(target)

    def _open_path(self, target):
        """Ouvre un fichier ou un dossier avec l'application par défaut de l'OS."""
        target = str(target)
        try:
            if sys.platform == 'win32':
                os.startfile(target)
            elif sys.platform == 'darwin':
                subprocess.run(['open', target])
            else:
                subprocess.run(['xdg-open', target])
        except Exception as e:
            messagebox.showerror(self.t('msg_error_title'), self.t('msg_open_folder_error', e=e))

    def _log(self, msg: str):
        tag = 'info'
        if msg.startswith('▶'):
            tag = 'header'
        elif '✗' in msg or 'ERREUR' in msg:
            tag = 'error'
        elif '⚠' in msg:
            tag = 'warning'
        elif '✓' in msg:
            tag = 'success'

        def _do():
            self.log_box.configure(state='normal')
            self.log_box.insert('end', msg + '\n', tag)
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        self.root.after(0, _do)

    def _set_prog(self, val: float):
        def _do():
            self.prog_var.set(val)
            self.prog_pct_var.set(f"{val:.0f}%")
        self.root.after(0, _do)

    def _set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def _set_current_file(self, name: str):
        display = f"→ {name}" if name else ""
        self.root.after(0, lambda: self.file_var.set(display))

    def _clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def _log_header(self):
        self._log(self.t('log_app_version', version=VERSION))
        libs = (
            f"PIL : {'✓' if PIL_AVAILABLE else '✗'}  |  "
            f"VTFLib : {'✓' if VTFLIB_AVAILABLE else '✗'}  |  "
            f"ffmpeg : {'✓' if FFMPEG_AVAILABLE else '✗'}"
        )
        self._log(libs)
        if not PIL_AVAILABLE:
            self._log(self.t('log_install_pillow'))
        self._log("")

    # ── Bascules thème / langue / taille cible ────────────────────────────────

    def _toggle_target_size(self):
        state = 'normal' if self.target_size_enabled.get() else 'disabled'
        self.target_size_entry.configure(state=state)

    def _toggle_theme(self):
        self.theme_name = 'light' if self.theme_name == 'dark' else 'dark'
        self._apply_palette()
        self._rebuild()

    def _toggle_language(self):
        self.lang = 'en' if self.lang == 'fr' else 'fr'
        self._rebuild()

    def _show_about(self):
        lib_status = [
            (self.t('lib_pillow'), PIL_AVAILABLE),
            (self.t('lib_vtflib'), VTFLIB_AVAILABLE),
            (self.t('lib_ffmpeg'), FFMPEG_AVAILABLE),
        ]
        libs = "\n".join(
            self.t('about_lib_yes' if ok else 'about_lib_no', lib=name)
            for name, ok in lib_status
        )
        messagebox.showinfo(
            self.t('about_title'),
            self.t('about_body', version=VERSION, libs=libs),
        )

    def _collect_state(self) -> dict:
        return {
            'source':              self.source_var.get(),
            'output':              self.output_var.get(),
            'src_type':            self.src_type.get(),
            'out_fmt':             self.out_fmt.get(),
            'profile_id':          self._profile_label_to_id.get(self.profile_var.get(), 'custom'),
            'rem_chands':          self.rem_chands.get(),
            'rem_unused':          self.rem_unused.get(),
            'check_materials':     self.check_materials.get(),
            'rem_unused_tex':      self.rem_unused_tex.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
            'gen_report':          self.gen_report.get(),
            'comp_tex':            self.comp_tex.get(),
            'max_res_no_limit':    not self.max_res.get().isdigit(),
            'max_res':             self.max_res.get(),
            'tex_qual':            self.tex_qual.get(),
            'gen_lua':             self.gen_lua.get(),
            'lua_chands':          self.lua_chands.get(),
            'comp_snd':            self.comp_snd.get(),
            'snd_qual':            self.snd_qual.get(),
            'zip_lvl':             self.zip_lvl.get(),
            'dry_run':             self.dry_run.get(),
            'backup':              self.backup.get(),
            'target_size_enabled': self.target_size_enabled.get(),
            'target_size_mb':      self.target_size_mb.get(),
            'batch':               self.batch.get(),
        }

    def _restore_state(self, state: dict):
        self.source_var.set(state.get('source', ''))
        self.output_var.set(state.get('output', ''))
        self.src_type.set(state.get('src_type', 'folder'))
        self.out_fmt.set(state.get('out_fmt', 'folder'))
        self.profile_var.set(self._profile_label(state.get('profile_id', 'custom')))
        self.rem_chands.set(state.get('rem_chands', True))
        self.rem_unused.set(state.get('rem_unused', True))
        self.check_materials.set(state.get('check_materials', True))
        self.rem_unused_tex.set(state.get('rem_unused_tex', False))
        self.convert_uncompressed.set(state.get('convert_uncompressed', True))
        self.gen_report.set(state.get('gen_report', True))
        self.comp_tex.set(state.get('comp_tex', True))
        self.max_res.set(self.t('no_limit') if state.get('max_res_no_limit', False) else state.get('max_res', '1024'))
        self.tex_qual.set(state.get('tex_qual', 85))
        self.gen_lua.set(state.get('gen_lua', True))
        self.lua_chands.set(state.get('lua_chands', True))
        self.comp_snd.set(state.get('comp_snd', False))
        self.snd_qual.set(state.get('snd_qual', '128k'))
        self.zip_lvl.set(state.get('zip_lvl', 6))
        self.dry_run.set(state.get('dry_run', False))
        self.backup.set(state.get('backup', False))
        self.target_size_enabled.set(state.get('target_size_enabled', False))
        self.target_size_mb.set(state.get('target_size_mb', '10'))
        self.batch.set(state.get('batch', False))

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()
        self._scan_source()

    # ── Préférences persistantes ──────────────────────────────────────────────

    @staticmethod
    def _load_config() -> dict | None:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _save_config(self):
        try:
            state = self._collect_state()
            state['lang'] = self.lang
            state['theme_name'] = self.theme_name
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')
        except OSError:
            pass

    def _on_close(self):
        self._save_config()
        self.root.destroy()

    def _rebuild(self):
        state = self._collect_state()
        log_content = self.log_box.get('1.0', 'end-1c')

        for child in self.root.winfo_children():
            child.destroy()

        self.root.configure(bg=self.BG)
        self._setup_styles()
        self._build_ui()
        self._restore_state(state)

        if log_content:
            for line in log_content.split('\n'):
                self._log(line)

    # ── Glisser-déposer ────────────────────────────────────────────────────────

    def _on_drop_source(self, event):
        raw = event.data.strip()
        if raw.startswith('{'):
            path = raw[1:raw.index('}')]
        else:
            path = raw.split()[0]
        path = path.strip()
        if not path:
            return
        p = Path(path)
        self.source_var.set(path)
        self.src_type.set('gma' if p.suffix.lower() == '.gma' else 'folder')
        if not self.output_var.get():
            self.output_var.set(str(p.parent / (p.stem + '_compressed')))
        self._scan_source()

    def run(self):
        self.root.mainloop()


# ─── Mode CLI ─────────────────────────────────────────────────────────────────

def cli_main():
    import argparse

    parser = argparse.ArgumentParser(
        prog='compressez_pm',
        description="Compressez PM GMod – Compresseur d'addons Playermodel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python compressez_pm.py mon_addon/              sortie/
  python compressez_pm.py mon_addon.gma           sortie.gma   --no-chands
  python compressez_pm.py mon_addon/              sortie.zip   --format zip --quality 70 --max-res 512
        """,
    )
    parser.add_argument('source',   help="Dossier ou fichier .gma source")
    parser.add_argument('output',   help="Chemin de sortie")
    parser.add_argument('--format', choices=['folder', 'gma', 'zip'], default='folder',
                        dest='output_format', help="Format de sortie (défaut : folder)")
    parser.add_argument('--no-chands',   action='store_true', help="Supprimer les C-Hands")
    parser.add_argument('--no-unused',   action='store_true', help="Supprimer les fichiers inutiles")
    parser.add_argument('--no-textures', action='store_true', help="Ne pas optimiser les textures")
    parser.add_argument('--quality',   type=int, default=85, metavar='10-100',
                        help="Qualité des textures (défaut : 85)")
    parser.add_argument('--max-res',   type=str, default='1024',
                        metavar='256|512|1024|2048|Aucune limite',
                        help="Résolution max des textures (défaut : 1024)")
    parser.add_argument('--compress-sounds', action='store_true',
                        help="Compresser les sons (nécessite ffmpeg)")
    parser.add_argument('--sound-quality', default='128k',
                        choices=['64k', '96k', '128k', '192k', '320k'],
                        help="Bitrate audio (défaut : 128k)")
    parser.add_argument('--zip-level', type=int, default=6,
                        choices=range(1, 10), metavar='1-9',
                        help="Niveau de compression ZIP (défaut : 6)")
    parser.add_argument('--gen-lua', action='store_true', default=True,
                        help="Générer/mettre à jour le fichier Lua PM (défaut : activé)")
    parser.add_argument('--no-lua', action='store_true',
                        help="Ne pas générer de fichier Lua")
    parser.add_argument('--no-lua-chands', action='store_true',
                        help="Ne pas inclure les C-Hands dans le Lua généré")
    parser.add_argument('--no-check-materials', action='store_true',
                        help="Ne pas vérifier les matériaux/textures manquants")
    parser.add_argument('--target-size', type=float, default=None, metavar='MO',
                        help="Taille cible en Mo : ajuste automatiquement "
                             "résolution/qualité des textures pour l'atteindre")
    parser.add_argument('--dry-run', action='store_true',
                        help="Mode aperçu : analyse et affiche les changements "
                             "sans rien écrire sur le disque")
    parser.add_argument('--backup', action='store_true',
                        help="Sauvegarder la sortie existante avant écrasement")
    parser.add_argument('--batch', action='store_true',
                        help="Mode batch : traite chaque sous-dossier/.gma de "
                             "la source comme un addon distinct")
    parser.add_argument('--remove-unused-textures', action='store_true',
                        help="Supprimer les textures .vtf référencées par aucun .vmt")
    parser.add_argument('--no-convert-uncompressed', action='store_true',
                        help="Ne pas recompresser les .vtf non compressés en DXT")
    parser.add_argument('--no-report', action='store_true',
                        help="Ne pas générer le rapport HTML d'analyse")
    parser.add_argument('--lang', choices=['fr', 'en'], default='fr',
                        help="Langue des messages (défaut : fr)")

    args = parser.parse_args()

    opts = {
        'source':            args.source,
        'output':            args.output,
        'source_type':       'gma' if args.source.endswith('.gma') else 'folder',
        'output_format':     args.output_format,
        'remove_chands':     args.no_chands,
        'remove_unused':     args.no_unused,
        'compress_textures': not args.no_textures,
        'max_resolution':    args.max_res,
        'texture_quality':   args.quality,
        'compress_sounds':   args.compress_sounds,
        'sound_quality':     args.sound_quality,
        'zip_level':         args.zip_level,
        'gen_lua':           not args.no_lua,
        'lua_chands':        not args.no_lua_chands,
        'check_materials':   not args.no_check_materials,
        'remove_unused_textures': args.remove_unused_textures,
        'convert_uncompressed': not args.no_convert_uncompressed,
        'gen_report':        not args.no_report,
        'target_size_mb':    args.target_size,
        'dry_run':           args.dry_run,
        'backup_original':   args.backup,
        'batch':             args.batch,
        'lang':              args.lang,
    }

    print(t('cli_header', args.lang, version=VERSION))
    Compressor(opts,
               log_fn=print,
               progress_fn=lambda v: None,
               status_fn=lambda s: print(f"[{s}]")).run()


# ─── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli_main()
    elif TK_AVAILABLE:
        App().run()
    else:
        print("tkinter non disponible. Utilisez le mode CLI :")
        print("  python compressez_pm.py --help")
        sys.exit(1)
