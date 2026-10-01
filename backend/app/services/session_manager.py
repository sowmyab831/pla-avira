"""
Session Manager - Persistent conversation sessions with context.

Features:
- Session-based message storage with full context
- 1000 session limit per user with LRU eviction
- Session resume capability
- Message history for context continuity
"""
import logging
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

MAX_SESSIONS_PER_USER = 1000
MAX_MESSAGES_PER_SESSION = 500


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Single message in a session."""
    role: MessageRole
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    masked_content: Optional[str] = None  # Content with PII masked
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "masked_content": self.masked_content,
        }


@dataclass
class Session:
    """Conversation session with full context."""
    session_id: str
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: List[Message] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)  # Shopping cart, travel prefs, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: MessageRole, content: str, masked_content: str = None, metadata: Dict = None):
        """Add a message to the session."""
        msg = Message(
            role=role,
            content=content,
            masked_content=masked_content,
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()
        
        # Trim if over limit
        if len(self.messages) > MAX_MESSAGES_PER_SESSION:
            self.messages = self.messages[-MAX_MESSAGES_PER_SESSION:]
    
    def get_context_window(self, last_n: int = 20) -> List[Dict]:
        """Get last N messages for LLM context."""
        return [m.to_dict() for m in self.messages[-last_n:]]
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "metadata": self.metadata,
            "message_count": len(self.messages),
        }


class SessionManager:
    """
    Manages user sessions with LRU eviction.
    
    In production, this would be backed by PostgreSQL/Redis.
    Currently uses in-memory storage for demo.
    """
    
    def __init__(self):
        # user_id -> OrderedDict[session_id -> Session] (LRU order)
        self._sessions: Dict[str, OrderedDict[str, Session]] = {}
        self._archived: Dict[str, List[Dict]] = {}  # Archived session summaries
    
    def create_session(self, user_id: str, session_id: str = None) -> Session:
        """Create a new session for a user."""
        if session_id is None:
            session_id = self._generate_session_id(user_id)
        
        session = Session(session_id=session_id, user_id=user_id)
        
        # Initialize user's session store if needed
        if user_id not in self._sessions:
            self._sessions[user_id] = OrderedDict()
        
        # Check session limit and evict if needed
        self._enforce_session_limit(user_id)
        
        # Add new session
        self._sessions[user_id][session_id] = session
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session
    
    def get_session(self, user_id: str, session_id: str) -> Optional[Session]:
        """Get a session by ID, moving it to end (most recent)."""
        if user_id not in self._sessions:
            return None
        
        if session_id not in self._sessions[user_id]:
            return None
        
        # Move to end (LRU)
        session = self._sessions[user_id].pop(session_id)
        self._sessions[user_id][session_id] = session
        
        return session
    
    def get_or_create_session(self, user_id: str, session_id: str) -> Session:
        """Get existing session or create new one."""
        session = self.get_session(user_id, session_id)
        if session is None:
            session = self.create_session(user_id, session_id)
        return session
    
    def list_sessions(self, user_id: str, limit: int = 50) -> List[Dict]:
        """List user's sessions (most recent first)."""
        if user_id not in self._sessions:
            return []
        
        sessions = list(self._sessions[user_id].values())
        sessions.reverse()  # Most recent first
        
        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "message_count": len(s.messages),
                "preview": s.messages[-1].content[:100] if s.messages else "",
            }
            for s in sessions[:limit]
        ]
    
    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session."""
        if user_id not in self._sessions:
            return False
        
        if session_id in self._sessions[user_id]:
            del self._sessions[user_id][session_id]
            logger.info(f"Deleted session {session_id}")
            return True
        
        return False
    
    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: MessageRole,
        content: str,
        masked_content: str = None,
        metadata: Dict = None,
    ) -> Session:
        """Add a message to a session."""
        session = self.get_or_create_session(user_id, session_id)
        session.add_message(role, content, masked_content, metadata)
        return session
    
    def update_context(self, user_id: str, session_id: str, context_update: Dict):
        """Update session context (shopping cart, preferences, etc.)."""
        session = self.get_session(user_id, session_id)
        if session:
            session.context.update(context_update)
            session.updated_at = datetime.now().isoformat()
    
    def _enforce_session_limit(self, user_id: str):
        """Evict oldest sessions if over limit."""
        if user_id not in self._sessions:
            return
        
        while len(self._sessions[user_id]) >= MAX_SESSIONS_PER_USER:
            # Pop oldest (first item in OrderedDict)
            oldest_id, oldest_session = self._sessions[user_id].popitem(last=False)
            
            # Archive summary
            if user_id not in self._archived:
                self._archived[user_id] = []
            
            self._archived[user_id].append({
                "session_id": oldest_id,
                "created_at": oldest_session.created_at,
                "archived_at": datetime.now().isoformat(),
                "message_count": len(oldest_session.messages),
            })
            
            logger.info(f"Evicted session {oldest_id} for user {user_id}")
    
    def _generate_session_id(self, user_id: str) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        data = f"{user_id}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """Get session manager statistics."""
        total_sessions = sum(len(s) for s in self._sessions.values())
        total_messages = sum(
            len(session.messages)
            for user_sessions in self._sessions.values()
            for session in user_sessions.values()
        )
        
        return {
            "total_users": len(self._sessions),
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "archived_sessions": sum(len(a) for a in self._archived.values()),
        }


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the singleton session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
