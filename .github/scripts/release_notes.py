import re
import sys
from pathlib import Path

FALLBACK = "Voir CHANGELOG.md pour la version {version}."

HEADER = """## Télécharger

- **`Slimgma-Setup-{version}.exe`** — le programme d'installation. Raccourci
  dans le menu Démarrer, désinstallation depuis *Applications installées*.
  C'est celui qu'il vous faut.
- `Slimgma.exe` — la version portable, un seul fichier, rien d'installé. Pour
  une clé USB ou un PC où vous ne voulez rien laisser.

Windows affiche « Windows a protégé votre ordinateur » ? Les fichiers ne sont
pas signés : *Informations complémentaires* puis *Exécuter quand même*.

---
"""


def body_for(version: str, changelog: str) -> str:
    pattern = rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)"
    found = re.search(pattern, changelog, re.S | re.M)
    if found and found.group(1).strip():
        return found.group(1).strip()
    return FALLBACK.format(version=version)


def notes_for(version: str, changelog: str) -> str:
    return f"{HEADER.format(version=version)}\n{body_for(version, changelog)}\n"


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: release_notes.py <version> <changelog> <sortie>")
        return 2
    version, changelog, destination = argv[1], argv[2], argv[3]
    text = Path(changelog).read_text(encoding='utf-8')
    Path(destination).write_text(notes_for(version, text), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
