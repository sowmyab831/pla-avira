"""
Chat Session Service - Manages AI assistant chat sessions with database persistence
"""
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import ChatSessionDB, ChatMessageDB

logger = logging.getLogger(__name__)


class ChatSessionService:
    """
    Chat session management service with:
    - Session creation and retrieval
    - Message history persistence
    - Multiple concurrent sessions per user
    - Session context management
    """
    
    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new chat session."""
        
        session_id = str(uuid.uuid4())
        
        session = ChatSessionDB(
            session_id=session_id,
            user_id=user_id,
            title=title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            is_active=True
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        logger.info(f"Created chat session {session_id} for user {user_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat()
        }
    
    async def get_session(
        self,
        db: AsyncSession,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get session details."""
        
        result = await db.execute(
            select(ChatSessionDB).where(ChatSessionDB.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "is_active": session.is_active
        }
    
    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """List all sessions for a user."""
        
        query = select(ChatSessionDB).where(ChatSessionDB.user_id == user_id)
        
        if active_only:
            query = query.where(ChatSessionDB.is_active == True)
        
        query = query.order_by(ChatSessionDB.updated_at.desc())
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        return [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "is_active": s.is_active
            }
            for s in sessions
        ]
    
    async def add_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a message to a session."""
        
        message = ChatMessageDB(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata
        )
        
        db.add(message)
        
        # Update session updated_at timestamp
        await db.execute(
            update(ChatSessionDB)
            .where(ChatSessionDB.session_id == session_id)
            .values(updated_at=datetime.utcnow())
        )
        
        await db.commit()
        await db.refresh(message)
        
        return {
            "success": True,
            "message_id": message.id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": message.created_at.isoformat()
        }
    
    async def get_messages(
        self,
        db: AsyncSession,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get message history for a session."""
        
        query = (
            select(ChatMessageDB)
            .where(ChatMessageDB.session_id == session_id)
            .order_by(ChatMessageDB.created_at.asc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.msg_metadata
            }
            for m in messages
        ]
    
    async def update_session_title(
        self,
        db: AsyncSession,
        session_id: str,
        title: str
    ) -> Dict[str, Any]:
        """Update session title."""
        
        await db.execute(
            update(ChatSessionDB)
            .where(ChatSessionDB.session_id == session_id)
            .values(title=title, updated_at=datetime.utcnow())
        )
        
        await db.commit()
        
        return {
            "success": True,
            "session_id": session_id,
            "title": title
        }
    
    async def deactivate_session(
        self,
        db: AsyncSession,
        session_id: str
    ) -> Dict[str, Any]:
        """Deactivate a session (soft delete)."""
        
        await db.execute(
            update(ChatSessionDB)
            .where(ChatSessionDB.session_id == session_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        
        await db.commit()
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Session deactivated"
        }
    
    async def get_session_context(
        self,
        db: AsyncSession,
        session_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """Get recent messages as context for AI."""
        
        messages = await self.get_messages(db, session_id, limit=max_messages)
        
        # Format for AI context
        return [
            {
                "role": m["role"],
                "content": m["content"]
            }
            for m in messages
        ]


# Singleton instance
_chat_session_service: Optional[ChatSessionService] = None


def get_chat_session_service() -> ChatSessionService:
    """Get chat session service instance."""
    global _chat_session_service
    if _chat_session_service is None:
        _chat_session_service = ChatSessionService()
    return _chat_session_service
