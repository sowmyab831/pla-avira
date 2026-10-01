"""Life Admin Radar — IMAP metadata-only email scanning.

Privacy contract:
  * We fetch HEADERS + a 400-char text snippet. Bodies are never persisted.
  * Sender addresses are reduced to a domain; subjects are PII-masked.
  * Deep links open the message in the user's own mail client (Gmail/Outlook web).
  * App passwords are Fernet-encrypted at rest with a key derived from
    `AVIRA_VAULT_KEY` (or a locally generated file key).
"""
from __future__ import annotations

import asyncio
import base64
import email
import hashlib
import imaplib
import logging
import os
import re
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional
from urllib.parse import quote

from cryptography.fernet import Fernet

from app.services.llm_client import generate_json

logger = logging.getLogger(__name__)

PROVIDERS = {
    "gmail": {"host": "imap.gmail.com", "help": "Google Account → Security → 2-Step Verification → App passwords"},
    "outlook": {"host": "outlook.office365.com", "help": "account.microsoft.com → Security → App passwords"},
    "icloud": {"host": "imap.mail.me.com", "help": "appleid.apple.com → Sign-In and Security → App-Specific Passwords"},
    "yahoo": {"host": "imap.mail.yahoo.com", "help": "Yahoo Account Security → Generate app password"},
    "custom": {"host": "", "help": "Ask your provider for IMAP host + app password"},
}


# ── crypto ───────────────────────────────────────────────────────────────────
def _key() -> bytes:
    raw = os.environ.get("AVIRA_VAULT_KEY")
    if raw:
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    path = os.environ.get("AVIRA_VAULT_KEY_FILE", "/tmp/avira_vault.key")
    if os.path.exists(path):
        return open(path, "rb").read()
    k = Fernet.generate_key()
    with open(path, "wb") as f:
        f.write(k)
    return k


def encrypt_secret(s: str) -> str:
    return Fernet(_key()).encrypt(s.encode()).decode()


def decrypt_secret(s: str) -> str:
    return Fernet(_key()).decrypt(s.encode()).decode()


