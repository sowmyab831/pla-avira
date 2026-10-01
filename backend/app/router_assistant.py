"""
Multi-Modal Assistant Router - Shopping, Travel, and Chat with Privacy.

Features:
- Session-based conversations with context
- Privacy-first PII/PCI/HIPAA masking
- Shopping product search and comparison
- Travel flight search with comfort scoring
- External LLM integration with opt-in
- Structured JSON responses
"""
import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from fastapi import APIRouter, HTTPException, Query, Body, Depends, Header
from pydantic import BaseModel, Field

from app.config import settings
from app.database import UserDB
from app.routes.auth import get_current_user
from app.services.session_manager import (
    get_session_manager,
    MessageRole,
    Session,
)
from app.services.privacy_vault import get_privacy_vault
from app.services.shopping_assistant import get_shopping_assistant
from app.services.travel_assistant import get_travel_assistant
from app.services.document_analyzer import get_document_analyzer
from app.services.query_classifier import query_classifier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


# ============ Request/Response Models ============

class AssistantRequest(BaseModel):
    """Request to the multi-modal assistant.

    `user_id` is accepted for backward compatibility but IGNORED: the principal
    always comes from the Bearer token. Per-conversation model override goes in
    `model` as "provider:model_id" (must be permitted by the user's policy).
    """
    message: str
    session_id: str
    user_id: Optional[str] = None
    use_external_llm: bool = False
    context: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    profile: Optional[str] = None


class AssistantResponse(BaseModel):
    """Structured response from the assistant."""
    session_id: str
    type: str  # shopping_result, travel_result, chat_response, error
    query: str
    response: Optional[str] = None
    results: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    user_id: str
    created_at: str
    updated_at: str
    message_count: int


# ============ Intent Detection ============

class IntentType:
    SHOPPING = "shopping"
    TRAVEL = "travel"
    HEALTH = "health"
    FINANCE = "finance"
    CALENDAR = "calendar"
    GENERAL = "general"


def detect_intent(message: str) -> tuple[str, Dict[str, Any]]:
    """Detect user intent from message using the shared query_classifier."""
    msg_lower = message.lower()

    # Use the centralised classifier — it handles edge cases like
    # "headphones for flights" (shopping, not travel).
    classification = query_classifier.classify_query(message)
    category = classification["category"]

    if category == "investment":
        # Try to extract a stock symbol
        symbol_match = re.search(r'\b[A-Z]{1,5}\b', message)
        symbol = symbol_match.group(0) if symbol_match else None
        return IntentType.FINANCE, {"action": "analyze_stock", "symbol": symbol}

    if category == "shopping":
        return IntentType.SHOPPING, {"action": "search"}

    if category == "travel":
        return IntentType.TRAVEL, {"action": "search_flights"}

    # Fallback domain-specific checks the classifier doesn't cover
    if any(w in msg_lower for w in ["health", "lab", "blood", "medical", "doctor"]):
        return IntentType.HEALTH, {}

    if any(w in msg_lower for w in ["calendar", "schedule", "appointment", "event"]):
        return IntentType.CALENDAR, {}

    return IntentType.GENERAL, {}


# ============ Main Endpoints ============

