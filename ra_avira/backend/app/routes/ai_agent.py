"""
AI Agent Routes
Conversational AI buyer assistant API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from app.services.ai_buyer_agent import ai_buyer_agent

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


class ChatRequest(BaseModel):
    message: str
    user_id: str = "demo"
    language: str = "auto"  # auto, te, en, hi
    conversation_id: Optional[str] = None


class VoiceRequest(BaseModel):
    user_id: str = "demo"
    language: str = "auto"


@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message to the AI buyer agent."""
    result = await ai_buyer_agent.chat(
        user_id=request.user_id,
        message=request.message,
        language=request.language,
    )
    return result


@router.post("/voice")
async def voice_chat(
    audio: UploadFile = File(...),
    user_id: str = "demo",
    language: str = "auto",
):
    """Send voice message to AI agent. Transcribes and responds."""
    # In production: Whisper transcription → AI agent → TTS response
    audio_bytes = await audio.read()
    
    return {
        "transcription": "Voice processing requires Whisper integration",
        "response": "Voice assistant is being set up. Please use text chat for now.",
        "language": language,
        "audio_response_url": None,
    }


@router.post("/reset")
async def reset_conversation(user_id: str = "demo"):
    """Reset conversation context for a user."""
    ai_buyer_agent.reset_context(user_id)
    return {"reset": True, "user_id": user_id}


@router.get("/context/{user_id}")
async def get_user_context(user_id: str):
    """Get current conversation context and extracted preferences."""
    ctx = ai_buyer_agent.contexts.get(user_id)
    if not ctx:
        return {"exists": False, "profile": None}
    
    return {
        "exists": True,
        "state": ctx.state.value,
        "profile": ai_buyer_agent._profile_to_dict(ctx.profile),
        "message_count": len(ctx.history),
    }


@router.get("/suggestions/{user_id}")
async def get_suggestions(user_id: str):
    """Get contextual suggestions for the user based on conversation."""
    ctx = ai_buyer_agent.contexts.get(user_id)
    
    if not ctx:
        return {
            "suggestions": [
                "I'm looking for a 3BHK in Gachibowli under 2 crore",
                "Anna, Kokapet lo villa kavali",
                "What's the best area for investment in Hyderabad?",
                "Show me apartments near metro stations",
            ]
        }
    
    # Context-aware suggestions
    profile = ctx.profile
    suggestions = []
    
    if not profile.budget_max:
        suggestions.append("My budget is 1.5 crore")
        suggestions.append("నా బడ్జెట్ 2 కోట్లు")
    elif not profile.preferred_areas:
        suggestions.append("I prefer Gachibowli or Kokapet")
        suggestions.append("Financial District లో చూడాలి")
    elif not profile.bedrooms:
        suggestions.append("3 BHK apartment")
        suggestions.append("4 BHK villa with garden")
    else:
        suggestions.append("Show me the best options")
        suggestions.append("What about investment potential?")
        suggestions.append("Any legal risks I should know?")
        suggestions.append("Compare top 3 properties")
    
    return {"suggestions": suggestions}
