"""Family dashboard and kids tracking models."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class ActivityType(str, Enum):
    """Types of activities."""
    SCHOOL = "school"
    SPORTS = "sports"
    MUSIC = "music"
    ART = "art"
    TUTORING = "tutoring"
    PLAYDATE = "playdate"
    EXTRACURRICULAR = "extracurricular"
    APPOINTMENT = "appointment"
    BIRTHDAY = "birthday"


class KidActivity(BaseModel):
    """Kid's activity."""
    activity_id: str
    kid_id: str
    title: str
    activity_type: ActivityType
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    recurring: bool = False
    recurrence_pattern: Optional[str] = None
    instructor: Optional[str] = None
    cost: Optional[float] = None
    completed: bool = False


class DevelopmentalMilestone(BaseModel):
    """Developmental milestone tracking."""
    milestone_id: str
    kid_id: str
    category: str  # academic, social, emotional, physical, creative
    skill: str
    description: str
    date_achieved: date
    notes: Optional[str] = None
    evidence: Optional[str] = None  # photo, video, document


class KidProfile(BaseModel):
    """Child profile."""
    kid_id: str
    family_id: str
    name: str
    date_of_birth: date
    age: int
    grade: Optional[str] = None
    school: Optional[str] = None
    interests: List[str] = []
    strengths: List[str] = []
    areas_for_growth: List[str] = []
    personality_traits: List[str] = []
    learning_style: Optional[str] = None


class WeeklyReport(BaseModel):
    """Weekly developmental report."""
    report_id: str
    kid_id: str
    week_start: date
    week_end: date
    activities_completed: int
    new_milestones: List[DevelopmentalMilestone]
    academic_progress: str
    social_emotional_notes: str
    physical_development: str
    recommendations: List[str]
    next_week_suggestions: List[str]


class FamilyMember(BaseModel):
    """Family member profile."""
    member_id: str
    family_id: str
    name: str
    role: str  # parent, child, guardian
    date_of_birth: date
    email: Optional[str] = None
    phone: Optional[str] = None
    preferences: dict = {}


class EmotionalCheckIn(BaseModel):
    """Daily emotional check-in."""
    checkin_id: str
    member_id: str
    date: date
    mood: str  # happy, sad, stressed, anxious, excited, tired, etc.
    mood_score: int  # 1-10
    stress_level: int  # 1-10
    energy_level: int  # 1-10
    notes: Optional[str] = None
    needs_support: bool = False
    support_type: Optional[str] = None


class FamilyEvent(BaseModel):
    """Family event."""
    event_id: str
    family_id: str
    title: str
    description: Optional[str] = None
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str]  # member_ids
    event_type: str  # meal, outing, celebration, appointment, etc.
    recurring: bool = False


class FamilyGoal(BaseModel):
    """Family goal."""
    goal_id: str
    family_id: str
    title: str
    description: str
    category: str  # financial, health, education, relationship, etc.
    target_date: date
    progress_percentage: int = 0
    milestones: List[dict] = []
    assigned_to: List[str] = []  # member_ids
    status: str = "active"  # active, completed, abandoned
