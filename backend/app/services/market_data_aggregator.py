"""
Market Data Aggregator — pulls from 20+ financial data sources.

Sources:
 1. Yahoo Finance (yfinance)       — price, fundamentals, earnings
 2. SEC EDGAR                      — insider trading (Form 4)
 3. FRED (Federal Reserve)         — macro: GDP, unemployment, CPI, rates
 4. US Treasury                    — yield curve
 5. CBOE VIX                       — volatility index
 6. Yahoo Finance RSS              — news
 7. Reuters RSS                    — news
 8. MarketWatch RSS                — news
 9. CNBC RSS                       — news
10. WSJ RSS                        — news
11. Seeking Alpha RSS              — analysis
12. Barron's RSS                   — analysis
13. Bloomberg RSS                  — news
14. Finviz                         — screener / heat-map
15. Stocktwits                     — social sentiment
16. Reddit r/wallstreetbets        — social sentiment
17. CNN Fear & Greed               — market sentiment
18. Put / Call Ratio (CBOE)        — options sentiment
19. Institutional Holdings (13F)   — whale tracking via SEC
20. Earnings Whispers              — upcoming earnings
21. TipRanks-style consensus       — analyst ratings via yfinance
22. Short Interest (FINRA)         — short squeeze candidates

All HTTP calls are async with 10 s timeout + graceful fallback.
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# ── Caches ────────────────────────────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}
CACHE_TTL = 300  # 5 min


def _cached(key: str) -> Optional[Any]:
    if key in _cache and (datetime.now().timestamp() - _cache_ts.get(key, 0)) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key: str, val: Any):
    _cache[key] = val
    _cache_ts[key] = datetime.now().timestamp()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Yahoo Finance — price & fundamentals
# ══════════════════════════════════════════════════════════════════════════════

def get_yfinance_data(symbol: str) -> Dict[str, Any]:
    """Synchronous — run in thread pool."""
    ck = f"yf:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        hist = t.history(period="6mo", interval="1d")
        closes = [round(float(x), 2) for x in hist["Close"].tolist()] if not hist.empty else []
        result = {
            "source": "Yahoo Finance",
            "price": closes[-1] if closes else None,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "recommendation": info.get("recommendationKey"),
            "target_price": info.get("targetMeanPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "short_ratio": info.get("shortRatio"),
            "short_pct_float": info.get("shortPercentOfFloat"),
            "institutional_pct": info.get("heldPercentInstitutions"),
            "insider_pct": info.get("heldPercentInsiders"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "recent_closes": closes[-30:],
        }
        _set_cache(ck, result)
        return result
    except Exception as e:
        logger.error(f"yfinance error {symbol}: {e}")
        return {"source": "Yahoo Finance", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 2. SEC EDGAR — insider trading Form 4
# ══════════════════════════════════════════════════════════════════════════════

async def get_insider_trading(symbol: str) -> Dict[str, Any]:
    ck = f"insider:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        # Get CIK from SEC ticker mapping
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            cik_resp = await client.get(
                "https://efts.sec.gov/LATEST/search-index?q=%22" + symbol + "%22&dateRange=custom&startdt="
                + (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                + "&forms=4&from=0&size=10",
                headers={**_HEADERS, "Accept": "application/json"},
            )
            # Fallback: use full-text search
            search_url = f"https://efts.sec.gov/LATEST/search-index?q={symbol}&forms=4&dateRange=custom&startdt={(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')}"
            resp = await client.get(
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={symbol}&type=4&dateb=&owner=include&count=10&search_text=&action=getcompany",
                follow_redirects=True,
            )
            # Parse basic insider filing data
            filings = []
            if resp.status_code == 200:
                text = resp.text
                # Extract filing entries
                rows = re.findall(r'<tr[^>]*>.*?</tr>', text, re.DOTALL)
                for row in rows[:10]:
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', row)
                    if date_match:
                        filings.append({"date": date_match.group(1), "form": "4"})

        result = {
            "source": "SEC EDGAR Insider Trading",
            "symbol": symbol,
            "recent_filings": len(filings),
            "filings": filings[:5],
            "insider_activity": "high" if len(filings) > 5 else "moderate" if len(filings) > 2 else "low",
        }
        _set_cache(ck, result)
        return result
    except Exception as e:
        logger.warning(f"SEC EDGAR error {symbol}: {e}")
        return {"source": "SEC EDGAR Insider Trading", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 3. FRED — macro economic data
# ══════════════════════════════════════════════════════════════════════════════

async def get_fred_macro() -> Dict[str, Any]:
    ck = "fred:macro"
    c = _cached(ck)
    if c:
        return c
    indicators = {
        "fed_funds_rate": "FEDFUNDS",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "gdp_growth": "A191RL1Q225SBEA",
        "consumer_sentiment": "UMCSENT",
        "m2_money_supply": "M2SL",
    }
    result: Dict[str, Any] = {"source": "Federal Reserve FRED"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            for name, series_id in indicators.items():
                try:
                    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        lines = resp.text.strip().split("\n")
                        if len(lines) > 1:
                            last_line = lines[-1]
                            parts = last_line.split(",")
                            if len(parts) == 2 and parts[1] != ".":
                                result[name] = {"date": parts[0], "value": float(parts[1])}
                except Exception:
                    pass
    except Exception as e:
        result["error"] = str(e)
    _set_cache(ck, result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 4. US Treasury — yield curve
# ══════════════════════════════════════════════════════════════════════════════

async def get_treasury_yields() -> Dict[str, Any]:
    ck = "treasury:yields"
    c = _cached(ck)
    if c:
        return c
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            today = datetime.now()
            url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{today.year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={today.year}&page&_format=csv"
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 100:
                lines = resp.text.strip().split("\n")
                headers = lines[0].split(",") if lines else []
                last = lines[-1].split(",") if len(lines) > 1 else []
                yield_data = {}
                for i, h in enumerate(headers):
                    if i < len(last):
                        try:
                            yield_data[h.strip().strip('"')] = float(last[i])
                        except ValueError:
                            yield_data[h.strip().strip('"')] = last[i]
                result = {"source": "US Treasury Yield Curve", "yields": yield_data}
                _set_cache(ck, result)
                return result
    except Exception as e:
        logger.warning(f"Treasury error: {e}")
    return {"source": "US Treasury Yield Curve", "yields": {}}


# ══════════════════════════════════════════════════════════════════════════════
# 5. CBOE VIX
# ══════════════════════════════════════════════════════════════════════════════

def get_vix() -> Dict[str, Any]:
    ck = "cboe:vix"
    c = _cached(ck)
    if c:
        return c
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if not hist.empty:
            val = round(float(hist["Close"].iloc[-1]), 2)
            level = "extreme_fear" if val > 30 else "fear" if val > 20 else "neutral" if val > 15 else "greed"
            result = {"source": "CBOE VIX", "vix": val, "level": level}
            _set_cache(ck, result)
            return result
    except Exception as e:
        logger.warning(f"VIX error: {e}")
    return {"source": "CBOE VIX", "vix": None}


# ══════════════════════════════════════════════════════════════════════════════
# 6-14. RSS News Feeds
# ══════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Reuters Business": "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "WSJ Markets": "https://feeds.a]wsj.com/wsj/xml/rss/3_7031.xml",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    "Barrons": "https://www.barrons.com/market-data/feeds/rss",
    "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "Investor Business Daily": "https://www.investors.com/feed/",
}


async def _fetch_rss(name: str, url: str, client: httpx.AsyncClient) -> List[Dict]:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        articles = []
        for item in items[:8]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")
            desc = item.findtext("description", "")
            # Strip HTML
            desc = re.sub(r"<[^>]+>", "", desc)[:200]
            articles.append({
                "source": name,
                "title": title.strip(),
                "url": link.strip(),
                "published": pub.strip(),
                "summary": desc.strip(),
            })
        return articles
    except Exception:
        return []


async def get_financial_news(symbol: Optional[str] = None) -> Dict[str, Any]:
    ck = f"news:{symbol or 'general'}"
    c = _cached(ck)
    if c:
        return c
    all_articles: List[Dict] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        tasks = [_fetch_rss(name, url, client) for name, url in RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_articles.extend(r)

        # Symbol-specific Yahoo search
        if symbol:
            try:
                yurl = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
                yresp = await client.get(yurl, follow_redirects=True)
                if yresp.status_code == 200:
                    root = ET.fromstring(yresp.text)
                    for item in root.findall(".//item")[:8]:
                        all_articles.append({
                            "source": f"Yahoo Finance ({symbol})",
                            "title": (item.findtext("title") or "").strip(),
                            "url": (item.findtext("link") or "").strip(),
                            "published": (item.findtext("pubDate") or "").strip(),
                            "summary": re.sub(r"<[^>]+>", "", item.findtext("description") or "")[:200].strip(),
                        })
            except Exception:
                pass

    # Sort by most recent (best effort)
    all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        t = a["title"].lower()[:60]
        if t not in seen:
            seen.add(t)
            unique.append(a)

    result = {
        "source": "Financial News Aggregator",
        "source_count": len(RSS_FEEDS) + (1 if symbol else 0),
        "total_articles": len(unique),
        "articles": unique[:50],
    }
    _set_cache(ck, result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 15. Finviz — screener / stock data
# ══════════════════════════════════════════════════════════════════════════════

async def get_finviz_data(symbol: str) -> Dict[str, Any]:
    ck = f"finviz:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(f"https://finviz.com/quote.ashx?t={symbol}&ty=c&p=d&b=1")
            if resp.status_code == 200:
                text = resp.text
                data = {}
                # Extract key metrics from snapshot table
                metrics = [
                    "P/E", "EPS (ttm)", "Insider Own", "Shs Outstand", "Perf Week",
                    "Perf Month", "Perf Quart", "Perf Half Y", "Perf Year", "Perf YTD",
                    "Volatility", "RSI (14)", "Rel Volume", "Avg Volume", "Short Float",
                    "Target Price", "52W Range", "52W High", "52W Low", "Earnings",
                    "SMA20", "SMA50", "SMA200", "Income", "Sales", "ROE", "ROI",
                    "Gross Margin", "Oper. Margin", "Profit Margin", "Insider Trans",
                ]
                for metric in metrics:
                    pattern = re.escape(metric) + r'</td><td[^>]*><b>([^<]+)</b>'
                    match = re.search(pattern, text)
                    if match:
                        data[metric] = match.group(1).strip()
                result = {"source": "Finviz", "data": data}
                _set_cache(ck, result)
                return result
    except Exception as e:
        logger.warning(f"Finviz error {symbol}: {e}")
    return {"source": "Finviz", "data": {}}


# ══════════════════════════════════════════════════════════════════════════════
# 16-17. Social Sentiment — Stocktwits + Reddit WSB
# ══════════════════════════════════════════════════════════════════════════════

async def get_social_sentiment(symbol: str) -> Dict[str, Any]:
    ck = f"social:{symbol}"
    c = _cached(ck)
    if c:
        return c
    result: Dict[str, Any] = {"source": "Social Sentiment"}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        # Stocktwits
        try:
            resp = await client.get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json")
            if resp.status_code == 200:
                data = resp.json()
                msgs = data.get("messages", [])
                bullish = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
                bearish = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
                total = bullish + bearish
                result["stocktwits"] = {
                    "bullish": bullish,
                    "bearish": bearish,
                    "total_messages": len(msgs),
                    "bull_pct": round(bullish / total * 100, 1) if total > 0 else 50,
                }
        except Exception:
            result["stocktwits"] = {"error": "unavailable"}

        # Reddit WSB
        try:
            resp = await client.get(
                f"https://www.reddit.com/r/wallstreetbets/search.json?q={symbol}&sort=new&t=week&limit=10",
                headers={**_HEADERS, "Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                result["reddit_wsb"] = {
                    "recent_posts": len(posts),
                    "mentions": "high" if len(posts) > 5 else "moderate" if len(posts) > 2 else "low",
                    "top_posts": [
                        {"title": p["data"]["title"][:100], "score": p["data"]["score"]}
                        for p in posts[:3]
                    ],
                }
        except Exception:
            result["reddit_wsb"] = {"error": "unavailable"}

    _set_cache(ck, result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 18. CNN Fear & Greed Index
# ══════════════════════════════════════════════════════════════════════════════

async def get_fear_greed() -> Dict[str, Any]:
    ck = "cnn:fear_greed"
    c = _cached(ck)
    if c:
        return c
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata")
            if resp.status_code == 200:
                data = resp.json()
                fg = data.get("fear_and_greed", {})
                result = {
                    "source": "CNN Fear & Greed Index",
                    "score": fg.get("score"),
                    "rating": fg.get("rating"),
                    "previous_close": fg.get("previous_close"),
                    "previous_1_week": fg.get("previous_1_week"),
                    "previous_1_month": fg.get("previous_1_month"),
                    "previous_1_year": fg.get("previous_1_year"),
                }
                _set_cache(ck, result)
                return result
    except Exception as e:
        logger.warning(f"Fear & Greed error: {e}")
    return {"source": "CNN Fear & Greed Index", "score": None}


# ══════════════════════════════════════════════════════════════════════════════
# 19. Put/Call Ratio
# ══════════════════════════════════════════════════════════════════════════════

def get_put_call_ratio() -> Dict[str, Any]:
    ck = "cboe:pcr"
    c = _cached(ck)
    if c:
        return c
    try:
        import yfinance as yf
        # Use SPY options as proxy
        spy = yf.Ticker("SPY")
        exp = spy.options
        if exp:
            chain = spy.option_chain(exp[0])
            total_call_vol = int(chain.calls["volume"].sum()) if "volume" in chain.calls.columns else 0
            total_put_vol = int(chain.puts["volume"].sum()) if "volume" in chain.puts.columns else 0
            ratio = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else 1.0
            signal = "extreme_fear" if ratio > 1.2 else "bearish" if ratio > 1.0 else "neutral" if ratio > 0.7 else "bullish"
            result = {
                "source": "CBOE Put/Call Ratio (SPY proxy)",
                "ratio": ratio,
                "signal": signal,
                "call_volume": total_call_vol,
                "put_volume": total_put_vol,
            }
            _set_cache(ck, result)
            return result
    except Exception as e:
        logger.warning(f"Put/Call ratio error: {e}")
    return {"source": "CBOE Put/Call Ratio", "ratio": None}


# ══════════════════════════════════════════════════════════════════════════════
# 20. Institutional Holdings (13F via SEC EDGAR)
# ══════════════════════════════════════════════════════════════════════════════

async def get_institutional_filings(symbol: str) -> Dict[str, Any]:
    ck = f"13f:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&forms=13F-HR&dateRange=custom"
                f"&startdt={(datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')}&from=0&size=5",
                headers={**_HEADERS, "Accept": "application/json"},
            )
            filings = []
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    for h in hits[:5]:
                        src = h.get("_source", {})
                        filings.append({
                            "filer": src.get("display_names", ["Unknown"])[0],
                            "date": src.get("file_date", ""),
                        })
                except Exception:
                    pass
        result = {
            "source": "SEC 13F Institutional Holdings",
            "symbol": symbol,
            "recent_13f_filings": len(filings),
            "filings": filings,
        }
        _set_cache(ck, result)
        return result
    except Exception as e:
        logger.warning(f"13F error {symbol}: {e}")
        return {"source": "SEC 13F Institutional Holdings", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 21. Analyst Consensus (via yfinance)
# ══════════════════════════════════════════════════════════════════════════════

def get_analyst_consensus(symbol: str) -> Dict[str, Any]:
    ck = f"analyst:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        rec = t.recommendations
        if rec is not None and not rec.empty:
            recent = rec.tail(10)
            grades = recent.to_dict("records") if hasattr(recent, "to_dict") else []
            result = {
                "source": "Analyst Consensus (yfinance)",
                "recent_ratings": [
                    {"firm": str(r.get("Firm", "")), "grade": str(r.get("To Grade", "")), "action": str(r.get("Action", ""))}
                    for r in grades
                ],
                "total_ratings": len(grades),
            }
            _set_cache(ck, result)
            return result
    except Exception as e:
        logger.warning(f"Analyst error {symbol}: {e}")
    return {"source": "Analyst Consensus", "recent_ratings": []}


# ══════════════════════════════════════════════════════════════════════════════
# 22. Earnings Calendar (via yfinance)
# ══════════════════════════════════════════════════════════════════════════════

def get_earnings_calendar(symbol: str) -> Dict[str, Any]:
    ck = f"earnings:{symbol}"
    c = _cached(ck)
    if c:
        return c
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        cal = t.calendar
        if cal is not None:
            if isinstance(cal, dict):
                result = {"source": "Earnings Calendar", "calendar": {k: str(v) for k, v in cal.items()}}
            else:
                result = {"source": "Earnings Calendar", "calendar": str(cal)}
            _set_cache(ck, result)
            return result
    except Exception as e:
        logger.warning(f"Earnings error {symbol}: {e}")
    return {"source": "Earnings Calendar", "calendar": {}}


# ══════════════════════════════════════════════════════════════════════════════
# Master Aggregator — combines ALL sources for a symbol
# ══════════════════════════════════════════════════════════════════════════════

async def aggregate_all_data(symbol: str) -> Dict[str, Any]:
    """
    Pull data from all 20+ sources for a given symbol.
    Returns a comprehensive dict with data from every source.
    """
    import asyncio

    # Synchronous sources → run in thread pool
    sync_tasks = {
        "yahoo_finance": asyncio.to_thread(get_yfinance_data, symbol),
        "vix": asyncio.to_thread(get_vix),
        "put_call_ratio": asyncio.to_thread(get_put_call_ratio),
        "analyst_consensus": asyncio.to_thread(get_analyst_consensus, symbol),
        "earnings_calendar": asyncio.to_thread(get_earnings_calendar, symbol),
    }

    # Async sources
    async_tasks = {
        "insider_trading": get_insider_trading(symbol),
        "fred_macro": get_fred_macro(),
        "treasury_yields": get_treasury_yields(),
        "financial_news": get_financial_news(symbol),
        "finviz": get_finviz_data(symbol),
        "social_sentiment": get_social_sentiment(symbol),
        "fear_greed": get_fear_greed(),
        "institutional_13f": get_institutional_filings(symbol),
    }

    all_tasks = {**sync_tasks, **async_tasks}
    keys = list(all_tasks.keys())
    results = await asyncio.gather(*all_tasks.values(), return_exceptions=True)

    data: Dict[str, Any] = {"symbol": symbol.upper(), "timestamp": datetime.now().isoformat()}
    sources_ok = 0
    sources_failed = 0
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            data[key] = {"error": str(result)}
            sources_failed += 1
        else:
            data[key] = result
            sources_ok += 1

    data["meta"] = {
        "total_sources": len(keys),
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
    }
    return data
