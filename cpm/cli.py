import sys

from .constants import VERSION
from .i18n import t
from .compressor import Compressor


def cli_main():
    import argparse

    parser = argparse.ArgumentParser(
        prog='slimgma',
        description="Slimgma – Compresseur d'addons Playermodel pour Garry's Mod",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python slimgma.py mon_addon/              sortie/
  python slimgma.py mon_addon.gma           sortie.gma   --keep-chands
  python slimgma.py mon_addon/              sortie.zip   --format zip --quality 70 --max-res 512
  python slimgma.py mon_addon/              --in-place --backup
        """,
    )
    parser.add_argument('source',   help="Dossier ou fichier .gma source")
    parser.add_argument('output', nargs='?', default=None,
                        help="Chemin de sortie (inutile avec --in-place)")
    parser.add_argument('--in-place', action='store_true',
                        help="Remplacer l'addon d'origine au lieu d'en créer "
                             "une copie compressée")
    parser.add_argument('--format', choices=['folder', 'gma', 'zip'], default='folder',
                        dest='output_format', help="Format de sortie (défaut : folder)")
    parser.add_argument('--keep-chands', action='store_true',
                        help="Conserver les C-Hands (supprimés par défaut)")
    parser.add_argument('--keep-unused', action='store_true',
                        help="Conserver les fichiers inutiles (supprimés par défaut)")
    parser.add_argument('--no-chands', action='store_true',
                        help="Déprécié : la suppression des C-Hands est le défaut")
    parser.add_argument('--no-unused', action='store_true',
                        help="Déprécié : la suppression des fichiers inutiles est le défaut")
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
    parser.add_argument('--dedup-textures', action='store_true',
                        help="Fusionner les textures .vtf identiques "
                             "(réécrit les .vmt vers une copie unique)")
    parser.add_argument('--strip-non-whitelisted', action='store_true',
                        help="Retirer les fichiers refusés par la whitelist GMA "
                             "(sortie .gma uniquement)")
    parser.add_argument('--no-convert-uncompressed', action='store_true',
                        help="Ne pas recompresser les .vtf non compressés en DXT")
    parser.add_argument('--no-addon-json', action='store_true',
                        help="Ne pas générer addon.json s'il manque (sortie dossier)")
    parser.add_argument('--lang', choices=['fr', 'en'], default='fr',
                        help="Langue des messages (défaut : fr)")

    args = parser.parse_args()

    if args.in_place:
        if args.output:
            parser.error("--in-place et un chemin de sortie sont exclusifs")
        args.output = args.source
        args.output_format = 'gma' if args.source.endswith('.gma') else 'folder'
    elif not args.output:
        parser.error("chemin de sortie manquant (ou utilisez --in-place)")

    for flag, alt in (('no_chands', '--keep-chands'), ('no_unused', '--keep-unused')):
        if getattr(args, flag):
            print(t('cli_deprecated', args.lang,
                    flag='--' + flag.replace('_', '-'), alt=alt))

    opts = {
        'source':            args.source,
        'output':            args.output,
        'source_type':       'gma' if args.source.endswith('.gma') else 'folder',
        'output_format':     args.output_format,
        'remove_chands':     not args.keep_chands,
        'remove_unused':     not args.keep_unused,
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
        'dedup_textures':    args.dedup_textures,
        'strip_non_whitelisted': args.strip_non_whitelisted,
        'convert_uncompressed': not args.no_convert_uncompressed,
        'gen_addon_json':    not args.no_addon_json,
        'target_size_mb':    args.target_size,
        'dry_run':           args.dry_run,
        'backup_original':   args.backup,
        'batch':             args.batch,
        'in_place':          args.in_place,
        'lang':              args.lang,
    }

    print(t('cli_header', args.lang, version=VERSION))
    Compressor(opts,
               log_fn=print,
               progress_fn=lambda v: None,
               status_fn=lambda s: print(f"[{s}]")).run()
