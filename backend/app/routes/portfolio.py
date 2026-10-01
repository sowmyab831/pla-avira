"""Stock portfolio tracking and sentiment analysis routes."""
import logging
import time
from typing import Optional, List
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.portfolio import (
    Stock, PortfolioHolding, Portfolio, StockNews,
    SocialSentiment, StockAlert, StockRecommendation
)
from app.services.stock_intelligence import get_stock_intelligence
from app.services import market_region, nse_client
from app.config import settings
from app.database import get_db, PortfolioHoldingDB, StockAlertDB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Legacy in-memory storage (fallback)
portfolios_store: dict = {}
holdings_store: List[PortfolioHolding] = []
alerts_store: List[StockAlert] = []


@router.get("/market/status")
async def get_market_status(region: str = "US"):
    """Market open/closed status for a region (US or IN). Deterministic."""
    return {"success": True, **market_region.market_status(region)}


@router.get("/market/indices")
async def get_market_indices(region: str = "US"):
    """Major indices for a region. IN uses NSE real-time fallback, then yfinance."""
    cfg = market_region.get_region(region)
    results = []
    if cfg.code == "IN":
        nse = await nse_client.get_index_quotes()
        if nse:
            return {"success": True, "region": cfg.code, "currency": cfg.currency, "indices": nse}
    intelligence = get_stock_intelligence()
    for sym, name in cfg.indices.items():
        try:
            q = await intelligence.get_real_time_quote(sym)
            results.append({
                "name": name,
                "symbol": sym,
                "last": q.get("price"),
                "change": q.get("change"),
                "change_percent": q.get("change_percent"),
                "source": "yfinance",
            })
        except Exception as e:
            logger.warning(f"Index quote failed for {sym}: {e}")
    return {"success": True, "region": cfg.code, "currency": cfg.currency, "indices": results}


@router.get("/market/movers")
async def get_market_movers(region: str = "US"):
    """Top gainers/losers. IN uses NSE; US computed from default universe."""
    cfg = market_region.get_region(region)
    if cfg.code == "IN":
        movers = await nse_client.get_top_movers()
        if movers:
            return {"success": True, "region": "IN", "currency": cfg.currency, **movers}
    # Fallback: compute from universe via yfinance quotes
    intelligence = get_stock_intelligence()
    rows = []
    for sym in cfg.default_universe[:15]:
        try:
            q = await intelligence.get_real_time_quote(market_region.resolve_symbol(sym, cfg.code))
            rows.append({
                "symbol": sym,
                "last_price": q.get("price"),
                "change_percent": q.get("change_percent"),
                "source": "yfinance",
            })
        except Exception:
            continue
    rows.sort(key=lambda r: r.get("change_percent") or 0, reverse=True)
    return {"success": True, "region": cfg.code, "currency": cfg.currency,
            "gainers": rows[:5], "losers": rows[-5:][::-1]}


@router.get("/market/universe")
async def get_market_universe(region: str = "US"):
    """Default stock universe for a region (used by scanners and watchlists)."""
    cfg = market_region.get_region(region)
    return {"success": True, "region": cfg.code, "currency": cfg.currency,
            "symbols": cfg.default_universe}


@router.get("/stocks/{symbol}")
async def get_stock_info(symbol: str, region: Optional[str] = None):
    """Get real-time stock information. Supports US and Indian (region=IN) symbols."""
    resolved = market_region.resolve_symbol(symbol, region)
    region_code = region or market_region.detect_region(symbol)
    intelligence = get_stock_intelligence()
    quote = await intelligence.get_real_time_quote(resolved)
    # BSE fallback if NSE symbol returned nothing
    if region_code == "IN" and not quote.get("price"):
        bse = market_region.bse_fallback_symbol(resolved)
        if bse:
            quote = await intelligence.get_real_time_quote(bse)
    return {
        "success": True,
        "symbol": market_region.display_symbol(symbol),
        "region": region_code,
        "currency": market_region.get_region(region_code).currency,
        "stock": {
            "symbol": market_region.display_symbol(symbol),
            "name": f"{market_region.display_symbol(symbol)}",
            "current_price": quote["price"],
            "previous_close": quote["previous_close"],
            "day_change": quote["change"],
            "day_change_percent": quote["change_percent"],
            "volume": quote["volume"],
            "market_cap": quote["market_cap"],
            "high": quote["high"],
            "low": quote["low"],
            "last_updated": quote["timestamp"]
        }
    }


