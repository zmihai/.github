# .github - Common Workflows & Actions

This repository contains reusable workflows, composite actions, and workflow templates that can be used across all repositories in this organization.

## 📋 Contents

- [Reusable Workflows](#reusable-workflows)
- [Composite Actions](#composite-actions)
- [Workflow Templates](#workflow-templates)
- [Usage Examples](#usage-examples)

---

## 🔄 Reusable Workflows

Reusable workflows are stored in `.github/workflows/` and can be called from other repositories.

### CI Workflow

**Path:** `.github/workflows/reusable-ci-npm.yml`

A comprehensive CI workflow that handles linting, testing, and building Node.js projects.

**Inputs:**
- `node-version` (string, default: '20'): Node.js version to use
- `working-directory` (string, default: '.'): Working directory for commands
- `run-lint` (boolean, default: true): Run linting
- `run-test` (boolean, default: true): Run tests
- `run-build` (boolean, default: true): Run build
- `build-before-test` (boolean, default: false): Run build before tests

**Secrets:**
- `CUSTOM_TOKEN` (optional): Custom token for private packages

**Example Usage:**
```yaml
jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      node-version: '20'
      run-lint: true
      run-test: true
      run-build: true
      build-before-test: false
```

### Release Workflow

**Path:** `.github/workflows/reusable-release.yml`

Automates the release process including version bumping, npm publishing, and GitHub release creation.

**Inputs:**
- `release-type` (string, default: 'patch'): Type of release (patch, minor, major)
- `node-version` (string, default: '20'): Node.js version to use
- `create-github-release` (boolean, default: true): Create GitHub release

**Secrets:**
- `NPM_TOKEN` (optional): NPM token for publishing
- `GH_TOKEN` (optional): GitHub token for creating releases

**Example Usage:**
```yaml
jobs:
  release:
    uses: zmihai/.github/.github/workflows/reusable-release.yml@v0.1.0
    with:
      release-type: 'minor'
      create-github-release: true
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Security Scan Workflow

**Path:** `.github/workflows/reusable-security-scan.yml`

Performs security scanning including dependency audits and CodeQL analysis.

**Inputs:**
- `scan-dependencies` (boolean, default: true): Scan npm dependencies
- `scan-code` (boolean, default: true): Run CodeQL analysis
- `language` (string, default: 'javascript'): Language for CodeQL

**Example Usage:**
```yaml
jobs:
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.1.0
    with:
      scan-dependencies: true
      scan-code: true
      language: 'javascript'
```

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
  - uses: zmihai/.github/actions/setup-node-env@v0.1.0
    with:
      node-version: '20'
      cache: 'npm'
```

### Docker Build and Push

**Path:** `actions/docker-build-push/action.yml`

Builds and pushes Docker images to container registries.

**Inputs:**
- `image-name` (required): Name of the Docker image
- `registry` (default: 'docker.io'): Container registry
- `username` (required): Registry username
- `password` (required): Registry password or token
- `tags` (default: 'latest'): Comma-separated list of tags
- `dockerfile` (default: './Dockerfile'): Path to Dockerfile
- `context` (default: '.'): Build context
- `build-args` (optional): Build arguments
- `push` (default: 'true'): Push image to registry

**Outputs:**
- `image-url`: Full image URL with tag
- `digest`: Image digest

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/docker-build-push@v0.1.0
    with:
      image-name: 'myuser/myapp'
      registry: 'ghcr.io'
      username: ${{ github.actor }}
      password: ${{ secrets.GITHUB_TOKEN }}
      tags: 'latest,${{ github.sha }}'
```

### Semantic Release

**Path:** `actions/semantic-release/action.yml`

Automates versioning and package publishing using semantic-release.

**Inputs:**
- `branches` (default: '["master"]'): Branches to release from (JSON array)
- `dry-run` (default: 'false'): Run in dry-run mode
- `plugins` (optional): Additional semantic-release plugins
- `github-token` (required): GitHub token for releases
- `npm-token` (optional): NPM token for publishing

**Outputs:**
- `new-release-published`: Whether a new release was published
- `new-release-version`: Version of the new release

**Example Usage:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/semantic-release@v0.1.0
    with:
      github-token: ${{ secrets.GITHUB_TOKEN }}
      npm-token: ${{ secrets.NPM_TOKEN }}
```

### Notify Slack

**Path:** `actions/notify-slack/action.yml`

Sends notifications to Slack channels with status indicators.

**Inputs:**
- `webhook-url` (required): Slack webhook URL
- `message` (required): Message to send
- `status` (default: 'success'): Status (success, failure, warning)
- `channel` (optional): Slack channel (overrides webhook default)
- `mention-users` (optional): Comma-separated list of user IDs to mention

**Example Usage:**
```yaml
steps:
  - uses: zmihai/.github/actions/notify-slack@v0.1.0
    if: always()
    with:
      webhook-url: ${{ secrets.SLACK_WEBHOOK }}
      message: 'Deployment completed for ${{ github.repository }}'
      status: ${{ job.status }}
```

---

## 📝 Workflow Templates

Workflow templates are starter workflows that appear in the "Actions" tab of your repositories.

Available templates:
- **CI Workflow** (`workflow-templates/ci.yml`) - Complete CI pipeline
- **Release Workflow** (`workflow-templates/release.yml`) - Automated releases
- **Security Scan** (`workflow-templates/security-scan.yml`) - Security scanning

These templates will automatically appear in the GitHub Actions workflow picker when creating new workflows in other repositories.

---

## 💡 Usage Examples

### Complete CI/CD Pipeline

```yaml
name: CI/CD

on:
  push:
    branches: [ master ]
  pull_request:
    branches: [ master ]
  release:
    types: [ created ]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      node-version: '20'
  
  security:
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@v0.1.0
    with:
      scan-dependencies: true
      scan-code: true
  
  release:
    needs: [ci, security]
    if: github.event_name == 'release'
    uses: zmihai/.github/.github/workflows/reusable-release.yml@v0.1.0
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### Custom Workflow with Composite Actions

```yaml
name: Build and Deploy

on:
  push:
    branches: [ master ]

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: zmihai/.github/actions/setup-node-env@v0.1.0
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Build
        run: npm run build
      
      - name: Docker Build and Push
        uses: zmihai/.github/actions/docker-build-push@v0.1.0
        with:
          image-name: 'myuser/myapp'
          registry: 'ghcr.io'
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          tags: 'latest,${{ github.sha }}'
```

---

## 🚀 Getting Started

### Using Reusable Workflows

1. In your repository, create a workflow file (e.g., `.github/workflows/ci.yml`)
2. Reference the reusable workflow using `uses: zmihai/.github/.github/workflows/<workflow-name>.yml@v0.1.0`
3. Pass required inputs and secrets

### Using Composite Actions

1. Add a step in your workflow
2. Reference the action using `uses: zmihai/.github/actions/<action-name>@v0.1.0`
3. Provide required inputs

### Using Workflow Templates

1. Go to your repository's "Actions" tab
2. Click "New workflow"
3. Find the templates in the workflow picker
4. Customize as needed

---

## 📚 Best Practices

1. **Pin versions**: Use specific commit SHAs or tags instead of `@master` in production
2. **Security**: Never hardcode secrets, always use GitHub Secrets
3. **Testing**: Test workflow changes in a separate branch before merging to master
4. **Documentation**: Keep this README updated when adding new workflows or actions

---

## 🤝 Contributing

When adding new workflows or actions:

1. Follow the existing structure and naming conventions
2. Add comprehensive documentation to this README
3. Include usage examples
4. Test thoroughly before merging

---

## 📄 License

This repository is for internal use within the organization.

---

## 📞 Support

For questions or issues, please open an issue in this repository.
