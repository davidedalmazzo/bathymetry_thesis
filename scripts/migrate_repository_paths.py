"""One-shot bulk mechanical rewrite of executable path literals, not artifacts.

Run from root with the thesis interpreter. Frozen block files are never edited.
"""
import ast
import io
import json
import sys
import tokenize
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from repository_paths import remap_relative


def mapped(value):
    prefix = ROOT.as_posix()
    normalized = value.replace('\\', '/')
    if normalized.lower().startswith(prefix.lower() + '/'):
        suffix = normalized[len(prefix) + 1:]
        new = remap_relative(suffix)
        return prefix + '/' + new if new != suffix else value
    new = remap_relative(value)
    return new if new != normalized else value


def main():
    changed = []
    for folder in ('code', 'tests', 'umbra/scripts'):
        for path in (ROOT / folder).rglob('*.py'):
            if path.name == 'repository_paths.py':
                continue
            source = path.read_text(encoding='utf-8-sig')
            lines = source.splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1] + len(line))
            edits = []
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type != tokenize.STRING:
                    continue
                try:
                    value = ast.literal_eval(token.string)
                except (ValueError, SyntaxError):
                    continue
                if not isinstance(value, str):
                    continue
                replacement = mapped(value)
                if replacement != value:
                    start = offsets[token.start[0] - 1] + token.start[1]
                    end = offsets[token.end[0] - 1] + token.end[1]
                    edits.append((start, end, repr(replacement)))
            if edits:
                for start, end, value in reversed(edits):
                    source = source[:start] + value + source[end:]
                ast.parse(source)
                path.write_text(source, encoding='utf-8', newline='\n')
                changed.append({'path': path.relative_to(ROOT).as_posix(), 'literals': len(edits)})
    out = ROOT / 'docs/reorganization'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'MECHANICAL_REWRITE.json').write_text(json.dumps(changed, indent=2) + '\n', encoding='utf-8')
    print(f'{len(changed)} source/test files mechanically migrated')


def migrate_dynamic():
    changed = []
    for folder in ('code', 'tests'):
        for path in (ROOT / folder).rglob('*.py'):
            if path.name == 'repository_paths.py':
                continue
            source = path.read_text(encoding='utf-8-sig')
            tree = ast.parse(source)
            lines = source.splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1] + len(line))
            edits = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div) or isinstance(node.right, ast.Constant):
                    continue
                left = node.left
                matched = (isinstance(left, ast.Name) and left.id in ('ROOT', 'root')) or (isinstance(left, ast.Attribute) and left.attr == 'ROOT')
                if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == 'Path' and len(left.args) == 1:
                    matched = isinstance(left.args[0], ast.Name) and left.args[0].id == 'root'
                if not matched:
                    continue
                start = offsets[node.lineno - 1] + node.col_offset
                end = offsets[node.end_lineno - 1] + node.end_col_offset
                edits.append((start, end, f'resolve_historical({ast.get_source_segment(source, node.right)}, {ast.get_source_segment(source, left)})'))
            # Exclude nested overlapping edits; the outer call resolves the full suffix.
            selected = []
            for edit in sorted(edits, key=lambda x: (x[0], -x[1])):
                if not selected or edit[0] >= selected[-1][1]:
                    selected.append(edit)
            if selected:
                for start, end, value in reversed(selected):
                    source = source[:start] + value + source[end:]
                if 'from repository_paths import resolve_historical' not in source:
                    insertion = 0
                    for node in tree.body:
                        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) or (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
                            insertion = offsets[node.end_lineno]
                        else:
                            break
                    source = source[:insertion] + 'from repository_paths import resolve_historical\n' + source[insertion:]
                ast.parse(source)
                path.write_text(source, encoding='utf-8', newline='\n')
                changed.append({'path': path.relative_to(ROOT).as_posix(), 'expressions': len(selected)})
    (ROOT / 'docs/reorganization/DYNAMIC_REWRITE.json').write_text(json.dumps(changed, indent=2) + '\n', encoding='utf-8')
    print(f'{len(changed)} dynamic path consumers migrated')


def migrate_docs():
    mappings = json.loads((ROOT / 'repository_paths.json').read_text())['prefixes']
    names = [ROOT / 'README.md', ROOT / 'CLAUDE.md', ROOT / 'docs/FRF_QUICKSTART.md', *(ROOT / 'code').glob('README_*.md')]
    changed = []
    for path in names:
        text = path.read_text(encoding='utf-8-sig')
        before = text
        for old, new in sorted(mappings.items(), key=lambda item: -len(item[0])):
            text = re.sub(r'(?<![\w/\\])' + re.escape(old) + r'(?=$|[^A-Za-z0-9_])', lambda _: new, text, flags=re.MULTILINE)
        text = re.sub(r'(?<![\w/\\])CHECKPOINT_(\d+)\.md', r'docs/checkpoints/CHECKPOINT_\1.md', text)
        if text != before:
            path.write_text(text, encoding='utf-8', newline='\n')
            changed.append(path.relative_to(ROOT).as_posix())
    (ROOT / 'docs/reorganization/DOC_REWRITE.json').write_text(json.dumps(changed, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if '--docs' in sys.argv:
        migrate_docs()
    elif '--dynamic' in sys.argv:
        migrate_dynamic()
    else:
        main()
