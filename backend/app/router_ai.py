"""AI/LLM routes: chat, completions, streaming."""
import logging
import json
import re
from typing import AsyncGenerator, Optional
from datetime import datetime
import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.middleware.subscription_gate import soft_rate_limit
from pydantic import BaseModel

from app.config import settings
from app.privacy import mask_text
from app.search import get_indexer
from app.services.data_context import get_data_context
from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ai"])


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    user_id: str
    context: Optional[str] = None
    use_external_llm: bool = False


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    masked_input: str
    pii_detected: bool
    sources: list = []


def _detect_intent(message: str) -> tuple[str, dict]:
    """Detect user intent from message."""
    msg_lower = message.lower()
    
    # Reminder/Appointment intent
    if any(word in msg_lower for word in ['remind', 'reminder', 'appointment', 'add task']):
        date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)', message, re.I)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))', message, re.I)
        return 'add_reminder', {
            'date': date_match.group(1) if date_match else None,
            'time': time_match.group(1) if time_match else None,
            'message': message
        }
    
    # Top spending / most spent intent
    if any(phrase in msg_lower for phrase in ['most spent', 'top spend', 'highest spend', 'where.*money', 'spending on']):
        days = 30
        if 'week' in msg_lower:
            days = 7
        elif 'year' in msg_lower:
            days = 365
        elif 'month' in msg_lower:
            days = 30
        return 'top_spending', {'days': days}
    
    # Budget/Finance intent
    if any(word in msg_lower for word in ['budget', 'afford', 'left', 'remaining']):
        return 'check_budget', {}
    
    # Spending suggestions
    if any(phrase in msg_lower for phrase in ['cut down', 'save money', 'spending habit', 'suggestion', 'reduce spend']):
        return 'spending_suggestions', {}
    
    # Month over month comparison
    if any(phrase in msg_lower for phrase in ['month over month', 'compared to last', 'vs last month', 'mom']):
        return 'month_over_month', {}
    
    # Specific lab test query (check first before general health)
    test_match = re.search(r'(triglyceride|cholesterol|glucose|hemoglobin|platelet|wbc|rbc|hdl|ldl|neutrophil|lymphocyte|monocyte|eosinophil|basophil|mcv|mch|mchc|pcv|hb)', msg_lower)
    if test_match:
        return 'compare_health_test', {'test_name': test_match.group(1)}
    
    # Health report intent
    if any(word in msg_lower for word in ['health', 'lab', 'blood', 'test result', 'medical']):
        return 'health_summary', {}
    
    # Vacation planning intent
    if any(word in msg_lower for word in ['vacation', 'free day', 'day off', 'plan trip', 'weekend']):
        return 'vacation_planning', {}
    
    # Calendar intent
    if any(word in msg_lower for word in ['calendar', 'events', 'upcoming', 'schedule', 'holiday']):
        return 'check_calendar', {}
    
    return 'general', {}