@router.get("/stocks/{symbol}/quote")
async def get_stock_quote(symbol: str, region: Optional[str] = None):
    """Get real-time stock quote (region-aware)."""
    resolved = market_region.resolve_symbol(symbol, region)
    region_code = region or market_region.detect_region(symbol)
    intelligence = get_stock_intelligence()
    quote = await intelligence.get_real_time_quote(resolved)
    if region_code == "IN" and not quote.get("price"):
        nse_q = await nse_client.get_quote(symbol)
        if nse_q:
            quote = {"price": nse_q["last_price"], "change": nse_q["change"],
                     "change_percent": nse_q["change_percent"], "high": nse_q["day_high"],
                     "low": nse_q["day_low"], "source": "nse"}
    return {
        "success": True,
        "symbol": market_region.display_symbol(symbol),
        "region": region_code,
        "currency": market_region.get_region(region_code).currency,
        "quote": quote
    }


@router.get("/stocks/{symbol}/history")
async def get_stock_history(symbol: str, period: str = "1M", region: Optional[str] = None):
    """Get historical stock data for charting (region-aware)."""
    intelligence = get_stock_intelligence()
    history = await intelligence.get_historical_prices(
        market_region.resolve_symbol(symbol, region), period)

    return {
        "success": True,
        "symbol": symbol,
        "period": period,
        "data": history.get("prices") or history.get("data", [])
    }


@router.get("/stocks/{symbol}/chart")
async def get_stock_chart(symbol: str, period: str = "1M", region: Optional[str] = None):
    """Alias for /stocks/{symbol}/history — used by the frontend chart views
    and the `pla chart` CLI."""
    return await get_stock_history(symbol, period, region)


@router.get("/stocks/{symbol}/deep-metrics")
async def get_deep_metrics(symbol: str, region: Optional[str] = None):
    """
    Deterministic deep-metrics scorecard (500-dimension catalog groups):
    growth, profitability, balance sheet, valuation, earnings/ownership,
    price structure, and options positioning. No AI involved.
    """
    from app.services.fundamental_metrics import compute_fundamental_metrics
    from app.services.options_metrics import compute_options_metrics
    from app.services.price_metrics import compute_price_metrics
    import asyncio

    resolved = market_region.resolve_symbol(symbol, region)
    region_code = region or market_region.detect_region(symbol)
    benchmark = "^NSEI" if region_code == "IN" else "^GSPC"

    loop = asyncio.get_event_loop()
    fundamentals, options, price = await asyncio.gather(
        loop.run_in_executor(None, compute_fundamental_metrics, resolved),
        loop.run_in_executor(None, compute_options_metrics, resolved),
        loop.run_in_executor(None, lambda: compute_price_metrics(resolved, benchmark)),
    )
    return {
        "success": True,
        "symbol": market_region.display_symbol(symbol),
        "region": region_code,
        "currency": market_region.get_region(region_code).currency,
        "fundamentals": fundamentals,
        "price_structure": price,
        "options": options,
    }


@router.get("/market/breadth")
async def get_market_breadth(region: str = "US"):
    """Universe breadth (% above 200DMA, A/D) for the region's default universe."""
    from app.services.price_metrics import compute_breadth
    import asyncio

    cfg = market_region.get_region(region)
    symbols = [market_region.resolve_symbol(s, cfg.code) for s in cfg.default_universe]
    loop = asyncio.get_event_loop()
    breadth = await loop.run_in_executor(None, compute_breadth, symbols)
    return {"success": True, "region": cfg.code, **breadth}


