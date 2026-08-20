import feedparser
import httpx


def fetch_reddit(niche, limit):
    try:
        r = httpx.get(
            f"https://www.reddit.com/r/{niche}/hot.json?limit={limit}",
            headers={"User-Agent": "MoneyWeaver"},
            timeout=5,
        )
        return [
            {"title": c["data"]["title"], "source": "reddit",
             "url": "https://reddit.com" + c["data"]["permalink"]}
            for c in r.json()["data"]["children"][:limit]
        ]
    except Exception:
        return []


def fetch_rss(niche, limit):
    try:
        return []  # MVP: niche RSS mapping, truncate 300char
    except Exception:
        return []


def fetch_trends(niche, limit):
    try:
        from pytrends.request import TrendReq
        return []  # MVP stub
    except Exception:
        return []


def fetch_topics(niche="general", limit=20):
    out = []
    out += fetch_reddit(niche, limit)
    out += fetch_rss(niche, limit)
    seen = set()
    dedup = []
    for t in out:
        if t["title"] not in seen:
            seen.add(t["title"])
            dedup.append(t)
    return dedup[:limit]


def gather_research(topic: str) -> str:
    # DuckDuckGo scrape + 300char truncate (MVP returns topic itself)
    return topic[:300]