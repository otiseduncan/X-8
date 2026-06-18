from x8.adapters.integrations.searxng_adapter import SearXNGAdapter
from x8.contracts.search import ResearchReceipt, SearchResultContract


class WebSearchManager:
    name = "web_search"
    version = "0.1.0"

    def __init__(self, provider: str, searxng_base_url: str) -> None:
        self.provider = provider
        self.searxng = SearXNGAdapter(searxng_base_url)

    def provider_status(self) -> dict[str, object]:
        if self.provider != "searxng_local":
            return {"status": "not_configured", "reason": "Only SearXNG local is enabled in MVP.", "provider": self.provider}
        return self.searxng.status()

    def search(self, query: str) -> tuple[SearchResultContract, ResearchReceipt]:
        result = self.searxng.search(query)
        receipt = ResearchReceipt(provider=result.provider, query=query, status=result.status, result_count=len(result.results))
        return result, receipt