@router.get("/stocks/{symbol}/sentiment")
async def get_stock_sentiment(symbol: str):
    """Get news sentiment for a stock."""
    intelligence = get_stock_intelligence()
    news = await intelligence.get_stock_news(symbol, limit=20)
    
    # Calculate sentiment from news
    positive = sum(1 for n in news if n.get("sentiment") == "positive")
    negative = sum(1 for n in news if n.get("sentiment") == "negative")
    total = len(news) or 1
    
    return {
        "success": True,
        "symbol": symbol,
        "sentiment": {
            "overall_sentiment": (positive - negative) / total,
            "news_count": total,
            "positive_news": positive,
            "negative_news": negative,
            "sentiment_trend": "bullish" if positive > negative else "bearish",
            "bullish_percent": (positive / total) * 100,
            "bearish_percent": (negative / total) * 100
        }
    }


@router.get("/stocks/{symbol}/news")
async def get_stock_news(symbol: str, limit: int = 10):
    """Get latest news for a stock."""
    intelligence = get_stock_intelligence()
    news = await intelligence.get_stock_news(symbol, limit=limit)
    
    return {
        "success": True,
        "symbol": symbol,
        "count": len(news),
        "news": news
    }


@router.post("/")
async def create_portfolio(user_id: str = "default"):
    """Create portfolio for user."""
    portfolio = Portfolio(
        portfolio_id=f"port_{user_id}_{int(time.time())}",
        user_id=user_id,
        total_value=0.0,
        total_cost=0.0,
        total_gain_loss=0.0,
        total_gain_loss_percent=0.0,
        holdings=[],
        last_updated=datetime.now().isoformat()
    )
    portfolios_store[user_id] = portfolio
    return {"success": True, "portfolio": portfolio}


@router.get("/")
async def get_portfolio(user_id: str = "default"):
    """Get user's portfolio."""
    if user_id not in portfolios_store:
        return {"success": False, "message": "Portfolio not found"}
    
    return {"success": True, "portfolio": portfolios_store[user_id]}


@router.post("/holdings")
async def add_holding(holding: PortfolioHolding, db: Session = Depends(get_db)):
    """Add stock holding to portfolio with database persistence. Averages cost if symbol already exists."""
    
    # Generate holding_id if not provided
    if not holding.holding_id:
        holding.holding_id = f"hold_{holding.user_id}_{holding.symbol}_{int(time.time())}"
    
    # Check if holding already exists in memory
    existing_holding = None
    for idx, h in enumerate(holdings_store):
        if h.user_id == holding.user_id and h.symbol == holding.symbol:
            existing_holding = (idx, h)
            break
    
    if existing_holding:
        # Average the cost and sum the shares
        idx, existing = existing_holding
        total_shares = existing.shares + holding.shares
        total_cost = (existing.average_cost * existing.shares) + (holding.average_cost * holding.shares)
        new_average_cost = total_cost / total_shares
        
        # Update existing holding
        holdings_store[idx].shares = total_shares
        holdings_store[idx].average_cost = new_average_cost
        holdings_store[idx].purchase_date = holding.purchase_date  # Use latest date
        
        logger.info(f"Updated {holding.symbol}: {total_shares} shares @ ${new_average_cost:.2f} avg")
        holding = holdings_store[idx]
    else:
        # Add new holding
        try:
            # Try to save to database
            if db is not None:
                db_holding = PortfolioHoldingDB(
                    user_id=holding.user_id,
                    symbol=holding.symbol,
                    shares=holding.shares,
                    average_cost=holding.average_cost,
                    purchase_date=holding.purchase_date
                )
                db.add(db_holding)
                db.commit()
                db.refresh(db_holding)
                logger.info(f"Saved holding {holding.symbol} to database")
            else:
                # Fallback to in-memory
                holdings_store.append(holding)
                logger.warning("Database not available, using in-memory storage")
        except Exception as e:
            logger.error(f"Error saving holding: {e}")
            # Fallback to in-memory
            holdings_store.append(holding)
    
    # Get enriched holdings with real-time data
    intelligence = get_stock_intelligence()
    try:
        quote = await intelligence.get_real_time_quote(holding.symbol)
        enriched_holding = {
            **holding.dict(),
            "current_price": quote["price"],
            "current_value": quote["price"] * holding.shares,
            "gain_loss": (quote["price"] - holding.average_cost) * holding.shares,
            "gain_loss_percent": ((quote["price"] - holding.average_cost) / holding.average_cost) * 100,
            "change_percent": quote["change_percent"]
        }
    except Exception as e:
        logger.error(f"Error enriching holding: {e}")
        enriched_holding = holding.dict()
    
    return {
        "success": True, 
        "message": "Holding added successfully", 
        "holding": enriched_holding
    }


