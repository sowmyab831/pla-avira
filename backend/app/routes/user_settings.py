"""
User Settings and Feature Toggle Routes
Controls which features are visible/enabled for each user.

Ownership: the principal is always derived from the Bearer token. The `user_id`
path segment is kept for URL compatibility but must equal the authenticated
user (or the caller must be an admin for read-only access). Browser-supplied
identity is never trusted.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, UserFeatureSettingsDB, get_session
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_FEATURES = [
    "show_investing", "show_travel", "show_shopping", "show_weather",
    "show_health", "show_calendar", "show_tasks", "show_grocery", "show_documents",
]


class FeatureSettings(BaseModel):
    """User feature toggle settings."""
    show_investing: bool = True
    show_travel: bool = True
    show_shopping: bool = True
    show_weather: bool = True
    show_health: bool = True
    show_calendar: bool = True
    show_tasks: bool = True
    show_grocery: bool = True
    show_documents: bool = True
    default_currency: str = "USD"
    temperature_unit: str = "F"
    theme: str = "dark"


class FeatureSettingsResponse(BaseModel):
    success: bool
    settings: Optional[FeatureSettings] = None
    error: Optional[str] = None


def _authorize(path_user_id: str, current: UserDB, *, write: bool) -> str:
    """Return the effective user id or raise 403."""
    if path_user_id in ("me", current.user_id):
        return current.user_id
    if not write and current.role == "admin":
        return path_user_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this user")


async def _load(db: AsyncSession, user_id: str) -> Optional[UserFeatureSettingsDB]:
    result = await db.execute(select(UserFeatureSettingsDB).filter(UserFeatureSettingsDB.user_id == user_id))
    return result.scalar_one_or_none()


def _to_model(row: UserFeatureSettingsDB) -> FeatureSettings:
    return FeatureSettings(**{f: getattr(row, f) for f in FeatureSettings.model_fields})


@router.get("/features/{user_id}", response_model=FeatureSettingsResponse)
async def get_user_features(
    user_id: str,
    current: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    uid = _authorize(user_id, current, write=False)
    row = await _load(db, uid)
    return FeatureSettingsResponse(success=True, settings=_to_model(row) if row else FeatureSettings())


@router.put("/features/{user_id}")
async def update_user_features(
    user_id: str,
    settings: FeatureSettings,
    current: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    uid = _authorize(user_id, current, write=True)
    row = await _load(db, uid)
    if row is None:
        row = UserFeatureSettingsDB(user_id=uid)
        db.add(row)
    for field, value in settings.model_dump().items():
        setattr(row, field, value)
    row.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "message": "Settings updated", "settings": settings.model_dump()}


@router.post("/features/{user_id}/toggle")
async def toggle_feature(
    user_id: str,
    feature: str,
    enabled: bool,
    current: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if feature not in VALID_FEATURES:
        raise HTTPException(status_code=400, detail=f"Invalid feature. Valid: {VALID_FEATURES}")
    uid = _authorize(user_id, current, write=True)
    row = await _load(db, uid)
    if row is None:
        row = UserFeatureSettingsDB(user_id=uid)
        db.add(row)
    setattr(row, feature, enabled)
    row.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "feature": feature, "enabled": enabled}


@router.get("/features/{user_id}/sync")
async def sync_features_for_mobile(
    user_id: str,
    current: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Settings formatted for mobile tab sync."""
    uid = _authorize(user_id, current, write=False)
    row = await _load(db, uid)
    model = _to_model(row) if row else FeatureSettings()
    labels = {
        "investing": ("trending-up", "Investing"), "travel": ("airplane", "Travel"),
        "shopping": ("cart", "Shopping"), "weather": ("cloud", "Weather"),
        "health": ("heart", "Health"), "calendar": ("calendar", "Calendar"),
        "tasks": ("check-square", "Tasks"), "grocery": ("shopping-bag", "Grocery"),
        "documents": ("file-text", "Documents"),
    }
    features = {
        k: {"enabled": getattr(model, f"show_{k}"), "icon": icon, "label": label}
        for k, (icon, label) in labels.items()
    }
    return {
        "success": True,
        "user_id": uid,
        "features": features,
        "preferences": {
            "currency": model.default_currency,
            "temperature_unit": model.temperature_unit,
            "theme": model.theme,
        },
        "active_tabs": [k for k, v in features.items() if v["enabled"]],
    }
