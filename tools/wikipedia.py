"""LangChain tool wrapping the Wikipedia API."""
import wikipedia as wiki_api
from langchain_core.tools import tool


@tool
def wikipedia_search(query: str, sentences: int = 10) -> str:
    """Search Wikipedia and return a summary of the most relevant article.

    Args:
        query: The search query.
        sentences: Number of sentences to include in the summary (default 10).

    Returns:
        Article title, URL, and summary text.
    """
    try:
        results = wiki_api.search(query, results=3)
        if not results:
            return f"No Wikipedia results found for: {query}"

        for title in results:
            try:
                page = wiki_api.page(title, auto_suggest=False)
                summary = wiki_api.summary(title, sentences=sentences, auto_suggest=False)
                return f"**{page.title}**\nURL: {page.url}\n\n{summary}"
            except wiki_api.DisambiguationError as e:
                # Try first option
                try:
                    page = wiki_api.page(e.options[0], auto_suggest=False)
                    summary = wiki_api.summary(e.options[0], sentences=sentences, auto_suggest=False)
                    return f"**{page.title}**\nURL: {page.url}\n\n{summary}"
                except Exception:
                    continue
            except wiki_api.PageError:
                continue

        return f"Could not retrieve Wikipedia content for: {query}"
    except Exception as e:
        return f"Wikipedia error: {e}"
