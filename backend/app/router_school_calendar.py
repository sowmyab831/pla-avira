"""API routes for school and calendar integrations."""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from datetime import datetime, timedelta
from typing import Optional
import uuid
import io
import re

from app.integrations.schoology import SchoologyIntegration
from app.integrations.calendar import CalendarIntegration, EventType, SCHOOL_CALENDARS
from app.services.file_storage import get_file_storage

router = APIRouter(prefix="/api", tags=["school", "calendar"])

# Initialize integrations
schoology = SchoologyIntegration(
    client_id="your_schoology_client_id",
    client_secret="your_schoology_client_secret",
    redirect_uri="http://localhost:8000/api/school/schoology/callback"
)

calendar = CalendarIntegration()

# In-memory storage for demo
schoology_tokens = {}
calendar_events = []

DEFAULT_USER_ID = "default-user"


# ============================================================================
# School - Schoology Integration
# ============================================================================

@router.get("/school/schoology/auth")
async def schoology_auth(state: str = ""):
    """Redirect to Schoology OAuth consent screen."""
    try:
        auth_url = schoology.get_auth_url(state or str(uuid.uuid4()))
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/school/schoology/callback")
async def schoology_callback(code: str, state: str):
    """Handle Schoology OAuth callback."""
    try:
        tokens = schoology.get_access_token(code)
        schoology_tokens[DEFAULT_USER_ID] = tokens
        
        return {
            "success": True,
            "message": "Schoology connected successfully",
            "redirect": "/school?success=true"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/school/schoology/courses")
async def get_schoology_courses():
    """Get user's Schoology courses."""
    if DEFAULT_USER_ID not in schoology_tokens:
        raise HTTPException(status_code=404, detail="Schoology not connected")
    
    try:
        tokens = schoology_tokens[DEFAULT_USER_ID]
        courses = await schoology.get_courses(tokens['access_token'])
        
        return {
            "success": True,
            "count": len(courses),
            "courses": courses
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/school/schoology/assignments")
async def get_schoology_assignments(course_id: str):
    """Get assignments for a course."""
    if DEFAULT_USER_ID not in schoology_tokens:
        raise HTTPException(status_code=404, detail="Schoology not connected")
    
    try:
        tokens = schoology_tokens[DEFAULT_USER_ID]
        assignments = await schoology.get_assignments(tokens['access_token'], course_id)
        
        return {
            "success": True,
            "count": len(assignments),
            "assignments": assignments
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/school/schoology/status")
async def schoology_status():
    """Check Schoology connection status."""
    if DEFAULT_USER_ID not in schoology_tokens:
        return {
            "connected": False,
            "name": None,
            "last_sync": None
        }
    
    return {
        "connected": True,
        "name": "Schoology",
        "last_sync": datetime.utcnow().isoformat()
    }


@router.post("/school/schoology/disconnect")
async def disconnect_schoology():
    """Disconnect Schoology."""
    if DEFAULT_USER_ID in schoology_tokens:
        del schoology_tokens[DEFAULT_USER_ID]
    
    return {
        "success": True,
        "message": "Schoology disconnected"
    }


# ============================================================================
# Calendar - Events Management
# ============================================================================

@router.get("/calendar/events")
async def get_calendar_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_type: Optional[str] = None
):
    """Get calendar events."""
    
    if start_date and end_date:
        events = calendar.get_events_for_range(start_date, end_date)
    else:
        events = calendar.get_upcoming_events(days=90)
    
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    
    return {
        "success": True,
        "count": len(events),
        "events": events
    }


@router.post("/calendar/events")
async def create_calendar_event(
    date: str,
    title: str,
    event_type: str = "custom",
    description: str = "",
    time: Optional[str] = None
):
    """Create a new calendar event."""
    
    try:
        event_type_enum = EventType(event_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
    
    try:
        event = calendar.add_event(
            date=date,
            title=title,
            event_type=event_type_enum,
            description=description,
            time=time
        )
        
        return {
            "success": True,
            "message": "Event created",
            "event": event
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calendar/events/{date}")
async def get_events_for_date(date: str):
    """Get events for a specific date."""
    
    events = calendar.get_events_for_date(date)
    
    return {
        "success": True,
        "date": date,
        "count": len(events),
        "events": events
    }


@router.get("/calendar/upcoming")
async def get_upcoming_events(days: int = Query(30, ge=1, le=365)):
    """Get upcoming events."""
    
    events = calendar.get_upcoming_events(days=days)
    
    return {
        "success": True,
        "days": days,
        "count": len(events),
        "events": events
    }


# ============================================================================
# Calendar - School Calendar Sync
# ============================================================================

@router.get("/calendar/schools")
async def get_available_schools():
    """Get list of available school calendars."""
    
    schools = [
        {
            "id": key,
            "name": value["name"],
            "type": value["type"]
        }
        for key, value in SCHOOL_CALENDARS.items()
    ]
    
    return {
        "success": True,
        "count": len(schools),
        "schools": schools
    }


@router.post("/calendar/sync-school")
async def sync_school_calendar(school_id: str):
    """Sync a school calendar."""
    
    if school_id not in SCHOOL_CALENDARS:
        raise HTTPException(status_code=404, detail=f"School not found: {school_id}")
    
    school = SCHOOL_CALENDARS[school_id]
    
    try:
        if school["type"] == "google_sheets":
            events = await calendar.parse_google_sheets_calendar(school["calendar_url"])
        elif school["type"] == "pdf":
            events = await calendar.parse_pdf_calendar(school["calendar_url"])
        else:
            raise HTTPException(status_code=400, detail=f"Unknown calendar type: {school['type']}")
        
        calendar.merge_events(events)
        
        return {
            "success": True,
            "school": school["name"],
            "events_synced": len(events),
            "message": f"Synced {len(events)} events from {school['name']}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calendar/sync-all-schools")
async def sync_all_schools():
    """Sync all school calendars."""
    
    total_events = 0
    results = []
    
    for school_id, school in SCHOOL_CALENDARS.items():
        try:
            if school["type"] == "google_sheets":
                events = await calendar.parse_google_sheets_calendar(school["calendar_url"])
            elif school["type"] == "pdf":
                events = await calendar.parse_pdf_calendar(school["calendar_url"])
            else:
                continue
            
            calendar.merge_events(events)
            total_events += len(events)
            
            results.append({
                "school": school["name"],
                "events": len(events),
                "status": "success"
            })
        except Exception as e:
            results.append({
                "school": school["name"],
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "success": True,
        "total_events_synced": total_events,
        "results": results
    }


# ============================================================================
# Calendar - Holiday/Break Management
# ============================================================================

@router.get("/calendar/holidays")
async def get_holidays(year: Optional[int] = None):
    """Get holidays and breaks."""
    
    if not year:
        year = datetime.now().year
    
    events = [
        e for e in calendar.events
        if e["type"] in ["holiday", "break"] and e["date"].startswith(str(year))
    ]
    
    return {
        "success": True,
        "year": year,
        "count": len(events),
        "events": events
    }


@router.post("/calendar/holidays")
async def add_holiday(
    date: str,
    name: str,
    description: str = ""
):
    """Add a holiday or break."""
    
    event = calendar.add_event(
        date=date,
        title=name,
        event_type=EventType.HOLIDAY,
        description=description
    )
    
    return {
        "success": True,
        "message": "Holiday added",
        "event": event
    }


# ============================================================================
# Calendar - Statistics
# ============================================================================

@router.get("/calendar/stats")
async def get_calendar_stats():
    """Get calendar statistics."""
    
    total_events = len(calendar.events)
    event_types = {}
    
    for event in calendar.events:
        event_type = event.get("type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    upcoming = calendar.get_upcoming_events(days=30)
    
    return {
        "success": True,
        "total_events": total_events,
        "event_types": event_types,
        "upcoming_30_days": len(upcoming),
        "sources": list(set(e.get("source", "unknown") for e in calendar.events))
    }


# ============================================================================
# Calendar - PDF Upload
# ============================================================================

@router.post("/calendar/upload-pdf")
async def upload_calendar_pdf(file: UploadFile = File(...), user_id: str = "default"):
    """Upload and parse a school calendar PDF or CSV."""
    
    try:
        # Read the uploaded file
        content = await file.read()
        
        # Save to persistent storage
        storage = get_file_storage()
        file_id = storage.save_file(
            file_content=content,
            filename=file.filename,
            category="school",
            user_id=user_id,
            metadata={"type": "school_calendar"}
        )
        
        events = []
        
        # Check file type
        if file.filename.endswith('.csv'):
            # Parse CSV calendar
            import pandas as pd
            csv_file = io.BytesIO(content)
            df = pd.read_csv(csv_file)
            
            # Extract events from CSV
            for idx, row in df.iterrows():
                # Skip header rows
                if idx < 2:
                    continue
                    
                event_name = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                if not event_name or event_name == "nan":
                    continue
                
                # Parse dates from columns
                for col_idx in range(1, len(row)):
                    date_str = str(row.iloc[col_idx])
                    if pd.notna(row.iloc[col_idx]) and date_str != "nan" and date_str.strip():
                        # Try to parse date
                        date_match = re.search(r'(\d{1,2})/(\d{1,2})', date_str)
                        if date_match:
                            month, day = date_match.groups()
                            year = "2025" if int(month) >= 9 else "2026"
                            event_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            
                            event = calendar.add_event(
                                date=event_date,
                                title=event_name,
                                event_type=EventType.TEST,
                                description=f"Grade level info: {date_str}",
                                source="csv_calendar"
                            )
                            events.append(event)
                            break
            
            return {
                "success": True,
                "filename": file.filename,
                "events_extracted": len(events),
                "message": f"Successfully extracted {len(events)} events from {file.filename}",
                "events": events[:10]
            }
        
        # Parse PDF calendar
        import pdfplumber
        pdf_file = io.BytesIO(content)
        
        events = []
        
        # Parse PDF with pdfplumber
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    # Extract dates and events from text
                    extracted = calendar._extract_dates_from_text(text)
                    events.extend(extracted)
        
        # Merge events into calendar
        calendar.merge_events(events)
        
        return {
            "success": True,
            "filename": file.filename,
            "events_extracted": len(events),
            "message": f"Successfully extracted {len(events)} events from {file.filename}",
            "events": events
        }
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="pdfplumber not installed. Install with: pip install pdfplumber"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")


# ============================================================================
# Calendar - Actionable Items
# ============================================================================

@router.post("/calendar/actionable-item")
async def add_actionable_item(
    date: str,
    time: Optional[str] = None,
    title: str = "",
    description: str = "",
    priority: str = "medium"
):
    """Add an actionable item to the calendar."""
    
    try:
        event = calendar.add_event(
            date=date,
            title=title or f"Action Item - {priority.upper()}",
            event_type=EventType.CUSTOM,
            description=description,
            time=time
        )
        
        # Add priority metadata
        event["priority"] = priority
        event["is_actionable"] = True
        
        return {
            "success": True,
            "message": "Actionable item added",
            "event": event
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calendar/actionable-items")
async def get_actionable_items(
    priority: Optional[str] = None,
    days: int = Query(30, ge=1, le=365)
):
    """Get all actionable items (upcoming)."""
    
    upcoming = calendar.get_upcoming_events(days=days)
    
    # Filter for actionable items
    actionable = [
        e for e in upcoming
        if e.get("is_actionable", False) or e.get("type") == "custom"
    ]
    
    if priority:
        actionable = [e for e in actionable if e.get("priority") == priority]
    
    return {
        "success": True,
        "count": len(actionable),
        "items": actionable
    }


# ============================================================================
# Calendar - CSV Upload
# ============================================================================

@router.post("/calendar/upload-csv")
async def upload_calendar_csv(file: UploadFile = File(...)):
    """Upload and parse a school calendar CSV file.
    
    Supports multiple formats:
    1. Standard: School,Date,Type,Description
    2. Table format: Event names in first column, dates in subsequent columns
    """
    import csv
    from datetime import datetime as dt
    
    try:
        content = await file.read()
        text = content.decode('utf-8')
        
        events = []
        lines = text.strip().split('\n')
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        
        # Try to detect format
        if len(rows) > 0 and 'School' in rows[0]:
            # Standard format with headers
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                school = row.get('School', '').strip()
                date_str = row.get('Date', '').strip()
                event_type = row.get('Type', '').strip()
                description = row.get('Description', '').strip()
                
                if not date_str:
                    continue
                
                # Handle date ranges
                if ' to ' in date_str:
                    start_str, end_str = date_str.split(' to ')
                    try:
                        start_date = dt.strptime(start_str.strip(), '%Y-%m-%d')
                        end_date = dt.strptime(end_str.strip(), '%Y-%m-%d')
                        current = start_date
                        while current <= end_date:
                            events.append({
                                "date": current.strftime('%Y-%m-%d'),
                                "title": f"{school}: {event_type}",
                                "type": _map_event_type(event_type),
                                "description": description,
                                "source": f"csv_{school.lower().replace(' ', '_')}",
                                "created_at": datetime.utcnow().isoformat()
                            })
                            current += timedelta(days=1)
                    except ValueError:
                        continue
                else:
                    try:
                        parsed_date = dt.strptime(date_str, '%Y-%m-%d')
                        events.append({
                            "date": parsed_date.strftime('%Y-%m-%d'),
                            "title": f"{school}: {event_type}",
                            "type": _map_event_type(event_type),
                            "description": description,
                            "source": f"csv_{school.lower().replace(' ', '_')}",
                            "created_at": datetime.utcnow().isoformat()
                        })
                    except ValueError:
                        continue
        else:
            # Table format - scan all cells for dates
            date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})|([A-Za-z]+)\s+(\d{4})|(\d{4})-(\d{1,2})-(\d{1,2})')
            
            for row_idx, row in enumerate(rows):
                if row_idx < 3:  # Skip first few header rows
                    continue
                    
                event_name = row[0].strip() if len(row) > 0 else ""
                if not event_name or event_name in ['Table', 'School', '']:
                    continue
                
                # Scan all columns for dates
                for col_idx, cell in enumerate(row[1:], 1):
                    cell = cell.strip()
                    if not cell or cell in ['N/A', 'TBD', '']:
                        continue
                    
                    # Try to extract dates
                    matches = date_pattern.findall(cell)
                    for match in matches:
                        try:
                            # Handle different date formats
                            if match[0] and match[1]:  # M/D format
                                month, day = int(match[0]), int(match[1])
                                year = 2025 if month >= 8 else 2026
                                event_date = dt(year, month, day)
                            elif match[2] and match[3]:  # Month YYYY format
                                month_name = match[2]
                                year = int(match[3])
                                month_map = {'January': 1, 'February': 2, 'March': 3, 'April': 4,
                                           'May': 5, 'June': 6, 'July': 7, 'August': 8,
                                           'September': 9, 'October': 10, 'November': 11, 'December': 12}
                                month = month_map.get(month_name, 1)
                                event_date = dt(year, month, 1)
                            elif match[4] and match[5]:  # YYYY-MM-DD format
                                year, month, day = int(match[4]), int(match[5]), int(match[6])
                                event_date = dt(year, month, day)
                            else:
                                continue
                            
                            events.append({
                                "date": event_date.strftime('%Y-%m-%d'),
                                "title": event_name,
                                "type": _map_event_type(event_name),
                                "description": cell,
                                "source": "csv_table",
                                "created_at": datetime.utcnow().isoformat()
                            })
                        except (ValueError, KeyError):
                            continue
        
        # Merge events into calendar
        calendar.merge_events(events)
        
        return {
            "success": True,
            "filename": file.filename,
            "events_extracted": len(events),
            "message": f"Successfully imported {len(events)} events from {file.filename}",
            "events": events[:10]  # Return first 10 for preview
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


def _map_event_type(type_str: str) -> str:
    """Map CSV event types to internal types."""
    type_lower = type_str.lower()
    if 'holiday' in type_lower or 'break' in type_lower:
        return 'holiday'
    elif 'teacher' in type_lower or 'workday' in type_lower:
        return 'teacher_workday'
    elif 'first day' in type_lower or 'last day' in type_lower:
        return 'school_day'
    elif 'remote' in type_lower:
        return 'remote'
    elif 'early' in type_lower or 'half' in type_lower:
        return 'early_release'
    elif 'exam' in type_lower:
        return 'exam'
    elif 'conference' in type_lower:
        return 'conference'
    else:
        return 'custom'


# ============================================================================
# Appointments / Reminders
# ============================================================================

@router.post("/calendar/appointment")
async def add_appointment(
    date: str,
    time: Optional[str] = None,
    title: str = "",
    description: str = "",
    reminder: bool = True
):
    """Add an appointment or reminder."""
    
    try:
        event = calendar.add_event(
            date=date,
            title=title or "Appointment",
            event_type=EventType.APPOINTMENT,
            description=description,
            time=time
        )
        
        event["reminder"] = reminder
        event["is_appointment"] = True
        
        return {
            "success": True,
            "message": "Appointment added",
            "event": event
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calendar/appointments")
async def get_appointments(days: int = Query(30, ge=1, le=365)):
    """Get all upcoming appointments."""
    
    upcoming = calendar.get_upcoming_events(days=days)
    
    appointments = [
        e for e in upcoming
        if e.get("is_appointment", False) or e.get("type") == "appointment"
    ]
    
    return {
        "success": True,
        "count": len(appointments),
        "appointments": appointments
    }


@router.post("/calendar/load-us-holidays")
async def load_us_holidays():
    """Load US federal holidays into the calendar."""
    from app.integrations.calendar import get_us_holidays
    
    holidays = get_us_holidays()
    
    # Merge with existing events
    for holiday in holidays:
        # Check if already exists
        existing = [e for e in calendar.events if e.get("date") == holiday["date"] and "holiday" in e.get("type", "").lower()]
        if not existing:
            calendar.events.append(holiday)
    
    # Sort events
    calendar.events.sort(key=lambda e: e.get("date", ""))
    
    return {
        "success": True,
        "message": f"Loaded {len(holidays)} US holidays",
        "holidays": holidays
    }


@router.get("/calendar/holidays")
async def get_holidays(year: int = Query(None)):
    """Get all holidays (US federal + school)."""
    
    if year is None:
        year = datetime.now().year
    
    holidays = [
        e for e in calendar.events
        if e.get("type") == "holiday" and e.get("date", "").startswith(str(year))
    ]
    
    return {
        "success": True,
        "year": year,
        "count": len(holidays),
        "holidays": sorted(holidays, key=lambda e: e.get("date", ""))
    }
