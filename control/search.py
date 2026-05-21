import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a formatted summary."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results found for: {query}"

        lines = [f"Web search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")[:200]
            href = r.get("href", "")
            lines.append(f"{i}. {title}\n   {body}\n   Source: {href}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"


def news_search(query: str, max_results: int = 5) -> str:
    """Search for recent news."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return f"No news found for: {query}"

        lines = [f"Latest news for: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")[:150]
            source = r.get("source", "")
            date = r.get("date", "")
            lines.append(f"{i}. [{date}] {title} — {source}\n   {body}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"News search failed: {e}"


if __name__ == "__main__":
    print(web_search("Addis Ababa startup ecosystem 2025"))