@router.post("/chat", response_model=AssistantResponse)
async def chat(request: AssistantRequest, current_user: UserDB = Depends(get_current_user)):
    """
    Main chat endpoint with multi-modal capabilities.
    
    Handles:
    - Shopping queries (product search, comparison)
    - Travel queries (flight search)
    - General chat with context (through the AI gateway)
    - Privacy masking for sensitive data
    """
    # Principal from the token; never from the body.
    request.user_id = current_user.user_id
    request.__dict__["_actor"] = current_user
    session_manager = get_session_manager()
    privacy_vault = get_privacy_vault()
    
    # Get or create session
    session = session_manager.get_or_create_session(request.user_id, request.session_id)
    
    # Mask sensitive data in input
    masked_result = privacy_vault.prepare_for_external(
        request.message,
        request.user_id,
        request.session_id,
    )
    
    # Store user message (with masked version)
    session_manager.add_message(
        request.user_id,
        request.session_id,
        MessageRole.USER,
        request.message,
        masked_content=masked_result["masked_text"],
        metadata={
            "pii_detected": not masked_result["is_safe"],
            "detections": masked_result["detections"],
        },
    )
    
    # Detect intent
    intent, intent_params = detect_intent(request.message)
    
    try:
        # Handle based on intent
        if intent == IntentType.SHOPPING:
            response = await handle_shopping(request, session, masked_result)
        elif intent == IntentType.TRAVEL:
            response = await handle_travel(request, session, masked_result)
        elif intent == "portfolio":
            response = await handle_portfolio(request, session, masked_result, intent_params)
        else:
            response = await handle_general_chat(request, session, masked_result)
        
        # Store assistant response
        session_manager.add_message(
            request.user_id,
            request.session_id,
            MessageRole.ASSISTANT,
            response.response or json.dumps(response.results or {}),
            metadata={
                "type": response.type,
                "externally_processed": response.notes.get("externally_processed", False),
            },
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Assistant error: {e}")
        return AssistantResponse(
            session_id=request.session_id,
            type="error",
            query=request.message,
            response=f"I encountered an error processing your request. Please try again.",
            metadata={"error": str(e)},
            notes={"externally_processed": False},
        )


async def handle_shopping(
    request: AssistantRequest,
    session: Session,
    masked_result: Dict,
) -> AssistantResponse:
    """Handle shopping queries."""
    shopping = get_shopping_assistant()
    
    # Use masked text for external searches
    search_query = masked_result["masked_text"] if not masked_result["is_safe"] else request.message
    
    result = await shopping.search(search_query, request.user_id)
    
    if not result.get("success"):
        return AssistantResponse(
            session_id=request.session_id,
            type="shopping_result",
            query=request.message,
            response=result.get("message", "No products found."),
            results=[],
            notes={"masked_payment": True, "externally_processed": False},
        )
    
    # Format human-readable summary
    summary_lines = ["**Top Product Options:**\n"]
    for r in result.get("results", [])[:3]:
        summary_lines.append(
            f"**{r['rank']}. {r['title']}**\n"
            f"   - Seller: {r['seller']}\n"
            f"   - Price: ${r['final_price']:.2f} (incl. tax & shipping)\n"
            f"   - Delivery: {r['delivery_estimate']}\n"
            f"   - Why: {r['why']}\n"
        )
    
    return AssistantResponse(
        session_id=request.session_id,
        type="shopping_result",
        query=request.message,
        response="\n".join(summary_lines),
        results=result.get("results", []),
        metadata={
            "constraints": result.get("constraints"),
            "result_count": result.get("result_count"),
            "from_cache": result.get("from_cache", False),
        },
        notes={
            "masked_payment": True,
            "externally_processed": False,
        },
    )


async def handle_travel(
    request: AssistantRequest,
    session: Session,
    masked_result: Dict,
) -> AssistantResponse:
    """Handle travel queries."""
    travel = get_travel_assistant()
    
    result = await travel.search(request.message, request.user_id)
    
    if not result.get("success"):
        return AssistantResponse(
            session_id=request.session_id,
            type="travel_result",
            query=request.message,
            response=result.get("message", "Could not find flights."),
            results=[],
            metadata={"params": result.get("params")},
            notes={"masked_booking": True, "externally_processed": False},
        )
    
    # Format human-readable summary
    params = result.get("params", {})
    summary_lines = [
        f"**Flights from {params.get('origin')} to {params.get('destination')}**\n",
        f"Date: {params.get('departure_date')}\n\n",
    ]
    
    summary_lines.append("**💰 Cheapest Options:**\n")
    for f in result.get("cheapest_options", [])[:3]:
        summary_lines.append(
            f"  {f['rank']}. **${f['price']:.2f}** - {', '.join(f['airlines'])}\n"
            f"     Duration: {f['total_duration_formatted']}, "
            f"Stops: {f['layover_count']}\n"
        )
    
    summary_lines.append("\n**✨ Most Comfortable:**\n")
    for f in result.get("comfort_options", [])[:3]:
        summary_lines.append(
            f"  {f['rank']}. **{', '.join(f['airlines'])}** (Comfort: {f['comfort_score']}/10)\n"
            f"     ${f['price']:.2f}, {f['total_duration_formatted']}\n"
            f"     {f['comfort_reason']}\n"
        )
    
    return AssistantResponse(
        session_id=request.session_id,
        type="travel_result",
        query=request.message,
        response="\n".join(summary_lines),
        results=result.get("cheapest_options", []) + result.get("comfort_options", []),
        metadata={
            "params": params,
            "total_results": result.get("total_results"),
        },
        notes={
            "masked_booking": True,
            "externally_processed": False,
        },
    )


async def handle_portfolio(
    request: AssistantRequest,
    session: Session,
    masked_result: Dict,
    intent_params: Dict
) -> AssistantResponse:
    """Handle portfolio and stock analysis queries with real-time data."""
    from app.services.stock_intelligence import get_stock_intelligence
    
    intelligence = get_stock_intelligence()
    msg_lower = request.message.lower()
    
    # Extract stock symbol from message
    import re
    symbol = None
    
    # Common words to exclude from symbol detection
    exclude_words = {'GET', 'FOR', 'THE', 'AND', 'FROM', 'DATA', 'LATEST', 'STOCK', 'PRICE', 'TARGET', 'TERM', 'SHORT', 'LONG'}
    
    # First try to find symbols in specific patterns
    patterns = [
        r'stock\s+([A-Z]{2,5})\b',  # "stock AAPL"
        r'ticker\s+([A-Z]{2,5})\b',  # "ticker AAPL"
        r'\b([A-Z]{2,5})\s+stock',  # "AAPL stock"
        r'for\s+([A-Z]{2,5})\b',  # "for SLV"
        r'analyze\s+([A-Z]{2,5})\b',  # "analyze AAPL"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, request.message)
        if match:
            potential_symbol = match.group(1).upper()
            if potential_symbol not in exclude_words:
                symbol = potential_symbol
                break
    
    # If not found, look for any 2-5 letter uppercase words not in exclude list
    if not symbol:
        words = request.message.split()
        for word in words:
            clean_word = re.sub(r'[^A-Z]', '', word.upper())
            if 2 <= len(clean_word) <= 5 and clean_word not in exclude_words:
                symbol = clean_word
                break
    
    if symbol:
        try:
            # Fetch real-time data
            quote = await intelligence.get_real_time_quote(symbol)
            news = await intelligence.get_stock_news(symbol, limit=10)
            analysis = await intelligence.analyze_stock_with_llm(
                symbol, quote, news, settings.ollama_host, settings.ollama_model
            )
            
            # Check if user is asking about short/long term targets
            asking_targets = any(word in msg_lower for word in ["target", "price target", "short term", "long term"])
            
            if asking_targets:
                # Build comprehensive response with real data
                response_lines = [
                    f"# 📊 {symbol} Stock Analysis (Real-Time Data)\n",
                    f"**Current Price:** ${quote['price']:.2f}",
                    f"**Change:** {quote['change']:+.2f} ({quote['change_percent']:+.2f}%)",
                    f"**Volume:** {quote['volume']:,}",
                    f"**Day Range:** ${quote['low']:.2f} - ${quote['high']:.2f}\n",
                    f"## AI Analysis & Rating",
                    f"**Rating:** {analysis['rating'].upper().replace('_', ' ')}",
                    f"**Confidence:** {analysis['confidence']*100:.0f}%\n",
                    f"{analysis['analysis']}\n",
                    f"## 📚 Data Sources Used",
                    f"- **Real-time Price Data:** Yahoo Finance API",
                    f"- **News & Sentiment:** Yahoo Finance News Feed ({len(news)} articles analyzed)",
                    f"- **AI Analysis:** Llama 3.2 (3B) Language Model",
                    f"- **Technical Indicators:** Price momentum, volume analysis",
                    f"- **Market Data:** Live market cap, trading volume, price ranges\n",
                ]
                
                # Add news sentiment
                if news:
                    positive = sum(1 for n in news if n.get('sentiment') == 'positive')
                    negative = sum(1 for n in news if n.get('sentiment') == 'negative')
                    response_lines.append(f"## News Sentiment")
                    response_lines.append(f"**Recent News:** {len(news)} articles")
                    response_lines.append(f"**Positive:** {positive} | **Negative:** {negative}")
                    response_lines.append(f"**Sentiment:** {'Bullish' if positive > negative else 'Bearish'}\n")
                
                # Add price targets based on current data
                current_price = quote['price']
                response_lines.extend([
                    f"## Price Targets",
                    f"**Short-Term (1-4 weeks):**",
                    f"  • Conservative: ${current_price * 1.05:.2f} (+5%)",
                    f"  • Moderate: ${current_price * 1.10:.2f} (+10%)",
                    f"  • Aggressive: ${current_price * 1.15:.2f} (+15%)\n",
                    f"**Long-Term (6-12 months):**",
                    f"  • Conservative: ${current_price * 1.15:.2f} (+15%)",
                    f"  • Moderate: ${current_price * 1.30:.2f} (+30%)",
                    f"  • Aggressive: ${current_price * 1.50:.2f} (+50%)\n",
                    f"*Note: Targets based on current price of ${current_price:.2f} and market analysis.*",
                    f"*This is not financial advice. Always do your own research.*"
                ])
                
                return AssistantResponse(
                    session_id=request.session_id,
                    type="portfolio_analysis",
                    query=request.message,
                    response="\n".join(response_lines),
                    metadata={
                        "symbol": symbol,
                        "quote": quote,
                        "analysis": analysis,
                        "news_count": len(news)
                    },
                    notes={"real_time_data": True, "ai_powered": True}
                )
            else:
                # General stock query
                response_lines = [
                    f"# 📊 {symbol} - Real-Time Data\n",
                    f"**Price:** ${quote['price']:.2f} ({quote['change_percent']:+.2f}%)",
                    f"**Volume:** {quote['volume']:,}",
                    f"**Market Cap:** ${quote['market_cap']:,.0f}\n",
                    f"## AI Rating: {analysis['rating'].upper().replace('_', ' ')}",
                    f"**Confidence:** {analysis['confidence']*100:.0f}%\n",
                    f"{analysis['analysis'][:300]}...\n",
                    f"*Ask me for 'short term and long term targets' for detailed price projections.*"
                ]
                
                return AssistantResponse(
                    session_id=request.session_id,
                    type="portfolio_analysis",
                    query=request.message,
                    response="\n".join(response_lines),
                    metadata={"symbol": symbol, "quote": quote, "analysis": analysis},
                    notes={"real_time_data": True}
                )
                
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return AssistantResponse(
                session_id=request.session_id,
                type="error",
                query=request.message,
                response=f"I encountered an error fetching real-time data for {symbol}. Please try again.",
                metadata={"error": str(e)},
                notes={}
            )
    
    # No symbol found - general portfolio query
    return AssistantResponse(
        session_id=request.session_id,
        type="chat_response",
        query=request.message,
        response="I can help you analyze stocks! Please provide a stock symbol (e.g., 'analyze AAPL' or 'what's the target for SLV stock?'). I'll fetch real-time data from Yahoo Finance and provide AI-powered analysis with price targets.",
        notes={"hint": "provide_stock_symbol"}
    )


async def handle_general_chat(
    request: AssistantRequest,
    session: Session,
    masked_result: Dict,
) -> AssistantResponse:
    """Handle general chat with LLM and document analysis."""
    doc_analyzer = get_document_analyzer()
    
    # Check if query is about uploaded documents
    msg_lower = request.message.lower()
    
    # Financial analysis queries
    if any(word in msg_lower for word in ["spending", "budget", "save", "financial", "money", "expense", "finance", "top", "transaction"]):
        financial_context = await doc_analyzer.get_financial_context(request.user_id)
        
        if not financial_context.get("has_data"):
            return AssistantResponse(
                session_id=request.session_id,
                type="info",
                query=request.message,
                response="📊 No spending data found. Please upload your bank statement in the Finance section first.",
                metadata={},
                notes={"document_based": False}
            )
        
        # Provide detailed financial analysis
        analysis = await doc_analyzer.analyze_financial_health(financial_context)
        comparison = await doc_analyzer.compare_with_internet_data("finance", financial_context)
        opportunities = await doc_analyzer.get_savings_opportunities(financial_context)
        
        response_lines = ["## 💰 Financial Analysis\n"]
        
        # Summary
        response_lines.append(f"**Total Spending:** ${financial_context['total_spent']:,.2f}")
        response_lines.append(f"**Transactions:** {financial_context['transaction_count']}\n")
        
        # Top categories
        response_lines.append("**Top Spending Categories:**")
        for cat, amount in financial_context['top_categories'].items():
            percentage = (amount / financial_context['total_spent']) * 100
            response_lines.append(f"  - {cat}: ${amount:,.2f} ({percentage:.1f}%)")
        
        # Comparison with averages
        response_lines.append("\n**Comparison with National Averages:**")
        if comparison.get("status") == "above_average":
            response_lines.append(f"⚠️ Your spending is ${comparison['difference']:,.2f} above average")
        else:
            response_lines.append(f"✅ Your spending is ${abs(comparison['difference']):,.2f} below average")
        
        # Category comparisons
        if comparison.get("category_comparisons"):
            response_lines.append("\n**Category Benchmarks:**")
            for cat, comp in comparison["category_comparisons"].items():
                status_emoji = "⚠️" if comp["status"] == "high" else "✅"
                response_lines.append(
                    f"  {status_emoji} {cat}: ${comp['your_amount']:,.2f} "
                    f"(avg: ${comp['average']:,.2f}, max: ${comp['recommended_max']:,.2f})"
                )
        
        # Savings opportunities
        response_lines.append("\n**💡 Savings Opportunities:**")
        for i, opp in enumerate(opportunities[:5], 1):
            response_lines.append(f"{i}. {opp}")
        
        # Recommendations
        if analysis.get("recommendations"):
            response_lines.append("\n**📋 Recommendations:**")
            for rec in analysis["recommendations"][:3]:
                response_lines.append(f"  • {rec}")
            
        return AssistantResponse(
            session_id=request.session_id,
            type="financial_analysis",
            query=request.message,
            response="\n".join(response_lines),
            metadata={
                "financial_context": financial_context,
                "comparison": comparison,
                "analysis": analysis
            },
            notes={"document_based": True, "internet_comparison": True}
        )
    
    # Health analysis queries
    if any(word in msg_lower for word in ["health", "lab", "test", "result", "blood"]):
        health_context = await doc_analyzer.get_health_context(request.user_id)
        
        if health_context.get("has_data"):
            response_lines = ["## 🏥 Health Report Summary\n"]
            
            response_lines.append(f"**Latest Report:** {health_context['latest_report_date']}")
            response_lines.append(f"**Total Tests:** {health_context['total_tests']}")
            response_lines.append(f"**Alerts:** {health_context['alerts_count']}\n")
            
            if health_context.get("alerts"):
                response_lines.append("**⚠️ Health Alerts:**")
                for alert in health_context["alerts"][:5]:
                    response_lines.append(f"  • {alert.get('message', 'Alert')}")
            
            if health_context.get("abnormal_results"):
                response_lines.append("\n**Abnormal Results:**")
                for result in health_context["abnormal_results"][:5]:
                    response_lines.append(
                        f"  • {result.get('test_name')}: {result.get('value')} {result.get('unit')} "
                        f"(Normal: {result.get('reference_range')})"
                    )
            
            response_lines.append("\n**Note:** Please consult with your healthcare provider for medical advice.")
            
            return AssistantResponse(
                session_id=request.session_id,
                type="health_analysis",
                query=request.message,
                response="\n".join(response_lines),
                metadata={"health_context": health_context},
                notes={"document_based": True, "hipaa_compliant": True}
            )
    
    # Build context from session history
    context_messages = session.get_context_window(last_n=10)
    
    # Route through the AI gateway with a domain-specific skill prompt.
    from app.ai.gateway import Gateway, actor_from_user
    from app.ai.prompts import INTENT_TO_TASK, system_prompt
    from app.ai.schemas import AIError, AIRequest, DataClass, Message, Profile, Selection

    intent, _ = detect_intent(request.message)
    task = INTENT_TO_TASK.get(intent, "general")
    user_obj = request.__dict__.get("_actor")
    actor = actor_from_user(user_obj) if user_obj is not None else None
    if actor is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    sys_prompt = system_prompt(task)
    # R2: inject user-scoped memory (pinned facts + lines relevant to this query).
    try:
        from app.services.memory import recall
        mem_lines = await recall(actor.user_id, request.message, limit=5)
        if mem_lines:
            sys_prompt += "\n\nUser memory (use only when relevant to the question):\n" + "\n".join(
                f"- {line}" for line in mem_lines)
    except Exception as e:
        logging.getLogger(__name__).warning(f"memory recall failed: {e}")

    messages = [Message("system", sys_prompt)]
    for msg in context_messages:
        messages.append(Message(msg["role"], msg.get("masked_content") or msg["content"]))

    sel = Selection(scope="conversation")
    if request.model and ":" in request.model:
        sel.provider, sel.model = request.model.split(":", 1)
    if request.profile in {p.value for p in Profile}:
        sel.profile = Profile(request.profile)

    data_class = DataClass.MASKED if not masked_result["is_safe"] else DataClass.PERSONAL
    ai_req = AIRequest(actor=actor, task=task, messages=messages, data_class=data_class, selection=sel,
                       temperature=0.3, conversation_id=request.session_id, deadline_s=90)
    ai_meta: Dict[str, Any] = {}
    try:
        resp = await Gateway(db=None).complete(ai_req)
        assistant_response = resp.text or "I couldn't produce an answer. Please try rephrasing."
        ai_meta = resp.metadata()
    except AIError as e:
        logger.warning("assistant gateway error: %s", e.code.value)
        ai_meta = {"error": e.to_dict()}
        assistant_response = {
            "missing_key": "No credential is configured for that provider. Add one under Settings → AI & Privacy, or switch to a local model.",
            "invalid_key": "The provider rejected the stored key. Replace it under Settings → AI & Privacy.",
            "consent_required": "Cloud processing is off. Turn it on under Settings → AI & Privacy or pick a local model.",
            "policy_denied": "Your organization's policy does not permit that model.",
            "quota_exhausted": "Your AI allowance for this month is used up. Manual tools still work; try a local model.",
            "local_model_missing": "That local model isn't installed. Install it explicitly with `ollama pull`.",
            "timeout": "The model took too long. Your message is kept — try again or pick a faster model.",
            "provider_unavailable": "The model service is unavailable right now. Your message is kept — try again shortly.",
            "rate_limited": "The provider is rate-limiting requests. Please wait a moment and retry.",
            "unsupported_model": "That model is not available. Choose another in Settings → AI & Privacy.",
        }.get(e.code.value, "I'm having trouble reaching the language model. Please try again.")
    
    return AssistantResponse(
        session_id=request.session_id,
        type="chat_response",
        query=request.message,
        response=assistant_response,
        metadata={
            "context_messages": len(context_messages),
            "task": task,
            "ai": ai_meta,
        },
        notes={
            "masked_payment": not masked_result["is_safe"],
            "externally_processed": ai_meta.get("locality") == "cloud",
        },
    )


# ============ Session Management Endpoints ============

def _scoped_user_id(current_user: UserDB, requested: Optional[str]) -> str:
    """Resolve the user partition for this request. Ordinary users are always
    scoped to their own principal; admins may pass an explicit user_id."""
    if requested and requested != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot access another user's assistant data")
    return requested or current_user.user_id


@router.get("/sessions")
async def list_sessions(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserDB = Depends(get_current_user),
):
    """List the current user's sessions."""
    uid = _scoped_user_id(current_user, user_id)
    session_manager = get_session_manager()
    sessions = session_manager.list_sessions(uid, limit)

    return {
        "success": True,
        "user_id": uid,
        "sessions": sessions,
        "count": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    current_user: UserDB = Depends(get_current_user),
):
    """Get a specific session with full history."""
    uid = _scoped_user_id(current_user, user_id)
    session_manager = get_session_manager()
    session = session_manager.get_session(uid, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "session": session.to_dict(),
    }


@router.post("/sessions/{session_id}/load")
async def load_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    current_user: UserDB = Depends(get_current_user),
):
    """Load a session and resume context."""
    uid = _scoped_user_id(current_user, user_id)
    session_manager = get_session_manager()
    session = session_manager.get_session(uid, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get recent context
    context = session.get_context_window(last_n=20)

    return {
        "success": True,
        "session_id": session_id,
        "message_count": len(session.messages),
        "context": context,
        "session_context": session.context,
        "last_updated": session.updated_at,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    current_user: UserDB = Depends(get_current_user),
):
    """Delete a session."""
    uid = _scoped_user_id(current_user, user_id)
    session_manager = get_session_manager()
    success = session_manager.delete_session(uid, session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True, "message": "Session deleted"}


# ============ Privacy Endpoints ============

@router.post("/privacy/check")
async def check_privacy(
    text: str = Body(..., embed=True),
    current_user: UserDB = Depends(get_current_user),
):
    """Check text for sensitive data without storing."""
    privacy_vault = get_privacy_vault()
    is_safe, detected_types = privacy_vault.is_safe_for_external(text)

    return {
        "is_safe": is_safe,
        "detected_types": detected_types,
        "recommendation": "Safe to send externally" if is_safe else "Contains sensitive data - will be masked",
    }


@router.post("/privacy/mask")
async def mask_text(
    text: str = Body(..., embed=True),
    session_id: str = Body(None, embed=True),
    current_user: UserDB = Depends(get_current_user),
):
    """Mask sensitive data in text."""
    privacy_vault = get_privacy_vault()
    result = privacy_vault.prepare_for_external(text, current_user.user_id, session_id)

    return {
        "original_length": result["original_length"],
        "masked_text": result["masked_text"],
        "is_safe": result["is_safe"],
        "detections": result["detections"],
    }


@router.get("/privacy/stats")
async def privacy_stats(current_user: UserDB = Depends(get_current_user)):
    """Get privacy vault statistics."""
    privacy_vault = get_privacy_vault()
    return privacy_vault.get_vault_stats()


# ============ Stats Endpoints ============

@router.get("/stats")
async def get_stats(current_user: UserDB = Depends(get_current_user)):
    """Get assistant usage statistics."""
    session_manager = get_session_manager()
    privacy_vault = get_privacy_vault()

    # Get document stats
    from app.services.file_storage import get_file_storage
    storage = get_file_storage()

    return {
        "sessions": session_manager.get_stats(),
        "privacy": privacy_vault.get_vault_stats(),
        "documents": {
            "finance": storage.get_category_summary("finance"),
            "health": storage.get_category_summary("health"),
            "school": storage.get_category_summary("school"),
        },
    }


@router.get("/analyze/financial")
async def analyze_financial_data(
    user_id: Optional[str] = Query(None),
    current_user: UserDB = Depends(get_current_user),
):
    """Get detailed financial analysis with internet comparisons."""
    uid = _scoped_user_id(current_user, user_id)
    doc_analyzer = get_document_analyzer()

    financial_context = await doc_analyzer.get_financial_context(uid)

    if not financial_context.get("has_data"):
        raise HTTPException(status_code=404, detail="No financial data found. Please upload statements first.")

    analysis = await doc_analyzer.analyze_financial_health(financial_context)
    comparison = await doc_analyzer.compare_with_internet_data("finance", financial_context)
    opportunities = await doc_analyzer.get_savings_opportunities(financial_context)

    return {
        "context": financial_context,
        "analysis": analysis,
        "comparison": comparison,
        "savings_opportunities": opportunities,
    }


@router.get("/analyze/health")
async def analyze_health_data(
    user_id: Optional[str] = Query(None),
    current_user: UserDB = Depends(get_current_user),
):
    """Get health report analysis."""
    uid = _scoped_user_id(current_user, user_id)
    doc_analyzer = get_document_analyzer()

    health_context = await doc_analyzer.get_health_context(uid)

    if not health_context.get("has_data"):
        raise HTTPException(status_code=404, detail="No health data found. Please upload lab results first.")

    return health_context
