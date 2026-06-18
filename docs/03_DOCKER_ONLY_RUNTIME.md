# Docker-Only Runtime

The host machine needs only Docker, Docker Compose, and Git.

Supported commands:

```bash
docker compose up --build
docker compose ps
docker compose logs x8-api
docker compose run --rm architecture-guard
docker compose run --rm api-tests
docker compose run --rm web-tests
docker compose run --rm e2e-tests
```

No README command requires host Python, Node, npm, pnpm, Playwright, Redis, PostgreSQL, or Ollama.

Runtime data is stored in named Docker volumes. Secrets belong in local environment files and are not committed.