async def _handle_intent(intent: str, params: dict, original_message: str, user_id: str = "default") -> str:
    """Handle detected intent and return response using unified data context."""
    ctx = get_data_context()

    # Sync data from stores, scoped to the current user
    try:
        from app.routes.finance import transactions_store
        from app.routes.health import health_reports_store, lab_results_store
        from app.router_school_calendar import calendar

        user_reports = [r for r in health_reports_store if r.get("user_id") == user_id]
        user_lab_results = [r for r in lab_results_store if r.get("user_id") == user_id]
        ctx.set_transactions(transactions_store)
        ctx.set_health_data(user_reports, user_lab_results)
        ctx.set_calendar_events(calendar.get_upcoming_events(days=90))
    except Exception as e:
        logger.warning(f"Could not sync all data: {e}")
    
    if intent == 'add_reminder':
        try:
            from app.router_school_calendar import calendar
            from app.integrations.calendar import EventType
            
            date_str = params.get('date')
            if date_str:
                for fmt in ['%B %d', '%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%d %B']:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        if parsed.year == 1900:
                            parsed = parsed.replace(year=datetime.now().year)
                            if parsed < datetime.now():
                                parsed = parsed.replace(year=datetime.now().year + 1)
                        date_str = parsed.strftime('%Y-%m-%d')
                        break
                    except:
                        continue
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            time_str = params.get('time', '')
            event = calendar.add_event(
                date=date_str,
                title=f"Reminder: {original_message[:50]}",
                event_type=EventType.APPOINTMENT,
                description=original_message,
                time=time_str
            )
            
            return f"✅ I've added a reminder for you!\n\n📅 **Date:** {date_str}\n⏰ **Time:** {time_str or 'All day'}\n📝 **Note:** {original_message[:100]}\n\nView in Calendar section."
        except Exception as e:
            logger.error(f"Failed to add reminder: {e}")
            return "I understood you want to add a reminder, but encountered an issue. Try the Calendar section directly."
    
    elif intent == 'top_spending':
        days = params.get('days', 30)
        result = ctx.query('top_spending', {'days': days})
        
        if not result.get('top_merchants'):
            return "📊 No spending data found. Please upload your bank statement in the Finance section first."
        
        merchants_text = "\n".join([f"• **{m[0]}**: ${m[1]:,.2f}" for m in result['top_merchants'][:5]])
        categories_text = "\n".join([f"• **{c[0]}**: ${c[1]:,.2f}" for c in result['top_categories'][:5]])
        
        return f"""💸 **Top Spending (Last {days} Days)**

**By Merchant:**
{merchants_text}

**By Category:**
{categories_text}

View details in Finance section."""
    
    elif intent == 'check_budget':
        summary = ctx.get_spending_summary(30)
        total_spent = summary['total_spent']
        monthly_budget = 5000
        remaining = monthly_budget - total_spent
        
        if total_spent == 0:
            return "I can help check your budget! Please upload your bank statement in Finance first."
        
        status = '🟢 Budget healthy!' if remaining > 500 else '🟡 Budget tight.' if remaining > 0 else '🔴 Over budget!'
        
        return f"""💰 **Budget Summary**

📊 **Monthly Budget:** ${monthly_budget:,.2f}
💸 **Spent:** ${total_spent:,.2f}
✨ **Remaining:** ${remaining:,.2f}

{status}

**Shopping allowance:** ~${max(0, remaining * 0.3):,.2f}"""
    
    elif intent == 'spending_suggestions':
        suggestions = ctx.get_spending_suggestions()
        suggestions_text = "\n".join(suggestions)
        return f"""💡 **Spending Suggestions**

{suggestions_text}

View detailed analysis in Finance section."""
    
    elif intent == 'month_over_month':
        mom = ctx.get_month_over_month()
        trend = "📈 Up" if mom['change'] > 0 else "📉 Down" if mom['change'] < 0 else "➡️ Same"
        
        return f"""📊 **Month-over-Month Comparison**

**This Month:** ${mom['this_month']:,.2f}
**Last Month:** ${mom['last_month']:,.2f}
**Change:** {trend} ${abs(mom['change']):,.2f} ({mom['change_percent']:+.1f}%)"""
    
    elif intent == 'health_summary':
        summary = ctx.get_health_summary()
        
        if summary.get('status') == 'no_data':
            return "🏥 No health data yet. Upload your lab results PDF in the Health section."
        
        abnormal_text = ""
        if summary['abnormal_tests']:
            abnormal_text = "\n**⚠️ Abnormal Results:**\n" + "\n".join([
                f"• {t['test_name']}: {t['value']} {t['unit']} (Ref: {t['reference_range']})"
                for t in summary['abnormal_tests'][:5]
            ])
        
        return f"""🏥 **Health Summary**

📋 **Total Tests:** {summary['total_tests']}
⚠️ **Abnormal:** {summary['abnormal_count']}
📅 **Last Report:** {summary.get('last_report_date', 'N/A')[:10] if summary.get('last_report_date') else 'N/A'}
{abnormal_text}

View full report in Health section."""
    
    elif intent == 'compare_health_test':
        test_name = params.get('test_name', '')
        result = ctx.compare_lab_results(test_name)
        
        if not result.get('found'):
            return f"No results found for '{test_name}'. Upload more lab reports to track trends."
        
        latest = result['latest']
        trend_emoji = "📈" if result['trend'] == 'increasing' else "📉" if result['trend'] == 'decreasing' else "➡️"
        
        history_text = "\n".join([
            f"• {r['date']}: {r['value']} {r['unit']} {'⚠️' if r['is_abnormal'] else '✅'}"
            for r in result['results'][-5:]
        ])
        
        return f"""🔬 **{test_name.title()} Trend** {trend_emoji}

**Latest:** {latest['value']} {latest['unit']}
**Reference:** {latest['reference_range']}
**Trend:** {result['trend'].title()}

**History:**
{history_text}"""
    
    elif intent == 'vacation_planning':
        free_days = ctx.find_free_days(60)
        weekends = [d for d in free_days if d['is_weekend']][:10]
        
        if not weekends:
            return "📅 Your calendar is quite busy! Consider blocking time for rest."
        
        weekends_text = "\n".join([f"• **{d['date']}** ({d['day']})" for d in weekends[:8]])
        
        return f"""🏖️ **Vacation Planning**

**Free Weekends (Next 60 Days):**
{weekends_text}

{'...and more free days available.' if len(weekends) > 8 else ''}

💡 **Tip:** Check US holidays in the Calendar section for long weekend opportunities!"""
    
    elif intent == 'check_calendar':
        events = ctx.get_calendar_events(14)
        
        if not events:
            return "📅 No events in the next 2 weeks. Add events in Calendar section."
        
        events_text = "\n".join([f"• **{e.get('date')}**: {e.get('title')}" for e in events[:7]])
        return f"""📅 **Upcoming Events (2 Weeks)**

{events_text}

{'...and more.' if len(events) > 7 else ''}"""
    
    return None  # Fall through to LLM


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(soft_rate_limit("ai_chat"))])
async def chat(request: ChatRequest):
    """
    Chat endpoint with privacy masking and local LLM inference.
    
    Flow:
    1. Detect intent and handle special commands
    2. Mask PII/PHI/PCI locally
    3. Generate embedding and search context
    4. Call local Ollama/Mistral for response
    """
    try:
        # Step 0: Detect intent and handle special commands
        intent, params = _detect_intent(request.message)
        
        if intent != 'general':
            intent_response = await _handle_intent(intent, params, request.message, request.user_id)
            if intent_response:
                return ChatResponse(
                    response=intent_response,
                    masked_input=request.message,
                    pii_detected=False,
                    sources=[]
                )
        
        # Step 1: Mask sensitive data
        masked_input, pii_metadata = mask_text(request.message)
        pii_detected = pii_metadata.get("is_masked", False)
        
        logger.info(f"User {request.user_id}: PII detected={pii_detected}")
        
        # Step 2: Generate embedding and search
        indexer = get_indexer()
        search_results = await indexer.search(
            masked_input,
            collection_name=f"user_{request.user_id}",
            limit=5,
        )
        
        # Build context from search results
        context_text = request.context or ""
        if search_results:
            context_text += "\n\nRelevant context:\n"
            for result in search_results:
                payload = result.get("payload", {})
                context_text += f"- {payload.get('text', '')}\n"
        
        # Step 3: Call local Ollama
        response_text = await _call_ollama(masked_input, context_text)
        
        # Step 4: Optional external LLM (for masked data analysis only)
        if request.use_external_llm and settings.openai_api_key:
            external_response = await _call_external_llm(masked_input)
            response_text = f"{response_text}\n\n[External Analysis]:\n{external_response}"
        
        # Index the interaction
        await indexer.index_document(
            text=masked_input,
            metadata={
                "id": hash(f"{request.user_id}_{request.message}"),
                "user_id": request.user_id,
                "category": "chat",
                "pii_detected": pii_detected,
            },
            collection_name=f"user_{request.user_id}",
        )
        
        return ChatResponse(
            response=response_text,
            masked_input=masked_input,
            pii_detected=pii_detected,
            sources=[r.get("payload", {}).get("id") for r in search_results],
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _call_ollama(prompt: str, context: str = "") -> str:
    """Call local Ollama via shared client (cached, fast model)."""
    try:
        full_prompt = f"{context}\n\nUser: {prompt}\n\nAssistant:"
        text = await llm_generate(
            full_prompt, task="assistant", temperature=0.7, timeout=60,
        )
        return text.strip() if text else "I'm unable to process your request at the moment."

    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        return "I'm unable to process your request at the moment."


async def _call_external_llm(masked_prompt: str) -> str:
    """
    Call external LLM (OpenAI, Anthropic, Gemini) with MASKED data only.
    
    IMPORTANT: Only send masked_prompt, never original PII/PHI/PCI.
    """
    try:
        # Release 0: cloud processing is blocked unless the deployment flag is on.
        # Release 1 replaces this with the AI gateway (consent + budget + audit).
        if not settings.ai_cloud_enabled or not settings.openai_api_key:
            return ""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": masked_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
    except Exception as e:
        logger.error(f"External LLM call failed: {e}")
        return ""


@router.post("/chat/stream", dependencies=[Depends(soft_rate_limit("ai_chat"))])
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            masked_input, pii_metadata = mask_text(request.message)
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.ollama_host}/api/generate",
                    json={
                        "model": settings.model_for_task("assistant"),
                        "prompt": masked_input,
                        "stream": True,
                    },
                )
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        yield f"data: {json.dumps(data)}\n\n"
                        
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return event_generator()
