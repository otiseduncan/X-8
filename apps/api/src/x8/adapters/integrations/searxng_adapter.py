import httpx

from x8.contracts.search import SearchResultContract, SourceCitationContract


class SearXNGAdapter:
    name = "SearXNG"
    version = "0.1.0"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def status(self) -> dict[str, object]:
        try:
            response = httpx.get(f"{self.base_url}/", timeout=3)
            return {"status": "available", "reachable": response.status_code < 500, "base_url": self.base_url}
        except Exception as exc:
            return {"status": "unavailable", "reachable": False, "reason": "SearXNG service is not reachable", "error": str(exc)}

    def search(self, query: str) -> SearchResultContract:
        try:
            response = httpx.get(f"{self.base_url}/search", params={"q": query, "format": "json"}, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return SearchResultContract(query=query, provider="searxng_local", status="unavailable", reason="SearXNG service is not reachable")
        results = [
            SourceCitationContract(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                snippet=str(item.get("content", "")),
                freshness=str(item.get("publishedDate") or "unknown"),
            )
            for item in payload.get("results", [])[:10]
        ]
        return SearchResultContract(query=query, provider="searxng_local", status="ok", search_ran=True, results=results)
