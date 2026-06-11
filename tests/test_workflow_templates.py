import json

# One root-level marker file per supported ecosystem; the workflow templates
# should be auto-suggested for repos of any supported language.
EXPECTED_PATTERNS = {
    'package.json$',        # javascript
    'composer.json$',       # php
    'requirements.txt$',    # python
    'pyproject.toml$',      # python
    'pom.xml$',             # java (maven)
    'build.gradle$',        # java (gradle)
    'build.gradle.kts$',
    'settings.gradle$',
    'settings.gradle.kts$',
}

def test_ci_template_suggested_for_all_supported_languages():
    with open('workflow-templates/ci.properties.json', 'r') as f:
        properties = json.load(f)
    assert set(properties['filePatterns']) == EXPECTED_PATTERNS

def test_security_scan_template_suggested_for_all_supported_languages():
    with open('workflow-templates/security-scan.properties.json', 'r') as f:
        properties = json.load(f)
    assert set(properties['filePatterns']) == EXPECTED_PATTERNS
