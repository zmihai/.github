import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW_DIR = REPO_ROOT / '.github' / 'workflows'
TEMPLATE_DIR = REPO_ROOT / 'workflow-templates'

USES = re.compile(r'''^\s*(?:-\s*)?uses:\s*['"]?([^'"\s#]+)''')


def uses_refs(directory):
    refs = []
    for path in sorted(directory.glob('*.yml')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = USES.match(line)
            if match:
                refs.append((f'{path.name}:{number}', match.group(1)))
    return refs


def test_self_repository_refs_point_at_existing_targets():
    # actionlint does not model `$/` yet (self-ci.yml ignores its complaint),
    # so the shape and the target of every self repository reference are
    # checked here instead.
    self_refs = [(where, ref) for where, ref in uses_refs(WORKFLOW_DIR) if ref.startswith('$/')]
    assert self_refs, 'expected the workflows to use $/ self repository references'
    for where, ref in self_refs:
        assert '@' not in ref, f'{where}: {ref} must not carry an @ref'
        target = REPO_ROOT / ref[2:]
        if target.suffix in ('.yml', '.yaml'):
            assert target.is_file(), f'{where}: {ref} does not exist'
        else:
            assert (target / 'action.yml').is_file(), f'{where}: {ref} has no action.yml'


def test_workflows_do_not_reference_this_repository_by_tag():
    # A tagged self reference has to be swept on every release and points at
    # a tag that does not exist until the release is published.
    tagged = [
        (where, ref) for where, ref in uses_refs(WORKFLOW_DIR)
        if re.match(r'[^./$][^/]*/\.github/', ref)
    ]
    assert tagged == []


def test_templates_do_not_use_self_repository_refs():
    # Templates are copied into consumer repositories, where `$/` would
    # resolve to the consumer, not to this repository.
    refs = uses_refs(TEMPLATE_DIR)
    assert refs, 'expected the templates to contain uses: references'
    assert [(where, ref) for where, ref in refs if ref.startswith('$/')] == []
