import os
import requests
from pathlib import Path

FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/entrepreneur/latest",
    "https://www.businessinsider.com/rss",
    "https://feeds.reuters.com/reuters/businessNews",
]

KEYWORDS = [
    "marketplace", "ecommerce", "e-commerce", "startup", "entrepreneur",
    "fintech", "trade", "import", "export", "tech", "ai",
    "artificial intelligence", "business", "economy", "technology"
]


def _parse_feed(url: str) -> list:
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "JARVIS/1.0"})
        if r.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:20]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()[:200]
            if title:
                items.append({"title": title, "link": link, "desc": desc})
        return items
    except Exception:
        return []


def _is_relevant(item: dict) -> bool:
    text = (item["title"] + " " + item["desc"]).lower()
    return any(kw in text for kw in KEYWORDS)


def get_news(max_items: int = 5) -> str:
    all_items = []
    for feed in FEEDS:
        all_items.extend(_parse_feed(feed))

    relevant = [i for i in all_items if _is_relevant(i)]
    if not relevant:
        return "No relevant news found."

    seen = set()
    unique = []
    for item in relevant:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    top = unique[:max_items]
    lines = [f"• {i['title']}" for i in top]
    return "\n".join(lines)


def get_news_briefing() -> str:
    news = get_news(5)
    if news == "No relevant news found.":
        return ""
    return f"NEWS RELEVANT TO YOU:\n{news}"
