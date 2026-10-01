"""
Market Intelligence Aggregator
==============================

Pulls multi-source, time-dependent market signals and feeds them into AVIRA's
analytics pipeline. No paid APIs required — uses public RSS, Yahoo Finance,
SEC EDGAR, Reddit, Hacker News, and similar.

Streams:
  - influencer_signals  : Trump / Musk / market personalities (news + social)
  - geopolitics_war     : Reuters / BBC world + defense news
  - big_money_flow      : SEC Form 4 (insiders) + 13F (institutions)
  - sec_filings         : 8-K / 10-K / 10-Q / S-1 / DEF 14A latest
  - tech_breakthroughs  : Hacker News + ArsTechnica + MIT Tech Review
  - resource_discoveries: oil / minerals / rare-earths (mining.com, OilPrice)
  - earnings_adherence  : actual vs analyst estimate, last 5y per ticker
  - ai_boom_index       : composite signal across the AI compute/energy stack
  - market_overview     : VIX, Fear&Greed, sector rotation, breadth

Each function returns a JSON-serializable dict and is async-safe.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Light-touch in-process cache (avoid hammering free sources)
# ─────────────────────────────────────────────────────────────────────────────
_CACHE: Dict[str, Tuple[float, Any]] = {}
_DEFAULT_TTL = 300  # 5 min


def _cache_get(key: str, ttl: int = _DEFAULT_TTL) -> Optional[Any]:
    if key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < ttl:
            return val
    return None


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


# ─────────────────────────────────────────────────────────────────────────────
# Curated source lists
# ─────────────────────────────────────────────────────────────────────────────

# Market-moving public personalities. We pull *news mentions* from Yahoo Finance
# search (which works without keys) plus Truth Social + best-effort Nitter.
INFLUENCERS: List[Dict[str, str]] = [
    {"handle": "realDonaldTrump", "name": "Donald Trump",   "category": "political",
     "rss": "https://truthsocial.com/users/realDonaldTrump/feed.rss"},
    {"handle": "elonmusk",        "name": "Elon Musk",      "category": "tech_ceo"},
    {"handle": "jimcramer",       "name": "Jim Cramer",     "category": "media"},
    {"handle": "CathieDWood",     "name": "Cathie Wood",    "category": "fund_manager"},
    {"handle": "BillAckman",      "name": "Bill Ackman",    "category": "fund_manager"},
    {"handle": "michaeljburry",   "name": "Michael Burry",  "category": "fund_manager"},
    {"handle": "WarrenBuffett",   "name": "Warren Buffett", "category": "fund_manager"},
    {"handle": "jpowell",         "name": "Jerome Powell",  "category": "central_bank"},
    {"handle": "SecYellen",       "name": "Janet Yellen",   "category": "treasury"},
    {"handle": "POTUS",           "name": "President of the United States", "category": "political"},
    {"handle": "saylor",          "name": "Michael Saylor", "category": "tech_ceo"},
    {"handle": "tim_cook",        "name": "Tim Cook",       "category": "tech_ceo"},
    {"handle": "satyanadella",    "name": "Satya Nadella",  "category": "tech_ceo"},
    {"handle": "sundarpichai",    "name": "Sundar Pichai",  "category": "tech_ceo"},
    {"handle": "JensenHuang",     "name": "Jensen Huang",   "category": "tech_ceo"},
]

WAR_GEO_FEEDS: List[Dict[str, str]] = [
    {"name": "Reuters World",       "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "BBC World",           "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Al Jazeera",          "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "Defense News",        "url": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"name": "Bloomberg Politics",  "url": "https://feeds.bloomberg.com/politics/news.rss"},
]

TECH_BREAKTHROUGH_FEEDS: List[Dict[str, str]] = [
    {"name": "Hacker News Top",     "url": "https://hnrss.org/frontpage"},
    {"name": "Ars Technica",        "url": "http://feeds.arstechnica.com/arstechnica/index"},
    {"name": "MIT Tech Review",     "url": "https://www.technologyreview.com/feed/"},
    {"name": "TechCrunch",          "url": "https://techcrunch.com/feed/"},
    {"name": "FDA Press",           "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"},
    {"name": "Nature",              "url": "https://www.nature.com/nature.rss"},
    {"name": "Science Daily Med",   "url": "https://www.sciencedaily.com/rss/health_medicine.xml"},
    {"name": "ArXiv cs.AI",         "url": "https://rss.arxiv.org/rss/cs.AI"},
]

RESOURCE_FEEDS: List[Dict[str, str]] = [
    {"name": "Mining.com",          "url": "https://www.mining.com/feed/"},
    {"name": "OilPrice",            "url": "https://oilprice.com/rss/main"},
    {"name": "Rigzone",             "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx"},
    {"name": "Reuters Commodities", "url": "https://feeds.reuters.com/reuters/commoditiesNews"},
]

# AI-stack universe — companies whose fortunes are tied to the AI boom.
# Categorized so the dashboard can show a stacked "where the boom is hottest".
AI_BOOM_UNIVERSE: Dict[str, List[str]] = {
    "compute_chips":     ["NVDA", "AMD", "AVGO", "TSM", "MU", "ARM", "QCOM", "MRVL", "SMCI"],
    "semi_equipment":    ["ASML", "AMAT", "KLAC", "LRCX"],
    "hyperscalers":      ["MSFT", "GOOGL", "META", "AMZN", "ORCL"],
    "ai_software":       ["PLTR", "CRM", "ADBE", "NOW", "SNOW", "CRWD", "NET"],
    "data_networking":   ["ANET", "CSCO", "CIEN"],
    "energy_grid":       ["VRT", "ETN", "PWR", "GEV", "ENPH", "CEG", "VST", "BWXT"],
    "defense_geopol":    ["LMT", "RTX", "NOC", "GD", "BA"],
    "rare_earth_miners": ["MP", "TMC", "FCX", "ALB", "REMX"],
}


# ─────────────────────────────────────────────────────────────────────────────
# RSS parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_rss(xml_text: str, limit: int = 12) -> List[Dict[str, str]]:
    """Tiny RSS / Atom parser — extracts title, link, pubDate, summary."""
    items: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Some feeds prepend BOMs / weird headers; salvage with regex
        for m in re.finditer(r"<item>(.*?)</item>", xml_text, re.DOTALL | re.IGNORECASE):
            block = m.group(1)
            t = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
            l = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
            d = re.search(r"<pubDate>(.*?)</pubDate>", block, re.DOTALL)
            items.append({
                "title": _strip_cdata(t.group(1)) if t else "",
                "link":  _strip_cdata(l.group(1)) if l else "",
                "published": _strip_cdata(d.group(1)) if d else "",
                "summary": "",
            })
            if len(items) >= limit:
                break
        return items

    # RSS 2.0
    for ch in root.findall(".//channel/item"):
        items.append({
            "title":     _txt(ch, "title"),
            "link":      _txt(ch, "link"),
            "published": _txt(ch, "pubDate") or _txt(ch, "{http://purl.org/dc/elements/1.1/}date"),
            "summary":   _strip_html(_txt(ch, "description"))[:400],
        })
        if len(items) >= limit:
            return items

    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for ch in root.findall(f".//{ns}entry"):
        link_el = ch.find(f"{ns}link")
        items.append({
            "title":     _txt(ch, f"{ns}title"),
            "link":      link_el.get("href", "") if link_el is not None else "",
            "published": _txt(ch, f"{ns}updated") or _txt(ch, f"{ns}published"),
            "summary":   _strip_html(_txt(ch, f"{ns}summary"))[:400],
        })
        if len(items) >= limit:
            break
    return items


def _txt(el, tag: str) -> str:
    node = el.find(tag)
    return _strip_cdata((node.text or "").strip()) if node is not None and node.text else ""


def _strip_cdata(s: str) -> str:
    return re.sub(r"^\s*<!\[CDATA\[(.*?)\]\]>\s*$", r"\1", s, flags=re.DOTALL).strip()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


async def _fetch_rss(client: httpx.AsyncClient, url: str, limit: int = 12) -> List[Dict[str, str]]:
    try:
        r = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 AVIRA/1.0"})
        if r.status_code != 200 or not r.text:
            return []
        return _parse_rss(r.text, limit=limit)
    except Exception as e:
        logger.debug("rss fetch failed %s: %s", url, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment scoring (lightweight — replace with FinBERT later)
# ─────────────────────────────────────────────────────────────────────────────
_POS = frozenset("""
beat surge rally bullish breakout upgrade strong outperform record growth boom expansion
approve approval breakthrough launch acquire merger profitable raised guidance accelerate
""".split())
_NEG = frozenset("""
miss plunge crash bearish downgrade weak underperform recession layoff cut bankruptcy
investigation lawsuit halted recall warning fraud subpoena slump default conflict war
sanction strike attack invasion shutdown scandal ban
""".split())


def _sentiment(text: str) -> float:
    if not text:
        return 0.0
    words = re.findall(r"[a-z]+", text.lower())
    pos = sum(1 for w in words if w in _POS)
    neg = sum(1 for w in words if w in _NEG)
    total = pos + neg
    return 0.0 if total == 0 else round((pos - neg) / total, 3)


def _label(score: float) -> str:
    if score >= 0.2: return "bullish"
    if score <= -0.2: return "bearish"
    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# Influencer signals
# ─────────────────────────────────────────────────────────────────────────────

async def _google_news_for(name: str, client: httpx.AsyncClient, count: int = 6) -> List[Dict[str, Any]]:
    """News articles mentioning this person, via Google News RSS (no API key)."""
    try:
        from urllib.parse import quote_plus
        q = quote_plus(f'"{name}" stock OR market OR finance')
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        items = await _fetch_rss(client, url, limit=count)
        out = []
        for it in items:
            title = _strip_html(it.get("title", ""))
            # Google News titles often end with " - Publisher Name"
            publisher = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts[1]) < 50:  # looks like a publisher
                    publisher = parts[1]
            out.append({
                "title": title,
                "publisher": publisher,
                "url": it.get("link", ""),
                "published": it.get("published", ""),
                "sentiment": _sentiment(title),
            })
        return out
    except Exception as e:
        logger.debug("google news for %s failed: %s", name, e)
        return []


async def get_influencer_signals(limit_per: int = 5) -> Dict[str, Any]:
    """For each tracked personality, pull their feed (if any) + news mentions."""
    cached = _cache_get("influencers")
    if cached:
        return cached

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def one(p: Dict[str, str]) -> Dict[str, Any]:
            posts: List[Dict[str, Any]] = []
            if p.get("rss"):
                feed = await _fetch_rss(client, p["rss"], limit=limit_per)
                for f in feed:
                    posts.append({
                        "source": "feed",
                        "title": _strip_html(f.get("title", ""))[:240],
                        "url": f.get("link", ""),
                        "published": f.get("published", ""),
                        "sentiment": _sentiment(f.get("title", "") + " " + f.get("summary", "")),
                    })
            news = await _google_news_for(p["name"], client, count=limit_per)
            posts.extend({**n, "source": "news"} for n in news)
            posts.sort(key=lambda x: x.get("published", ""), reverse=True)
            avg = round(sum(x["sentiment"] for x in posts) / len(posts), 3) if posts else 0.0
            return {
                "handle": p["handle"],
                "name": p["name"],
                "category": p["category"],
                "items": posts[:limit_per * 2],
                "avg_sentiment": avg,
                "signal": _label(avg),
            }

        results = await asyncio.gather(*[one(p) for p in INFLUENCERS], return_exceptions=True)

    rows = [r for r in results if isinstance(r, dict)]

    # Fallback: if no live signals were fetched, still return the tracked influencer list
    if not rows:
        rows = [
            {
                "handle": p["handle"],
                "name": p["name"],
                "category": p["category"],
                "items": [],
                "avg_sentiment": 0.0,
                "signal": "neutral",
            }
            for p in INFLUENCERS
        ][:15]

    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(rows),
        "influencers": rows,
    }
    _cache_set("influencers", out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# War / geopolitics
# ─────────────────────────────────────────────────────────────────────────────

async def get_geopolitics() -> Dict[str, Any]:
    cached = _cache_get("geopolitics")
    if cached:
        return cached

    async with httpx.AsyncClient(follow_redirects=True) as client:
        feeds = await asyncio.gather(*[_fetch_rss(client, f["url"], 8) for f in WAR_GEO_FEEDS])

    out_items: List[Dict[str, Any]] = []
    for src, items in zip(WAR_GEO_FEEDS, feeds):
        for it in items:
            title = _strip_html(it.get("title", ""))
            out_items.append({
                "source": src["name"],
                "title": title[:240],
                "url": it.get("link", ""),
                "published": it.get("published", ""),
                "summary": it.get("summary", "")[:240],
                "sentiment": _sentiment(title + " " + it.get("summary", "")),
                "is_conflict": _is_conflict(title),
            })
    out_items.sort(key=lambda x: x["published"], reverse=True)
    avg = round(sum(x["sentiment"] for x in out_items) / len(out_items), 3) if out_items else 0.0

    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "headline_count": len(out_items),
        "avg_sentiment": avg,
        "risk_level": _conflict_risk(out_items),
        "items": out_items[:50],
    }
    _cache_set("geopolitics", out)
    return out


_CONFLICT_RX = re.compile(
    r"\b(war|conflict|attack|strike|invasion|missile|drone|airstrike|killed|"
    r"sanction|sanctions|nuclear|escalat|ceasefire|hostage|gaza|ukraine|"
    r"taiwan|iran|israel|russia|china|north korea|hamas|hezbollah)\b",
    re.IGNORECASE,
)


def _is_conflict(text: str) -> bool:
    return bool(_CONFLICT_RX.search(text or ""))


def _conflict_risk(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    conflict = sum(1 for it in items if it.get("is_conflict"))
    pct = conflict / len(items)
    if pct > 0.45: return "elevated"
    if pct > 0.25: return "moderate"
    return "calm"


# ─────────────────────────────────────────────────────────────────────────────
# SEC filings — Form 4 (insider) + 8-K, 13F summary
# ─────────────────────────────────────────────────────────────────────────────

SEC_HEADERS = {"User-Agent": "AVIRA Research avira@example.com", "Accept-Encoding": "gzip"}


async def get_sec_recent_filings(form_types: Optional[List[str]] = None, days: int = 7) -> Dict[str, Any]:
    """Pull the latest filings of given form types from SEC EDGAR full-text search."""
    form_types = form_types or ["8-K", "10-K", "10-Q", "S-1", "DEF 14A", "4", "13F-HR", "SC 13D", "SC 13G"]
    cache_key = f"sec_filings:{','.join(form_types)}:{days}"
    cached = _cache_get(cache_key, ttl=600)
    if cached:
        return cached

    out: Dict[str, List[Dict[str, Any]]] = {ft: [] for ft in form_types}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for ft in form_types:
            try:
                # EDGAR "latest filings" RSS by form type — use getcurrent which
                # returns recent filings *across all companies* for the form.
                url = (
                    "https://www.sec.gov/cgi-bin/browse-edgar"
                    f"?action=getcurrent&type={ft.replace(' ', '+')}&company=&datea=&dateb="
                    "&owner=include&count=40&output=atom"
                )
                r = await client.get(url, headers=SEC_HEADERS, timeout=10)
                if r.status_code != 200:
                    continue
                items = _parse_rss(r.text, limit=40)
                # EDGAR's `type=` is a prefix match, so type=4 also returns
                # 424B2, 4-A12B, etc. Enforce strict form match on the title.
                ft_norm = ft.upper().replace(" ", "").replace("/", "")
                kept = 0
                for it in items:
                    title = (it.get("title") or "").strip()
                    head = title.split(" ", 1)[0].upper().replace("/", "")
                    if head != ft_norm and not head.startswith(ft_norm + "-"):
                        continue
                    out[ft].append({
                        "title": title,
                        "link": it.get("link", ""),
                        "published": it.get("published", ""),
                    })
                    kept += 1
                    if kept >= 20:
                        break
            except Exception as e:
                logger.debug("sec %s failed: %s", ft, e)

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "by_form": out,
        "totals": {k: len(v) for k, v in out.items()},
    }
    _cache_set(cache_key, summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Big money flow — top insider buy/sells (Form 4) + 13F highlights
# ─────────────────────────────────────────────────────────────────────────────

async def get_big_money_flow() -> Dict[str, Any]:
    """Combine SEC Form 4 insider trades + 13F-HR institutional changes."""
    cached = _cache_get("big_money", ttl=900)
    if cached:
        return cached
    sec = await get_sec_recent_filings(form_types=["4", "13F-HR", "SC 13D", "SC 13G"])

    insider = sec["by_form"].get("4", [])[:25]
    institutional = sec["by_form"].get("13F-HR", [])[:15]
    activist = (sec["by_form"].get("SC 13D", []) + sec["by_form"].get("SC 13G", []))[:15]

    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "insider_form4": insider,
        "institutional_13f": institutional,
        "activist_13d_13g": activist,
        "summary": {
            "insider_filings_24h": len(insider),
            "institutional_filings_24h": len(institutional),
            "activist_filings_24h": len(activist),
        },
    }
    _cache_set("big_money", out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Tech breakthroughs + resource discoveries
# ─────────────────────────────────────────────────────────────────────────────

async def _aggregate_feeds(feeds: List[Dict[str, str]], items_per: int = 8) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(*[_fetch_rss(client, f["url"], items_per) for f in feeds])
    out: List[Dict[str, Any]] = []
    for src, items in zip(feeds, results):
        for it in items:
            title = _strip_html(it.get("title", ""))
            out.append({
                "source": src["name"],
                "title": title[:240],
                "url": it.get("link", ""),
                "published": it.get("published", ""),
                "summary": it.get("summary", "")[:240],
                "sentiment": _sentiment(title + " " + it.get("summary", "")),
            })
    out.sort(key=lambda x: x["published"], reverse=True)
    return out


async def get_tech_breakthroughs() -> Dict[str, Any]:
    cached = _cache_get("tech_breakthroughs")
    if cached:
        return cached
    items = await _aggregate_feeds(TECH_BREAKTHROUGH_FEEDS, items_per=8)
    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(items),
        "items": items[:60],
    }
    _cache_set("tech_breakthroughs", out)
    return out


async def get_resource_discoveries() -> Dict[str, Any]:
    cached = _cache_get("resources")
    if cached:
        return cached
    items = await _aggregate_feeds(RESOURCE_FEEDS, items_per=8)
    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(items),
        "items": items[:50],
    }
    _cache_set("resources", out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Earnings adherence — actual vs estimate, last 5y
# ─────────────────────────────────────────────────────────────────────────────

async def get_earnings_adherence(symbol: str, years: int = 5) -> Dict[str, Any]:
    """Did they meet/beat their forecasts? Pulled via yfinance.earnings_history."""
    cache_key = f"earnings:{symbol.upper()}:{years}"
    cached = _cache_get(cache_key, ttl=3600)
    if cached:
        return cached
    try:
        import yfinance as yf  # local-only optional dep
    except ImportError:
        return {"symbol": symbol, "error": "yfinance not installed"}

    try:
        t = yf.Ticker(symbol.upper())
        hist = getattr(t, "earnings_history", None)
        if hist is None:
            hist = t.get_earnings_dates(limit=4 * years) if hasattr(t, "get_earnings_dates") else None
        rows: List[Dict[str, Any]] = []
        if hist is not None:
            try:
                df = hist.reset_index()
            except Exception:
                df = hist
            for _, r in df.iterrows():
                est = r.get("EPS Estimate", r.get("epsEstimate"))
                act = r.get("Reported EPS", r.get("epsActual"))
                if est is None or act is None:
                    continue
                surprise = float(act) - float(est) if est not in (0, None) else None
                rows.append({
                    "date": str(r.get("Earnings Date") or r.get("date") or ""),
                    "estimate": float(est) if est is not None else None,
                    "actual": float(act) if act is not None else None,
                    "surprise": round(surprise, 4) if surprise is not None else None,
                    "beat": bool(surprise > 0) if surprise is not None else None,
                })
        beats = sum(1 for r in rows if r.get("beat"))
        rate = round(beats / len(rows), 3) if rows else 0.0

        out = {
            "symbol": symbol.upper(),
            "years_requested": years,
            "quarters_returned": len(rows),
            "beat_rate": rate,
            "history": rows,
            "verdict": "consistent_beats" if rate >= 0.7
                        else "mixed" if rate >= 0.4
                        else "consistent_misses",
        }
    except Exception as e:
        logger.warning("earnings_adherence %s: %s", symbol, e)
        out = {"symbol": symbol.upper(), "error": str(e), "history": [], "beat_rate": 0.0}

    _cache_set(cache_key, out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# AI Boom composite index
# ─────────────────────────────────────────────────────────────────────────────

async def get_ai_boom_index() -> Dict[str, Any]:
    """
    Build a composite AI-stack momentum index using yfinance.
    For each sub-sector, average % change (5d, 30d, 90d), then aggregate.
    Output drives the 'AI Boom' tab on the dashboard.
    """
    cached = _cache_get("ai_boom", ttl=600)
    if cached:
        return cached

    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed"}

    flat: List[Tuple[str, str]] = [(cat, sym) for cat, syms in AI_BOOM_UNIVERSE.items() for sym in syms]
    syms = list({s for _, s in flat})

    # one bulk download keeps things fast
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(
        None,
        lambda: yf.download(syms, period="6mo", interval="1d", progress=False, group_by="ticker", auto_adjust=True, threads=True),
    )

    rows: Dict[str, Dict[str, float]] = {}
    for sym in syms:
        try:
            sub = df[sym] if sym in df else df
            close = sub["Close"].dropna()
            if len(close) < 6:
                continue
            last = float(close.iloc[-1])
            chg_5 = float(close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else None
            chg_30 = float(close.iloc[-1] / close.iloc[-min(30, len(close))] - 1) * 100
            chg_90 = float(close.iloc[-1] / close.iloc[-min(90, len(close))] - 1) * 100
            vol = float(close.pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5) * 100) if len(close) >= 21 else None
            rows[sym] = {
                "price": round(last, 2),
                "chg_5d_pct": round(chg_5, 2) if chg_5 is not None else None,
                "chg_30d_pct": round(chg_30, 2),
                "chg_90d_pct": round(chg_90, 2),
                "ann_vol_pct": round(vol, 2) if vol is not None else None,
            }
        except Exception as e:
            logger.debug("ai_boom %s: %s", sym, e)

    # category roll-up
    cats: Dict[str, Dict[str, Any]] = {}
    for cat, sym_list in AI_BOOM_UNIVERSE.items():
        present = [rows[s] for s in sym_list if s in rows]
        if not present:
            continue
        cats[cat] = {
            "tickers": [{"symbol": s, **rows[s]} for s in sym_list if s in rows],
            "avg_5d_pct": round(_mean([p["chg_5d_pct"] for p in present if p.get("chg_5d_pct") is not None]), 2),
            "avg_30d_pct": round(_mean([p["chg_30d_pct"] for p in present if p.get("chg_30d_pct") is not None]), 2),
            "avg_90d_pct": round(_mean([p["chg_90d_pct"] for p in present if p.get("chg_90d_pct") is not None]), 2),
        }

    overall_30 = _mean([c["avg_30d_pct"] for c in cats.values()])
    overall_90 = _mean([c["avg_90d_pct"] for c in cats.values()])
    score = round(0.4 * overall_30 + 0.6 * overall_90, 2)
    regime = (
        "blow-off-top" if score > 30 else
        "expansion"     if score > 12 else
        "stable"        if score > 0  else
        "cooling"       if score > -10 else
        "correction"
    )

    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "ai_boom_score": score,
        "regime": regime,
        "overall_avg_30d_pct": round(overall_30, 2),
        "overall_avg_90d_pct": round(overall_90, 2),
        "categories": cats,
        "leaders": sorted(
            [{"symbol": s, **r} for s, r in rows.items() if r.get("chg_30d_pct") is not None],
            key=lambda x: x["chg_30d_pct"],
            reverse=True,
        )[:10],
        "laggards": sorted(
            [{"symbol": s, **r} for s, r in rows.items() if r.get("chg_30d_pct") is not None],
            key=lambda x: x["chg_30d_pct"],
        )[:10],
    }
    _cache_set("ai_boom", out)
    return out


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Market overview — VIX, Fear&Greed, sector rotation, breadth
# ─────────────────────────────────────────────────────────────────────────────

SECTOR_ETFS = {
    "Technology": "XLK", "Communications": "XLC", "Discretionary": "XLY",
    "Staples": "XLP", "Energy": "XLE", "Financials": "XLF",
    "Healthcare": "XLV", "Industrials": "XLI", "Materials": "XLB",
    "Real Estate": "XLRE", "Utilities": "XLU",
}


async def get_market_overview() -> Dict[str, Any]:
    cached = _cache_get("market_overview", ttl=600)
    if cached:
        return cached

    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed"}

    loop = asyncio.get_event_loop()
    syms = ["^VIX", "^GSPC", "^IXIC", "^DJI", "^TNX", "DX-Y.NYB", "GC=F", "CL=F"] + list(SECTOR_ETFS.values())
    df = await loop.run_in_executor(
        None,
        lambda: yf.download(syms, period="3mo", interval="1d", progress=False, group_by="ticker", auto_adjust=True, threads=True),
    )

    def _stat(sym: str) -> Optional[Dict[str, Any]]:
        try:
            sub = df[sym] if sym in df else df
            c = sub["Close"].dropna()
            if len(c) < 6:
                return None
            return {
                "price": round(float(c.iloc[-1]), 2),
                "chg_1d_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
                "chg_5d_pct": round(float(c.iloc[-1] / c.iloc[-6] - 1) * 100, 2) if len(c) >= 6 else None,
                "chg_30d_pct": round(float(c.iloc[-1] / c.iloc[-min(30, len(c))] - 1) * 100, 2),
            }
        except Exception:
            return None

    indices = {k: _stat(k) for k in ["^GSPC", "^IXIC", "^DJI"]}
    macro = {
        "vix": _stat("^VIX"),
        "ten_year_yield": _stat("^TNX"),
        "dxy": _stat("DX-Y.NYB"),
        "gold": _stat("GC=F"),
        "wti_crude": _stat("CL=F"),
    }
    sectors = {name: _stat(sym) for name, sym in SECTOR_ETFS.items()}
    sector_sorted = sorted(
        [(n, (s or {}).get("chg_30d_pct")) for n, s in sectors.items() if s],
        key=lambda x: (x[1] is None, x[1] or 0),
        reverse=True,
    )
    out = {
        "timestamp": datetime.utcnow().isoformat(),
        "indices": indices,
        "macro": macro,
        "sectors": sectors,
        "sector_rotation_30d": {
            "leaders": sector_sorted[:3],
            "laggards": sector_sorted[-3:][::-1],
        },
    }
    _cache_set("market_overview", out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Master snapshot — what the dashboard's "General" tab consumes
# ─────────────────────────────────────────────────────────────────────────────

async def get_full_intelligence_snapshot() -> Dict[str, Any]:
    """Run everything in parallel; return a single payload for the dashboard."""
    influencers, geo, big_money, sec, tech, resources, ai_boom, overview = await asyncio.gather(
        get_influencer_signals(),
        get_geopolitics(),
        get_big_money_flow(),
        get_sec_recent_filings(form_types=["8-K", "10-K", "10-Q", "S-1", "DEF 14A"]),
        get_tech_breakthroughs(),
        get_resource_discoveries(),
        get_ai_boom_index(),
        get_market_overview(),
        return_exceptions=True,
    )

    def _safe(x, fallback):
        return x if isinstance(x, dict) else fallback

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "market_overview": _safe(overview, {}),
        "ai_boom": _safe(ai_boom, {}),
        "influencers": _safe(influencers, {"influencers": []}),
        "geopolitics": _safe(geo, {"items": []}),
        "big_money_flow": _safe(big_money, {}),
        "sec_filings": _safe(sec, {"by_form": {}}),
        "tech_breakthroughs": _safe(tech, {"items": []}),
        "resource_discoveries": _safe(resources, {"items": []}),
    }
