"""Family dashboard and kids tracking routes."""
import logging
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.family import (
    KidActivity, KidProfile, WeeklyReport, FamilyMember,
    EmotionalCheckIn, FamilyEvent, FamilyGoal, ActivityType
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/family", tags=["family"])

# In-memory storage (should be database)
kids_store: List[KidProfile] = []
activities_store: List[KidActivity] = []
checkins_store: List[EmotionalCheckIn] = []
events_store: List[FamilyEvent] = []


@router.post("/kids")
async def add_kid(kid: KidProfile):
    """Add child profile."""
    kids_store.append(kid)
    return {"success": True, "message": "Child profile created", "kid": kid}


@router.get("/kids")
async def get_kids(family_id: str = "default"):
    """Get all children in family."""
    family_kids = [k for k in kids_store if k.family_id == family_id]
    return {"success": True, "count": len(family_kids), "kids": family_kids}


@router.post("/activities")
async def add_activity(activity: KidActivity):
    """Add kid's activity."""
    activities_store.append(activity)
    return {"success": True, "message": "Activity added", "activity": activity}


@router.get("/activities")
async def get_activities(
    kid_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """Get activities for a kid."""
    activities = activities_store
    
    if kid_id:
        activities = [a for a in activities if a.kid_id == kid_id]
    
    if start_date:
        activities = [a for a in activities if a.date >= start_date]
    
    if end_date:
        activities = [a for a in activities if a.date <= end_date]
    
    return {"success": True, "count": len(activities), "activities": activities}


@router.post("/checkin")
async def emotional_checkin(checkin: EmotionalCheckIn):
    """Record emotional check-in."""
    checkins_store.append(checkin)
    
    # Check if support is needed
    alert = None
    if checkin.needs_support:
        alert = f"⚠️ {checkin.member_id} needs support: {checkin.support_type}"
    
    return {
        "success": True,
        "message": "Check-in recorded",
        "checkin": checkin,
        "alert": alert
    }


@router.get("/checkins")
async def get_checkins(member_id: str, days: int = 7):
    """Get emotional check-ins for a family member."""
    member_checkins = [c for c in checkins_store if c.member_id == member_id]
    
    # Sort by date
    member_checkins.sort(key=lambda c: c.date, reverse=True)
    
    return {
        "success": True,
        "member_id": member_id,
        "count": len(member_checkins),
        "checkins": member_checkins[:days]
    }


@router.post("/events")
async def add_family_event(event: FamilyEvent):
    """Add family event."""
    events_store.append(event)
    return {"success": True, "message": "Event added", "event": event}


@router.get("/events")
async def get_family_events(family_id: str = "default", upcoming: bool = True):
    """Get family events."""
    family_events = [e for e in events_store if e.family_id == family_id]
    
    if upcoming:
        today = date.today()
        family_events = [e for e in family_events if e.date >= today]
    
    family_events.sort(key=lambda e: e.date)
    
    return {"success": True, "count": len(family_events), "events": family_events}


@router.get("/dashboard")
async def get_family_dashboard(family_id: str = "default"):
    """Get complete family dashboard."""
    family_kids = [k for k in kids_store if k.family_id == family_id]
    upcoming_events = [e for e in events_store if e.family_id == family_id and e.date >= date.today()]
    recent_checkins = checkins_store[-7:] if checkins_store else []
    
    return {
        "success": True,
        "family_id": family_id,
        "kids": family_kids,
        "upcoming_events": upcoming_events[:5],
        "recent_checkins": recent_checkins,
        "needs_attention": [c for c in recent_checkins if c.needs_support]
    }


@router.get("/stats")
async def get_family_stats(family_id: str = "default"):
    """Get family statistics."""
    return {
        "success": True,
        "total_kids": len([k for k in kids_store if k.family_id == family_id]),
        "activities_this_week": len([a for a in activities_store if a.date >= date.today()]),
        "upcoming_events": len([e for e in events_store if e.date >= date.today()])
    }


# New Family Member Management Endpoints

@router.post("/members")
async def add_family_member(
    name: str,
    age: int,
    gender: str,
    birth_date: Optional[str] = None,
    relationship: str = "family",
    health_conditions: Optional[List[str]] = None,
    dietary_preferences: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
    user_id: str = "default"
):
    """Add family member with age/gender for personalized recommendations."""
    from app.services.family_service import get_family_service
    import uuid
    
    service = get_family_service()
    member_id = str(uuid.uuid4())
    
    result = service.add_member(
        member_id=member_id,
        name=name,
        age=age,
        gender=gender,
        birth_date=birth_date,
        relationship=relationship,
        health_conditions=health_conditions,
        dietary_preferences=dietary_preferences,
        interests=interests
    )
    
    return result


@router.get("/members")
async def get_family_members(user_id: str = "default"):
    """Get all family members."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    members = service.get_all_members(user_id)
    
    return {
        "success": True,
        "count": len(members),
        "members": members
    }


@router.get("/members/{member_id}")
async def get_family_member(member_id: str):
    """Get specific family member."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    member = service.get_member(member_id)
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    return {
        "success": True,
        "member": member
    }


@router.put("/members/{member_id}")
async def update_family_member(member_id: str, updates: dict):
    """Update family member."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    result = service.update_member(member_id, updates)
    
    return result


@router.delete("/members/{member_id}")
async def delete_family_member(member_id: str):
    """Delete family member."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    result = service.delete_member(member_id)
    
    return result


@router.get("/members/{member_id}/recommendations")
async def get_member_recommendations(member_id: str):
    """Get personalized recommendations for family member based on age/gender."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    result = service.get_recommendations_for_member(member_id)
    
    return result


@router.get("/wellness-score")
async def get_family_wellness_score(user_id: str = "default"):
    """Get overall family wellness score."""
    from app.services.family_service import get_family_service
    
    service = get_family_service()
    result = service.get_family_wellness_score(user_id)
    
    return result