# ── masking ──────────────────────────────────────────────────────────────────
_MASKS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\b\+?1?[ -.]?\(?\d{3}\)?[ -.]?\d{3}[ -.]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b(?:acct|account|member|policy|order|confirmation|ref)(?:\s*(?:#|no\.?|number|id))?\s*[:#]?\s*[A-Z0-9-]{6,}\b", re.I), "[ACCOUNT]"),
]


def mask(text: str) -> str:
    for pat, rep in _MASKS:
        text = pat.sub(rep, text)
    return text


# ── classification ───────────────────────────────────────────────────────────
_CATS = [
    ("bill", r"\b(bill|invoice|statement (?:is )?(?:ready|available)|payment due|amount due|autopay|past due|minimum payment|your .* payment|utility bill|electric bill|water bill|gas bill|internet bill|insurance premium|tuition)\b"),
    ("appointment", r"\b(appointment|visit|reservation|booking confirm|check-?up|dentist|doctor|dr\.|clinic|vet|salon|confirm your (?:appointment|visit)|reminder: your)\b"),
    ("school", r"\b(school|teacher|principal|pta|pto|classroom|homework|field trip|permission slip|report card|parent[- ]teacher|conference|early dismissal|picture day|spirit week|fundraiser|schoology|powerschool|classdojo|seesaw|remind)\b"),
    ("delivery", r"\b(shipped|out for delivery|delivered|your package|tracking|arriving|on its way|order (?:has )?(?:shipped|update))\b"),
    ("renewal", r"\b(renew|renewal|expir(?:es|ing|ation)|subscription (?:will|is)|auto-?renew|membership|license|registration|passport|warranty)\b"),
    ("travel", r"\b(itinerary|boarding|flight|check-in|hotel|reservation|airbnb|trip|gate change|e-?ticket)\b"),
    ("refund", r"\b(refund|reimburs|credit (?:has been )?(?:issued|applied)|chargeback|dispute)\b"),
    ("action", r"\b(action required|please (?:review|sign|confirm|complete|verify|respond|update)|response needed|needs your|signature|approve|deadline|rsvp|form|application|tax|1099|w-?2|irs)\b"),
    ("promo", r"\b(sale|% off|deal|offer|coupon|save \$|last chance|limited time|free shipping|newsletter|unsubscribe|weekly digest|recommended for you)\b"),
]
_AMOUNT = re.compile(r"\$\s?(\d+(?:,\d+)*(?:\.\d{1,2})?)(?![\d.])")
_DUE = re.compile(
    r"\b(?:due(?:\s+(?:by|on|date))?|pay(?:able)?(?:\s+(?:by|before|on))?|payment\s+due|must\s+(?:be\s+)?(?:paid|submitted|completed|reviewed|verified|responded|confirmed)?\s*(?:by|before|on)?|expires?(?:\s+(?:on|by))?|expir(?:es|ing|ation)(?:\s+(?:on|by))?|renew(?:al|s?)(?:\s+(?:on|by|date))?|deadline|no\s+later\s+than|by|before|on|until|valid\s+(?:through|until)|good\s+(?:through|until)|scheduled\s+(?:for|on)|arriv(?:e|es|ing)|starting\s*(?:on)?)\s*(?:date|is|:)?\s*:?\s*(?:the\s+)?((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2}|(?:this\s+|next\s+)?(?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|in\s+\d+\s+days?)",
    re.I,
)
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _parse_date_str(s: str, ref: date) -> Optional[date]:
    s = re.sub(r"\b(?:the|st|nd|rd|th)\b", "", s.strip().lower().rstrip(".,")).strip()
    try:
        if s == "tomorrow":
            return ref + timedelta(days=1)
        m = re.match(r"in\s+(\d+)\s+days?", s)
        if m:
            return ref + timedelta(days=int(m.group(1)))
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return date.fromisoformat(s[:10])
        m = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", s)
        if m:
            y = int(m.group(3)) if m.group(3) else ref.year
            y = y + 2000 if y < 100 else y
            d = date(y, int(m.group(1)), int(m.group(2)))
            if not m.group(3) and d < ref - timedelta(days=30):
                d = date(y + 1, d.month, d.day)
            return d
        m = re.match(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?", s)
        if m and m.group(1) in _MONTHS:
            y = int(m.group(3)) if m.group(3) else ref.year
            d = date(y, _MONTHS.index(m.group(1)) + 1, int(m.group(2)))
            if not m.group(3) and d < ref - timedelta(days=30):
                d = date(y + 1, d.month, d.day)
            return d
        s_clean = re.sub(r"\bthis\s+|\bnext\s+", "", s).strip()
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if s_clean in days:
            delta = (days.index(s_clean) - ref.weekday()) % 7
            delta = delta or 7
            if s.startswith("next "):
                delta += 7
            return ref + timedelta(days=delta)
    except ValueError:
        return None
    return None


def classify(subject: str, snippet: str, sender_domain: str, received: Optional[datetime]) -> dict:
    text = f"{subject} {snippet}".lower()
    ref = (received or datetime.utcnow()).date()
    category = "other"
    for cat, pat in _CATS:
        if re.search(pat, text):
            category = cat
            break
    if category == "promo" and re.search(r"\b(due|expir|renew)\b", text):
        category = "renewal"
    amount = None
    m = _AMOUNT.search(f"{subject} {snippet}")
    if m and category in ("bill", "refund", "renewal", "delivery", "other", "action"):
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    due = None
    m = _DUE.search(f"{subject} {snippet}")
    if m:
        due = _parse_date_str(m.group(1), ref)
    if category == "appointment" and not due:
        for cand in re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?", text, re.I):
            due = _parse_date_str(cand, ref)
            if due:
                break
    time_s = None
    mt = _TIME.search(f"{subject} {snippet}")
    if mt and category in ("appointment", "school", "travel"):
        h = int(mt.group(1)) % 12 + (12 if mt.group(3).lower() == "pm" else 0)
        time_s = f"{h:02d}:{mt.group(2) or '00'}"
    priority = "medium"
    if category in ("bill", "action", "renewal") and due and (due - ref).days <= 5:
        priority = "high"
    elif category in ("promo", "delivery", "other"):
        priority = "low"
    if re.search(r"\b(past due|urgent|final notice|action required|last chance to)\b", text) and category != "promo":
        priority = "high"
    return {"category": category, "amount": amount, "due_date": due, "time": time_s, "priority": priority}


def deep_link(provider: str, message_id: Optional[str], email_addr: str) -> Optional[str]:
    if not message_id:
        return None
    mid = message_id.strip("<>")
    if provider == "gmail":
        # u/0 plus authuser selects the right account; keep the rfc822msgid colon literal
        # so Gmail parses the search operator correctly.
        return f"https://mail.google.com/mail/u/0/?authuser={quote(email_addr)}#search/rfc822msgid:{quote(mid, safe='@._-~')}"
    if provider == "outlook":
        return f"https://outlook.live.com/mail/0/inbox?searchTerm={quote(mid)}"
    if provider == "icloud":
        return "https://www.icloud.com/mail/"
    return f"message:%3C{quote(mid)}%3E"  # macOS Mail URL scheme


def suggested_reply(category: str, subject: str) -> Optional[str]:
    if category == "appointment":
        return "Hi, confirming our appointment — thank you. Please let me know if anything changes."
    if category == "school":
        return "Thank you for the update. We've noted the date and will make sure everything is ready."
    if category == "action":
        return "Thanks — I'll review this and get back to you by end of week."
    if category == "refund":
        return "Thanks for processing this. Could you confirm when the credit will post?"
    return None


# ── IMAP fetch (runs in a thread; imaplib is blocking) ───────────────────────
def _decode(h) -> str:
    try:
        return str(make_header(decode_header(h or "")))
    except Exception:
        return h or ""


def _snippet(msg) -> str:
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8", "ignore")[:400]
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True) or b""
                    html = payload.decode(part.get_content_charset() or "utf-8", "ignore")
                    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:400]
        else:
            payload = msg.get_payload(decode=True) or b""
            return payload.decode(msg.get_content_charset() or "utf-8", "ignore")[:400]
    except Exception:
        pass
    return ""


