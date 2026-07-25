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
- `language` (string, default: 'javascript'): Language to use ('javascript', 'python', 'php', or 'java')
- `language-version` (string): Version of the language to use (examples: '20' for JS, '3.11' for Python, '8.4' for PHP, '21' for Java)
- `working-directory` (string, default: '.'): Working directory for commands
- `extensions` (string, default: ''): Extra extensions or packages to install during environment setup. For **PHP** these are passed as extensions to `shivammathur/setup-php`. For **Java** these are installed as apt system packages before the build (e.g. `protobuf-compiler` to provide `protoc`). Not yet used by JS/Python.
- `run-lint` (boolean, default: true): Run linting. For Java this always compiles main + test sources, and additionally runs SpotBugs/Checkstyle when those plugins are configured.
- `run-test` (boolean, default: true): Run tests
- `run-build` (boolean, default: true): Run build (JS and Java). For Java this runs Maven `package` with tests skipped, or Gradle `assemble` so lint/check tasks remain controlled by `run-lint`.
- `build-before-test` (boolean, default: false): Run build before tests (JS only)
- `ref` (string, optional): The branch, tag or SHA to checkout. Automatically resolves the PR head SHA if available. Defaults to `github.sha` otherwise.

**Outputs:**
- `outcome`: The result of the CI run (`success` or `failure`).

**Secrets:**
- `CUSTOM_TOKEN` (optional): Custom token for private packages (JS only)

**Example Usage:**
```yaml
# The ref-resolution job inside the called workflow requests these reads;
# GitHub validates nested permission requests against this grant at startup.
permissions:
  contents: read
  issues: read
  pull-requests: read

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'php'
      language-version: '8.4'
      run-lint: true
```

### Security Scan Workflow

**Path:** `.github/workflows/reusable-security-scan.yml`

Performs security scanning including dependency audits and CodeQL analysis. Supports JavaScript, Python, PHP, and Java. Use this workflow to generate the `scan-outcome` for the Gemini Review/Merge workflows.

