"""Task and habit management routes."""
import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete

from app.models.task import Task as TaskModel
from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Pydantic models for API
class TaskCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    category: str  # task, chore, habit
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    completed: Optional[bool] = None
    title: Optional[str] = None
    description: Optional[str] = None


@router.post("")
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_session)):
    """Create a new task."""
    try:
        db_task = TaskModel(
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            category=task.category,
            due_date=datetime.fromisoformat(task.due_date) if task.due_date else None
        )
        db.add(db_task)
        await db.commit()
        await db.refresh(db_task)
        return {"success": True, "message": "Task created", "task": db_task.to_dict()}
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_tasks(user_id: str = "default", db: AsyncSession = Depends(get_session)):
    """Get tasks for user."""
    try:
        result = await db.execute(
            select(TaskModel).filter(TaskModel.user_id == user_id).order_by(TaskModel.created_at.desc())
        )
        tasks = result.scalars().all()
        return {"success": True, "count": len(tasks), "tasks": [t.to_dict() for t in tasks]}
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return {"success": False, "tasks": [], "count": 0}


@router.patch("/{task_id}")
async def update_task(task_id: str, update: TaskUpdate, db: AsyncSession = Depends(get_session)):
    """Update task."""
    try:
        result = await db.execute(select(TaskModel).filter(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if update.completed is not None:
            task.completed = update.completed
        if update.title:
            task.title = update.title
        if update.description:
            task.description = update.description
        
        task.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(task)
        return {"success": True, "message": "Task updated", "task": task.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_session)):
    """Delete a task."""
    try:
        result = await db.execute(select(TaskModel).filter(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        await db.delete(task)
        await db.commit()
        return {"success": True, "message": "Task deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
