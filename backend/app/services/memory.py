"""Assistant memory — durable, user-scoped facts and notes.

Recall ranks by pinned-first, then token overlap, then recency. Deterministic
and privacy-safe: memory never leaves the local store and is always scoped to
the authenticated user.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete

from app.database import async_session_maker
from app.models.ops import MemoryItemDB

VALID_KINDS = {"note", "fact", "preference", "event", "capture"}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall((text or "").lower()))


async def add_memory(
    user_id: str,
    text: str,
    *,
    kind: str = "note",
    tags: Optional[List[str]] = None,
    source: str = "manual",
    pinned: bool = False,
) -> Dict[str, Any]:
    if kind not in VALID_KINDS:
        kind = "note"
    async with async_session_maker() as session:
        item = MemoryItemDB(
            user_id=user_id, kind=kind, text=text.strip(),
            tags=tags or [], source=source, pinned=pinned,
        )
        session.add(item)
        await session.commit()
        return _to_dict(item)


def _to_dict(item: MemoryItemDB) -> Dict[str, Any]:
    return {
        "id": item.id, "kind": item.kind, "text": item.text,
        "tags": item.tags or [], "source": item.source,
        "pinned": item.pinned,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def list_memories(
    user_id: str, *, kind: Optional[str] = None, limit: int = 100
) -> List[Dict[str, Any]]:
    async with async_session_maker() as session:
        q = select(MemoryItemDB).where(MemoryItemDB.user_id == user_id)
        if kind:
            q = q.where(MemoryItemDB.kind == kind)
        q = q.order_by(MemoryItemDB.pinned.desc(), MemoryItemDB.updated_at.desc()).limit(limit)
        return [_to_dict(r) for r in (await session.execute(q)).scalars().all()]


async def search(user_id: str, query: str, *, limit: int = 20) -> List[Dict[str, Any]]:
    items = await list_memories(user_id, limit=500)
    qt = _tokens(query)
    if not qt:
        return items[:limit]
    scored = []
    for it in items:
        overlap = len(qt & _tokens(it["text"] + " " + " ".join(it["tags"])))
        if overlap:
            scored.append((overlap, it))
    scored.sort(key=lambda s: (not s[1]["pinned"], -s[0], s[1]["updated_at"] or ""))
    return [it for _, it in scored[:limit]]


async def recall(user_id: str, context_query: str, *, limit: int = 5) -> List[str]:
    """Memory lines to inject into an LLM prompt. Pinned items always included."""
    pinned = [m for m in await list_memories(user_id, limit=200) if m["pinned"]]
    hits = [m for m in await search(user_id, context_query, limit=limit) if not m["pinned"]]
    seen, lines = set(), []
    for m in (pinned + hits)[:limit]:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        lines.append(f"[{m['kind']}] {m['text']}")
    return lines


async def update_memory(user_id: str, memory_id: str, **fields) -> Optional[Dict[str, Any]]:
    async with async_session_maker() as session:
        row = await session.execute(
            select(MemoryItemDB).where(
                MemoryItemDB.id == memory_id, MemoryItemDB.user_id == user_id
            )
        )
        item = row.scalar_one_or_none()
        if item is None:
            return None
        if "text" in fields and fields["text"]:
            item.text = fields["text"].strip()
        if "pinned" in fields:
            item.pinned = bool(fields["pinned"])
        if "tags" in fields and fields["tags"] is not None:
            item.tags = fields["tags"]
        if "kind" in fields and fields["kind"] in VALID_KINDS:
            item.kind = fields["kind"]
        item.updated_at = datetime.utcnow()
        await session.commit()
        return _to_dict(item)


async def delete_memory(user_id: str, memory_id: str) -> bool:
    async with async_session_maker() as session:
        res = await session.execute(
            delete(MemoryItemDB).where(
                MemoryItemDB.id == memory_id, MemoryItemDB.user_id == user_id
            )
        )
        await session.commit()
        return (res.rowcount or 0) > 0
