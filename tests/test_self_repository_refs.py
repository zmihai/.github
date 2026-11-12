import posixpath
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW_DIR = REPO_ROOT / '.github' / 'workflows'
ACTION_DIR = REPO_ROOT / 'actions'
TEMPLATE_DIR = REPO_ROOT / 'workflow-templates'

# This repository, as other repositories name it in a `uses:` value.
THIS_REPO = 'zmihai/.github/'
SELF_REF = re.compile(r'\$/[A-Za-z0-9._/-]+')
TEMPLATE_REF = re.compile(re.escape(THIS_REPO) + r'[A-Za-z0-9._/-]+@v\d+\.\d+\.\d+')


def is_this_repo(ref):
    # Owner and repository names are case-insensitive on GitHub.
    return str(ref).lower().startswith(THIS_REPO)

# These are convention guards for honest mistakes, not a defence against
# deliberate evasion. They read the parsed YAML, so quoting and folded
# scalars make no difference.


def yaml_files(directory):
    return sorted(p for p in directory.rglob('*') if p.suffix in ('.yml', '.yaml'))


def uses_refs(directory):
    """Every `uses:` value under directory as (file, 'job' | 'step', value)."""
    refs = []
    for path in yaml_files(directory):
        document = yaml.safe_load(path.read_text()) or {}
        name = str(path.relative_to(REPO_ROOT))
        jobs = document.get('jobs') or {}
        for job in jobs.values():
            if 'uses' in job:
                refs.append((name, 'job', job['uses']))
            for step in job.get('steps') or []:
                if 'uses' in step:
                    refs.append((name, 'step', step['uses']))
        for step in (document.get('runs') or {}).get('steps') or []:
            if 'uses' in step:
                refs.append((name, 'step', step['uses']))
    return refs


def repo_refs():
    return uses_refs(WORKFLOW_DIR) + uses_refs(ACTION_DIR)


def test_self_repository_refs_point_at_existing_targets():
    # actionlint does not model `$/` yet (self-ci.yml ignores its complaint),
    # so the shape and the target of every self repository reference are
    # checked here instead.
    self_refs = [r for r in repo_refs() if str(r[2]).startswith('$')]
    assert self_refs, 'expected the workflows to use $/ self repository references'
    for name, kind, ref in self_refs:
        assert SELF_REF.fullmatch(ref), f'{name}: {ref!r} is not a plain $/path (no @ref)'
        assert posixpath.normpath(ref[2:]) == ref[2:], f'{name}: {ref!r} is not a canonical path'
        target = REPO_ROOT / ref[2:]
        if kind == 'job':
            assert target.parent == WORKFLOW_DIR and target.is_file(), (
                f'{name}: job-level {ref!r} is not a workflow in .github/workflows')
        else:
            assert target.is_dir() and any(
                (target / metadata).is_file() for metadata in ('action.yml', 'action.yaml')
            ), f'{name}: step-level {ref!r} is not an action directory'


def test_workflows_do_not_reference_this_repository_by_tag():
    # A tagged self reference has to be swept on every release and points at
    # a tag that does not exist until the release is published.
    refs = repo_refs()
    assert refs, 'expected the workflows to contain uses: references'
    assert [r for r in refs if is_this_repo(r[2])] == []


def test_workflow_steps_do_not_use_workspace_local_actions():
    # A step-level `./path` resolves against the runner's workspace, which in
    # a reusable workflow is the consumer's checkout, not this repository.
    # (Job-level `./.github/workflows/x.yml` calls are fine: they resolve to
    # this repository at the caller's commit.)
    refs = repo_refs()
    assert any(kind == 'step' for _, kind, _ in refs)
    assert [r for r in refs if r[1] == 'step' and str(r[2]).startswith('.')] == []


def test_templates_reference_this_repository_by_tag():
    # Templates are copied into consumer repositories, where `$/` would
    # resolve to the consumer, not to this repository.
    # Every reference in the templates is to this repository, by release tag:
    # no `$/`, no `./`, no missing or floating ref.
    refs = uses_refs(TEMPLATE_DIR)
    assert refs, 'expected the templates to contain uses: references'
    assert [r for r in refs if not TEMPLATE_REF.fullmatch(str(r[2]))] == []
