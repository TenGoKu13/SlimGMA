NEW = 'new'
FIX = 'fix'
CHANGE = 'change'


RELEASES: list[dict] = [
    {
        'version': '1.2.1',
        'date': '2026-09-06',
        'entries': [
            (CHANGE, {
                'fr': "L'outil s'appelle désormais Slimgma. Vos réglages, votre langue et vos sources récentes sont conservés automatiquement.",
                'en': "The tool is now called Slimgma. Your settings, language and recent sources are carried over automatically.",
            }),
            (FIX, {
                'fr': "Les textures sortaient entièrement noires : les pixels du .vtf n'étaient jamais décodés avant redimensionnement. Si vous avez compressé un addon avec la 1.2.0, repartez de l'original.",
                'en': "Textures came out completely black: the .vtf pixels were never decoded before resizing. If you compressed an addon with 1.2.0, start again from the original.",
            }),
            (FIX, {
                'fr': "L'éclairage des textures pouvait changer : la réflectivité et l'échelle de bump de l'en-tête étaient perdues à la réécriture. Elles sont désormais conservées.",
                'en': "Texture lighting could change: the header's reflectivity and bump scale were lost when rewriting. They are now preserved.",
            }),
            (NEW, {
                'fr': "Garde-fou : si une texture perd toute sa couleur pendant l'optimisation, l'outil garde l'originale au lieu d'écrire un fichier abîmé.",
                'en': "Safety net: if a texture loses all its colour during optimization, the tool keeps the original instead of writing a damaged file.",
            }),
        ],
    },
    {
        'version': '1.2.0',
        'date': '2026-08-12',
        'entries': [
            (CHANGE, {
                'fr': "Interface entièrement redessinée : navigation latérale à cinq pages (Source, Options, Avancé, Journal, Rapport) au lieu des onglets empilés.",
                'en': "Completely redesigned interface: a five-page sidebar (Source, Options, Advanced, Log, Report) replaces the stacked tabs.",
            }),
            (NEW, {
                'fr': "Barre d'action permanente : progression, chronomètre, fichier en cours et boutons restent visibles depuis n'importe quelle page.",
                'en': "Permanent action bar: progress, timer, current file and buttons stay visible from every page.",
            }),
            (NEW, {
                'fr': "Bandeau des 7 étapes en pastilles reliées, cochées au fur et à mesure de la compression.",
                'en': "A seven-step pipeline strip, ticked off as the compression advances.",
            }),
            (NEW, {
                'fr': "Le nombre d'avertissements et d'erreurs s'affiche directement sur l'entrée « Journal ».",
                'en': "Warning and error counts now show directly on the “Log” entry.",
            }),
            (CHANGE, {
                'fr': "Le rapport d'analyse est désormais une page de l'application, plus un fichier HTML à ouvrir dans un navigateur. Il est copiable en un clic.",
                'en': "The analysis report is now a page inside the app instead of an HTML file to open in a browser. One click copies it.",
            }),
            (NEW, {
                'fr': "Cette fenêtre : les nouveautés de chaque version sont consultables depuis l'en-tête.",
                'en': "This window: each release's highlights are now readable from the header.",
            }),
            (CHANGE, {
                'fr': "Nouveaux thèmes clair et sombre, contraste renforcé, options regroupées en cartes.",
                'en': "New light and dark themes, stronger contrast, options grouped into cards.",
            }),
            (CHANGE, {
                'fr': "Projet passé en logiciel libre : licence MIT, guide de contribution, code de conduite et téléchargement direct de l'exécutable depuis les releases GitHub.",
                'en': "The project is now free software: MIT license, contributing guide, code of conduct and a direct executable download from the GitHub releases.",
            }),
            (CHANGE, {
                'fr': "Mode taille cible jusqu'à cinq fois plus rapide : les passes de qualité inutiles sur les addons sans images non-VTF ne sont plus tentées.",
                'en': "Target-size mode up to five times faster: useless quality passes are skipped on addons that only contain .vtf textures.",
            }),
            (FIX, {
                'fr': "La recompression DXT ne faisait rien : elle dépendait d'une bibliothèque introuvable. Les .vtf sont maintenant vraiment redimensionnés et recompressés (jusqu'à -90 % sur un addon de textures).",
                'en': "DXT recompression did nothing: it relied on a library that could not be installed. .vtf files are now genuinely resized and recompressed (up to -90% on a texture-heavy addon).",
            }),
            (FIX, {
                'fr': "Un traitement par lot réussi s'affichait comme un échec, sans récapitulatif ni boutons de fin.",
                'en': "A successful batch run was displayed as a failure, with no summary and no final buttons.",
            }),
            (CHANGE, {
                'fr': "En ligne de commande, les C-Hands et les fichiers inutiles sont supprimés par défaut, comme dans l'interface. Utilisez --keep-chands et --keep-unused pour les garder.",
                'en': "On the command line, C-Hands and junk files are removed by default, matching the interface. Use --keep-chands and --keep-unused to keep them.",
            }),
            (FIX, {
                'fr': "L'application pouvait se figer en pleine compression : l'interface était pilotée depuis le thread de travail.",
                'en': "The app could freeze mid-compression: the interface was driven from the worker thread.",
            }),
            (FIX, {
                'fr': "La ligne de détection des bibliothèques n'est plus comptée comme une erreur dans le journal.",
                'en': "The library detection line is no longer counted as an error in the log.",
            }),
            (FIX, {
                'fr': "Le pourcentage affichait « --2.7 % » quand la sortie grossissait ; le signe est désormais correct, en +.",
                'en': "The percentage read “--2.7%” when the output grew; the sign is now correct, as a +.",
            }),
        ],
    },
    {
        'version': '1.1.0',
        'date': '2026-07-17',
        'entries': [
            (FIX, {
                'fr': "Support des .gma réparé : toute lecture ou écriture d'un .gma plantait.",
                'en': "Fixed .gma support: reading or writing a .gma crashed.",
            }),
            (FIX, {
                'fr': "Les .tga et .bmp ne sont plus corrompus (ils étaient réécrits en PNG sous leur extension d'origine).",
                'en': "No more corrupted .tga and .bmp files (they were rewritten as PNG under their original extension).",
            }),
            (FIX, {
                'fr': "Le Lua généré n'appelait pas la bonne API GMod et provoquait une erreur en jeu.",
                'en': "The generated Lua called the wrong GMod API and raised an in-game error.",
            }),
            (FIX, {
                'fr': "Les sons ne sont plus renommés : chaque fichier est réencodé dans son format d'origine, les chemins Lua restent valides.",
                'en': "Sounds are no longer renamed: each file is re-encoded in its original format, so Lua paths stay valid.",
            }),
            (NEW, {
                'fr': "Fusion des textures identiques : une seule copie est conservée et les .vmt sont réécrits, sans perte.",
                'en': "Identical texture merging: a single copy is kept and .vmt files are rewritten, losslessly.",
            }),
            (NEW, {
                'fr': "Whitelist GMA : les fichiers que GMod refuserait au montage sont signalés, avec retrait automatique en option.",
                'en': "GMA whitelist: files GMod would reject at mount time are reported, with optional auto-strip.",
            }),
            (NEW, {
                'fr': "addon.json généré automatiquement s'il manque en sortie dossier.",
                'en': "addon.json generated automatically when missing from a folder output.",
            }),
            (NEW, {
                'fr': "Rapport HTML d'analyse, info-bulles sur chaque option, sources récentes et raccourcis clavier.",
                'en': "HTML analysis report, tooltips on every option, recent sources and keyboard shortcuts.",
            }),
            (CHANGE, {
                'fr': "Optimisation des textures en parallèle, jusqu'à 8 threads.",
                'en': "Parallel texture optimization, up to 8 threads.",
            }),
        ],
    },
    {
        'version': '1.0.0',
        'date': '',
        'entries': [
            (NEW, {
                'fr': "Première version : compression d'addons Playermodel en interface graphique et en ligne de commande.",
                'en': "First release: Playermodel addon compression with a graphical interface and a command line.",
            }),
        ],
    },
]


def _version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split('.'))


def releases_since(version: str | None) -> list[dict]:
    if not version:
        return []
    try:
        floor = _version_key(version)
    except ValueError:
        return list(RELEASES)
    return [r for r in RELEASES if _version_key(r['version']) > floor]
