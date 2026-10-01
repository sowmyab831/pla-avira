"""Daily life management models - chores, tasks, habits."""
from datetime import datetime, date, time
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task status."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Task or chore."""
    task_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    category: str  # chore, errand, work, personal, etc.
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    estimated_duration_minutes: Optional[int] = None
    assigned_to: Optional[str] = None  # family_member_id
    recurring: bool = False
    recurrence_pattern: Optional[str] = None  # daily, weekly, monthly
    tags: List[str] = []
    created_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None


class Chore(BaseModel):
    """Household chore."""
    chore_id: str
    family_id: str
    title: str
    description: Optional[str] = None
    assigned_to: str  # family_member_id
    frequency: str  # daily, weekly, biweekly, monthly
    last_completed: Optional[date] = None
    next_due: date
    estimated_duration_minutes: int
    points: int = 0  # gamification
    completed_count: int = 0


class Errand(BaseModel):
    """Shopping errand or task."""
    errand_id: str
    user_id: str
    title: str
    location: str
    address: Optional[str] = None
    items: List[str] = []
    estimated_cost: Optional[float] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[date] = None
    completed: bool = False
    notes: Optional[str] = None


class ErrandRoute(BaseModel):
    """Optimized errand route."""
    route_id: str
    user_id: str
    errands: List[Errand]
    optimized_order: List[str]  # errand_ids in optimal order
    total_distance_miles: float
    estimated_time_minutes: int
    map_url: Optional[str] = None
    created_date: datetime


class Habit(BaseModel):
    """Habit tracking."""
    habit_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    category: str  # health, productivity, learning, etc.
    frequency_goal: str  # daily, 3x_week, weekly, etc.
    target_count: int = 7  # per week/month, default to daily (7 per week)
    current_streak: int = 0
    longest_streak: int = 0
    total_completions: int = 0
    start_date: date
    reminder_time: Optional[time] = None
    is_active: bool = True


class HabitLog(BaseModel):
    """Habit completion log."""
    log_id: str
    habit_id: str
    date: date
    completed: bool
    notes: Optional[str] = None
    mood: Optional[str] = None


class WeeklySchedule(BaseModel):
    """Weekly schedule overview."""
    user_id: str
    week_start: date
    week_end: date
    tasks: List[Task]
    chores: List[Chore]
    errands: List[Errand]
    habits: List[Habit]
    family_events: List[dict]
    total_estimated_hours: float
    completion_rate: float


class Reminder(BaseModel):
    """Reminder for tasks, events, etc."""
    reminder_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    reminder_date: date
    reminder_time: time
    related_to: Optional[str] = None  # task_id, event_id, etc.
    related_type: Optional[str] = None  # task, event, habit, etc.
    sent: bool = False
    recurring: bool = False
