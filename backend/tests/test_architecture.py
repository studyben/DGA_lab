from pathlib import Path

import pytest
from architecture import violations


@pytest.mark.parametrize('source,statement', [
    ('dga.laboratory.service', 'from dga.assets.internal import Repository'),
    ('dga.laboratory.service', 'from ..assets import internal'),
    ('dga.assets.service', 'from dga.laboratory.public import MODULE'),
    ('dga.shared.config', 'import dga.assets.public'),
    ('dga.laboratory.service', 'from dga import assets'),
])
def test_forbidden_dependency_is_rejected(source, statement):
    assert violations(source, statement)


def test_public_forward_dependencies_are_allowed():
    assert violations('dga.laboratory.service', 'from ..assets.public import MODULE') == []
    assert violations('dga.condition_analysis.public', 'from dga.laboratory.public import MODULE') == []


def test_application_obeys_module_ownership():
    errors = []
    for path in Path('dga').rglob('*.py'):
        name = '.'.join(path.with_suffix('').parts)
        if name.endswith('.__init__'):
            name = name.removesuffix('.__init__')
        errors.extend(violations(name, path.read_text(encoding='utf-8'), path.name == '__init__.py'))
    assert errors == []
