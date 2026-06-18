# SearXNG Web Search

XV8 uses SearXNG as the default Docker-local web-search provider.

Default configuration:

- `X8_WEB_SEARCH_PROVIDER=searxng_local`
- `X8_SEARXNG_BASE_URL=http://x8-searxng:8080`

If SearXNG is unavailable, XV8 reports `status: unavailable`, `reason: SearXNG service is not reachable`, and `search_ran: false`.

Search results are normalized into citation-ready source contracts with research receipts.
