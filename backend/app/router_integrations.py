"""API routes for integrations (Gmail, etc.) - Simplified version."""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import uuid

from app.integrations.gmail import GmailIntegration
from app.integrations.email_analyzer import EmailAnalyzer

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Initialize integrations
import os
from app.config import settings

credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
# Use the actual backend port from config or default to 30000
backend_port = 30000
redirect_uri = f"http://localhost:{backend_port}/api/integrations/gmail/callback"

gmail = GmailIntegration(
    credentials_file=credentials_path,
    redirect_uri=redirect_uri
)
analyzer = EmailAnalyzer()

# In-memory storage for demo (replace with database later)
gmail_tokens = {}
action_items = {}
appointments = {}

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
    except (FileNotFoundError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth2 credentials are not configured. To connect Gmail, use the IMAP/app-password flow at /api/radar/accounts, or create a Google OAuth2 client and mount a credentials.json at /app/credentials.json."
        )
    except Exception as e:
        error_msg = str(e)
        if "Client secrets must be for a web or installed app" in error_msg or "invalid_client" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Gmail credentials not configured. Please create a Google OAuth2 client at https://console.cloud.google.com/ and update backend/credentials.json with your client_id and client_secret."
            )
        raise HTTPException(status_code=400, detail=error_msg)


@router.get("/gmail/callback")
async def gmail_callback(code: str, state: str):
    """Handle OAuth callback and store credentials."""
    try:
        tokens = gmail.get_access_token(code)
        gmail_tokens[DEFAULT_USER_ID] = tokens

        return {
            "success": True,
            "message": "Gmail connected successfully",
            "redirect": "/integrations?success=true"
        }
    except (FileNotFoundError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Gmail OAuth2 credentials are not configured. To connect Gmail, use the IMAP/app-password flow at /api/radar/accounts, or mount a valid credentials.json at /app/credentials.json."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Gmail Email Operations
# ============================================================================

@router.get("/gmail/emails")
async def get_gmail_emails(limit: int = Query(10, ge=1, le=50)):
    """Fetch unread emails from Gmail."""
    
    if DEFAULT_USER_ID not in gmail_tokens:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    
    try:
        tokens = gmail_tokens[DEFAULT_USER_ID]
        emails = await gmail.get_unread_emails(tokens['access_token'], limit)
        
        return {
            "success": True,
            "count": len(emails),
            "emails": emails
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gmail/analyze")
async def analyze_email(email_id: str):
    """Extract action items and dates from email."""
    
    if DEFAULT_USER_ID not in gmail_tokens:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    
    try:
        tokens = gmail_tokens[DEFAULT_USER_ID]
        emails = await gmail.get_unread_emails(tokens['access_token'], limit=50)
        email = next((e for e in emails if e['id'] == email_id), None)
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Analyze
        analysis = await analyzer.extract_action_items(email['body'], email['subject'])
        
        # Store action items in memory
        for item in analysis.get('action_items', []):
            item_id = str(uuid.uuid4())
            action_items[item_id] = {
                'id': item_id,
                'title': item,
                'description': email['subject'],
                'priority': analysis.get('priority', 'medium'),
                'is_completed': False,
                'created_at': datetime.utcnow().isoformat()
            }
        
        # Store appointments in memory
        for date_str in analysis.get('dates', []):
            try:
                appt_id = str(uuid.uuid4())
                appointments[appt_id] = {
                    'id': appt_id,
                    'title': email['subject'],
                    'date_time': date_str,
                    'description': email['body'][:200],
                    'created_at': datetime.utcnow().isoformat()
                }
            except Exception as e:
                print(f"Error parsing date {date_str}: {e}")
                continue
        
        return {
            "success": True,
            "analysis": analysis,
            "action_items_created": len(analysis.get('action_items', [])),
            "appointments_created": len(analysis.get('dates', []))
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Action Items
# ============================================================================

@router.get("/action-items")
async def get_action_items(status: str = Query("pending", regex="^(pending|completed|all)$")):
    """Get action items."""
    
    items = list(action_items.values())
    
    if status == "pending":
        items = [i for i in items if not i['is_completed']]
    elif status == "completed":
        items = [i for i in items if i['is_completed']]
    
    return {
        "success": True,
        "count": len(items),
        "items": items
    }


@router.post("/action-items/{item_id}/complete")
async def complete_action_item(item_id: str):
    """Mark action item as complete."""
    
    if item_id not in action_items:
        raise HTTPException(status_code=404, detail="Item not found")
    
    action_items[item_id]['is_completed'] = True
    
    return {
        "success": True,
        "message": "Item marked complete"
    }


# ============================================================================
# Appointments
# ============================================================================

@router.get("/appointments")
async def get_appointments(days: int = Query(30, ge=1, le=365)):
    """Get upcoming appointments."""
    
    return {
        "success": True,
        "count": len(appointments),
        "appointments": list(appointments.values())
    }


# ============================================================================
# Integration Status
# ============================================================================

@router.get("/gmail/status")
async def gmail_status():
    """Get Gmail integration status."""
    
    if DEFAULT_USER_ID not in gmail_tokens:
        return {
            "connected": False,
            "email": None,
            "last_sync": None
        }
    
    return {
        "connected": True,
        "email": "user@example.com",
        "last_sync": datetime.utcnow().isoformat()
    }


@router.post("/gmail/disconnect")
async def disconnect_gmail():
    """Disconnect Gmail integration."""
    
    if DEFAULT_USER_ID in gmail_tokens:
        del gmail_tokens[DEFAULT_USER_ID]
    
    return {
        "success": True,
        "message": "Gmail disconnected"
    }
