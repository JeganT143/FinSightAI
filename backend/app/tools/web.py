from agents import function_tool
from app.core.config import settings
from pydantic import BaseModel
from tavily import AsyncTavilyClient


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str


@function_tool
async def web_search(query: str, max_results: int = 5) -> list[SearchHit]:
    """Search the web for recent reputable sorces

    Args:
        query (str): The natural language search query,
        max_results : Cap of the returned hits (1-10)

    """

    max_results = max(1, min(max_results, 10))  # Ensure max_results is between 1 and 10
    async with AsyncTavilyClient(api_key=settings.tavily_api_key) as client:
        results = await client.search(query=query, num_results=max_results, search_depth="advanced")
        results.raise_for_status()  # Raise an exception for HTTP errors
        return [SearchHit(**h) for h in results.json().get("results", [])]
