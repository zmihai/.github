# .github - Common Workflows & Actions

This repository contains reusable workflows, composite actions, and workflow templates that can be used across all repositories in this organization.

## 📋 Contents

- [Reusable Workflows](#reusable-workflows)
- [Gemini AI Workflows](#gemini-ai-workflows)
- [Composite Actions](#composite-actions)
- [Workflow Templates](#workflow-templates)
- [Usage Examples](#usage-examples)

---

## 🔄 Reusable Workflows

Reusable workflows are stored in `.github/workflows/` and can be called from other repositories.

### CI Workflow

**Path:** `.github/workflows/reusable-ci.yml`

A comprehensive CI workflow that handles linting, testing, and building for multiple languages. Use this workflow to generate the `ci-outcome` for the Gemini Review/Merge workflows.

**Inputs:**
- `language` (string, default: 'javascript'): Language to use ('javascript', 'python', or 'php')
- `language-version` (string): Version of the language to use (examples: '20' for JS, '3.11' for Python, '8.3' for PHP)
- `working-directory` (string, default: '.'): Working directory for commands
- `run-lint` (boolean, default: true): Run linting
- `run-test` (boolean, default: true): Run tests (JS and PHP only)
- `run-build` (boolean, default: true): Run build (JS only)
- `build-before-test` (boolean, default: false): Run build before tests (JS only)

**Outputs:**
- `outcome`: The result of the CI run (`success` or `failure`).

**Secrets:**
- `CUSTOM_TOKEN` (optional): Custom token for private packages (JS only)

**Example Usage:**
```yaml
jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'php'
      language-version: '8.3'
      run-lint: true
```

### Security Scan Workflow

**Path:** `.github/workflows/reusable-security-scan.yml`

Performs security scanning including dependency audits and CodeQL analysis. Supports JavaScript, Python, and PHP. Use this workflow to generate the `scan-outcome` for the Gemini Review/Merge workflows.

**Inputs:**
- `scan-dependencies` (boolean, default: true): Scan dependencies for vulnerabilities
- `scan-code` (boolean, default: false): Run CodeQL analysis
- `language` (string, default: 'javascript'): Language for CodeQL ('javascript', 'python', or 'php')
- `working-directory` (string, default: '.'): Working directory

**Outputs:**
- `outcome`: The overall result of the security scans (`success` or `failure`).

**Example Usage:**
```yaml
jobs:
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.6.0
    with:
      scan-dependencies: true
      scan-code: true
      language: 'php'
```

---

## 🤖 Gemini AI Workflows

These workflows integrate Google Gemini for automated PR reviews and merging.

### Gemini Dispatch

**Path:** `.github/workflows/reusable-gemini-dispatch.yml`

The entry point for Gemini commands. It parses comments like `@gemini-cli /review` and dispatches to the appropriate workflow.

### Gemini Review

**Path:** `.github/workflows/gemini-review.yml`

Performs an AI-powered review of a Pull Request, providing feedback and suggestions.

### Gemini Test & Merge

**Path:** `.github/workflows/gemini-merge.yml`

Uses Gemini to analyze CI/Security results and merge the PR if everything passes. It expects a JSON list of projects, each including the `ci-outcome` and `scan-outcome`.

**Inputs:**
- `pull_request_number` (string, required): The PR number.
- `projects` (string, required): A JSON array of project objects. Each object must follow this schema:
  ```json
  {
    "working-directory": "./python-server",
    "language": "python",
    "language-version": "3.11",
    "ci-outcome": "success",
    "scan-outcome": "failure"
  }
  ```
- `review_summary` (string, optional): Summary from a previous review step.

---

## 🎬 Composite Actions

Composite actions are reusable action steps that can be used in any workflow.

### Setup Node Environment

**Path:** `actions/setup-node-env/action.yml`

Sets up Node.js environment with caching and automatic dependency installation.

**Inputs:**
- `node-version` (default: '20'): Node.js version
- `cache` (default: 'npm'): Package manager (npm, yarn, pnpm)
- `install-dependencies` (default: 'true'): Auto-install dependencies
- `working-directory` (default: '.'): Working directory

**Outputs:**
- `cache-hit`: Whether cache was hit


**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/setup-node-env@v0.6.0
    with:
      node-version: '20'
      cache: 'npm'
```

### Setup PHP Environment

**Path:** `actions/setup-php-env/action.yml`

Sets up PHP environment with composer caching and automatic dependency installation.

**Inputs:**
- `php-version` (default: '8.3'): PHP version
- `install-dependencies` (default: 'true'): Auto-install dependencies
- `working-directory` (default: '.'): Working directory
- `extensions` (default: 'json, mbstring, xml, iconv'): PHP extensions to install

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/setup-php-env@v0.6.0
    with:
      php-version: '8.2'
      extensions: 'gd, intl, zip'
      install-dependencies: 'false'
```

### Setup Python Environment

**Path:** `actions/setup-python-env/action.yml`

Sets up Python environment with pip caching and automatic dependency installation from `requirements.txt` and `pyproject.toml`.

**Inputs:**
- `python-version` (default: '3.11'): Python version
- `install-dependencies` (default: 'true'): Auto-install dependencies
- `working-directory` (default: '.'): Working directory

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/setup-python-env@v0.6.0
    with:
      python-version: '3.11'
```

---

## 📝 Workflow Templates

Workflow templates are starter workflows that appear in the "Actions" tab of your repositories.

Available templates:
- **CI Workflow** (`workflow-templates/ci.yml`) - Complete CI pipeline
- **Security Scan** (`workflow-templates/security-scan.yml`) - Security scanning

---

## 💡 Usage Examples

### Gemini Merge Workflow (Multi-Project)

To use the Gemini Merge workflow, you'll need to provide a JSON list of projects as input. Here's how to call it by capturing outputs from the reusable workflows:

```yaml
name: Merge Request

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  ci_project_a:
    name: CI - Project A
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'python'
      language-version: '3.11'
      working-directory: './project_a'

  security_project_a:
    name: Security - Project A
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.6.0
    with:
      language: 'python'
      working-directory: './project_a'

  ci_project_b:
    name: CI - Project B
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'javascript'
      language-version: '20'
      working-directory: './project_b'

  security_project_b:
    name: Security - Project B
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.6.0
    with:
      language: 'javascript'
      working-directory: './project_b'

  aggregate:
    name: Aggregate Results
    runs-on: ubuntu-latest
    needs: [ci_project_a, security_project_a, ci_project_b, security_project_b]
    if: always()
    outputs:
      projects_json: ${{ steps.build_json.outputs.projects }}

    steps:
      - name: Build Projects JSON
        id: build_json
        run: |
          PROJECTS=$(cat <<EOF
          [
            {
              "working-directory": "./project_a",
              "language": "python",
              "language-version": "3.11",
              "ci-outcome": "${{ needs.ci_project_a.outputs.outcome }}",
              "scan-outcome": "${{ needs.security_project_a.outputs.outcome }}"
            },
            {
              "working-directory": "./project_b",
              "language": "javascript",
              "language-version": "20",
              "ci-outcome": "${{ needs.ci_project_b.outputs.outcome }}",
              "scan-outcome": "${{ needs.security_project_b.outputs.outcome }}"
            }
          ]
          EOF
          )
          # Escape for GitHub Actions output
          echo "projects=$(echo "$PROJECTS" | jq -c .)" >> $GITHUB_OUTPUT

  gemini_merge:
    name: Gemini Merge
    needs: aggregate
    uses: zmihai/.github/.github/workflows/gemini-merge.yml@v0.6.0
    with:
      pull_request_number: ${{ github.event.pull_request.number }}
      projects: ${{ needs.aggregate.outputs.projects_json }}
    secrets: inherit
```

### Complete CI Pipeline (PHP)

```yaml
name: CI

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'php'
      language-version: '8.3'
  
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.6.0
    with:
      language: 'php'
      scan-dependencies: true
      scan-code: true
```

### Complete CI Pipeline (Python)

```yaml
name: CI

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'python'
      language-version: '3.11'
  
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.6.0
    with:
      language: 'python'
      scan-dependencies: true
      scan-code: true
```

---

## 🚀 Getting Started

### Using Reusable Workflows

1. In your repository, create a workflow file (e.g., `.github/workflows/ci.yml`)
2. Reference reusable workflows using `uses: zmihai/.github/.github/workflows/<name>.yml@v0.6.0`
3. Reference composite actions using `uses: zmihai/.github/actions/<name>@v0.6.0`
4. Pass required inputs and secrets

---

## 📚 Best Practices

1. **Pin versions**: Use specific tags (like `@v0.6.0`) or commit SHAs in production.
2. **Security**: Use GitHub Secrets for all sensitive information.
3. **Testing**: Test workflow changes in a separate branch before merging to master
4. **Documentation**: Keep this README updated when adding new workflows or actions
5. **Timeouts**: All jobs should have a `timeout-minutes` set.

---

## 🤝 Contributing

When adding new workflows or actions:

1. Follow the existing structure and naming conventions
2. Add comprehensive documentation to this README
3. Include usage examples
4. Test thoroughly before merging

---

## 📄 License

This repository is provided as-is. Keep it mind it was build for personal/internal use, so support may or may not be provided. 

---

## 📞 Support

For questions or issues, please open an issue in this repository.
