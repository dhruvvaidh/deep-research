"""LangChain tool for full-page content extraction via requests + BeautifulSoup."""
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def web_scraper(url: str, max_chars: int = 8000) -> str:
    """Fetch a web page and extract its main text content.

    Args:
        url: The URL to scrape.
        max_chars: Maximum characters to return (default 8000).

    Returns:
        Cleaned text content of the page.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DeepResearchBot/1.0; "
            "+https://github.com/deep-research)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # Detect binary / non-HTML responses and bail early
        content_type = resp.headers.get("Content-Type", "")
        if "text" not in content_type and "html" not in content_type:
            return f"Skipped {url}: non-HTML content ({content_type})"
    except requests.RequestException as e:
        return f"Error fetching {url}: {e}"

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        return f"Error parsing {url}: {e}"

    # Remove script, style, nav, footer noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Prefer article/main content blocks
    main = soup.find("article") or soup.find("main") or soup.body
    if main is None:
        return "Could not parse page content."

    text = main.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    lines = [ln for ln in text.splitlines() if ln.strip()]
    cleaned = "\n".join(lines)
    return cleaned[:max_chars]
