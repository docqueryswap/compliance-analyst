import os
import logging
from tavily import TavilyClient

logger = logging.getLogger(__name__)

class WebSearchClient:
    def __init__(self):
        self.client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    def search(self, query: str, max_results=3):
        try:
            response = self.client.search(
                query, 
                max_results=max_results, 
                search_depth="basic",
                timeout=10
            )
            return [r["content"] for r in response.get("results", [])]
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []