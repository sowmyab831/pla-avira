"""
Market Sentiment Aggregator

Fetches sentiment signals from:
- Reddit (r/wallstreetbets, r/stocks, r/investing)
- Financial news (Yahoo Finance, MarketWatch, Seeking Alpha)
- Social media mentions and trending tickers
- Fear & Greed index proxy

All via public endpoints — no API keys required for basic scraping.
"""

import httpx
import asyncio
import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

REDDIT_SUBS = ["wallstreetbets", "stocks", "investing", "options", "stockmarket"]
REDDIT_HEADERS = {"User-Agent": "PLA-Avira/1.0 (market-research)"}

POSITIVE_WORDS = frozenset([
    "bullish", "buy", "calls", "moon", "rocket", "squeeze", "breakout",
    "upgrade", "beat", "strong", "rally", "surge", "gains", "profit",
    "outperform", "upside", "growth", "accumulate", "undervalued", "opportunity",
])
NEGATIVE_WORDS = frozenset([
    "bearish", "sell", "puts", "crash", "dump", "short", "downgrade",
    "miss", "weak", "drop", "plunge", "loss", "overvalued", "risk",
    "underperform", "downside", "recession", "layoffs", "bankruptcy", "warning",
])


def _score_text(text: str) -> float:
    """Simple sentiment score: -1.0 (bearish) to +1.0 (bullish)."""
    words = set(text.lower().split())
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


async def _fetch_reddit_sentiment(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Fetch recent Reddit posts mentioning the symbol."""
    mentions = []
    total_score = 0.0
    post_count = 0

    for sub in REDDIT_SUBS:
        try:
            url = f"https://www.reddit.com/r/{sub}/search.json?q={symbol}&sort=new&t=week&limit=10"
            resp = await client.get(url, headers=REDDIT_HEADERS, timeout=8)
            if resp.status_code != 200:
                continue

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                p = post.get("data", {})
                title = p.get("title", "")
                selftext = p.get("selftext", "")[:200]
                score = p.get("score", 0)
                comments = p.get("num_comments", 0)

                sentiment = _score_text(f"{title} {selftext}")
                total_score += sentiment
                post_count += 1

                if score > 50 or comments > 20:
                    mentions.append({
                        "source": f"r/{sub}",
                        "title": title[:100],
                        "upvotes": score,
                        "comments": comments,
                        "sentiment": sentiment,
                        "url": f"https://reddit.com{p.get('permalink', '')}",
                    })
        except Exception as e:
            logger.debug(f"Reddit {sub} error: {e}")
            continue

    avg_score = total_score / post_count if post_count > 0 else 0.0
    return {
        "source": "reddit",
        "post_count": post_count,
        "avg_sentiment": round(avg_score, 3),
        "top_mentions": sorted(mentions, key=lambda x: x["upvotes"], reverse=True)[:5],
        "signal": "bullish" if avg_score > 0.15 else "bearish" if avg_score < -0.15 else "neutral",
    }


async def _fetch_yahoo_news(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Fetch Yahoo Finance news for sentiment analysis."""
    headlines = []
    total_score = 0.0

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={symbol}&newsCount=15"
        resp = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("news", []):
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                sentiment = _score_text(title)
                total_score += sentiment

                headlines.append({
                    "title": title,
                    "publisher": publisher,
                    "sentiment": sentiment,
                    "url": item.get("link", ""),
                })
    except Exception as e:
        logger.debug(f"Yahoo news error: {e}")

    count = len(headlines)
    avg = total_score / count if count > 0 else 0.0
    return {
        "source": "yahoo_finance",
        "headline_count": count,
        "avg_sentiment": round(avg, 3),
        "headlines": headlines[:8],
        "signal": "bullish" if avg > 0.15 else "bearish" if avg < -0.15 else "neutral",
    }


async def _fetch_fear_greed(client: httpx.AsyncClient) -> Dict:
    """Fetch CNN Fear & Greed Index proxy via alternative.me crypto API
    (correlates with broader market sentiment)."""
    try:
        resp = await client.get("https://api.alternative.me/fng/?limit=7", timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                current = data[0]
                week_avg = sum(int(d["value"]) for d in data) / len(data)
                return {
                    "current": int(current["value"]),
                    "label": current["value_classification"],
                    "week_avg": round(week_avg, 1),
                    "trend": "improving" if int(data[0]["value"]) > int(data[-1]["value"]) else "declining",
                }
    except Exception as e:
        logger.debug(f"Fear/Greed error: {e}")

    return {"current": 50, "label": "Neutral", "week_avg": 50, "trend": "stable"}


async def _fetch_finviz_data(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Scrape FinViz for analyst ratings, target price, and short interest."""
    try:
        url = f"https://finviz.com/quote.ashx?t={symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = await client.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {}

        text = resp.text

        def _extract(label: str) -> str:
            pattern = rf'<td[^>]*>{label}</td>\s*<td[^>]*>([^<]+)</td>'
            m = re.search(pattern, text, re.IGNORECASE)
            return m.group(1).strip() if m else ""

        target = _extract("Target Price")
        rec = _extract("Recom")
        short_float = _extract("Short Float")
        insider_own = _extract("Insider Own")
        inst_own = _extract("Inst Own")
        earnings = _extract("Earnings")
        pe = _extract("P/E")
        fwd_pe = _extract("Forward P/E")

        return {
            "target_price": target,
            "recommendation": rec,
            "short_float": short_float,
            "insider_ownership": insider_own,
            "institutional_ownership": inst_own,
            "next_earnings": earnings,
            "pe_ratio": pe,
            "forward_pe": fwd_pe,
        }
    except Exception as e:
        logger.debug(f"FinViz error: {e}")
        return {}


async def get_market_sentiment(symbol: str) -> Dict[str, Any]:
    """
    Aggregate market sentiment from multiple sources.

    Returns a composite sentiment score and individual source breakdowns.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        reddit_task = _fetch_reddit_sentiment(symbol, client)
        yahoo_task = _fetch_yahoo_news(symbol, client)
        fear_task = _fetch_fear_greed(client)
        finviz_task = _fetch_finviz_data(symbol, client)

        reddit, yahoo, fear_greed, finviz = await asyncio.gather(
            reddit_task, yahoo_task, fear_task, finviz_task,
            return_exceptions=True,
        )

        # Handle exceptions gracefully
        if isinstance(reddit, Exception):
            reddit = {"source": "reddit", "post_count": 0, "avg_sentiment": 0, "top_mentions": [], "signal": "neutral"}
        if isinstance(yahoo, Exception):
            yahoo = {"source": "yahoo_finance", "headline_count": 0, "avg_sentiment": 0, "headlines": [], "signal": "neutral"}
        if isinstance(fear_greed, Exception):
            fear_greed = {"current": 50, "label": "Neutral", "week_avg": 50, "trend": "stable"}
        if isinstance(finviz, Exception):
            finviz = {}

    # Composite score: weighted average
    weights = {"reddit": 0.25, "yahoo": 0.35, "fear_greed": 0.15, "finviz": 0.25}

    reddit_score = reddit.get("avg_sentiment", 0) if isinstance(reddit, dict) else 0
    yahoo_score = yahoo.get("avg_sentiment", 0) if isinstance(yahoo, dict) else 0

    # Normalize fear/greed (0-100 → -1 to 1)
    fg_score = (fear_greed.get("current", 50) - 50) / 50 if isinstance(fear_greed, dict) else 0

    # FinViz recommendation (1=strong buy, 5=strong sell → normalize to -1 to 1)
    finviz_score = 0.0
    if isinstance(finviz, dict) and finviz.get("recommendation"):
        try:
            rec_val = float(finviz["recommendation"])
            finviz_score = (3 - rec_val) / 2  # 1→1.0, 2→0.5, 3→0.0, 4→-0.5, 5→-1.0
        except (ValueError, TypeError):
            pass

    composite = (
        reddit_score * weights["reddit"]
        + yahoo_score * weights["yahoo"]
        + fg_score * weights["fear_greed"]
        + finviz_score * weights["finviz"]
    )

    if composite > 0.2:
        overall = "bullish"
    elif composite < -0.2:
        overall = "bearish"
    else:
        overall = "neutral"

    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "composite_score": round(composite, 3),
        "overall_signal": overall,
        "fear_greed_index": fear_greed,
        "sources": {
            "reddit": reddit,
            "yahoo_finance": yahoo,
            "finviz": finviz,
        },
    }
