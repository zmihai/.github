import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW_DIR = REPO_ROOT / '.github' / 'workflows'
LOCKFILE = WORKFLOW_DIR / 'actions.lock'

# A full release tag: v6.0.2, 2.37.0. Not a floating v6 / v6.0, a branch or a SHA.
RELEASE_TAG = re.compile(r'v?\d+\.\d+\.\d+')
LOCKED_COMMIT = re.compile(r'sha1-[0-9a-f]{40}')

# The one ref that is not a release tag: the commit we need is on main and has
# no tag, so the workflows name the commit and the lockfile keys the entry by it.
NON_TAG_REFS_ALLOWED = {
    'google-github-actions/run-gemini-cli@3ca2577f2714990269a7378904cf70ae1e01e288',
}

# Why this file exists: the runner only resolves actions from the lockfile
# when a workflow's `uses:` refs are the ones the lockfile lists for it. When
# they differ (a bare SHA where the lockfile has the release tag), the runner
# silently ignores the lockfile for that workflow, and `gh actions-lock
# --verify` still reports it valid. These tests compare the two as text.
# They are a net for honest mistakes, not a defence against deliberate evasion.


def load(path):
    return yaml.safe_load(path.read_text()) or {}


def step_uses(document):
    # `uses:` values of every step, for a workflow (jobs.*.steps) or a
    # composite action (runs.steps).
    step_lists = [job.get('steps') or [] for job in (document.get('jobs') or {}).values()]
    step_lists.append((document.get('runs') or {}).get('steps') or [])
    return [str(step['uses']) for steps in step_lists for step in steps if 'uses' in step]


def lock_key(ref):
    # 'github/codeql-action/init@v4' -> 'github/codeql-action@v4': the lockfile
    # records a repository once, whichever of its sub-path actions is used.
    name, _, version = ref.partition('@')
    return '/'.join(name.split('/')[:2]) + '@' + version


def third_party_refs(document, seen=None):
    # Third-party refs a workflow needs locked: its own steps' refs plus those
    # of this repository's composite actions it runs through `$/` refs.
    seen = set() if seen is None else seen
    refs = set()
    for ref in step_uses(document):
        if ref.startswith('$/'):
            if ref in seen:
                continue
            seen.add(ref)
            action_dir = REPO_ROOT / ref[2:]
            manifest = next(p for p in (action_dir / 'action.yml', action_dir / 'action.yaml') if p.is_file())
            refs |= third_party_refs(load(manifest), seen)
        elif not ref.startswith(('./', 'docker://')):
            refs.add(lock_key(ref))
    return refs


def workflow_files():
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in ('.yml', '.yaml'))


def test_lockfile_lists_exactly_the_refs_each_workflow_uses():
    locked = load(LOCKFILE).get('workflows') or {}
    files = workflow_files()
    assert files, 'no workflow files found'
    checked = 0
    for path in files:
        name = path.relative_to(REPO_ROOT).as_posix()
        used = third_party_refs(load(path))
        assert used == set(locked.get(name) or []), (
            f'{name}: `uses:` refs and lockfile entries differ - run `gh actions-lock`'
        )
        checked += len(used)
    assert checked, 'no third-party action refs were compared'
    assert set(locked) <= {p.relative_to(REPO_ROOT).as_posix() for p in files}, (
        'the lockfile records a workflow file that does not exist'
    )


def test_every_listed_ref_has_a_locked_commit():
    lock = load(LOCKFILE)
    dependencies = lock.get('dependencies') or {}
    listed = {ref for refs in (lock.get('workflows') or {}).values() for ref in refs}
    listed |= {ref for entry in dependencies.values() for ref in entry.get('uses') or []}
    assert listed, 'the lockfile lists no refs'
    for ref in sorted(listed):
        assert ref in dependencies, f'{ref} has no entry under dependencies'
        assert LOCKED_COMMIT.fullmatch(str(dependencies[ref].get('commit'))), f'{ref} has no locked commit'


def test_uses_refs_name_a_full_release_tag():
    documents = [load(p) for p in workflow_files()]
    documents += [load(p) for p in sorted((REPO_ROOT / 'actions').rglob('action.y*ml'))]
    refs = {lock_key(ref) for document in documents for ref in step_uses(document)
            if not ref.startswith(('$/', './', 'docker://'))}
    assert refs, 'no third-party `uses:` refs found'
    assert NON_TAG_REFS_ALLOWED <= refs, 'an allowed exception is no longer used - remove it'
    not_tags = sorted(ref for ref in refs - NON_TAG_REFS_ALLOWED
                      if not RELEASE_TAG.fullmatch(ref.partition('@')[2]))
    assert not_tags == [], (
        'write the full release tag (not a SHA, a floating major/minor tag or a branch) '
        'and run `gh actions-lock`; the lockfile pins the commit'
    )
