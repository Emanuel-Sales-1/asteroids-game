"""Coleta de notícias (RSS) e marcação por ação/setor/fator político."""
from __future__ import annotations

import html
import math
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .config import DIRECT_FEEDS, FACTORS, NEWS_QUERIES, UNIVERSE
from .sentiment import normalize, score_text

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}+when:7d&hl=pt-BR&gl=BR&ceid=BR:pt-419"
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Article:
    title: str
    summary: str
    link: str
    source: str
    published: datetime
    sentiment: float = 0.0
    tickers: list[str] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}"

    def age_days(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.published).total_seconds() / 86400)

    def weight(self, half_life_days: float = 2.0, now: datetime | None = None) -> float:
        return math.pow(0.5, self.age_days(now) / half_life_days)


def _parse_date(entry) -> datetime:
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


def _clean(text: str) -> str:
    return html.unescape(_TAG.sub(" ", text or "")).strip()


def fetch_feed(url: str, timeout: int = 10) -> list[Article]:
    import feedparser
    import requests

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 B3Radar/1.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return []
    parsed = feedparser.parse(resp.content)
    feed_title = parsed.feed.get("title", urllib.parse.urlparse(url).netloc)
    out = []
    for e in parsed.entries:
        title = _clean(e.get("title", ""))
        source = feed_title
        src = e.get("source")
        if src and src.get("title"):
            source = src["title"]
            title = re.sub(rf"\s+-\s+{re.escape(source)}$", "", title)
        out.append(Article(title=title, summary=_clean(e.get("summary", ""))[:400],
                           link=e.get("link", ""), source=source, published=_parse_date(e)))
    return out


def fetch_all(extra_queries: list[str] | None = None, max_age_days: float = 7) -> list[Article]:
    """Busca notícias em Google News (consultas) e feeds diretos, em paralelo."""
    from concurrent.futures import ThreadPoolExecutor

    queries = list(NEWS_QUERIES) + [f"{s.name} ações" for s in UNIVERSE] + (extra_queries or [])
    urls = [GOOGLE_NEWS.format(q=urllib.parse.quote_plus(q)) for q in queries] + DIRECT_FEEDS
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(fetch_feed, urls))
    articles = [a for batch in results for a in batch]
    return tag_articles(dedupe([a for a in articles if a.age_days() <= max_age_days]))


def dedupe(articles: list[Article]) -> list[Article]:
    seen, out = set(), []
    for a in sorted(articles, key=lambda a: a.published, reverse=True):
        key = re.sub(r"[^a-z0-9]", "", normalize(a.title))[:80]
        if key and key not in seen:
            seen.add(key)
            out.append(a)
    return out


def _contains(norm_text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(normalize(term))}(?![a-z0-9])", norm_text) is not None


def tag_articles(articles: list[Article]) -> list[Article]:
    for a in articles:
        norm = normalize(a.text)
        a.sentiment = score_text(a.title) * 0.7 + score_text(a.summary) * 0.3 if a.summary else score_text(a.title)
        a.tickers = [s.ticker for s in UNIVERSE
                     if _contains(norm, s.ticker) or any(_contains(norm, al) for al in s.aliases)
                     or any(re.search(rf"\b{re.escape(al)}\b(?!\s+a\s+pena)", a.text) for al in s.cased_aliases)]
        a.factors = [f for f, cfg in FACTORS.items() if any(_contains(norm, k) for k in cfg["keywords"])]
    return articles
