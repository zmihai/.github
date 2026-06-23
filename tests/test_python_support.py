import os
import yaml

def test_setup_python_env_exists():
    assert os.path.exists('actions/setup-python-env/action.yml')

def test_setup_python_env_schema():
    with open('actions/setup-python-env/action.yml', 'r') as f:
        action = yaml.safe_load(f)
    assert action['name'] == 'Setup Python Environment'
    assert 'python-version' in action['inputs']
    assert 'install-dependencies' in action['inputs']
    assert 'working-directory' in action['inputs']

def test_reusable_python_ci_exists():
    assert os.path.exists('.github/workflows/ci-python.yml')

def test_security_scan_supports_python():
    with open('.github/workflows/reusable-security-scan.yml', 'r') as f:
        workflow = yaml.safe_load(f)
    assert 'dependency-scan-python' in workflow['jobs']
