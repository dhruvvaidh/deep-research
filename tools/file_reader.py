"""LangChain tool to read PDF/CSV files as research inputs."""
import csv
import io
from pathlib import Path

from langchain_core.tools import tool


@tool
def file_reader(file_path: str, max_chars: int = 10000) -> str:
    """Read a local PDF or CSV file and return its text content.

    Args:
        file_path: Absolute or relative path to a .pdf or .csv file.
        max_chars: Maximum characters to return (default 10000).

    Returns:
        Extracted text content from the file.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return _read_csv(path, max_chars)
    elif suffix == ".pdf":
        return _read_pdf(path, max_chars)
    else:
        return f"Unsupported file type: {suffix}. Only .pdf and .csv are supported."


def _read_csv(path: Path, max_chars: int) -> str:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return "CSV file is empty."

    lines = []
    for row in rows:
        lines.append(", ".join(row))
    text = "\n".join(lines)
    return text[:max_chars]


def _read_pdf(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "pypdf is not installed. Run: pip install pypdf"

    reader = PdfReader(str(path))
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")

    text = "\n\n".join(pages_text)
    return text[:max_chars]
