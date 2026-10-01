"""
Market Region Service — US + India dual-market support.

Deterministic symbol resolution, market hours, indices and currency formatting.
US symbols pass through unchanged; Indian symbols get .NS (NSE) primary with
.BO (BSE) fallback. No AI involved.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

VALID_REGIONS = ("US", "IN")


@dataclass(frozen=True)
class RegionConfig:
    code: str
    name: str
    currency: str
    currency_symbol: str
    timezone: str
    open_time: time
    close_time: time
    indices: Dict[str, str]           # yfinance symbol -> display name
    default_universe: List[str] = field(default_factory=list)


US = RegionConfig(
    code="US",
    name="United States",
    currency="USD",
    currency_symbol="$",
    timezone="America/New_York",
    open_time=time(9, 30),
    close_time=time(16, 0),
    indices={
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq Composite",
        "^DJI": "Dow Jones",
        "^RUT": "Russell 2000",
        "^VIX": "VIX",
    },
    default_universe=[
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
        "BRK-B", "JPM", "V", "UNH", "XOM", "LLY", "MA", "HD", "COST",
        "ORCL", "AMD", "NFLX",
    ],
)

# NIFTY 50 core constituents (NSE symbols, no suffix — resolver adds .NS)
IN = RegionConfig(
    code="IN",
    name="India",
    currency="INR",
    currency_symbol="₹",
    timezone="Asia/Kolkata",
    open_time=time(9, 15),
    close_time=time(15, 30),
    indices={
        "^NSEI": "NIFTY 50",
        "^BSESN": "SENSEX",
        "^NSEBANK": "NIFTY Bank",
        "^CNXIT": "NIFTY IT",
    },
    default_universe=[
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
        "BHARTIARTL", "SBIN", "ITC", "KOTAKBANK", "LT", "BAJFINANCE",
        "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
        "ULTRACEMCO", "WIPRO", "NTPC", "TATAMOTORS", "TATASTEEL",
        "POWERGRID", "M&M", "HCLTECH",
    ],
)

REGIONS: Dict[str, RegionConfig] = {"US": US, "IN": IN}

# Known Indian tickers for auto-detection when clients don't pass region
_IN_SYMBOLS = set(IN.default_universe) | {
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "BAJAJFINSV", "BAJAJ-AUTO",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "INDUSINDBK", "JSWSTEEL", "NESTLEIND", "ONGC", "SBILIFE", "SHRIRAMFIN",
    "TATACONSUM", "TECHM", "UPL", "LTIM", "ZOMATO", "PAYTM", "IRCTC", "DMART",
}


def get_region(code: Optional[str]) -> RegionConfig:
    """Return the region config; defaults to US for unknown/missing codes."""
    if not code:
        return US
    return REGIONS.get(code.upper(), US)


def detect_region(symbol: str) -> str:
    """Best-effort region detection from a raw symbol."""
    s = symbol.upper().strip()
    if s.endswith(".NS") or s.endswith(".BO") or s in ("^NSEI", "^BSESN", "^NSEBANK", "^CNXIT"):
        return "IN"
    if s in _IN_SYMBOLS:
        return "IN"
    return "US"


def resolve_symbol(symbol: str, region: Optional[str] = None) -> str:
    """
    Resolve a user-facing symbol to a yfinance symbol.
    - US: passthrough (AAPL -> AAPL)
    - IN: add .NS unless already suffixed (RELIANCE -> RELIANCE.NS)
    Indices (^...) always pass through.
    """
    s = symbol.upper().strip()
    if s.startswith("^") or "." in s or "=" in s:
        return s
    r = (region or detect_region(s)).upper()
    if r == "IN":
        return f"{s}.NS"
    return s


def bse_fallback_symbol(symbol: str) -> Optional[str]:
    """Given RELIANCE or RELIANCE.NS, return RELIANCE.BO for BSE fallback."""
    s = symbol.upper().strip()
    if s.startswith("^"):
        return None
    base = s[:-3] if s.endswith(".NS") or s.endswith(".BO") else s
    return f"{base}.BO"


def display_symbol(symbol: str) -> str:
    """Strip exchange suffix for display (RELIANCE.NS -> RELIANCE)."""
    s = symbol.upper().strip()
    if s.endswith(".NS") or s.endswith(".BO"):
        return s[:-3]
    return s


def market_status(region_code: str = "US") -> Dict:
    """Deterministic market open/closed status with local time."""
    region = get_region(region_code)
    now = datetime.now(ZoneInfo(region.timezone))
    is_weekday = now.weekday() < 5
    now_t = now.time()
    is_open = is_weekday and region.open_time <= now_t <= region.close_time
    if is_open:
        status = "open"
    elif is_weekday and now_t < region.open_time:
        status = "pre_market"
    else:
        status = "closed"
    return {
        "region": region.code,
        "status": status,
        "local_time": now.strftime("%Y-%m-%d %H:%M %Z"),
        "open_time": region.open_time.strftime("%H:%M"),
        "close_time": region.close_time.strftime("%H:%M"),
        "currency": region.currency,
        "currency_symbol": region.currency_symbol,
    }


def format_price(value: float, region_code: str = "US") -> str:
    """Format a price in region currency. Indian format uses lakh/crore grouping."""
    region = get_region(region_code)
    if region.code == "IN":
        # Indian digit grouping: 12,34,567.89
        s = f"{value:,.2f}"
        parts = s.split(".")
        intpart = parts[0].replace(",", "")
        if len(intpart) > 3:
            last3 = intpart[-3:]
            rest = intpart[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            intpart = ",".join(groups + [last3])
        return f"{region.currency_symbol}{intpart}.{parts[1]}"
    return f"{region.currency_symbol}{value:,.2f}"
