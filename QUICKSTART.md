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
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.11.0
    with:
      language: 'javascript'
      language-version: '20'
```

### 2. Use a Composite Action

Add this to any workflow job:

```yaml
steps:
  - uses: actions/checkout@v6
  - uses: zmihai/.github/actions/setup-node-env@v0.11.0
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
- **CI** - Complete Node.js, Python, PHP & Java CI pipeline
- **Security Scan** - Dependency and code security scanning (JS, Python, PHP & Java)

### 🤖 Gemini AI Workflows
- **Gemini Guard** - Shared trigger gate: validates `@gemini-cli` commands and resolves the PR head ref before any job sees code or secrets
- **Gemini Review** - AI-powered PR review
- **Gemini Test & Merge** - Automated merging based on CI/Security outcomes

To wire up the full automation, start from the **Gemini Review & Merge** workflow template (Actions tab → New workflow) — it ships the guard-first job graph, the minimum `permissions` grant, and a per-PR `concurrency` group.

### 🎬 Composite Actions
- **Setup Node Environment** - Node.js with caching
- **Setup Python Environment** - Python with caching
- **Setup PHP Environment** - PHP with composer caching
- **Setup Java Environment** - Java with Maven/Gradle detection and caching

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
