"""
Earnings Intelligence Service
──────────────────────────────
Comprehensive pre-earnings analysis using 12+ data dimensions + LLM synthesis.

Dimensions analysed:
 1. Financial performance (revenue, EPS, margins, guidance)
 2. SEC filings (10-K, 10-Q, 8-K recent)
 3. Insider trading (Form 4 buys/sells)
 4. Stock buyback programs
 5. Leadership & governance (CEO changes, board moves)
 6. Competitive landscape
 7. Supply chain & raw materials
 8. Geopolitical exposure
 9. Analyst consensus & revisions
10. Social / retail sentiment
11. Options market positioning (put/call skew)
12. Macro & sector context

Output: LLM-synthesised earnings preview with bull/bear/base scenarios.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import os

import httpx

from app.services.llm_client import extract_json, generate as _llm_generate

logger = logging.getLogger(__name__)

# Ollama config — host uses Apple Silicon Metal GPU; backend reaches it via
# hostNetwork localhost. qwen2.5:14b is the finance-tuned default and fits GPU.
OLLAMA_HOST = os.getenv("OLLAMA_API_BASE", os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
EARNINGS_LLM_MODEL = os.getenv("EARNINGS_LLM_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:14b"))

# ── cache ────────────────────────────────────────────────────────────────────
_CACHE: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 min


def _cache_get(key: str) -> Optional[Any]:
    if key in _CACHE:
        val, ts = _CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None


def _cache_set(key: str, val: Any):
    _CACHE[key] = (val, time.time())


# ── 1. Financial Performance (yfinance) ─────────────────────────────────────
async def _get_financials(symbol: str) -> Dict[str, Any]:
    """Revenue, EPS, margins, guidance from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        
        # Earnings history
        earnings_hist = []
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                for _, row in eh.tail(4).iterrows():
                    earnings_hist.append({
                        "quarter": str(row.name),
                        "eps_estimate": float(row.get("epsEstimate", 0)),
                        "eps_actual": float(row.get("epsActual", 0)),
                        "surprise_pct": float(row.get("surprisePercent", 0)) * 100,
                    })
        except Exception:
            pass

        # Quarterly financials
        quarterly_rev = []
        try:
            qf = t.quarterly_financials
            if qf is not None and not qf.empty:
                for col in list(qf.columns)[:4]:
                    rev = qf.loc["Total Revenue", col] if "Total Revenue" in qf.index else 0
                    gp = qf.loc["Gross Profit", col] if "Gross Profit" in qf.index else 0
                    ni = qf.loc["Net Income", col] if "Net Income" in qf.index else 0
                    quarterly_rev.append({
                        "quarter": col.strftime("%Y-Q%q") if hasattr(col, 'strftime') else str(col),
                        "revenue": float(rev) if rev else 0,
                        "gross_profit": float(gp) if gp else 0,
                        "net_income": float(ni) if ni else 0,
                    })
        except Exception:
            pass

        return {
            "name": info.get("longName", symbol),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap", 0),
            "price": info.get("currentPrice", info.get("regularMarketPrice", 0)),
            "pe_ratio": info.get("trailingPE", 0),
            "forward_pe": info.get("forwardPE", 0),
            "peg_ratio": info.get("pegRatio", 0),
            "revenue_growth": info.get("revenueGrowth", 0),
            "earnings_growth": info.get("earningsGrowth", 0),
            "profit_margins": info.get("profitMargins", 0),
            "gross_margins": info.get("grossMargins", 0),
            "operating_margins": info.get("operatingMargins", 0),
            "debt_to_equity": info.get("debtToEquity", 0),
            "free_cash_flow": info.get("freeCashflow", 0),
            "eps_trailing": info.get("trailingEps", 0),
            "eps_forward": info.get("forwardEps", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "beta": info.get("beta", 0),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
            "50d_avg": info.get("fiftyDayAverage", 0),
            "200d_avg": info.get("twoHundredDayAverage", 0),
            "earnings_date": str(info.get("earningsTimestamp", "")),
            "earnings_history": earnings_hist,
            "quarterly_revenue": quarterly_rev,
            "analyst_target_mean": info.get("targetMeanPrice", 0),
            "analyst_target_low": info.get("targetLowPrice", 0),
            "analyst_target_high": info.get("targetHighPrice", 0),
            "recommendation": info.get("recommendationKey", ""),
            "num_analysts": info.get("numberOfAnalystOpinions", 0),
        }
    except Exception as e:
        logger.error(f"Financials for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


# ── 2. SEC Filings ──────────────────────────────────────────────────────────
async def _get_sec_filings(symbol: str, client: httpx.AsyncClient) -> List[Dict]:
    """Recent SEC filings (10-K, 10-Q, 8-K, DEF 14A)."""
    try:
        cik_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&dateRange=custom&startdt=2024-01-01&forms=10-K,10-Q,8-K"
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&forms=10-K,10-Q,8-K,DEF+14A&dateRange=custom&startdt={(datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')}"
        
        # Use EDGAR full-text search
        search_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&forms=10-K,10-Q,8-K&dateRange=custom&startdt={(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')}"
        
        # Simpler approach: EDGAR company filings
        headers = {"User-Agent": "AVIRA Research research@avira.app"}
        ticker_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={symbol}&type=10-K%2C10-Q%2C8-K&dateb=&owner=include&count=10&search_text=&action=getcompany"
        
        # Use EDGAR XBRL API
        filings = []
        submissions_url = f"https://data.sec.gov/submissions/CIK{symbol}.json"
        
        # Try ticker lookup first
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        r = await client.get(tickers_url, headers=headers, timeout=10)
        if r.status_code == 200:
            tickers = r.json()
            cik = None
            for entry in tickers.values():
                if entry.get("ticker", "").upper() == symbol.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    break
            
            if cik:
                sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                r2 = await client.get(sub_url, headers=headers, timeout=10)
                if r2.status_code == 200:
                    data = r2.json()
                    recent = data.get("filings", {}).get("recent", {})
                    forms = recent.get("form", [])
                    dates = recent.get("filingDate", [])
                    descriptions = recent.get("primaryDocument", [])
                    accessions = recent.get("accessionNumber", [])
                    
                    for i in range(min(len(forms), 15)):
                        form = forms[i]
                        if form in ("10-K", "10-Q", "8-K", "DEF 14A", "SC 13D", "SC 13G", "4"):
                            filings.append({
                                "form": form,
                                "date": dates[i] if i < len(dates) else "",
                                "description": descriptions[i] if i < len(descriptions) else "",
                                "url": f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accessions[i].replace('-', '')}/{descriptions[i]}" if i < len(descriptions) and i < len(accessions) else "",
                            })
        
        return filings[:10]
    except Exception as e:
        logger.debug(f"SEC filings for {symbol}: {e}")
        return []


# ── 3. Insider Trading (Form 4) ─────────────────────────────────────────────
async def _get_insider_trading(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Recent insider buys/sells from SEC EDGAR."""
    try:
        headers = {"User-Agent": "AVIRA Research research@avira.app"}
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}&type=4&dateb=&owner=only&count=20&search_text=&action=getcompany"
        
        # Use EDGAR RSS for Form 4
        rss_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22&forms=4&dateRange=custom&startdt={(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')}"
        
        # Simpler: use yfinance insider data
        import yfinance as yf
        t = yf.Ticker(symbol)

        def _ownership_label(code: str) -> str:
            return {"D": "Derivative", "I": "Indirect", "M": "Material"}.get(code, code)

        def _infer_transaction(text: str) -> str:
            """yfinance's 'Transaction' column is often blank, so derive from the 'Text' column."""
            if not text:
                return ""
            t = text.strip().lower()
            if "stock gift" in t or "gift at" in t or ("gift" in t and "stock" in t):
                return "Gift"
            if "acquired" in t or "purchase" in t or "bought" in t:
                return "Purchase"
            if "sale at" in t or " sale" in t or "sold" in t or "disposed" in t:
                return "Sale"
            if "conversion of" in t or "converted" in t or "exercise" in t:
                return "Conversion"
            # fall back to first meaningful word
            words = text.split()
            return words[0].capitalize() if words else ""

        insider_txns = []
        try:
            it = t.insider_transactions
            if it is not None and not it.empty:
                for _, row in it.head(10).iterrows():
                    # yfinance's 'Transaction' column is often blank or a single code;
                    # the 'Text' column has the full description, so infer from it first.
                    txn = _infer_transaction(str(row.get("Text", "")))
                    if not txn:
                        txn = str(row.get("Transaction", "")).strip()
                    if not txn:
                        txn = _ownership_label(str(row.get("Ownership", "")).strip())
                    insider_txns.append({
                        "insider": str(row.get("Insider", row.get("Insider Trading", row.get("insider", "")))),
                        "title": str(row.get("Position", row.get("Relationship", row.get("relation", row.get("title", ""))))),
                        "relation": str(row.get("Position", row.get("Relationship", row.get("relation", "")))),
                        "transaction": txn,
                        "date": str(row.get("Start Date", row.get("date", ""))),
                        "shares": int(row.get("Shares", row.get("shares", 0))) if row.get("Shares", row.get("shares")) is not None else 0,
                        "value": float(row.get("Value", row.get("value", 0))) if row.get("Value", row.get("value")) is not None else 0,
                    })
        except Exception:
            pass
        
        insider_holders = []
        try:
            ih = t.insider_holders
            if ih is not None and not ih.empty:
                for _, row in ih.iterrows():
                    insider_holders.append({
                        "name": str(row.get("Name", "")),
                        "position": str(row.get("Position", "")),
                        "shares": int(row.get("Shares", 0)) if row.get("Shares") else 0,
                        "latest_transaction": str(row.get("Date Reported", "")),
                    })
        except Exception:
            pass
        
        # Aggregate buy vs sell
        total_buys = sum(1 for t in insider_txns if "buy" in str(t.get("transaction", "")).lower() or "purchase" in str(t.get("transaction", "")).lower())
        total_sells = sum(1 for t in insider_txns if "sell" in str(t.get("transaction", "")).lower() or "sale" in str(t.get("transaction", "")).lower())
        
        return {
            "recent_transactions": insider_txns,
            "insider_holders": insider_holders,
            "buy_count_90d": total_buys,
            "sell_count_90d": total_sells,
            "signal": "bullish" if total_buys > total_sells else "bearish" if total_sells > total_buys else "neutral",
        }
    except Exception as e:
        logger.debug(f"Insider trading for {symbol}: {e}")
        return {"recent_transactions": [], "signal": "unknown"}


# ── 4. Buyback Programs ─────────────────────────────────────────────────────
async def _get_buyback_info(symbol: str) -> Dict:
    """Stock buyback / share repurchase info from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        
        shares_outstanding = info.get("sharesOutstanding", 0)
        float_shares = info.get("floatShares", 0)
        shares_short = info.get("sharesShort", 0)
        short_ratio = info.get("shortRatio", 0)
        short_pct_float = info.get("shortPercentOfFloat", 0)
        
        # Check cash flow for buybacks
        buyback_amount = 0
        try:
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                for label in ["Repurchase Of Capital Stock", "Common Stock Repurchased", "Stock Repurchased"]:
                    if label in cf.index:
                        recent = cf.loc[label].iloc[0]
                        buyback_amount = abs(float(recent)) if recent else 0
                        break
        except Exception:
            pass
        
        return {
            "shares_outstanding": shares_outstanding,
            "float_shares": float_shares,
            "shares_short": shares_short,
            "short_ratio": short_ratio,
            "short_pct_float": short_pct_float,
            "recent_buyback_amount": buyback_amount,
            "has_active_buyback": buyback_amount > 0,
        }
    except Exception as e:
        logger.debug(f"Buyback info for {symbol}: {e}")
        return {}


# ── 5. Leadership & Governance ───────────────────────────────────────────────
async def _get_leadership(symbol: str) -> Dict:
    """Key executives from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        
        officers = []
        try:
            for officer in (t.info.get("companyOfficers", []) or []):
                officers.append({
                    "name": officer.get("name", ""),
                    "title": officer.get("title", ""),
                    "age": officer.get("age"),
                    "total_pay": officer.get("totalPay", 0),
                    "exercised_value": officer.get("exercisedValue", 0),
                    "unexercised_value": officer.get("unexercisedValue", 0),
                })
        except Exception:
            pass
        
        return {
            "officers": officers[:10],
            "governance_risk": t.info.get("overallRisk", "N/A"),
            "audit_risk": t.info.get("auditRisk", "N/A"),
            "board_risk": t.info.get("boardRisk", "N/A"),
            "compensation_risk": t.info.get("compensationRisk", "N/A"),
            "shareholder_rights_risk": t.info.get("shareHolderRightsRisk", "N/A"),
        }
    except Exception as e:
        logger.debug(f"Leadership for {symbol}: {e}")
        return {"officers": []}


# ── 6. Competitive Landscape ────────────────────────────────────────────────
SECTOR_COMPETITORS = {
    "AAPL": ["MSFT", "GOOGL", "SAMSUNG"],
    "MSFT": ["AAPL", "GOOGL", "AMZN"],
    "GOOGL": ["META", "MSFT", "AMZN"],
    "AMZN": ["WMT", "MSFT", "GOOGL"],
    "META": ["GOOGL", "SNAP", "PINS"],
    "NVDA": ["AMD", "INTC", "AVGO"],
    "AMD": ["NVDA", "INTC", "QCOM"],
    "TSLA": ["RIVN", "F", "GM"],
    "JPM": ["BAC", "GS", "MS"],
    "JNJ": ["PFE", "UNH", "ABT"],
}


async def _get_competitors(symbol: str) -> List[Dict]:
    """Basic competitive comparison."""
    try:
        import yfinance as yf
        comps = SECTOR_COMPETITORS.get(symbol.upper(), [])
        if not comps:
            # Try to find sector peers
            t = yf.Ticker(symbol)
            sector = t.info.get("sector", "")
            industry = t.info.get("industry", "")
            return [{"note": f"Sector: {sector}, Industry: {industry}", "competitors": "auto-detect not available for this symbol"}]
        
        results = []
        for comp in comps[:3]:
            try:
                ct = yf.Ticker(comp)
                ci = ct.info or {}
                results.append({
                    "symbol": comp,
                    "name": ci.get("longName", comp),
                    "market_cap": ci.get("marketCap", 0),
                    "pe_ratio": ci.get("trailingPE", 0),
                    "revenue_growth": ci.get("revenueGrowth", 0),
                    "profit_margins": ci.get("profitMargins", 0),
                    "price": ci.get("currentPrice", ci.get("regularMarketPrice", 0)),
                })
            except Exception:
                results.append({"symbol": comp, "error": "data unavailable"})
        
        return results
    except Exception as e:
        logger.debug(f"Competitors for {symbol}: {e}")
        return []


# ── 7. Supply Chain & Raw Materials ──────────────────────────────────────────
SUPPLY_CHAIN_MAP = {
    "AAPL": {"raw_materials": ["semiconductors", "rare earths", "glass", "aluminum"], "key_suppliers": ["TSMC (TSM)", "Foxconn", "Samsung Display"], "supply_risks": ["China-Taiwan tensions", "chip shortage cycles"]},
    "TSLA": {"raw_materials": ["lithium", "cobalt", "nickel", "steel", "copper"], "key_suppliers": ["Panasonic", "CATL", "LG Energy"], "supply_risks": ["lithium price volatility", "EV battery supply constraints"]},
    "NVDA": {"raw_materials": ["silicon wafers", "rare gases", "photoresist"], "key_suppliers": ["TSMC (TSM)", "Samsung Foundry", "SK Hynix"], "supply_risks": ["TSMC concentration risk", "export controls to China"]},
    "AMD": {"raw_materials": ["silicon wafers", "rare gases"], "key_suppliers": ["TSMC (TSM)", "ASE Group"], "supply_risks": ["TSMC capacity allocation vs NVDA/AAPL"]},
    "AMZN": {"raw_materials": ["server hardware", "networking equipment"], "key_suppliers": ["Intel", "AMD", "NVDA", "Broadcom"], "supply_risks": ["datacenter chip demand", "energy costs"]},
    "MSFT": {"raw_materials": ["server hardware", "GPUs"], "key_suppliers": ["NVDA", "AMD", "Intel"], "supply_risks": ["GPU supply for Azure AI", "energy for datacenters"]},
    "META": {"raw_materials": ["GPUs", "VR components", "server hardware"], "key_suppliers": ["NVDA", "Qualcomm"], "supply_risks": ["GPU allocation for AI training"]},
    "GOOGL": {"raw_materials": ["TPU chips", "server hardware"], "key_suppliers": ["Broadcom (TPU)", "Intel", "Samsung"], "supply_risks": ["custom chip yields", "energy costs"]},
}


async def _get_supply_chain(symbol: str) -> Dict:
    """Supply chain and raw materials exposure."""
    default = {
        "raw_materials": ["general industrial inputs"],
        "key_suppliers": ["varies by industry"],
        "supply_risks": ["general supply chain disruption"],
    }
    data = SUPPLY_CHAIN_MAP.get(symbol.upper(), default)
    
    # Add commodity prices for relevant materials
    commodity_symbols = {
        "lithium": "ALB",  # proxy
        "copper": "HG=F",
        "gold": "GC=F",
        "oil": "CL=F",
        "steel": "X",  # proxy
        "aluminum": "AA",  # proxy
    }
    
    relevant_commodities = {}
    try:
        import yfinance as yf
        for material in data["raw_materials"]:
            for keyword, sym in commodity_symbols.items():
                if keyword in material.lower():
                    try:
                        t = yf.Ticker(sym)
                        hist = t.history(period="1mo")
                        if not hist.empty:
                            current = float(hist["Close"].iloc[-1])
                            month_ago = float(hist["Close"].iloc[0])
                            change = ((current - month_ago) / month_ago) * 100
                            relevant_commodities[keyword] = {
                                "proxy_symbol": sym,
                                "current": round(current, 2),
                                "30d_change_pct": round(change, 2),
                            }
                    except Exception:
                        pass
    except Exception:
        pass
    
    data["commodity_prices"] = relevant_commodities
    return data


# ── 8. Geopolitical Exposure ────────────────────────────────────────────────
async def _get_geopolitical_exposure(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Geopolitical risk factors for the company."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        country = info.get("country", "US")
        sector = info.get("sector", "")
        
        # Known geopolitical risks by sector/company
        geo_risks = []
        sym = symbol.upper()
        
        if sym in ("AAPL", "NVDA", "AMD", "QCOM", "AVGO"):
            geo_risks.append({"region": "China/Taiwan", "risk": "high", "detail": "Heavy reliance on TSMC and Chinese market"})
        if sym in ("TSLA", "NIO", "BABA", "JD", "PDD"):
            geo_risks.append({"region": "China", "risk": "high", "detail": "Significant China revenue or operations"})
        if sym in ("XOM", "CVX", "COP", "OXY"):
            geo_risks.append({"region": "Middle East", "risk": "medium", "detail": "Oil price sensitivity to OPEC and conflicts"})
        if sector in ("Technology", "Communication Services"):
            geo_risks.append({"region": "EU", "risk": "medium", "detail": "Digital Services Act, AI Act regulatory risk"})
        if sector == "Financials":
            geo_risks.append({"region": "Global", "risk": "medium", "detail": "Interest rate policy divergence, banking regulation"})
        
        if not geo_risks:
            geo_risks.append({"region": "General", "risk": "low", "detail": "Standard US market exposure"})
        
        return {
            "headquartered": country,
            "sector": sector,
            "risks": geo_risks,
        }
    except Exception as e:
        logger.debug(f"Geo exposure for {symbol}: {e}")
        return {"risks": []}


# ── 9. Analyst Consensus ────────────────────────────────────────────────────
async def _get_analyst_consensus(symbol: str) -> Dict:
    """Analyst ratings and estimate revisions."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        
        recommendations = []
        try:
            recs = t.recommendations
            if recs is not None and not recs.empty:
                for _, row in recs.tail(10).iterrows():
                    recommendations.append({
                        "firm": str(row.get("Firm", "")),
                        "grade": str(row.get("To Grade", "")),
                        "action": str(row.get("Action", "")),
                        "date": str(row.name),
                    })
        except Exception:
            pass
        
        return {
            "recommendation": info.get("recommendationKey", ""),
            "mean_recommendation": info.get("recommendationMean", 0),
            "target_mean": info.get("targetMeanPrice", 0),
            "target_low": info.get("targetLowPrice", 0),
            "target_high": info.get("targetHighPrice", 0),
            "target_median": info.get("targetMedianPrice", 0),
            "num_analysts": info.get("numberOfAnalystOpinions", 0),
            "recent_ratings": recommendations,
        }
    except Exception as e:
        logger.debug(f"Analyst consensus for {symbol}: {e}")
        return {}


# ── 10. Social / Retail Sentiment ────────────────────────────────────────────
async def _get_social_sentiment(symbol: str, client: httpx.AsyncClient) -> Dict:
    """Social media sentiment from Google News RSS."""
    try:
        import feedparser
        
        articles = []
        sentiment_scores = []
        
        # Google News RSS
        url = f"https://news.google.com/rss/search?q={symbol}+stock+earnings&hl=en-US&gl=US&ceid=US:en"
        r = await client.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            feed = feedparser.parse(r.text)
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                score = _simple_sentiment(title)
                sentiment_scores.append(score)
                articles.append({
                    "title": title,
                    "source": entry.get("source", {}).get("title", ""),
                    "published": entry.get("published", ""),
                    "sentiment": score,
                })
        
        avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores), 3) if sentiment_scores else 0
        
        return {
            "articles": articles,
            "avg_sentiment": avg_sentiment,
            "signal": "bullish" if avg_sentiment > 0.1 else "bearish" if avg_sentiment < -0.1 else "neutral",
            "article_count": len(articles),
        }
    except Exception as e:
        logger.debug(f"Social sentiment for {symbol}: {e}")
        return {"articles": [], "signal": "unknown"}


def _simple_sentiment(text: str) -> float:
    """Quick keyword-based sentiment score [-1.0, 1.0]."""
    text_lower = text.lower()
    bullish = ["beat", "surge", "soar", "rally", "upgrade", "buy", "outperform", "strong", "growth",
               "record", "bullish", "positive", "exceed", "profit", "gain", "rise", "jump", "boom",
               "breakthrough", "innovation", "expand", "optimistic", "upside"]
    bearish = ["miss", "plunge", "crash", "downgrade", "sell", "underperform", "weak", "decline",
               "loss", "bearish", "negative", "disappoint", "cut", "drop", "fall", "slump",
               "recession", "layoff", "warning", "risk", "concern", "fear", "worst"]
    
    b_count = sum(1 for w in bullish if w in text_lower)
    s_count = sum(1 for w in bearish if w in text_lower)
    total = b_count + s_count
    if total == 0:
        return 0.0
    return round((b_count - s_count) / total, 3)


# ── 11. Options Market Positioning ───────────────────────────────────────────
async def _get_options_positioning(symbol: str) -> Dict:
    """Options market sentiment: put/call ratio, implied volatility."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        
        expirations = t.options[:3] if t.options else []
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0
        avg_iv = []
        
        for exp in expirations[:2]:
            try:
                chain = t.option_chain(exp)
                calls = chain.calls
                puts = chain.puts
                
                total_call_oi += int(calls["openInterest"].sum()) if "openInterest" in calls else 0
                total_put_oi += int(puts["openInterest"].sum()) if "openInterest" in puts else 0
                total_call_vol += int(calls["volume"].sum()) if "volume" in calls else 0
                total_put_vol += int(puts["volume"].sum()) if "volume" in puts else 0
                
                if "impliedVolatility" in calls:
                    avg_iv.extend(calls["impliedVolatility"].dropna().tolist())
                if "impliedVolatility" in puts:
                    avg_iv.extend(puts["impliedVolatility"].dropna().tolist())
            except Exception:
                continue
        
        pc_ratio_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else 0
        pc_ratio_vol = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else 0
        implied_vol = round(sum(avg_iv) / len(avg_iv) * 100, 2) if avg_iv else 0
        
        return {
            "expirations_analyzed": expirations[:2],
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "pc_ratio_oi": pc_ratio_oi,
            "pc_ratio_volume": pc_ratio_vol,
            "avg_implied_volatility": implied_vol,
            "signal": "bearish" if pc_ratio_oi > 1.2 else "bullish" if pc_ratio_oi < 0.7 else "neutral",
        }
    except Exception as e:
        logger.debug(f"Options positioning for {symbol}: {e}")
        return {"signal": "unknown"}


# ── 12. Macro & Sector Context ───────────────────────────────────────────────
async def _get_macro_context(client: httpx.AsyncClient) -> Dict:
    """VIX, 10Y yield, DXY, sector performance."""
    try:
        import yfinance as yf
        
        macro = {}
        for sym, name in [("^VIX", "vix"), ("^TNX", "10y_yield"), ("DX-Y.NYB", "dxy"), ("^GSPC", "sp500")]:
            try:
                t = yf.Ticker(sym)
                hist = t.history(period="5d")
                if not hist.empty:
                    current = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[0])
                    macro[name] = {
                        "value": round(current, 2),
                        "5d_change_pct": round(((current - prev) / prev) * 100, 2),
                    }
            except Exception:
                pass
        
        return macro
    except Exception as e:
        logger.debug(f"Macro context: {e}")
        return {}


# ── LLM Synthesis ────────────────────────────────────────────────────────────
async def _llm_earnings_synthesis(symbol: str, data: Dict) -> Dict:
    """Send all collected data to LLM for comprehensive earnings analysis."""
    try:
        prompt = f"""You are a senior equity research analyst. Analyze the following pre-earnings data for {symbol} and provide a comprehensive earnings preview.

DATA:
- Financial Performance: Revenue growth {data.get('financials', {}).get('revenue_growth', 'N/A')}, EPS trailing ${data.get('financials', {}).get('eps_trailing', 'N/A')}, Forward PE {data.get('financials', {}).get('forward_pe', 'N/A')}, Profit margins {data.get('financials', {}).get('profit_margins', 'N/A')}
- Insider Activity: {data.get('insider_trading', {}).get('signal', 'N/A')} ({data.get('insider_trading', {}).get('buy_count_90d', 0)} buys, {data.get('insider_trading', {}).get('sell_count_90d', 0)} sells in 90 days)
- Buybacks: Active={data.get('buyback', {}).get('has_active_buyback', False)}, Short interest {data.get('buyback', {}).get('short_pct_float', 0)}% of float
- Analyst Consensus: {data.get('analyst', {}).get('recommendation', 'N/A')}, Target ${data.get('analyst', {}).get('target_mean', 0)} ({data.get('analyst', {}).get('num_analysts', 0)} analysts)
- Options Market: P/C ratio {data.get('options', {}).get('pc_ratio_oi', 'N/A')}, IV {data.get('options', {}).get('avg_implied_volatility', 0)}%
- News Sentiment: {data.get('social_sentiment', {}).get('signal', 'N/A')} (avg score: {data.get('social_sentiment', {}).get('avg_sentiment', 0)})
- Geopolitical Risks: {[r.get('detail', '') for r in data.get('geopolitical', {}).get('risks', [])]}
- Supply Chain: Risks={data.get('supply_chain', {}).get('supply_risks', [])}
- Leadership: {len(data.get('leadership', {}).get('officers', []))} officers, Governance risk={data.get('leadership', {}).get('governance_risk', 'N/A')}
- SEC Filings: {len(data.get('sec_filings', []))} recent filings
- Macro: VIX={data.get('macro', {}).get('vix', {}).get('value', 'N/A')}, 10Y={data.get('macro', {}).get('10y_yield', {}).get('value', 'N/A')}

Respond in this EXACT JSON format (no markdown, no code fences):
{{
  "overall_outlook": "bullish|bearish|neutral",
  "confidence": 75,
  "summary": "2-3 sentence executive summary",
  "bull_case": {{"scenario": "description", "probability": 40, "target_price": 0}},
  "bear_case": {{"scenario": "description", "probability": 30, "target_price": 0}},
  "base_case": {{"scenario": "description", "probability": 30, "target_price": 0}},
  "key_factors": ["factor 1", "factor 2", "factor 3", "factor 4", "factor 5"],
  "risks": ["risk 1", "risk 2", "risk 3"],
  "catalysts": ["catalyst 1", "catalyst 2"],
  "earnings_estimate": {{"eps_estimate": 0.0, "revenue_estimate": "0B", "beat_probability": 50}},
  "recommendation": "buy|hold|sell"
}}"""

        text = await _llm_generate(
            prompt, task="finance", temperature=0.3,
            max_tokens=900, json_mode=True, timeout=LLM_TIMEOUT_S,
        )
        if text:
            parsed = extract_json(text)
            if isinstance(parsed, dict) and parsed.get("overall_outlook") and parsed.get("summary"):
                return parsed
            fb = _heuristic_synthesis(symbol, data, note="AI returned malformed JSON; showing rule-based read.")
            fb["ai_notes"] = text[:1200]
            return fb
    except Exception as e:
        logger.error(f"LLM synthesis for {symbol}: {e}")
        return _heuristic_synthesis(symbol, data, note=f"AI synthesis unavailable ({type(e).__name__}); showing rule-based read.")
    return _heuristic_synthesis(symbol, data, note="AI synthesis returned nothing; showing rule-based read.")


def _heuristic_synthesis(symbol: str, data: Dict, note: str = "") -> Dict:
    """Deterministic fallback so the deep dive never comes back empty."""
    fin = data.get("financials", {}) or {}
    an = data.get("analyst", {}) or {}
    ins = data.get("insider_trading", {}) or {}
    opt = data.get("options", {}) or {}
    score = 0
    factors, risks = [], []
    rg = fin.get("revenue_growth") or 0
    if rg > 0.1:
        score += 1; factors.append(f"Revenue growing {rg*100:.0f}% YoY")
    elif rg < 0:
        score -= 1; risks.append(f"Revenue shrinking {abs(rg)*100:.0f}% YoY")
    rec = (an.get("recommendation") or fin.get("recommendation") or "").lower()
    if rec in ("buy", "strong_buy"):
        score += 1; factors.append(f"Street consensus: {rec.replace('_', ' ')}")
    elif rec in ("sell", "underperform"):
        score -= 1; risks.append("Street consensus leans negative")
    if (ins.get("signal") or "").lower().startswith("bull"):
        score += 1; factors.append("Net insider buying in last 90 days")
    elif (ins.get("signal") or "").lower().startswith("bear"):
        score -= 1; risks.append("Net insider selling in last 90 days")
    pc = opt.get("pc_ratio_oi")
    if isinstance(pc, (int, float)):
        if pc < 0.7:
            score += 1; factors.append(f"Options skew bullish (P/C {pc:.2f})")
        elif pc > 1.2:
            score -= 1; risks.append(f"Options skew defensive (P/C {pc:.2f})")
    iv = opt.get("avg_implied_volatility")
    if isinstance(iv, (int, float)) and iv > 60:
        risks.append(f"Elevated implied volatility ({iv:.0f}%) — big move priced in")
    outlook = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    price = fin.get("price") or 0
    tgt = an.get("target_mean") or fin.get("analyst_target_mean") or price
    return {
        "overall_outlook": outlook,
        "confidence": 45,
        "summary": f"{symbol}: {outlook} setup on a rule-based read of {len(factors)} supporting and {len(risks)} risk signals. {note}".strip(),
        "bull_case": {"scenario": "Beat-and-raise; multiple holds", "probability": 35 + 10 * (outlook == 'bullish'), "target_price": round(tgt * 1.08, 2) if tgt else 0},
        "bear_case": {"scenario": "Guide-down or margin miss", "probability": 25 + 10 * (outlook == 'bearish'), "target_price": round((price or tgt) * 0.9, 2) if (price or tgt) else 0},
        "base_case": {"scenario": "In-line print, muted reaction", "probability": 30, "target_price": round(tgt, 2) if tgt else 0},
        "key_factors": factors or ["Insufficient data for factor scoring"],
        "risks": risks or ["No acute risk flags in collected data"],
        "catalysts": ["Earnings release", "Forward guidance"],
        "earnings_estimate": {"eps_estimate": fin.get("eps_forward") or 0, "revenue_estimate": "n/a", "beat_probability": 50 + 5 * score},
        "recommendation": "buy" if outlook == "bullish" else "sell" if outlook == "bearish" else "hold",
        "fallback": True,
    }


# ── Upcoming Earnings Calendar ───────────────────────────────────────────────
EARNINGS_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "JPM", "BAC", "GS", "MS", "WFC", "C",
    "JNJ", "UNH", "PFE", "ABT", "MRK", "LLY",
    "XOM", "CVX", "COP",
    "DIS", "NFLX", "COST", "WMT", "TGT", "HD",
    "CRM", "ORCL", "ADBE", "INTC", "AVGO", "QCOM", "MU", "ARM", "PLTR", "SMCI",
    "V", "MA", "PYPL",
    "BA", "LMT", "RTX",
    "PG", "KO", "PEP",
    "NKE", "SBUX", "MCD",
    "UBER", "ABNB", "SHOP", "SNOW", "CRWD", "PANW",
]


def _extract_next_earnings_date(t, now: datetime) -> Optional[datetime]:
    """
    Resolve the NEXT earnings date reliably.

    yfinance's info['earningsTimestamp'] is frequently STALE (returns the
    *previous* report). The `calendar` dict carries the forward-looking
    'Earnings Date' which is the authoritative source; we fall back to
    get_earnings_dates() then the (stale) timestamp only as a last resort.
    """
    import datetime as _dt

    # 1. calendar['Earnings Date'] — most reliable forward date
    try:
        cal = t.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                dates = ed if isinstance(ed, (list, tuple)) else [ed]
                for d in dates:
                    dd = datetime(d.year, d.month, d.day) if isinstance(d, _dt.date) and not isinstance(d, datetime) else d
                    if dd and dd >= now - timedelta(days=1):
                        return dd
        elif cal is not None and hasattr(cal, "columns"):
            for col in cal.columns:
                dd = datetime(col.year, col.month, col.day) if hasattr(col, "year") else None
                if dd and dd >= now - timedelta(days=1):
                    return dd
    except Exception:
        pass

    # 2. get_earnings_dates() — pick the soonest future row
    try:
        ed = t.get_earnings_dates(limit=8)
        if ed is not None and not ed.empty:
            for idx in ed.index:
                dd = idx.to_pydatetime().replace(tzinfo=None) if hasattr(idx, "to_pydatetime") else None
                if dd and dd >= now - timedelta(days=1):
                    return dd
    except Exception:
        pass

    # 3. last resort: info timestamp (may be stale)
    try:
        ts = (t.info or {}).get("earningsTimestamp")
        if ts:
            dd = datetime.fromtimestamp(ts)
            if dd >= now - timedelta(days=1):
                return dd
    except Exception:
        pass

    return None


def _fetch_one_upcoming(sym: str, now: datetime, cutoff: datetime) -> Optional[Dict]:
    """Blocking single-symbol fetch (run in a thread)."""
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        earnings_date = _extract_next_earnings_date(t, now)
        if not earnings_date or not (now - timedelta(days=1) <= earnings_date <= cutoff):
            return None
        info = t.info or {}
        return {
            "symbol": sym,
            "name": info.get("longName", sym),
            "earnings_date": earnings_date.strftime("%Y-%m-%d"),
            "earnings_time": "BMO" if earnings_date.hour and earnings_date.hour < 12 else "AMC",
            "market_cap": info.get("marketCap", 0),
            "sector": info.get("sector", ""),
            "price": info.get("currentPrice", info.get("regularMarketPrice", 0)),
            "pe_ratio": info.get("trailingPE", 0),
            "eps_estimate": info.get("forwardEps", 0),
            "recommendation": info.get("recommendationKey", ""),
        }
    except Exception:
        return None


async def get_upcoming_earnings(days: int = 30, universe: Optional[List[str]] = None) -> List[Dict]:
    """
    Get upcoming earnings for major stocks in the next N days.

    Uses calendar-based date resolution (reliable) and scans the universe in
    parallel threads. Results cached for 1h (earnings dates rarely change).
    """
    syms = universe or EARNINGS_UNIVERSE
    cache_key = f"upcoming:{days}:{len(syms)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    now = datetime.now()
    cutoff = now + timedelta(days=days)

    loop = asyncio.get_event_loop()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=10) as pool:
        tasks = [
            loop.run_in_executor(pool, _fetch_one_upcoming, sym, now, cutoff)
            for sym in syms
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    upcoming = [r for r in results if isinstance(r, dict) and r]
    upcoming.sort(key=lambda x: x["earnings_date"])

    # Cache for 1h instead of 5min — earnings dates are stable
    _CACHE[cache_key] = (upcoming, time.time() + 3600 - CACHE_TTL)
    return upcoming


COLLECT_TIMEOUT_S = 45
LLM_TIMEOUT_S = 75


def _json_safe(obj):
    """Replace NaN/Inf (yfinance loves them) with None, recursively."""
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _in_thread(coro_fn, *args):
    """Run a coroutine whose body is CPU/IO-blocking (yfinance) on a worker thread."""
    return asyncio.to_thread(lambda: asyncio.run(coro_fn(*args)))


# ── Main Entry Point ─────────────────────────────────────────────────────────
async def get_earnings_intelligence(symbol: str) -> Dict[str, Any]:
    """
    Full earnings intelligence report for a symbol.
    Fetches all 12 dimensions in parallel, then synthesizes with LLM.
    """
    cache_key = f"earnings_intel_{symbol.upper()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    symbol = symbol.upper()

    async def _guard(aw, default, label):
        try:
            return await asyncio.wait_for(aw, timeout=COLLECT_TIMEOUT_S)
        except Exception as e:
            logger.warning(f"earnings-intel {symbol} {label}: {type(e).__name__}: {e}")
            return default

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # yfinance collectors are blocking → run each in its own worker thread so the
        # event loop (and the rest of the API) stays responsive.
        results = await asyncio.gather(
            _guard(_in_thread(_get_financials, symbol), {}, "financials"),            # 1
            _guard(_get_sec_filings(symbol, client), [], "sec"),                      # 2
            _guard(_get_insider_trading(symbol, client), {}, "insider"),              # 3
            _guard(_in_thread(_get_buyback_info, symbol), {}, "buyback"),             # 4
            _guard(_in_thread(_get_leadership, symbol), {}, "leadership"),            # 5
            _guard(_in_thread(_get_competitors, symbol), [], "competitors"),          # 6
            _guard(_in_thread(_get_supply_chain, symbol), {}, "supply"),              # 7
            _guard(_get_geopolitical_exposure(symbol, client), {}, "geo"),            # 8
            _guard(_in_thread(_get_analyst_consensus, symbol), {}, "analyst"),        # 9
            _guard(_get_social_sentiment(symbol, client), {}, "sentiment"),           # 10
            _guard(_in_thread(_get_options_positioning, symbol), {}, "options"),      # 11
            _guard(_get_macro_context(client), {}, "macro"),                          # 12
            return_exceptions=True,
        )
    
    data = {
        "financials": results[0] if not isinstance(results[0], Exception) else {},
        "sec_filings": results[1] if not isinstance(results[1], Exception) else [],
        "insider_trading": results[2] if not isinstance(results[2], Exception) else {},
        "buyback": results[3] if not isinstance(results[3], Exception) else {},
        "leadership": results[4] if not isinstance(results[4], Exception) else {},
        "competitors": results[5] if not isinstance(results[5], Exception) else [],
        "supply_chain": results[6] if not isinstance(results[6], Exception) else {},
        "geopolitical": results[7] if not isinstance(results[7], Exception) else {},
        "analyst": results[8] if not isinstance(results[8], Exception) else {},
        "social_sentiment": results[9] if not isinstance(results[9], Exception) else {},
        "options": results[10] if not isinstance(results[10], Exception) else {},
        "macro": results[11] if not isinstance(results[11], Exception) else {},
    }
    
    # LLM synthesis
    llm_analysis = await _llm_earnings_synthesis(symbol, data)
    
    result = _json_safe({
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_analysis": llm_analysis,
        **data,
    })
    
    _cache_set(cache_key, result)
    return result
