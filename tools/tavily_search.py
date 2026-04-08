"""LangChain tool wrapping the Tavily search API."""
import os
from langchain_core.tools import tool
from tavily import TavilyClient


@tool
def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the web using Tavily and return a formatted list of results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        Formatted string with titles, URLs, and snippets.
    """
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query, max_results=max_results, search_depth="advanced")

    results = response.get("results", [])
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.get('title', 'No title')}")
        lines.append(f"    URL: {r.get('url', '')}")
        lines.append(f"    {r.get('content', '')[:400]}")
        lines.append("")
    return "\n".join(lines)
