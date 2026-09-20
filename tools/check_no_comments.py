import ast
import io
import sys
import tokenize
from pathlib import Path

DOC_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
SKIP_DIRS = {'.git', '__pycache__', 'build', 'dist', '.venv', 'venv'}


def sources(root: Path):
    for path in sorted(root.rglob('*.py')):
        if SKIP_DIRS.isdisjoint(path.parts):
            yield path


def offences(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    found = []

    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        if token.start[0] == 1 and text.startswith('#!'):
            continue
        found.append(f"{path}:{token.start[0]}: commentaire — {token.string}")

    for node in ast.walk(ast.parse(text)):
        if isinstance(node, DOC_NODES) and ast.get_docstring(node):
            name = getattr(node, 'name', '<module>')
            line = getattr(node, 'lineno', 1)
            found.append(f"{path}:{line}: docstring — {name}")

    return found


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    problems = [line for path in sources(root) for line in offences(path)]

    if problems:
        print("Ce dépôt interdit les commentaires et les docstrings "
              "(voir CONTRIBUTING.md).\n")
        for line in problems:
            print(line)
        return 1

    print("Aucun commentaire ni docstring.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
