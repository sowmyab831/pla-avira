---
name: pla-calendar
description: School calendar sync, event management, and scheduling via PLA backend.
metadata: { "openclaw": { "emoji": "📅", "requires": { "bins": ["pla"] } } }
---

# Calendar Skill

Manage school calendars (Socrates Academy, LN Charter), family events, and appointments.

## Commands

```bash
pla calendar              # Upcoming 30 days
pla calendar 90           # Upcoming 90 days
pla calendar-sync         # Sync all school calendars
pla calendar-add 2025-04-15 "Dentist appointment" appointment
pla calendar-add 2025-12-25 "Christmas" holiday
```

## Event types
- holiday, break, appointment, assignment_due, test, custom

## Schools tracked
- Socrates Academy (Charlotte, NC)
- LN Charter (Charlotte, NC)
- Family Google Sheet calendar