def _fetch_sync(host: str, port: int, user: str, secret: str, since_days: int, last_uid: int, limit: int) -> list[dict]:
    out: list[dict] = []
    conn = imaplib.IMAP4_SSL(host, port)
    try:
        conn.login(user, secret)
        conn.select("INBOX", readonly=True)
        since = (datetime.utcnow() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        crit = f"(SINCE {since})" if not last_uid else f"(UID {last_uid + 1}:* SINCE {since})"
        typ, data = conn.uid("search", None, crit)
        if typ != "OK" or not data or not data[0]:
            return out
        uids = [int(u) for u in data[0].split()]
        uids = [u for u in uids if u > last_uid][-limit:]
        for uid in uids:
            typ, parts = conn.uid("fetch", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID LIST-UNSUBSCRIBE)] BODY.PEEK[TEXT]<0.2000>)")
            if typ != "OK":
                continue
            raw_hdr = b""
            raw_txt = b""
            for p in parts:
                if isinstance(p, tuple):
                    if b"HEADER" in p[0]:
                        raw_hdr = p[1]
                    elif b"TEXT" in p[0]:
                        raw_txt = p[1]
            hdr = email.message_from_bytes(raw_hdr)
            name, addr = parseaddr(_decode(hdr.get("From")))
            try:
                received = parsedate_to_datetime(hdr.get("Date")) if hdr.get("Date") else None
                if received and received.tzinfo:
                    received = received.astimezone().replace(tzinfo=None)
            except Exception:
                received = None
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw_txt.decode("utf-8", "ignore")))[:400]
            out.append({
                "uid": uid,
                "message_id": (hdr.get("Message-ID") or "").strip(),
                "sender_name": name or addr.split("@")[0],
                "sender_domain": addr.split("@")[-1].lower() if "@" in addr else None,
                "subject": _decode(hdr.get("Subject")),
                "received_at": received,
                "snippet": snippet,
                "is_list": bool(hdr.get("List-Unsubscribe")),
            })
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    return out


