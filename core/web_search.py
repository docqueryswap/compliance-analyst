import os
import logging
from tavily import TavilyClient

logger = logging.getLogger(__name__)


class WebSearchClient:
    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")
        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 3):
        try:
            response = self.client.search(query, max_results=max_results)
            return [r["content"] for r in response.get("results", [])]
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []