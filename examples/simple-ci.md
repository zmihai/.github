# Simple CI Example

A minimal CI workflow for a Node.js project.

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

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

That's it! This single job will:
- Checkout your code
- Setup Node.js with caching
- Install dependencies
- Run linting
- Run tests
- Run build

## Customization

### Skip specific steps

```yaml
jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      node-version: '20'
      run-lint: false    # Skip linting
      run-test: true
      run-build: true
      build-before-test: true # Build the app before running tests, for example if testing includes looking for the presence of build artifacts
```

### Change Node.js version

```yaml
jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      node-version: '18'  # Use Node 18
```

### Use in monorepo

```yaml
jobs:
  ci-frontend:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      working-directory: './frontend'
      
  ci-backend:
    uses: zmihai/.github/.github/workflows/reusable-ci-npm.yml@v0.2.0
    with:
      working-directory: './backend'
```
