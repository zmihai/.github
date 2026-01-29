# Tech Stack - .github (Common Workflows & Actions)

## Automation & CI/CD
- **GitHub Actions:** The primary engine for all CI/CD processes, utilizing both **Reusable Workflows** and **Composite Actions** to maximize modularity and reuse.
- **Workflow Language:** YAML

## Supported Languages & Environments
- **Node.js:** Support for JavaScript/TypeScript projects, including automated environment setup, dependency caching, and standard CI tasks (lint, test, build).
- **Python:** Support for Python projects, including automated setup with `pip` caching and dependency installation.
- **PHP:** Support for PHP projects, including automated setup with `composer` caching and dependency installation.

## Infrastructure & Deployment
- **Docker:** Support for building and pushing Docker images to various container registries.
- **Slack:** Integration for sending real-time build and deployment notifications.

## Advanced Capabilities
- **Google Gemini AI:** Specialized workflows for AI-powered code reviews and automated merge decision-making.
- **Multi-Project Support:** JSON-based project configuration for monorepos, allowing unified reviews and merge decisions across multiple subdirectories and languages.