Dependency scanning uses the native auditor per language:
- **JavaScript**: Uses `npm audit`.
- **Python**: Uses `pip-audit` against committed `requirements*.txt` or `requirements/*.txt` files. For `uv`-managed projects, if a `uv.lock` is present, it is automatically exported to a temporary requirements file (`uv export --frozen`, read-only, no project build) before running the audit.
- **PHP**: Uses `composer audit`.
- **Java**: Uses a [Trivy](https://github.com/aquasecurity/trivy) filesystem scan (fails on `MEDIUM`/`HIGH`/`CRITICAL` vulnerabilities). Trivy can scan Maven `pom.xml` files, built JAR/WAR/PAR/EAR artifacts, and committed Gradle/SBT lockfiles; a Gradle project with only `build.gradle`/`build.gradle.kts` may not have its dependencies fully assessed by this reusable workflow.

The security scan workflow is independent from the CI workflow and does not build Java projects or generate dependency lockfiles before scanning. CodeQL (`scan-code: true`) covers Java code analysis natively.

**Inputs:**
- `scan-dependencies` (boolean, default: true): Scan dependencies for vulnerabilities
- `scan-code` (boolean, default: false): Run CodeQL analysis
- `language` (string, default: 'javascript'): Language for CodeQL ('javascript', 'python', 'php', or 'java')
- `language-version` (string, optional): Language version to use (20, 3.11, 8.4, etc)
- `working-directory` (string, default: '.'): Working directory
- `ref` (string, optional): The branch, tag or SHA to checkout. Automatically resolves the PR head SHA if available. Defaults to `github.sha` otherwise.

**Outputs:**
- `outcome`: The overall result of the security scans (`success` or `failure`).

**Example Usage:**
```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
  # Needed only because scan-code is true below (CodeQL):
  security-events: write
  actions: read

jobs:
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      scan-dependencies: true
      scan-code: true
      language: 'php'
      language-version: '8.4'
```

---

## 🤖 Gemini AI Workflows

These workflows integrate Google Gemini for automated PR reviews and merging.

### Gemini Model Selection

The Gemini workflows select models from task-specific variables first, then fall back to the shared `GEMINI_MODEL` variable. If neither is set, the workflow uses `gemini-flash-latest`.

- `GEMINI_REVIEW_MODEL`: Pull request review model.
- `GEMINI_SECURITY_REVIEW_MODEL`: Security-focused review model.
- `GEMINI_MERGE_MODEL`: Merge workflow model.
- `GEMINI_MODEL`: Shared fallback model for all Gemini tasks.
- `GEMINI_CLI_VERSION`: Optional Gemini CLI version override. If unset, the
  Gemini workflows pin to `0.46.0` instead of floating `latest`, because newer
  CLI releases tightened environment/MCP permissions and require prompt/action
  updates before they can safely replace the pinned default.

### Gemini Guard

**Path:** `.github/workflows/reusable-gemini-guard.yml`

The single source of truth for the Gemini trigger policy. Run it as the **first job** of your caller workflow — before any job that checks out code or receives secrets — and gate everything downstream on its outputs. `reusable-gemini-dispatch` calls it internally too, so your gate and the dispatch's gate can never drift apart.

It validates the trigger (non-fork `pull_request` events; `issues` opened/reopened; comments/reviews starting with `@gemini-cli` from an `OWNER`/`MEMBER`/`COLLABORATOR` human user — and `@gemini-cli` commands in *any* event, including issue bodies, are honored only from such authors), resolves the PR head SHA (via the API for `issue_comment` events, whose payload carries no PR head — without this a caller-side build silently builds the default branch), and computes `is_fork` **failing closed**.

**Inputs:**
- `ref` (string, optional): Overrides PR-head resolution.

**Outputs:**
- `proceed` (`'true'`/`'false'`): Whether the event passes the trigger policy. Gate every downstream job on this.
- `resolved_ref`: The PR head SHA (or the `ref` input, or the event SHA). Pass it as the `ref` input of `reusable-ci`, `reusable-security-scan`, and `reusable-gemini-dispatch` so every job builds and reviews the same commit.
- `is_fork` (`'true'`/`'false'`): Fails closed — never build or expose secrets to the ref when `'true'`.
- `is_pr` (`'true'`/`'false'`): Whether the event relates to a PR. Use it to skip build jobs on plain issues.
- `command`, `request`, `additional_context`, `issue_number`: The parsed `@gemini-cli` command and its context.

**Recommended caller-side gates:**

```yaml
jobs:
  guard:
    uses: zmihai/.github/.github/workflows/reusable-gemini-guard.yml@v0.12.2

  ci:
    needs: guard
    if: >-
      needs.guard.outputs.proceed == 'true' &&
      needs.guard.outputs.is_pr == 'true' &&
      needs.guard.outputs.is_fork == 'false'
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'javascript'
      language-version: '20'
      ref: ${{ needs.guard.outputs.resolved_ref }}
```

See `workflow-templates/gemini.yml` for the full caller pattern.

### Gemini Dispatch

**Path:** `.github/workflows/reusable-gemini-dispatch.yml`

The entry point for Gemini commands. It parses comments like `@gemini-cli /review` (via the Gemini Guard workflow above) and dispatches to the appropriate workflow.

**Inputs:**
- `projects` (string, required): JSON list of projects.
- `ref` (string, optional): The branch, tag or SHA to checkout. Automatically resolves the PR head SHA if available. Defaults to `github.sha` otherwise.

**Caller permissions:** the caller's `GITHUB_TOKEN` caps what called reusable workflows can do, so the calling workflow must grant at least:

```yaml
permissions:
  contents: write        # gemini-merge pushes remediation commits and merges
  pull-requests: write   # reviews, review comments, merging
  issues: write          # acknowledgement / failure comments
  id-token: write        # GCP Workload Identity Federation (Vertex AI), if used
```

Callers that also run `reusable-security-scan` with `scan-code: true` (CodeQL) additionally need `security-events: write` and `actions: read` — CodeQL uploads SARIF and reads workflow metadata at runtime. (The `codeql-scan` job deliberately carries no `permissions:` block: GitHub validates nested permission requests against the caller's grant at startup regardless of `if:` conditions, so a static request would startup-fail every least-privilege caller that leaves `scan-code` off.)

### Gemini Review

**Path:** `.github/workflows/gemini-review.yml`

Performs an AI-powered review of a Pull Request, providing feedback and suggestions.

**Inputs:**
- `command` (string, required): The command used to call this workflow.
- `issue_number` (string, required): The issue/pull request number.
- `projects` (string, optional): JSON list of projects.
- `additional_context` (string, optional): Any additional context from the request.
- `ref` (string, optional): The branch, tag or SHA to checkout. Inherited when called via `reusable-gemini-dispatch`. Defaults to the event's ref or PR head SHA for other invocations.

### Gemini Test & Merge

**Path:** `.github/workflows/gemini-merge.yml`

Uses Gemini to analyze CI/Security results and merge the PR when the changes are sound and every failure related to the PR has passed or been remediated; unrelated, pre-existing failures do not block the merge. It can also apply and push a fix for a related failure before merging. It expects a JSON list of projects, each including the `ci-outcome` and `scan-outcome`.

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
- `ref` (string, optional): The branch, tag or SHA to checkout. Inherited when called via `reusable-gemini-dispatch`. Defaults to the event's ref or PR head SHA for other invocations.

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
  - uses: actions/checkout@v6
  - uses: zmihai/.github/actions/setup-node-env@v0.12.2
    with:
      node-version: '20'
      cache: 'npm'
```

### Setup PHP Environment

**Path:** `actions/setup-php-env/action.yml`

Sets up PHP environment with composer caching and automatic dependency installation.

**Inputs:**
- `php-version` (default: '8.4'): PHP version
- `install-dependencies` (default: 'true'): Auto-install dependencies
- `working-directory` (default: '.'): Working directory
- `extensions` (default: ''): PHP extensions to install. Defaults to 'json, mbstring, xml, iconv' if not specified.

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v6
  - uses: zmihai/.github/actions/setup-php-env@v0.12.2
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
  - uses: actions/checkout@v6
  - uses: zmihai/.github/actions/setup-python-env@v0.12.2
    with:
      python-version: '3.11'
```

### Setup Java Environment

**Path:** `actions/setup-java-env/action.yml`

Sets up a JDK (Temurin by default) and auto-detects the build tool (Maven via `pom.xml`, Gradle via `build.gradle(.kts)`/`settings.gradle(.kts)`). The action fails if no supported build tool is found. Enables build-tool caching and best-effort dependency resolution.

**Inputs:**
- `java-version` (default: '21'): Java version
- `distribution` (default: 'temurin'): JDK distribution (temurin, zulu, corretto, etc.)
- `install-dependencies` (default: 'true'): Auto-resolve/download dependencies (non-fatal warmup; real errors surface during the build)
- `working-directory` (default: '.'): Working directory
- `system-packages` (default: ''): Comma- or space-separated apt package names to install before building (e.g. `protobuf-compiler` to provide `protoc`). Package names are validated and option-like or shell-like values are rejected. When called via the reusable CI workflow this maps to the `extensions` input.

**Outputs:**
- `build-tool`: Detected build tool (`maven` or `gradle`)

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v6
  - uses: zmihai/.github/actions/setup-java-env@v0.12.2
    with:
      java-version: '21'
      distribution: 'temurin'
      system-packages: 'protobuf-compiler'
```

---

## 📝 Workflow Templates

Workflow templates are starter workflows that appear in the "Actions" tab of your repositories.

Available templates:
- **CI Workflow** (`workflow-templates/ci.yml`) - Complete CI pipeline
- **Security Scan** (`workflow-templates/security-scan.yml`) - Security scanning
- **Gemini Review & Merge** (`workflow-templates/gemini.yml`) - AI review/merge automation with the guard → CI/scan → dispatch wiring, least-privilege `permissions`, and a per-PR `concurrency` group

Templates are served from the repository's **default branch** (not a version tag), so changes to the `workflow-templates/` directory take effect without a new release.

### Auto-suggestion (`filePatterns`)

Each template has a `*.properties.json` whose `filePatterns` decide when GitHub suggests the template for a repository. The entries are **regexes** matched against the repo's file paths, with one marker file per supported ecosystem (`package.json`, `composer.json`, `requirements.txt`/`pyproject.toml`, `pom.xml`/`build.gradle(.kts)`/`settings.gradle(.kts)`).

Two intentional conventions:
- **Dots are escaped** (`package\.json$`) so they match a literal `.` rather than any character.
- **Patterns are not anchored to the repo root** (no leading `^`). A marker file therefore matches anywhere in the tree, so a monorepo's `frontend/package.json` still triggers the suggestion. The trade-off — a rare stray match like `my-package.json` — is harmless because the pattern only *suggests* a template.

Because templates can't auto-detect language, they hardcode `language: 'javascript'`; the inline comments list the supported languages so users adjust `language`/`language-version` for their project. The `tests/test_workflow_templates.py` suite keeps these patterns in sync with the supported languages.

---

## 💡 Usage Examples

### Gemini Merge Workflow (Multi-Project)

To use the Gemini Merge workflow, you'll need to provide a JSON list of projects as input. Here's how to call it by capturing outputs from the reusable workflows:

```yaml
name: Merge Request

on:
  pull_request:
    types: [opened, synchronize, reopened]

# Union of what the called workflows' jobs request (validated at startup):
# the reads for ref resolution, plus gemini-merge's write set.
permissions:
  contents: write
  pull-requests: write
  issues: write
  id-token: write

# Per-PR serialization — load-bearing for the merge step: the reusable merge
# workflow has no concurrency group of its own and relies on the caller's.
concurrency:
  group: gemini-${{ github.event.pull_request.number || github.event.issue.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  ci_project_a:
    name: CI - Project A
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'python'
      language-version: '3.11'
      working-directory: './project_a'

  security_project_a:
    name: Security - Project A
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      language: 'python'
      language-version: '3.11'
      working-directory: './project_a'

  ci_project_b:
    name: CI - Project B
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'javascript'
      language-version: '20'
      working-directory: './project_b'

  security_project_b:
    name: Security - Project B
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      language: 'javascript'
      language-version: '20'
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
    uses: zmihai/.github/.github/workflows/gemini-merge.yml@v0.12.2
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

permissions:
  contents: read
  issues: read
  pull-requests: read
  # Needed only because scan-code is true below (CodeQL):
  security-events: write
  actions: read

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'php'
      language-version: '8.5'

  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      language: 'php'
      language-version: '8.5'
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

permissions:
  contents: read
  issues: read
  pull-requests: read
  # Needed only because scan-code is true below (CodeQL):
  security-events: write
  actions: read

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'python'
      language-version: '3.13'

  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      language: 'python'
      language-version: '3.13'
      scan-dependencies: true
      scan-code: true
```

### Complete CI Pipeline (Java)

```yaml
name: CI

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]

permissions:
  contents: read
  issues: read
  pull-requests: read
  # Needed only because scan-code is true below (CodeQL):
  security-events: write
  actions: read

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.12.2
    with:
      language: 'java'
      language-version: '21'
      # Install apt packages the build needs (e.g. protoc). Omit if not needed.
      extensions: 'protobuf-compiler'

  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.12.2
    with:
      language: 'java'
      language-version: '21'
      scan-dependencies: true
      scan-code: true
```

> **protoc note:** apt installs `protoc` to `/usr/bin/protoc`. If your `pom.xml` hardcodes a different path, either align the build to use `protoc` from `PATH` or add a step to symlink it.

> **Java dependency scan note:** the reusable security workflow runs independently from the reusable CI workflow, so it does not reuse Java build outputs. Maven projects are scanned from `pom.xml`; Gradle projects should commit dependency lockfiles or use a custom security workflow that builds artifacts before running Trivy.

---

## 🚀 Getting Started

### Using Reusable Workflows

1. In your repository, create a workflow file (e.g., `.github/workflows/ci.yml`)
2. Reference reusable workflows using `uses: zmihai/.github/.github/workflows/<name>.yml@v0.12.2`
3. Reference composite actions using `uses: zmihai/.github/actions/<name>@v0.12.2`
4. Pass required inputs and secrets

---

## 📚 Best Practices

1. **Pin versions**: Use specific tags (like `@v0.12.2`) or commit SHAs in production.
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

This repository is provided as-is. Keep in mind it was built for personal/internal use, so support may or may not be provided.

---

## 📞 Support

For questions or issues, please open an issue in this repository.
