"""Calendar integration - sync school calendars and user appointments."""

import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from enum import Enum
import re

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of calendar events."""
    HOLIDAY = "holiday"
    SCHOOL_DAY = "school_day"
    BREAK = "break"
    APPOINTMENT = "appointment"
    ASSIGNMENT_DUE = "assignment_due"
    TEST = "test"
    CUSTOM = "custom"


class CalendarIntegration:
    """Handle calendar data from multiple sources."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
    
    async def parse_google_sheets_calendar(self, sheet_url: str) -> List[Dict[str, Any]]:
        """
        Parse Google Sheets calendar.
        
        Expected format:
        - Column A: Date (MM/DD/YYYY or similar)
        - Column B: Event Type (Holiday, Break, etc.)
        - Column C: Description
        """
        try:
            # Convert share URL to export URL
            sheet_id = self._extract_sheet_id(sheet_url)
            if not sheet_id:
                logger.error(f"Could not extract sheet ID from {sheet_url}")
                return []
            
            # Export as CSV
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(csv_url)
                response.raise_for_status()
                
                events = []
                lines = response.text.strip().split('\n')
                
                for line in lines[1:]:  # Skip header
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        try:
                            event_date = self._parse_date(parts[0])
                            if event_date:
                                event = {
                                    "date": event_date.isoformat(),
                                    "type": parts[1] if len(parts) > 1 else "event",
                                    "description": parts[2] if len(parts) > 2 else "",
                                    "source": "google_sheets",
                                    "created_at": datetime.utcnow().isoformat()
                                }
                                events.append(event)
                        except Exception as e:
                            logger.warning(f"Error parsing calendar row: {e}")
                            continue
                
                return events
        except Exception as e:
            logger.error(f"Failed to parse Google Sheets calendar: {e}")
            return []
    
    async def parse_pdf_calendar(self, pdf_url: str) -> List[Dict[str, Any]]:
        """
        Parse PDF calendar (school calendar PDFs).
        
        Uses pdfplumber to extract text and identify dates and events.
        """
        try:
            import pdfplumber
            import io
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
                
                logger.info(f"PDF calendar downloaded: {len(response.content)} bytes")
                
                # Parse PDF with pdfplumber
                events = []
                pdf_file = io.BytesIO(response.content)
                
                with pdfplumber.open(pdf_file) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text:
                            # Extract dates and events from text
                            extracted = self._extract_dates_from_text(text)
                            events.extend(extracted)
                
                logger.info(f"Extracted {len(events)} events from PDF")
                return events
        except ImportError:
            logger.warning("pdfplumber not installed. Install with: pip install pdfplumber")
            return []
        except Exception as e:
            logger.error(f"Failed to parse PDF calendar: {e}")
            return []
    
    def _extract_dates_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract dates and events from PDF text."""
        events = []
        
        # Common holiday patterns
        holiday_patterns = {
            "holiday": r"(holiday|break|recess|closed|no school|vacation)",
            "school_day": r"(school day|classes|instruction)",
            "break": r"(spring break|winter break|fall break|thanksgiving|christmas)",
        }
        
        # Date patterns: MM/DD, MM/DD/YYYY, Month DD, etc.
        date_pattern = r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2})"
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            # Try to find dates in the line
            dates = re.findall(date_pattern, line, re.IGNORECASE)
            
            for date_str in dates:
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    # Determine event type from line content
                    event_type = "school_day"
                    for type_name, pattern in holiday_patterns.items():
                        if re.search(pattern, line, re.IGNORECASE):
                            event_type = type_name
                            break
                    
                    event = {
                        "date": parsed_date.isoformat(),
                        "title": f"{event_type.replace('_', ' ').title()} - {parsed_date.strftime('%B %d')}",
                        "type": event_type,
                        "description": line[:100],  # First 100 chars as description
                        "source": "pdf_calendar",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    events.append(event)
        
        return events
    
    def add_event(
        self,
        date: str,
        title: str,
        event_type: EventType = EventType.CUSTOM,
        description: str = "",
        time: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a custom event to calendar."""
        event = {
            "id": f"event_{datetime.utcnow().timestamp()}",
            "date": date,
            "time": time,
            "title": title,
            "type": event_type.value,
            "description": description,
            "source": "user_input",
            "created_at": datetime.utcnow().isoformat()
        }
        self.events.append(event)
        return event
    
    def get_events_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Get all events for a specific date."""
        return [e for e in self.events if e["date"] == date]
    
    def get_events_for_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get all events in a date range."""
        return [
            e for e in self.events
            if start_date <= e["date"] <= end_date
        ]
    
    def get_upcoming_events(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get upcoming events."""
        from datetime import timedelta
        today = date.today().isoformat()
        future_date = date.today() + timedelta(days=days)
        
        return self.get_events_for_range(today, future_date.isoformat())
    
    def _extract_sheet_id(self, url: str) -> Optional[str]:
        """Extract sheet ID from Google Sheets URL."""
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        formats = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d/%m/%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        
        return None
    
    def merge_events(self, other_events: List[Dict[str, Any]]) -> None:
        """Merge events from another source."""
        for event in other_events:
            if not any(
                e["date"] == event["date"] and e["title"] == event.get("title")
                for e in self.events
            ):
                self.events.append(event)
        
        # Sort by date
        self.events.sort(key=lambda e: e["date"])


# US Federal Holidays for 2025-2026
US_HOLIDAYS = {
    # 2025
    "2025-01-01": "New Year's Day",
    "2025-01-20": "Martin Luther King Jr. Day",
    "2025-02-17": "Presidents' Day",
    "2025-05-26": "Memorial Day",
    "2025-06-19": "Juneteenth",
    "2025-07-04": "Independence Day",
    "2025-09-01": "Labor Day",
    "2025-10-13": "Columbus Day",
    "2025-11-11": "Veterans Day",
    "2025-11-27": "Thanksgiving Day",
    "2025-12-25": "Christmas Day",
    # 2026
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)",
    "2026-09-07": "Labor Day",
    "2026-10-12": "Columbus Day",
    "2026-11-11": "Veterans Day",
    "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
}


def get_us_holidays() -> List[Dict[str, Any]]:
    """Get US federal holidays as calendar events."""
    events = []
    for date_str, name in US_HOLIDAYS.items():
        events.append({
            "id": f"us_holiday_{date_str}",
            "date": date_str,
            "title": name,
            "type": "holiday",
            "description": f"US Federal Holiday: {name}",
            "source": "us_holidays",
            "is_public_holiday": True,
            "created_at": datetime.now().isoformat(),
        })
    return events


# Predefined school calendars
SCHOOL_CALENDARS = {
    "socrates_academy": {
        "name": "Socrates Academy",
        "calendar_url": "https://www.socratesacademy.us/_files/ugd/a20ab5_3da5fbc523bc462592df1de9b1d80d6e.pdf",
        "type": "pdf"
    },
    "ln_charter": {
        "name": "LN Charter",
        "calendar_url": "https://www.lncharter.org/cms/lib/NC02225560/Centricity/Domain/631/2025-2026_SchoolYearCalendar.pdf",
        "type": "pdf"
    },
    "family_calendar": {
        "name": "Family Calendar",
        "calendar_url": "https://docs.google.com/spreadsheets/d/1BUPvQ1zqEZ4BTcnawcctom3HKAhkZSD46Q3KI9YZhl0/edit?pli=1&gid=1419189595#gid=1419189595",
        "type": "google_sheets"
    }
}
