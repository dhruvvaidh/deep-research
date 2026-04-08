"""LangChain tool wrapping the arXiv API."""
import arxiv
from langchain_core.tools import tool


@tool
def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search arXiv for academic papers matching a query.

    Args:
        query: The search query (supports arXiv search syntax).
        max_results: Maximum number of papers to return (default 5).

    Returns:
        Formatted list of papers with titles, authors, abstracts, and links.
    """
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers = list(client.results(search))
    if not papers:
        return f"No arXiv papers found for: {query}"

    lines = []
    for i, paper in enumerate(papers, 1):
        authors = ", ".join(a.name for a in paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."
        lines.append(f"[{i}] {paper.title}")
        lines.append(f"    Authors: {authors}")
        lines.append(f"    Published: {paper.published.strftime('%Y-%m-%d')}")
        lines.append(f"    URL: {paper.entry_id}")
        lines.append(f"    Abstract: {paper.summary[:400]}...")
        lines.append("")
    return "\n".join(lines)
