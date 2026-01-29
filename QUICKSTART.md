# Quick Start Guide

Welcome to the `.github` common workflows and actions repository!

## What is this repository?

This is a special GitHub repository that provides reusable workflows, composite actions, and workflow templates that can be used across all your repositories.

## Quick Usage

### 1. Use a Reusable Workflow

Add this to your repository's `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.6.0
    with:
      language: 'javascript'
      language-version: '20'
```

### 2. Use a Composite Action

Add this to any workflow job:

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: zmihai/.github/actions/setup-node-env@v0.6.0
    with:
      node-version: '20'
```

### 3. Browse Workflow Templates

When creating a new workflow in any repository:
1. Go to the "Actions" tab
2. Click "New workflow"
3. Find templates provided by this repository
4. Click "Configure" to use them

## What's Available?

### 🔄 Reusable Workflows
- **CI** - Complete Node.js, Python & PHP CI pipeline (v0.6.0+)
- **Security Scan** - Dependency and code security scanning (JS, Python & PHP) (v0.6.0+)

### 🤖 Gemini AI Workflows
- **Gemini Review** - AI-powered PR review
- **Gemini Test & Merge** - Automated merging based on CI/Security outcomes (v0.6.0+)

### 🎬 Composite Actions
- **Setup Node Environment** - Node.js with caching
- **Setup Python Environment** - Python with caching
- **Setup PHP Environment** - PHP with composer caching
- **Docker Build & Push** - Container image building
- **Notify Slack** - Slack notifications

## Learn More

- [Complete Documentation](README.md)
- [Usage Examples](examples/)
- [Contributing Guide](CONTRIBUTING.md)

## Next Steps

1. Browse the [examples/](examples/) directory for common patterns
2. Check the [README.md](README.md) for detailed documentation
3. Start using these workflows in your projects!

## Support

Questions? Open an issue in this repository.
