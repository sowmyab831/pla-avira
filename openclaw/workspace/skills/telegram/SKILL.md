---
name: pla-telegram
description: Telegram bot management — check status, toggle alerts, send test, trigger day-trade tips.
metadata: { "openclaw": { "emoji": "✈️", "requires": { "bins": ["pla"] } } }
---

# Telegram Skill

Use `pla telegram` to manage bot alerts.

## Commands

```bash
pla telegram status          # Show bot config + feature toggles
pla telegram enable tips     # Enable day-trade tips
pla telegram disable tips    # Disable day-trade tips
pla telegram enable email    # Enable email action-item alerts
pla telegram disable email   # Disable email action-item alerts
pla telegram enable price    # Enable price alerts
pla telegram enable exits    # Enable trade-exit alerts (stop/TP)
pla telegram test            # Send a test message
pla telegram tips           # Push day-trade tips now
```

## Usage Examples

- "Send me a test message on Telegram" → `pla telegram test`
- "Turn on day-trade tips" → `pla telegram enable tips`
- "Turn off email alerts" → `pla telegram disable email`
- "Show my Telegram bot status" → `pla telegram status`
