# Complete CI/CD Pipeline Example

This example shows a complete CI/CD pipeline using the reusable workflows.

```yaml
name: Complete CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  release:
    types: [published]

jobs:
  # Run CI on all branches
  ci:
    uses: zmihai/.github/.github/workflows/reusable-ci.yml@main
    with:
      node-version: '20'
      run-lint: true
      run-test: true
      run-build: true

  # Run security scans
  security:
    needs: ci
    uses: zmihai/.github/.github/workflows/reusable-security-scan.yml@main
    with:
      scan-dependencies: true
      scan-code: true
      language: 'javascript'

  # Deploy to staging on develop branch
  deploy-staging:
    needs: [ci, security]
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: zmihai/.github/actions/setup-node-env@main
        with:
          node-version: '20'
      
      - name: Build
        run: npm run build
      
      - uses: zmihai/.github/actions/docker-build-push@main
        with:
          image-name: 'myuser/myapp'
          registry: 'ghcr.io'
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          tags: 'staging,latest'
      
      - uses: zmihai/.github/actions/notify-slack@main
        if: always()
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          message: 'Staging deployment ${{ job.status }} for ${{ github.repository }}'
          status: ${{ job.status }}

  # Deploy to production on release
  deploy-production:
    needs: [ci, security]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: zmihai/.github/actions/setup-node-env@main
        with:
          node-version: '20'
      
      - name: Build
        run: npm run build
      
      - uses: zmihai/.github/actions/docker-build-push@main
        with:
          image-name: 'myuser/myapp'
          registry: 'ghcr.io'
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          tags: 'production,${{ github.event.release.tag_name }}'
      
      - uses: zmihai/.github/actions/notify-slack@main
        if: always()
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          message: 'Production deployment ${{ job.status }} - ${{ github.event.release.tag_name }}'
          status: ${{ job.status }}
          mention-users: 'U123456,U789012'
```

## Key Features

1. **Multi-stage validation**: CI and security scans run on all changes
2. **Environment-based deployment**: Automatic staging and production deployments
3. **Notifications**: Slack notifications for deployment status
4. **Docker support**: Containerized deployments with proper tagging
5. **Conditional execution**: Jobs run based on branch and event type
