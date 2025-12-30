# Docker Build and Push Example

Examples of building and pushing Docker images.

## Basic Example

```yaml
name: Build Docker Image

on:
  push:
    branches: [master]

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: zmihai/.github/actions/docker-build-push@v0.1.0
        with:
          image-name: 'myusername/myapp'
          registry: 'docker.io'
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
          tags: 'latest,${{ github.sha }}'
```

## GitHub Container Registry (GHCR)

```yaml
name: Build and Push to GHCR

on:
  push:
    branches: [master]
    tags: ['v*']

jobs:
  docker:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Extract metadata
        id: meta
        run: |
          if [[ $GITHUB_REF == refs/tags/* ]]; then
            echo "tags=latest,${GITHUB_REF#refs/tags/}" >> $GITHUB_OUTPUT
          else
            echo "tags=latest,sha-${GITHUB_SHA::7}" >> $GITHUB_OUTPUT
          fi
      
      - uses: zmihai/.github/actions/docker-build-push@v0.1.0
        with:
          image-name: '${{ github.repository }}'
          registry: 'ghcr.io'
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          tags: ${{ steps.meta.outputs.tags }}
```

## Multi-stage Build with Build Args

```yaml
name: Multi-stage Docker Build

on:
  push:
    branches: [master]

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: zmihai/.github/actions/docker-build-push@v0.1.0
        with:
          image-name: 'myusername/myapp'
          registry: 'ghcr.io'
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          dockerfile: './docker/Dockerfile.prod'
          context: '.'
          build-args: |
            NODE_ENV=production
            API_URL=${{ secrets.API_URL }}
            VERSION=${{ github.sha }}
          tags: 'latest,v1.0.0'
```

## Build Without Pushing (for testing)

```yaml
name: Test Docker Build

on:
  pull_request:
    branches: [master]

jobs:
  test-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: zmihai/.github/actions/docker-build-push@v0.1.0
        with:
          image-name: 'myusername/myapp'
          registry: 'docker.io'
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
          push: 'false'  # Don't push, just build to test
```
