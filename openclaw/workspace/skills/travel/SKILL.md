---
name: pla-travel
description: Flight search, hotel booking, and itinerary planning via PLA backend.
metadata: { "openclaw": { "emoji": "✈️", "requires": { "bins": ["pla"] } } }
---

# Travel Skill

Use the `pla` CLI to search flights with realistic distance-based pricing.

## Commands

```bash
pla flights CLT RDU 2025-04-15          # Short haul domestic
pla flights CLT LAX 2025-05-01          # Cross-country
pla flights JFK DEL 2025-06-01          # International (NYC → Delhi)
pla flights CLT LHR 2025-07-01          # Transatlantic
```

## Airport codes

Common codes for the user:
- CLT = Charlotte, NC (home)
- RDU = Raleigh-Durham, NC
- JFK/EWR/LGA = New York area
- LAX = Los Angeles
- SFO = San Francisco
- DEL = Delhi, India
- BOM = Mumbai, India
- HYD = Hyderabad, India
- LHR = London Heathrow

## Response format

- Show top 3 flights sorted by value (price + duration)
- Include airline, departure/arrival times, duration, stops
- Flag deals (>20% below average for that route)
- For international: note visa requirements if applicable
