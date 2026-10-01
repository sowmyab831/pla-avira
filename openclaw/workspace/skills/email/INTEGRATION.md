# OpenClaw Email Integration Guide

## Overview

Avira uses OpenClaw as the channel layer to read, analyze, and extract actionable tasks from your email. The PLA backend handles all privacy-preserving analysis using the local Ollama LLM (mistral:7b-instruct).

## Architecture

```
Gmail / Outlook
      │
      ▼
OpenClaw Gateway (Node.js)
      │  ← AGENTS.md / SOUL.md define Avira personality
      │  ← skills/email/SKILL.md defines commands
      ▼
pla CLI (bash + curl)
      │
      ▼
PLA Backend (FastAPI :30000)
      │
      ├─► Gmail Integration    → OAuth2 → fetch unread
      ├─► Email Analyzer       → Ollama LLM → extract action items
      ├─► Privacy Masking      → Presidio NER → strip PII before LLM
      └─► Task Store           → actionable items + appointments
```

## Setup Steps

### 1. Configure Gmail OAuth

Create a Google Cloud project and enable the Gmail API:

```bash
# 1. Go to https://console.cloud.google.com
# 2. Create project → Enable Gmail API
# 3. Create OAuth 2.0 credentials (Desktop app)
# 4. Download client_secret.json
```

Place credentials in the backend:

```bash
cp client_secret.json pla-avira/backend/credentials/gmail_client_secret.json
```

Set environment variables:

```bash
export GMAIL_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GMAIL_CLIENT_SECRET="your-client-secret"
export GMAIL_REDIRECT_URI="http://localhost:30000/api/integrations/gmail/callback"
```

### 2. Authenticate via OpenClaw

```bash
# Start OpenClaw
openclaw onboard --install-daemon

# Authenticate Gmail through Avira
> Avira, connect my Gmail

# Or use the pla CLI directly:
pla emails --auth
```

This opens a browser for OAuth2 consent. Once authorized, Avira can read your email.

### 3. Read & Analyze Emails

```bash
# Via OpenClaw conversation:
> Avira, check my emails for action items

# Via pla CLI:
pla emails                    # List unread emails
pla emails --analyze          # Analyze and extract action items
pla emails --action-items     # Show pending action items
```

### 4. Actionable Personal Tasks

Avira automatically extracts:

| Task Type      | Example                                    |
|----------------|--------------------------------------------|
| **Reply**      | "Reply to John about the meeting"          |
| **Appointment**| "Doctor appointment March 25 at 2pm"       |
| **Deadline**   | "Submit report by Friday"                  |
| **Payment**    | "Pay electric bill - due March 30"         |
| **Follow-up**  | "Follow up with recruiter next week"       |

Tasks appear in the **Tasks** page of the Avira app and sync to the Calendar.

## API Endpoints

| Method | Endpoint                                    | Description                    |
|--------|---------------------------------------------|--------------------------------|
| GET    | `/api/integrations/gmail/auth`              | Get OAuth URL                  |
| GET    | `/api/integrations/gmail/callback`          | OAuth callback                 |
| GET    | `/api/integrations/gmail/emails`            | Fetch unread emails            |
| POST   | `/api/integrations/gmail/analyze`           | Analyze email with LLM         |
| GET    | `/api/integrations/action-items`            | Get extracted action items     |
| POST   | `/api/integrations/action-items/{id}/complete` | Mark task complete          |
| GET    | `/api/integrations/appointments`            | Get extracted appointments     |
| GET    | `/api/integrations/gmail/status`            | Check connection status        |
| POST   | `/api/integrations/gmail/disconnect`        | Disconnect Gmail               |

## OpenClaw Skill File

The email skill is defined in `openclaw/workspace/skills/email/SKILL.md`:

```markdown
# pla-email

## Commands

- `pla emails` — List unread emails
- `pla emails --analyze` — Analyze emails and extract action items
- `pla emails --action-items` — Show pending action items
- `pla emails --auth` — Start Gmail OAuth flow
```

## Privacy

- All email content is processed through the **Privacy Masking Pipeline** before reaching the LLM
- PII (names, SSNs, credit cards, addresses) is replaced with UUIDs
- The LLM (Ollama mistral:7b-instruct) runs **locally** — no data leaves your machine
- Email content is never stored permanently; only extracted tasks are saved

## Troubleshooting

```bash
# Check Gmail connection status
curl http://localhost:30000/api/integrations/gmail/status

# Check backend health
curl http://localhost:30000/health

# Check OpenClaw daemon
openclaw status

# Re-authenticate
pla emails --auth
```

## Mobile App

The same email integration works on the React Native mobile app. Action items and appointments appear in:
- **Tasks** tab — actionable items with priority and due dates
- **Calendar** tab — appointments auto-synced from email
- Push notifications for high-priority items