async def fetch_headers(host: str, port: int, user: str, secret: str, since_days: int = 14,
                        last_uid: int = 0, limit: int = 200) -> list[dict]:
    return await asyncio.to_thread(_fetch_sync, host, port, user, secret, since_days, last_uid, limit)


def test_login_sync(host: str, port: int, user: str, secret: str) -> tuple[bool, str]:
    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, secret)
        conn.logout()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _recompute_priority(category: str, due: Optional[date], text: str, received: Optional[datetime]) -> str:
    ref = (received or datetime.utcnow()).date()
    priority = "medium"
    if category in ("bill", "action", "renewal") and due and (due - ref).days <= 5:
        priority = "high"
    elif category in ("promo", "delivery", "other"):
        priority = "low"
    if re.search(r"\b(past due|urgent|final notice|action required|last chance to)\b", text) and category != "promo":
        priority = "high"
    return priority


async def llm_refine(signals: list[dict]) -> list[dict]:
    """Re-classify every extracted signal with the fast model.
    Regex pre-classification is fast but error-prone; the LLM corrects categories,
    amounts, and due dates from the masked subject + snippet.
    """
    if not signals:
        return signals
    batch_size = 15
    for start in range(0, len(signals), batch_size):
        batch = signals[start:start + batch_size]
        lines = "\n".join(f"{i}. [{s['sender_domain']}] {mask(s['subject'])} :: {mask(s['snippet'])[:160]}" for i, s in enumerate(batch))
        prompt = f"""Classify each email into EXACTLY one of: bill, appointment, school, delivery, renewal, travel, refund, action, promo, other.
Also extract amount (number or null) and due_date (YYYY-MM-DD or null).
Use the sender, subject, and snippet context. Be concise and accurate.
Emails:
{lines}
Return ONLY a JSON array of {{"i": index, "category": "...", "amount": null, "due_date": null}}."""
        data = await generate_json(prompt, task="email", timeout=45)
        for it in data or []:
            try:
                idx = int(it["i"])
                s = batch[idx]
                if it.get("category") in dict(_CATS) or it.get("category") == "other":
                    s["category"] = it["category"]
                if it.get("amount") is not None:
                    s["amount"] = float(it["amount"])
                else:
                    s["amount"] = None
                if it.get("due_date"):
                    s["due_date"] = date.fromisoformat(str(it["due_date"])[:10])
                else:
                    s["due_date"] = None
                text = f"{s.get('subject', '')} {s.get('snippet', '')}".lower()
                s["priority"] = _recompute_priority(s["category"], s.get("due_date"), text, s.get("received_at"))
            except Exception:
                continue
    return signals


def build_signals(raw: list[dict], provider: str, account_email: str) -> list[dict]:
    out = []
    for r in raw:
        c = classify(r["subject"], r["snippet"], r.get("sender_domain") or "", r.get("received_at"))
        if r.get("is_list") and c["category"] in ("other",):
            c["category"] = "promo"
        out.append({
            **c,
            "uid": r["uid"], "message_id": r["message_id"], "sender_name": r["sender_name"],
            "sender_domain": r["sender_domain"], "subject": mask(r["subject"])[:255], "received_at": r["received_at"],
            "snippet": r["snippet"], "is_list": r.get("is_list", False),
            "deep_link": deep_link(provider, r["message_id"], account_email),
            "suggested_reply": suggested_reply(c["category"], r["subject"]),
        })
    return out
