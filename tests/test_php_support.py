import os
import yaml
import pytest

def test_setup_php_env_exists():
    assert os.path.exists('actions/setup-php-env/action.yml')

def test_setup_php_env_schema():
    with open('actions/setup-php-env/action.yml', 'r') as f:
        action = yaml.safe_load(f)
    assert action['name'] == 'Setup PHP Environment'
    assert 'php-version' in action['inputs']

def test_reusable_php_ci_exists():
    assert os.path.exists('.github/workflows/ci-php.yml')