@router.get("/holdings")
async def get_holdings(user_id: str = "default"):
    """Get all holdings for user with real-time prices."""
    user_holdings = [h for h in holdings_store if h.user_id == user_id]
    intelligence = get_stock_intelligence()
    
    # Enrich holdings with real-time data
    enriched_holdings = []
    for holding in user_holdings:
        try:
            quote = await intelligence.get_real_time_quote(holding.symbol)
            holding_dict = holding.dict()
            holding_dict["current_price"] = quote["price"]
            holding_dict["current_value"] = quote["price"] * holding.shares
            holding_dict["change_percent"] = quote["change_percent"]
            
            # Calculate gain/loss
            if holding.average_cost > 0:
                holding_dict["gain_loss"] = (quote["price"] - holding.average_cost) * holding.shares
                holding_dict["gain_loss_percent"] = ((quote["price"] - holding.average_cost) / holding.average_cost) * 100
            else:
                holding_dict["gain_loss"] = 0
                holding_dict["gain_loss_percent"] = 0
            
            enriched_holdings.append(holding_dict)
            logger.info(f"Enriched {holding.symbol}: ${quote['price']:.2f}")
        except Exception as e:
            logger.error(f"Error enriching holding {holding.symbol}: {e}")
            # Return with zeros if enrichment fails
            holding_dict = holding.dict()
            holding_dict["current_price"] = 0
            holding_dict["current_value"] = 0
            holding_dict["gain_loss"] = 0
            holding_dict["gain_loss_percent"] = 0
            holding_dict["change_percent"] = 0
            enriched_holdings.append(holding_dict)
    
    return {"success": True, "count": len(enriched_holdings), "holdings": enriched_holdings}


@router.post("/alerts")
async def create_stock_alert(alert: StockAlert):
    """Create stock alert."""
    alerts_store.append(alert)
    
    return {"success": True, "message": "Alert created", "alert": alert}


@router.get("/alerts")
async def get_alerts(user_id: str = "default", active_only: bool = True):
    """Get stock alerts for user."""
    user_alerts = [a for a in alerts_store if a.user_id == user_id]
    
    if active_only:
        user_alerts = [a for a in user_alerts if a.is_active]
    
    return {"success": True, "count": len(user_alerts), "alerts": user_alerts}


@router.delete("/holdings/{symbol}")
async def remove_holding(symbol: str, user_id: str = "default", db: Session = Depends(get_db)):
    """Remove a stock holding completely from portfolio."""
    global holdings_store
    
    # Find and remove from in-memory store
    original_count = len(holdings_store)
    holdings_store = [h for h in holdings_store if not (h.user_id == user_id and h.symbol.upper() == symbol.upper())]
    
    removed = original_count > len(holdings_store)
    
    if removed:
        logger.info(f"Removed {symbol} from {user_id}'s portfolio")
        return {"success": True, "message": f"Removed {symbol} from portfolio"}
    else:
        return {"success": False, "message": f"Holding {symbol} not found in portfolio"}


class SellRequest(BaseModel):
    shares: float
    sell_price: Optional[float] = None


