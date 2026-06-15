import json
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / 'workflow-templates'

# One marker file per supported ecosystem; the workflow templates should be
# auto-suggested for repos of any supported language. Patterns are regexes
# (dots escaped to match a literal '.') and are intentionally not anchored to
# the repo root, so a marker file matches anywhere in the tree — e.g. a
# monorepo's frontend/package.json still triggers the suggestion.
EXPECTED_PATTERNS = {
    r'package\.json$',        # javascript
    r'composer\.json$',       # php
    r'requirements\.txt$',    # python
    r'pyproject\.toml$',      # python
    r'pom\.xml$',             # java (maven)
    r'build\.gradle$',        # java (gradle)
    r'build\.gradle\.kts$',
    r'settings\.gradle$',
    r'settings\.gradle\.kts$',
}

def test_ci_template_suggested_for_all_supported_languages():
    with open(TEMPLATE_DIR / 'ci.properties.json', 'r') as f:
        properties = json.load(f)
    assert set(properties['filePatterns']) == EXPECTED_PATTERNS

def test_security_scan_template_suggested_for_all_supported_languages():
    with open(TEMPLATE_DIR / 'security-scan.properties.json', 'r') as f:
        properties = json.load(f)
    assert set(properties['filePatterns']) == EXPECTED_PATTERNS
