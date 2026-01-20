# Simple CI Example

A minimal CI workflow for a project.

## JavaScript (Node.js)

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.4.0
    with:
      language: 'javascript'
      language-version: '20'
      run-lint: true
      run-test: true
      run-build: true
      build-before-test: false
```

## Python

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.4.0
    with:
      language: 'python'
      language-version: '3.11'
      run-lint: true
```

## Customization

### Skip specific steps (JS)

```yaml
jobs:
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.4.0
    with:
      language: 'javascript'
      language-version: '24'
      run-lint: false    # Skip linting
      run-test: true
      run-build: true
      build-before-test: true # Build the app before running tests, for example if testing includes looking for the presence of build artifacts
```

### Use in monorepo

```yaml
jobs:
  ci-frontend:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.4.0
    with:
      language: 'javascript'
      language-version: '22'
      working-directory: './frontend'
      
  ci-backend:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@v0.4.0
    with:
      language: 'python'
      working-directory: './backend'
```