@router.post("/holdings/{symbol}/sell")
async def sell_holding(symbol: str, request: SellRequest, user_id: str = "default"):
    """Sell shares of a stock holding. Records the transaction and updates shares."""
    intelligence = get_stock_intelligence()
    
    # Find the holding
    holding_idx = None
    for idx, h in enumerate(holdings_store):
        if h.user_id == user_id and h.symbol.upper() == symbol.upper():
            holding_idx = idx
            break
    
    if holding_idx is None:
        raise HTTPException(status_code=404, detail=f"Holding {symbol} not found")
    
    holding = holdings_store[holding_idx]
    
    if request.shares > holding.shares:
        raise HTTPException(status_code=400, detail=f"Cannot sell {request.shares} shares, only {holding.shares} available")
    
    # Get current price if not provided
    if request.sell_price:
        sell_price = request.sell_price
    else:
        quote = await intelligence.get_real_time_quote(symbol)
        sell_price = quote["price"]
    
    # Calculate realized gain/loss
    proceeds = sell_price * request.shares
    cost_basis = holding.average_cost * request.shares
    realized_gain = proceeds - cost_basis
    realized_gain_percent = ((sell_price - holding.average_cost) / holding.average_cost) * 100
    
    # Update or remove holding
    remaining_shares = holding.shares - request.shares
    if remaining_shares <= 0:
        # Remove completely
        holdings_store.pop(holding_idx)
        message = f"Sold all {request.shares} shares of {symbol}"
    else:
        # Update shares (average cost remains same)
        holdings_store[holding_idx].shares = remaining_shares
        message = f"Sold {request.shares} shares of {symbol}, {remaining_shares} remaining"
    
    logger.info(f"{message} - Realized gain: ${realized_gain:.2f}")
    
    return {
        "success": True,
        "message": message,
        "transaction": {
            "symbol": symbol,
            "shares_sold": request.shares,
            "sell_price": sell_price,
            "proceeds": proceeds,
            "cost_basis": cost_basis,
            "realized_gain": realized_gain,
            "realized_gain_percent": realized_gain_percent,
            "remaining_shares": remaining_shares,
            "transaction_date": datetime.now().isoformat()
        }
    }


@router.get("/stats")
async def get_portfolio_stats(user_id: str = "default"):
    """Get portfolio statistics."""
    return {
        "success": True,
        "total_holdings": len([h for h in holdings_store if h.user_id == user_id]),
        "active_alerts": len([a for a in alerts_store if a.user_id == user_id and a.is_active]),
        "portfolio_value": 0.0
    }


@router.post("/stocks/{symbol}/analyze")
async def analyze_stock(symbol: str, user_id: str = "default"):
    """Get AI-powered stock analysis with buy/sell recommendations."""
    intelligence = get_stock_intelligence()
    
    # Get real-time data
    quote = await intelligence.get_real_time_quote(symbol)
    news = await intelligence.get_stock_news(symbol, limit=10)
    
    # Get LLM analysis
    analysis = await intelligence.analyze_stock_with_llm(
        symbol, quote, news, settings.ollama_host, settings.ollama_model
    )
    
    return {
        "success": True,
        "symbol": symbol,
        "quote": quote,
        "analysis": analysis,
        "news_count": len(news),
        "top_news": news[:3]
    }


@router.get("/daily-picks")
async def get_daily_stock_picks():
    """Get AI-powered daily stock recommendations."""
    intelligence = get_stock_intelligence()
    picks = await intelligence.get_daily_picks(settings.ollama_host, settings.ollama_model)
    
    return {
        "success": True,
        "picks": picks
    }


