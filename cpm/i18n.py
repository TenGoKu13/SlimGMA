"""Internationalisation (FR/EN)."""


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
