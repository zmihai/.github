# Specification: Add PHP Support

## Goal
Add reusable workflows and actions to support PHP projects within the organization.

## Requirements
- Create \ctions/setup-php-env/action.yml\ to handle PHP setup, extensions, and composer caching.
- Create \.github/workflows/reusable-php-ci.yml\ for linting and testing PHP code.
- Support Composer for dependency installation.
- Support PHPUnit for running tests.
- Update other reusable workflows (e.g., `reusable-security-scan.yml`) to include PHP references and language-specific steps.