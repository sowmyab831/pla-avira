"""
AI Assistant API Routes
Handles chat interactions with context-aware LLM responses
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx
import logging
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.services.enhanced_prompts import enhanced_prompts
from app.services.llm_client import generate as llm_generate
from app.services.query_classifier import query_classifier
from app.database import get_session, ChatSessionDB, ChatMessageDB

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    response: str
    context_used: bool = False
    session_id: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_session)):
    """
    Handle chat messages with intelligent query classification and session persistence.
    
    Automatically classifies queries as:
    - investment: Stock analysis, portfolio advice
    - shopping: Product search, price comparison
    - travel: Flight search, hotel booking
    - general: Other queries
    """
    try:
        # Classify the query
        classification = query_classifier.classify_query(request.message)
        category = classification['category']
        confidence = classification['confidence']
        
        logger.info(f"Query classified as '{category}' with confidence {confidence:.2f}")
        logger.info(f"Reasoning: {classification['reasoning']}")
        
        # Get or create session
        session_id = request.session_id or f"session_{request.user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Load conversation history from database
        conversation_history = await _load_conversation_history(db, session_id)
        
        # Route to appropriate service based on classification
        if category == 'investment':
            # Route to portfolio/stock analysis
            from app.services.stock_intelligence import get_stock_intelligence
            
            # Extract ticker if present
            import re
            ticker_match = re.search(r'\b([A-Z]{1,5})\b', request.message)
            
            if ticker_match:
                ticker = ticker_match.group(1)
                # Get stock analysis
                stock_service = get_stock_intelligence()
                analysis = await stock_service.get_comprehensive_analysis(ticker)
                
                prompt = f"""You are a financial investment advisor analyzing stock {ticker}.

User Question: {request.message}

Stock Data:
- Current Price: ${analysis.get('current_price', 'N/A')}
- Change: {analysis.get('change_percent', 0):.2f}%
- Recommendation: {analysis.get('recommendation', 'N/A')}
- Analysis: {analysis.get('analysis', 'No analysis available')}

Provide investment advice based on this data. Focus on:
1. Current market position
2. Technical indicators
3. Investment recommendation (buy/hold/sell)
4. Risk factors

DO NOT provide shopping links or product information."""
            else:
                prompt = f"""{query_classifier.get_routing_instructions('investment')}

User Question: {request.message}

Conversation History:
{_format_history(conversation_history)}

Provide investment advice and analysis."""
        
        elif category == 'shopping':
            # Route to shopping service
            from app.services.shopping_service import get_shopping_service
            
            shopping_service = get_shopping_service()
            search_results = await shopping_service.smart_search(request.message)
            
            prompt = f"""{query_classifier.get_routing_instructions('shopping')}

User Question: {request.message}

Available Products:
{json.dumps(search_results, indent=2)}

Provide shopping recommendations with actual product links and prices.
DO NOT provide investment advice."""
        
        elif category == 'travel':
            # Route to travel service
            prompt = f"""{query_classifier.get_routing_instructions('travel')}

User Question: {request.message}

Provide travel recommendations and booking information."""
        
        else:
            # General query
            prompt = f"""{query_classifier.get_routing_instructions('general')}

User Question: {request.message}

Conversation History:
{_format_history(conversation_history)}

Provide a helpful response."""
        
        # Call Ollama via shared client (cached, routed to fast model)
        ai_response = await llm_generate(
            prompt, task="assistant", temperature=0.7,
            max_tokens=800, timeout=60,
        )

        if ai_response:
            # Save messages to database
            await _save_message(db, session_id, request.user_id, "user", request.message)
            await _save_message(db, session_id, request.user_id, "assistant", ai_response,
                               metadata=json.dumps(classification))

            return ChatResponse(
                response=ai_response,
                context_used=bool(request.context),
                session_id=session_id,
                category=category,
                confidence=confidence
            )
        else:
            logger.error("Ollama returned empty response")
            raise HTTPException(
                status_code=500,
                detail="AI service error: empty response"
            )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat: {str(e)}"
        )


async def _load_conversation_history(db: AsyncSession, session_id: str, limit: int = 10) -> List[Dict]:
    """Load recent conversation history from database."""
    try:
        result = await db.execute(
            select(ChatMessageDB)
            .filter(ChatMessageDB.session_id == session_id)
            .order_by(ChatMessageDB.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in reversed(messages)
        ]
    except Exception as e:
        logger.error(f"Failed to load conversation history: {e}")
        return []


async def _save_message(db: AsyncSession, session_id: str, user_id: str, 
                       role: str, content: str, metadata: str = None):
    """Save a chat message to database."""
    try:
        message = ChatMessageDB(
            session_id=session_id,
            role=role,
            content=content,
            msg_metadata=metadata
        )
        db.add(message)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        await db.rollback()


def _format_history(history: List[Dict]) -> str:
    """Format conversation history for prompt."""
    if not history:
        return "No previous conversation."
    
    formatted = []
    for msg in history[-5:]:  # Last 5 messages
        role = msg['role'].capitalize()
        content = msg['content'][:200]  # Truncate long messages
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


@router.get("/sessions/{user_id}")
async def get_user_sessions(user_id: str, db: AsyncSession = Depends(get_session)):
    """Get all chat sessions for a user."""
    try:
        result = await db.execute(
            select(ChatSessionDB)
            .filter(ChatSessionDB.user_id == user_id)
            .order_by(ChatSessionDB.updated_at.desc())
        )
        sessions = result.scalars().all()
        
        return {
            "success": True,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                }
                for s in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: AsyncSession = Depends(get_session)):
    """Get all messages for a session."""
    try:
        messages = await _load_conversation_history(db, session_id, limit=100)
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_session)):
    """Delete a chat session and all its messages."""
    try:
        # Delete messages
        await db.execute(
            ChatMessageDB.__table__.delete().where(ChatMessageDB.session_id == session_id)
        )
        
        # Delete session
        await db.execute(
            ChatSessionDB.__table__.delete().where(ChatSessionDB.session_id == session_id)
        )
        
        await db.commit()
        
        return {"success": True, "message": "Session deleted"}
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Check if assistant service is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "ollama_available": True,
                    "model": settings.ollama_model
                }
            else:
                return {
                    "status": "degraded",
                    "ollama_available": False,
                    "error": "Ollama not responding"
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "ollama_available": False,
            "error": str(e)
        }
