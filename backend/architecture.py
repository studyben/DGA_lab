"""Static import policy. Business behavior tests live at public application seams."""
import ast
from importlib.util import resolve_name

BUSINESS = {'assets', 'laboratory', 'condition_analysis'}
ALLOWED = {'assets': set(), 'laboratory': {'assets'}, 'condition_analysis': {'assets', 'laboratory'}, 'shared': set()}


def violations(source: str, code: str, is_package: bool = False) -> list[str]:
    owner = source.split('.')[1] if '.' in source else ''
    package = source if is_package else source.rpartition('.')[0]
    errors = []
    for node in ast.walk(ast.parse(code)):
        targets = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                base = resolve_name('.' * node.level + base, package)
            targets = [base + '.' + alias.name for alias in node.names]
        for target in targets:
            parts = target.split('.')
            if len(parts) < 2 or parts[0] != 'dga':
                continue
            destination = parts[1]
            if owner in ALLOWED and destination == 'main':
                errors.append(f'{source}:{node.lineno}: reverse dependency on composition root')
            if destination in BUSINESS and destination != owner:
                if len(parts) < 3 or parts[2] != 'public' or (owner in ALLOWED and destination not in ALLOWED[owner]):
                    errors.append(f'{source}:{node.lineno}: forbidden dependency {target}')
    return errors