@router.get("/watchlist/analyze")
async def analyze_watchlist(symbols: str):
    """Analyze multiple stocks in watchlist."""
    intelligence = get_stock_intelligence()
    symbol_list = symbols.split(",")[:10]  # Limit to 10 stocks
    
    results = []
    for symbol in symbol_list:
        try:
            quote = await intelligence.get_real_time_quote(symbol.strip())
            news = await intelligence.get_stock_news(symbol.strip(), limit=5)
            analysis = await intelligence.analyze_stock_with_llm(
                symbol.strip(), quote, news, settings.ollama_host, settings.ollama_model
            )
            
            results.append({
                "symbol": symbol.strip(),
                "price": quote["price"],
                "change_percent": quote["change_percent"],
                "rating": analysis["rating"],
                "confidence": analysis["confidence"],
                "summary": analysis["analysis"][:150]
            })
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
    
    # Sort by rating and confidence
    results.sort(key=lambda x: (x["rating"] in ["buy", "strong_buy"], x["confidence"]), reverse=True)
    
    return {
        "success": True,
        "count": len(results),
        "watchlist": results,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/stocks/{symbol}/historical")
async def get_historical_prices(symbol: str, period: str = "1m", interval: str = "1d"):
    """
    Get historical price data for charts.
    
    Periods: 1d, 1w, 1m, 3m, 1y, 5y
    Intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    """
    from app.services.stock_intelligence import StockIntelligence
    
    intelligence = StockIntelligence()
    data = await intelligence.get_historical_prices(symbol, period, interval)
    
    return data


@router.get("/stocks/{symbol}/intraday-targets")
async def get_intraday_targets(symbol: str):
    """
    Real-time intraday analysis for options traders.

    Returns:
    - Live price (yfinance, no cache)
    - Classic / Woodie / Camarilla pivot points
    - ATR-based buy/sell/stop targets
    - Expected daily move range
    - Algorithmically detected chart patterns
    """
    import asyncio
    from app.services.intraday_analysis import get_intraday_analysis

    result = await asyncio.to_thread(get_intraday_analysis, symbol.upper())
    return result


@router.get("/stocks/{symbol}/options")
async def get_options_analysis(symbol: str):
    """
    Get comprehensive options trading analysis with:
    - Options strategies (calls, puts, spreads)
    - Greeks (Delta, Gamma, Theta, Vega)
    - Insider trading tracking
    - Institutional holdings
    - Earnings calendar
    - Entry/exit recommendations
    - Stock vs Options comparison
    """
    from app.services.options_trading import get_options_service
    from app.services.advanced_stock_analyzer import get_advanced_analyzer
    
    # Get stock analysis first
    analyzer = get_advanced_analyzer()
    stock_analysis = await analyzer.get_comprehensive_analysis(
        symbol, settings.ollama_host, settings.ollama_model
    )
    
    # Get options analysis
    options_service = get_options_service()
    options_analysis = await options_service.get_comprehensive_options_analysis(
        symbol,
        stock_analysis.get("price_data", {}).get("current_price", 0),
        stock_analysis.get("technical_analysis", {}),
        settings.ollama_host,
        settings.ollama_model
    )
    
    # Backward-compatible summary with real Black-Scholes Greeks
    from app.utils.black_scholes import BlackScholesCalculator
    chain = options_analysis.get("options_chain", {}) or {}
    current_price = stock_analysis.get("price_data", {}).get("current_price", 0) or 0
    atm_strike = chain.get("atm_strike") or (round(current_price / 5) * 5 if current_price else 0)
    iv_rank = chain.get("implied_volatility_rank", 50)
    strategies = []
    if current_price and atm_strike:
        bs = BlackScholesCalculator()
        strategy_specs = [
            ("covered_call", "call", atm_strike * 1.05, "low"),
            ("cash_secured_put", "put", atm_strike * 0.95, "low"),
            ("long_call", "call", atm_strike, "medium"),
        ]
        for name, opt_type, strike, risk in strategy_specs:
            greeks = bs.calculate_greeks(
                S=current_price, K=strike, T=30 / 365, r=0.045,
                sigma=0.30, option_type=opt_type,
            )
            strategies.append({
                "type": name,
                "name": name.replace("_", " ").title(),
                "description": f"{'Sell' if name != 'long_call' else 'Buy'} {opt_type} option at ${strike:.2f} strike",
                "premium_estimate": greeks["price"],
                "risk_level": risk,
                "time_horizon": "short_term",
                "greeks": {k: greeks[k] for k in ("delta", "gamma", "theta", "vega", "rho")},
            })

    return {
        "success": True,
        "symbol": symbol,
        "stock_analysis": stock_analysis,
        "options_analysis": options_analysis,
        "options": {
            "symbol": symbol,
            "current_price": current_price,
            "strategies": strategies,
            "recommended_strategy": options_analysis.get("recommended_strategies", {}).get("options_strategies", {}).get("primary_strategy", "none"),
            "iv_rank": iv_rank,
            "timestamp": datetime.now().isoformat(),
        },
        "combined_recommendation": {
            "stock_rating": stock_analysis.get("ai_recommendation", {}).get("rating", "hold"),
            "options_strategy": options_analysis.get("recommended_strategies", {}).get("options_strategies", {}).get("primary_strategy", "none"),
            "best_approach": "See detailed analysis for stock vs options comparison"
        }
    }


@router.get("/stocks/{symbol}/comprehensive")
async def get_comprehensive_analysis(symbol: str):
    """
    Get comprehensive stock analysis with:
    - Multiple data sources
    - Technical analysis (candlesticks, support/resistance, ABC curves)
    - Social sentiment
    - News analysis
    - Market calendar
    - AI recommendations with disclaimer
    """
    from app.services.advanced_stock_analyzer import get_advanced_analyzer
    
    analyzer = get_advanced_analyzer()
    analysis = await analyzer.get_comprehensive_analysis(
        symbol, settings.ollama_host, settings.ollama_model
    )
    
    # Extract data from nested structure
    price_data = analysis.get("price_data", {})
    technical = analysis.get("technical_analysis", {})
    ai_rec = analysis.get("ai_recommendation", {})
    news = analysis.get("news_analysis", {})
    
    return {
        "success": True,
        "symbol": symbol,
        "current_price": price_data.get("current_price", technical.get("current_price", 0)),
        "change_percent": price_data.get("change_percent", 0),
        "recommendation": ai_rec.get("recommendation", "hold"),
        "analysis": ai_rec.get("analysis", ai_rec.get("reasoning", "")),
        "technical_analysis": technical,
        "top_news": news.get("articles", [])[:3],
        "price_data": price_data,
        "ai_recommendation": ai_rec,
        "disclaimer": analysis.get("disclaimer", ""),
        "data_sources_used": analysis.get("data_sources_used", []),
        "analysis_timestamp": analysis.get("analysis_timestamp", "")
    }


@router.get("/resilience/{symbol}")
async def get_resilience_score(symbol: str):
    """
    Get geopolitical resilience score for a stock (1-10 scale).
    
    Factors: tariff exposure, geographic concentration,
    supply chain risk, energy cost sensitivity.
    """
    from app.services.resilience_service import get_resilience_service
    
    service = get_resilience_service()
    result = service.score_stock(symbol)
    
    return {
        "success": True,
        **result,
    }


@router.get("/resilience")
async def get_portfolio_resilience(symbols: str = "AAPL,MSFT,GOOGL,NVDA,TSLA"):
    """
    Get resilience scores for all portfolio stocks.
    Pass comma-separated symbols.
    """
    from app.services.resilience_service import get_resilience_service
    
    service = get_resilience_service()
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    result = service.score_portfolio(symbol_list)
    
    return {
        "success": True,
        **result,
    }


@router.get("/deep-analysis/{symbol}")
async def get_deep_stock_analysis(symbol: str, fast: bool = False):
    """
    Comprehensive deep analysis combining:
    - Elliott Wave patterns + Fibonacci levels
    - Technical indicators (RSI, MACD, Bollinger, S/R)
    - Market sentiment (Reddit, Yahoo News, Fear/Greed Index)
    - Institutional tracking (13F holders, insider trades, analyst ratings)
    - Weekly posture + next-week outlook
    - AI synthesis via Mistral 7B

    Use ?fast=true to skip AI synthesis for ~3x faster response.
    Results are cached for 5 minutes.
    """
    from app.services.deep_analysis import get_deep_analysis

    result = await get_deep_analysis(symbol.upper(), skip_ai=fast)
    return result


@router.get("/sentiment/{symbol}")
async def get_stock_sentiment(symbol: str):
    """
    Market sentiment from Reddit, Yahoo Finance news, Fear/Greed Index, FinViz.
    """
    from app.services.market_sentiment import get_market_sentiment

    result = await get_market_sentiment(symbol.upper())
    return {"success": True, **result}


@router.get("/institutional/{symbol}")
async def get_institutional_data(symbol: str):
    """
    Institutional holders, insider trades, analyst ratings, accumulation signals.
    Tracks BlackRock, Vanguard, Goldman Sachs, JPMorgan, etc.
    """
    from app.services.institutional_tracker import get_institutional_analysis

    result = await get_institutional_analysis(symbol.upper())
    return {"success": True, **result}


# ═══════════════════════════════════════════════════════════════════════════════
# Trading Dashboard endpoints — forecasting, multi-source data, recommendations
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/stocks/{symbol}/forecast")
async def get_stock_forecast(symbol: str):
    """
    Multi-horizon forecast: 1d, 1w, 1m, 3m, 1y predictions with
    confidence bands, direction, and method used per horizon.
    """
    import asyncio
    from app.services.forecast_service import generate_forecasts

    result = await asyncio.to_thread(generate_forecasts, symbol.upper())
    return result


@router.get("/stocks/{symbol}/aggregated-data")
async def get_aggregated_data(symbol: str):
    """
    Pull data from all 20+ financial sources: Yahoo Finance, SEC EDGAR insider
    trading, FRED macro, Treasury yields, VIX, RSS news (9 sources), Finviz,
    Stocktwits, Reddit WSB, CNN Fear & Greed, Put/Call ratio, 13F institutional,
    analyst consensus, earnings calendar.
    """
    from app.services.market_data_aggregator import aggregate_all_data

    result = await aggregate_all_data(symbol.upper())
    return {"success": True, **result}


@router.get("/market/news")
async def get_market_news(symbol: Optional[str] = None):
    """
    Aggregated financial news from 10+ RSS sources.
    Optionally filter by stock symbol.
    """
    from app.services.market_data_aggregator import get_financial_news

    result = await get_financial_news(symbol.upper() if symbol else None)
    return {"success": True, **result}


@router.get("/market/macro")
async def get_macro_data():
    """
    Macro economic dashboard: FRED data (rates, unemployment, CPI, GDP),
    Treasury yields, VIX, Fear & Greed, Put/Call ratio.
    """
    import asyncio
    from app.services.market_data_aggregator import (
        get_fred_macro, get_treasury_yields, get_vix,
        get_fear_greed, get_put_call_ratio,
    )

    fred, yields, vix, fg, pcr = await asyncio.gather(
        get_fred_macro(),
        get_treasury_yields(),
        asyncio.to_thread(get_vix),
        get_fear_greed(),
        asyncio.to_thread(get_put_call_ratio),
        return_exceptions=True,
    )
    return {
        "success": True,
        "fred": fred if not isinstance(fred, Exception) else {"error": str(fred)},
        "treasury_yields": yields if not isinstance(yields, Exception) else {"error": str(yields)},
        "vix": vix if not isinstance(vix, Exception) else {"error": str(vix)},
        "fear_greed": fg if not isinstance(fg, Exception) else {"error": str(fg)},
        "put_call_ratio": pcr if not isinstance(pcr, Exception) else {"error": str(pcr)},
    }


@router.get("/market/recommendations")
async def get_stock_recommendations(count: int = 10):
    """
    Scan 50-stock universe across all data sources, score on 5 dimensions
    (technical, fundamental, sentiment, value, macro), return top N picks.
    Heavy call — cached 5 min.
    """
    from app.services.stock_recommendations import get_top_recommendations

    result = await get_top_recommendations(count)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Deals & Shopping endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/deals/latest")
async def get_latest_deals(query: Optional[str] = None):
    """
    Aggregated deals from SlickDeals, DealNews, Ben's Bargains, Reddit.
    Optionally filter by keyword query.
    """
    from app.services.deals_crawler import get_latest_deals as _get_deals

    result = await _get_deals(query)
    return result


@router.post("/deals/watchlist-check")
async def check_watchlist_deals(items: List[str]):
    """
    Check if any watchlist items have matching deals across all sources.
    """
    from app.services.deals_crawler import check_watchlist_deals as _check

    result = await _check(items)
    return result


@router.get("/deals/credit-cards")
async def get_credit_card_recs(category: str = "travel"):
    """
    Credit card + points recommendations for travel, cashback, or flights.
    """
    from app.services.deals_crawler import get_credit_card_recommendations

    return get_credit_card_recommendations(category)
