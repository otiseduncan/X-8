# Acceptance Gauntlet

The repeatable gauntlet is Docker-only.

```bash
docker compose config
docker compose build
docker compose run --rm architecture-guard
docker compose run --rm api-tests
docker compose run --rm web-tests
docker compose run --rm e2e-tests
```

For the focused conversation authority proof while iterating:

```bash
docker compose -f compose.yaml run --rm --build api-tests python -m pytest tests/test_conversation_readiness.py tests/test_conversation_authority.py
```

## Covered Checks

- Docker stack configuration.
- API health endpoint.
- Web app render smoke.
- Capability truth model.
- Structured chat receipt.
- Team council seed loading.
- UI and AI seed availability.
- Email, SMS, and remote access disabled or stubbed.
- Artifact preview without repo write.
- Repo write denial without approval.
- File-size guard behavior.
- Browser smoke through Playwright.
- Conversation repair routes to a conversational lane, not GitHub pull or self-build.
- Model-owned conversation lanes do not inject X8 memory or markdown knowledge into every turn.
