import os
import yaml
import pytest

def test_setup_java_env_exists():
    assert os.path.exists('actions/setup-java-env/action.yml')

def test_setup_java_env_schema():
    with open('actions/setup-java-env/action.yml', 'r') as f:
        action = yaml.safe_load(f)
    assert action['name'] == 'Setup Java Environment'
    assert 'java-version' in action['inputs']
    assert 'distribution' in action['inputs']
    assert 'system-packages' in action['inputs']
    assert 'build-tool' in action['outputs']

def test_setup_java_env_fails_without_supported_build_tool():
    with open('actions/setup-java-env/action.yml', 'r') as f:
        action = yaml.safe_load(f)
    detect = next(s for s in action['runs']['steps']
                  if s.get('id') == 'detect')
    assert 'No supported Java build tool found' in detect['run']
    assert 'exit 1' in detect['run']
    assert 'tool=none' not in detect['run']

def test_setup_java_env_safely_installs_system_packages():
    with open('actions/setup-java-env/action.yml', 'r') as f:
        action = yaml.safe_load(f)
    install = next(s for s in action['runs']['steps']
                   if s.get('name') == 'Install system packages')
    script = install['run']
    assert install['env']['SYSTEM_PACKAGES'] == '${{ inputs.system-packages }}'
    assert "IFS=$' \\t,' read -r -a raw_packages" in script
    assert "system-packages must be a single comma- or space-separated line" in script
    assert 'packages+=("$package")' in script
    assert '[[ "$package" == -*' in script
    assert '^[a-z0-9][a-z0-9.+-]*$' in script
    assert 'sudo apt-get install -y --no-install-recommends -- "${packages[@]}"' in script
    assert '$PACKAGES' not in script

def test_ci_java_passes_extensions_as_system_packages():
    with open('.github/workflows/ci-java.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    setup = next(s for s in workflow['jobs']['ci']['steps']
                 if s.get('id') == 'setup')
    assert setup['with']['system-packages'] == '${{ inputs.extensions }}'

def test_reusable_java_ci_exists():
    assert os.path.exists('.github/workflows/ci-java.yml')

def test_reusable_ci_dispatches_java():
    with open('.github/workflows/reusable-ci.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    assert 'ci-java' in workflow['jobs']

def test_security_scan_supports_java():
    with open('.github/workflows/reusable-security-scan.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    assert 'dependency-scan-java' in workflow['jobs']
