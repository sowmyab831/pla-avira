"""Memory + capture API (R2). All rows strictly scoped to the JWT principal."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import UserDB
from app.routes.auth import get_current_user
from app.services import memory as mem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["memory"])


class MemoryCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    kind: str = Field("note", max_length=32)
    tags: List[str] = Field(default_factory=list, max_length=20)
    pinned: bool = False


class MemoryPatch(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=4000)
    kind: Optional[str] = Field(None, max_length=32)
    tags: Optional[List[str]] = None
    pinned: Optional[bool] = None


@router.post("/memory")
async def create_memory(req: MemoryCreate, user: UserDB = Depends(get_current_user)):
    return {"success": True, "item": await mem.add_memory(
        user.user_id, req.text, kind=req.kind, tags=req.tags,
        source="manual", pinned=req.pinned,
    )}


@router.get("/memory")
async def list_memory(
    kind: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500),
    user: UserDB = Depends(get_current_user),
):
    items = await mem.list_memories(user.user_id, kind=kind, limit=limit)
    return {"success": True, "items": items, "count": len(items)}


@router.get("/memory/search")
async def search_memory(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=100),
    user: UserDB = Depends(get_current_user),
):
    items = await mem.search(user.user_id, q, limit=limit)
    return {"success": True, "items": items, "count": len(items)}


@router.patch("/memory/{memory_id}")
async def patch_memory(memory_id: str, req: MemoryPatch, user: UserDB = Depends(get_current_user)):
    item = await mem.update_memory(user.user_id, memory_id, **req.dict(exclude_unset=True))
    if item is None:
        raise HTTPException(404, "Memory not found")
    return {"success": True, "item": item}


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, user: UserDB = Depends(get_current_user)):
    if not await mem.delete_memory(user.user_id, memory_id):
        raise HTTPException(404, "Memory not found")
    return {"success": True, "deleted": memory_id}


class CaptureRequest(BaseModel):
    """Quick capture: a note/url/thought that lands in memory as kind='capture'."""
    text: str = Field(..., min_length=1, max_length=8000)
    tags: List[str] = Field(default_factory=list, max_length=20)


@router.post("/capture")
async def capture(req: CaptureRequest, user: UserDB = Depends(get_current_user)):
    item = await mem.add_memory(
        user.user_id, req.text, kind="capture", tags=req.tags, source="capture",
    )
    return {"success": True, "item": item}


@router.get("/capture")
async def list_captures(limit: int = Query(50, ge=1, le=200), user: UserDB = Depends(get_current_user)):
    items = await mem.list_memories(user.user_id, kind="capture", limit=limit)
    return {"success": True, "items": items, "count": len(items)}
