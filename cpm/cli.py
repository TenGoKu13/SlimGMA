"""Point d'entrée ligne de commande."""
import sys

from .constants import VERSION
from .i18n import t
from .compressor import Compressor


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
