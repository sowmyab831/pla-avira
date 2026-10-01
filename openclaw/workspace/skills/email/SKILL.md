---
name: pla-email
description: Gmail integration — unread emails, action items, and appointments via PLA backend.
metadata: { "openclaw": { "emoji": "📧", "requires": { "bins": ["pla"] } } }
---

# Email Skill

Access Gmail-analyzed emails, extracted action items, and detected appointments.

## Commands

```bash
pla emails                # Unread emails (analyzed by Qwen2.5:14b)
pla action-items          # Pending action items from emails
pla appointments          # Upcoming appointments from emails
```

## Response format

- Group action items by priority (high → low)
- For appointments: show date, time, location if available
- Flag overdue action items
