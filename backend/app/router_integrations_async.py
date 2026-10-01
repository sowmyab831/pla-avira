"""API routes for integrations (Gmail, etc.)."""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import os

from app.integrations.gmail import GmailIntegration
from app.integrations.email_analyzer import EmailAnalyzer
from app.models.email import EmailIntegration, ActionItem, Appointment
from app.database import get_session

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Initialize integrations
gmail = GmailIntegration(
    credentials_file="backend/credentials.json",
    redirect_uri="http://localhost:8000/api/integrations/gmail/callback"
)
analyzer = EmailAnalyzer()

# Default user ID for single-user mode
DEFAULT_USER_ID = "default-user"


# ============================================================================
# Gmail OAuth Flow
# ============================================================================

@router.get("/gmail/auth")
async def gmail_auth(state: str = ""):
    """Redirect to Gmail OAuth consent screen."""
    try:
        auth_url = gmail.get_auth_url(state or str(uuid.uuid4()))
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    db: Session = Depends(get_session)
):
    """Handle OAuth callback and store credentials."""
    try:
        # Exchange code for token
        tokens = gmail.get_access_token(code)
        
        # Check if integration already exists
        existing = db.query(EmailIntegration).filter(
            EmailIntegration.user_id == DEFAULT_USER_ID
        ).first()
        
        if existing:
            # Update existing
            existing.access_token = tokens['access_token']
            existing.refresh_token = tokens.get('refresh_token')
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            email_integration = EmailIntegration(
                id=str(uuid.uuid4()),
                user_id=DEFAULT_USER_ID,
                email="user@example.com",
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                is_active=True
            )
            db.add(email_integration)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Gmail connected successfully",
            "redirect": "/integrations?success=true"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Gmail Email Operations
# ============================================================================

@router.get("/gmail/emails")
async def get_gmail_emails(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_session)
):
    """Fetch unread emails from Gmail."""
    
    # Get user's Gmail integration
    integration = db.query(EmailIntegration).filter(
        EmailIntegration.user_id == DEFAULT_USER_ID
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    
    if not integration.is_active:
        raise HTTPException(status_code=403, detail="Gmail integration is disabled")
    
    try:
        # Fetch emails
        emails = await gmail.get_unread_emails(integration.access_token, limit)
        
        # Update last sync
        integration.last_sync = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gmail/analyze")
async def analyze_email(
    email_id: str,
    db: Session = Depends(get_session)
):
    """Extract action items and dates from email."""
    
    # Get user's Gmail integration
    integration = db.query(EmailIntegration).filter(
        EmailIntegration.user_id == DEFAULT_USER_ID
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    
    try:
        # Fetch emails
        emails = await gmail.get_unread_emails(integration.access_token, limit=50)
        email = next((e for e in emails if e['id'] == email_id), None)
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Analyze
        analysis = await analyzer.extract_action_items(email['body'], email['subject'])
        
        # Store action items
        action_items_created = 0
        for item in analysis.get('action_items', []):
            action_item = ActionItem(
                id=str(uuid.uuid4()),
                user_id=DEFAULT_USER_ID,
                email_id=email_id,
                title=item,
                description=email['subject'],
                priority=analysis.get('priority', 'medium'),
                source='gmail'
            )
            db.add(action_item)
            action_items_created += 1
        
        # Store appointments
        appointments_created = 0
        for date_str in analysis.get('dates', []):
            try:
                date_obj = datetime.fromisoformat(date_str)
                appointment = Appointment(
                    id=str(uuid.uuid4()),
                    user_id=DEFAULT_USER_ID,
                    title=email['subject'],
                    date_time=date_obj,
                    description=email['body'][:200],
                    source='gmail'
                )
                db.add(appointment)
                appointments_created += 1
            except Exception as e:
                print(f"Error parsing date {date_str}: {e}")
                continue
        
        db.commit()
        
        return {
            "success": True,
            "analysis": analysis,
            "action_items_created": action_items_created,
            "appointments_created": appointments_created
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Action Items
# ============================================================================

@router.get("/action-items")
async def get_action_items(
    status: str = Query("pending", regex="^(pending|completed|all)$"),
    db: Session = Depends(get_session)
):
    """Get action items for current user."""
    
    query = db.query(ActionItem).filter(ActionItem.user_id == DEFAULT_USER_ID)
    
    if status == "pending":
        query = query.filter(ActionItem.is_completed == False)
    elif status == "completed":
        query = query.filter(ActionItem.is_completed == True)
    
    items = query.order_by(ActionItem.due_date).all()
    
    return {
        "success": True,
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "due_date": item.due_date.isoformat() if item.due_date else None,
                "priority": item.priority,
                "is_completed": item.is_completed,
                "source": item.source,
                "created_at": item.created_at.isoformat()
            }
            for item in items
        ]
    }


@router.post("/action-items/{item_id}/complete")
async def complete_action_item(
    item_id: str,
    db: Session = Depends(get_session)
):
    """Mark action item as complete."""
    
    item = db.query(ActionItem).filter(
        ActionItem.id == item_id,
        ActionItem.user_id == DEFAULT_USER_ID
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    try:
        item.is_completed = True
        item.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Item marked complete"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Appointments
# ============================================================================

@router.get("/appointments")
async def get_appointments(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session)
):
    """Get upcoming appointments for current user."""
    
    now = datetime.utcnow()
    future = now + timedelta(days=days)
    
    appointments = db.query(Appointment).filter(
        Appointment.user_id == DEFAULT_USER_ID,
        Appointment.date_time >= now,
        Appointment.date_time <= future
    ).order_by(Appointment.date_time).all()
    
    return {
        "success": True,
        "count": len(appointments),
        "appointments": [
            {
                "id": appt.id,
                "title": appt.title,
                "date_time": appt.date_time.isoformat(),
                "location": appt.location,
                "description": appt.description,
                "source": appt.source,
                "created_at": appt.created_at.isoformat()
            }
            for appt in appointments
        ]
    }


# ============================================================================
# Integration Status
# ============================================================================

@router.get("/gmail/status")
async def gmail_status(
    db: Session = Depends(get_session)
):
    """Get Gmail integration status."""
    
    integration = db.query(EmailIntegration).filter(
        EmailIntegration.user_id == DEFAULT_USER_ID
    ).first()
    
    if not integration:
        return {
            "connected": False,
            "email": None,
            "last_sync": None
        }
    
    return {
        "connected": integration.is_active,
        "email": integration.email,
        "last_sync": integration.last_sync.isoformat() if integration.last_sync else None
    }


@router.post("/gmail/disconnect")
async def disconnect_gmail(
    db: Session = Depends(get_session)
):
    """Disconnect Gmail integration."""
    
    integration = db.query(EmailIntegration).filter(
        EmailIntegration.user_id == DEFAULT_USER_ID
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    
    try:
        integration.is_active = False
        integration.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Gmail disconnected"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
