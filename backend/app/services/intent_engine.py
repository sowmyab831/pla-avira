"""Multi-intent engine: one utterance → many domain actions.

"Add milk to the list, remind me to call the dentist at 4, and log 180 lbs"
    → shopping.add_items, reminder.add, health.log_biometric

Two layers:
  1. Deterministic parser (regex + date phrases) — instant, offline, testable.
  2. LLM (fast model) fills in anything the parser could not classify.

Output is a list of Nexus action dicts plus an Avira-persona spoken reply.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, date
from typing import Optional

from app.services.llm_client import generate_json, generate

DOMAINS_DOC = """
shopping.add_items      {items:[{name, quantity?}]}
pantry.add_items        {items:[{name, qty?, unit?}]}
pantry.consume          {items:[name]}
reminder.add            {title, due_at ISO}
calendar.add_event      {title, starts_at ISO, duration_min?, location?, member_id?, kind?}
tasks.add               {title, due_date ISO?, category: task|chore|habit}
health.add_medication   {name, dose?, times:["HH:MM"], with_food?}
health.log_medication   {name, taken: bool}
health.log_biometric    {metric: weight|bp_sys|bp_dia|glucose|steps|sleep_h|hr|waist, value, unit?}
health.checkin          {kind: workout|water|mood|stretch|sleep, value}
health.log_fasting      {kept: bool}
health.analyze          {report_text?}
family.add_chore        {title, member_name, recurrence: daily|weekdays|weekly:mon|once, points?}
family.add_milestone    {title, member_name, category?}
finance.add_transaction {merchant, amount, category?, date?}
finance.list_recurring_transactions {}
finance.find_transactions {query?}
"""

# Valid domain.action pairs the LLM may emit (parsed from DOMAINS_DOC).
VALID_ACTIONS = {m.group(1) for m in re.finditer(r"^(\w+\.\w+)", DOMAINS_DOC, re.M)}

SAFE_ACTIONS = {"shopping.add_items", "reminder.add", "tasks.add", "health.log_biometric", "health.checkin",
                "health.log_medication", "health.log_fasting", "health.analyze", "pantry.add_items",
                "pantry.consume", "family.add_chore", "family.add_milestone",
                "finance.list_recurring_transactions", "finance.find_transactions"}

_VERBS = r"remind|reminder|add|log|put|schedule|book|set|track|note|mark|record|tell|buy|get|weigh|weighed|i |i'm|took|take|taken|start|we |we're|assign|don'?t forget|ping|spent|paid|slept|kept|broke|skipped|missed|used up|finished|ran out|worked out|did |my |bp|blood|glucose|sugar|mood|feeling|need to|have to|[A-Za-z]+ (?:learned|learnt|can now|won|passed|should|must|has to|needs to|is |are |has |have |wants |will )"
_SPLIT = re.compile(r"\s*(?:,|;|\.\s|\band then\b|\bthen\b|\balso\b|\band\b)\s*(?=(?:" + _VERBS + r"))", re.I)

_TIME = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _resolve_datetime(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    now = now or datetime.now()
    t = text.lower()
    # "at nine in the morning" → "at 9 am"
    t = re.sub(r"\b(" + "|".join(_WORD_NUM) + r")\b(?=\s*(?:o'?clock|am|pm|in the (?:morning|afternoon|evening)|tonight|$|,))",
               lambda m: str(_WORD_NUM[m.group(1)]), t)
    t = re.sub(r"\bin the morning\b", "am", t)
    t = re.sub(r"\bin the (?:afternoon|evening)\b", "pm", t)
    t = re.sub(r"\bo'?clock\b", "", t)
    t = re.sub(r"\b(?:around|about|approximately|roughly|~)\s*(?=\d)", "at ", t)
    day = None
    if "tomorrow" in t:
        day = now.date() + timedelta(days=1)
    elif "today" in t or "tonight" in t:
        day = now.date()
    else:
        for i, wd in enumerate(_WEEKDAYS):
            if wd in t or wd[:3] in re.findall(r"\b(mon|tue|wed|thu|fri|sat|sun)\b", t):
                delta = (i - now.weekday()) % 7
                if delta == 0 and "next" in t:
                    delta = 7
                day = now.date() + timedelta(days=delta or (7 if "next" in t else 0))
                break
        m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
        if m and not day:
            y = int(m.group(3)) if m.group(3) else now.year
            y = y + 2000 if y < 100 else y
            try:
                day = date(y, int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass
        m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
        if m and not day:
            mon = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(m.group(1)) + 1
            try:
                day = date(now.year, mon, int(m.group(2)))
                if day < now.date():
                    day = date(now.year + 1, mon, int(m.group(2)))
            except ValueError:
                pass
        m = re.search(r"\b(?:on\s+)?the\s+(\d{1,2})(?:st|nd|rd|th)\b", t)
        if m and not day:
            d = int(m.group(1))
            try:
                day = date(now.year, now.month, d)
                if day < now.date():
                    nm = now.month % 12 + 1
                    day = date(now.year + (1 if nm == 1 else 0), nm, d)
            except ValueError:
                pass

    hour, minute = None, 0
    m = re.search(r"\b(?:at|by|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\b", t)
    if not m:
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ap = (m.group(3) or "").replace(".", "")
        if ap == "pm" and hour < 12:
            hour += 12
        elif ap == "am" and hour == 12:
            hour = 0
        elif not ap and hour < 7:
            hour += 12  # "at 4" almost always means 4pm
    elif "noon" in t:
        hour = 12
    elif "morning" in t:
        hour = 8
    elif "evening" in t or "tonight" in t:
        hour = 18
    elif "afternoon" in t:
        hour = 14

    m = re.search(r"\bin\s+(\d+)\s*(min|minute|hour|hr|day|week)s?\b", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {"min": timedelta(minutes=n), "minute": timedelta(minutes=n), "hour": timedelta(hours=n),
                 "hr": timedelta(hours=n), "day": timedelta(days=n), "week": timedelta(weeks=n)}[unit]
        return now + delta

    if day is None and hour is None:
        return None
    if day is None:
        day = now.date()
        if hour is not None and datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute) < now:
            day = day + timedelta(days=1)
    return datetime.combine(day, datetime.min.time()).replace(hour=hour if hour is not None else 9, minute=minute)


def _strip_time_words(s: str) -> str:
    s = re.sub(r"\b(?:at\s+)?(?:" + "|".join(_WORD_NUM) + r")\s*(?:o'?clock)?\s*(?:in the (?:morning|afternoon|evening)|am|pm)\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:on\s+)?the\s+\d{1,2}(?:st|nd|rd|th)\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:at|by|@|around|about)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", "", s, flags=re.I)
    s = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:on\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:on\s+)?\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:on\s+)?(tomorrow|today|tonight|next|this|morning|evening|afternoon|noon|" + "|".join(_WEEKDAYS) + r")\b", "", s, flags=re.I)
    s = re.sub(r"^(?:we(?:'re| are)\s+(?:hosting|having|going to)|there(?:'s| is)|i have|i've got|put|add)\s+(?:a\s+|an\s+|the\s+)?", "", s, flags=re.I)
    s = re.sub(r"\s+(?:on|at)\s*$", "", s, flags=re.I)
    s = re.sub(r"\bin\s+\d+\s*(?:min|minute|hour|hr|day|week)s?\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .,")


def _items(text: str) -> list[dict]:
    text = re.sub(r"^(?:add|buy|get|put|pick up|grab)\s+", "", text.strip(), flags=re.I)
    text = re.sub(r"\s+(?:to|on|in)\s+(?:the\s+)?(?:shopping|grocery)?\s*(?:list|cart|pantry).*$", "", text, flags=re.I)
    parts = re.split(r"\s*(?:,|\band\b|\+)\s*", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.match(r"^(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?|ml|litres?|liters?|l|lbs?|oz|gallons?|dozen|cans?|bags?|boxes?|bottles?|packs?|x)?\s+(.+)$", p, re.I)
        if m:
            out.append({"name": m.group(3).strip(), "quantity": f"{m.group(1)} {m.group(2) or ''}".strip(), "qty": float(m.group(1)), "unit": m.group(2) or "count"})
        else:
            out.append({"name": p, "qty": 1, "unit": "count"})
    return out


def parse_clause(clause: str, now: Optional[datetime] = None) -> Optional[dict]:
    """Deterministically map one clause to an action. Returns None when unsure."""
    c = clause.strip().rstrip(".!")
    low = c.lower()
    if not c:
        return None

    # shopping list
    if re.search(r"\b(shopping|grocery)\s+list\b|\bto (?:the )?(?:list|cart)\b|\bbuy\b|\bneed to (?:get|buy)\b|\bwe(?:'re| are) out of\b|\b(?:running )?low on\b|\balmost out of\b|\bneed more\b", low):
        c2 = re.sub(r"^.*?\b(?:we(?:'re| are) out of|(?:we(?:'re| are) )?(?:running )?low on|almost out of|need more|need to (?:get|buy))\b", "", c, flags=re.I)
        return _act("shopping", "add_items", {"items": [{"name": i["name"], "quantity": i.get("quantity")} for i in _items(c2)], "reason": "voice"})

    # pantry
    if re.search(r"\b(pantry|fridge|freezer)\b", low) and re.search(r"\b(add|put|bought|have)\b", low):
        return _act("pantry", "add_items", {"items": _items(c)})
    if re.search(r"\b(used up|finished|ran out of|we're out of the)\b", low):
        return _act("pantry", "consume", {"items": [i["name"] for i in _items(re.sub(r".*?(used up|finished|ran out of)\s+", "", c, flags=re.I))]})

    # medication
    m = re.search(r"\b(?:i )?(?:took|take|taken|had)\s+(?:my\s+)?([a-z][a-z0-9 \-]{1,40}?)(?:\s+(?:pill|tablet|dose|meds?|medication))?$", low)
    if m and not re.search(r"\bshower|walk|run|nap|breakfast|lunch|dinner|coffee\b", low):
        return _act("health", "log_medication", {"name": m.group(1).strip(), "taken": True})
    m = re.search(r"\b(?:skipped|missed|didn'?t take)\s+(?:my\s+)?([a-z][a-z0-9 \-]{1,40})", low)
    if m:
        return _act("health", "log_medication", {"name": m.group(1).strip(), "taken": False})
    m = re.search(r"\b(?:start|add|new)\s+(?:med(?:ication)?|prescription)\s+([a-z][a-z0-9\- ]+?)(?:\s+(\d+\s*(?:mg|mcg|ml|iu)))?(?:\s+(?:every|at|twice|once|daily|in the)\b.*)?$", low)
    if m:
        times = ["08:00"]
        if "twice" in low or "2x" in low:
            times = ["08:00", "20:00"]
        if "night" in low or "evening" in low or "bedtime" in low:
            times = ["21:00"]
        found = re.findall(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
        if found:
            times = [f"{(int(h) % 12) + (12 if ap == 'pm' else 0):02d}:{mi or '00'}" for h, mi, ap in found]
        wf = "with" if "with food" in low else ("before" if "before" in low else ("after" if "after" in low else None))
        return _act("health", "add_medication", {"name": m.group(1).strip(), "dose": m.group(2), "times": times, "with_food": wf})

    # biometrics
    m = re.search(r"\b(?:weigh(?:ed|t)?(?: is| in at)?|i'?m at|log weight)\s*(\d{2,3}(?:\.\d)?)\s*(lbs?|kg|pounds?)?\b", low)
    if m:
        return _act("health", "log_biometric", {"metric": "weight", "value": float(m.group(1)), "unit": (m.group(2) or "lb").replace("pounds", "lb").replace("lbs", "lb")})
    m = re.search(r"\b(?:bp|blood pressure)\s*(?:is|was|of)?\s*(\d{2,3})\s*(?:/|over)\s*(\d{2,3})\b", low)
    if m:
        return {"multi": [_act("health", "log_biometric", {"metric": "bp_sys", "value": float(m.group(1)), "unit": "mmHg"}),
                          _act("health", "log_biometric", {"metric": "bp_dia", "value": float(m.group(2)), "unit": "mmHg"})]}
    m = re.search(r"\b(?:glucose|sugar|blood sugar)\s*(?:is|was|of|at)?\s*(\d{2,3})\b", low)
    if m:
        return _act("health", "log_biometric", {"metric": "glucose", "value": float(m.group(1)), "unit": "mg/dL"})
    m = re.search(r"\b(\d[\d,]{2,6})\s*steps\b", low)
    if m:
        return _act("health", "log_biometric", {"metric": "steps", "value": float(m.group(1).replace(",", "")), "unit": "steps"})
    m = re.search(r"\bslept\s+(\d(?:\.\d)?)\s*(?:h|hrs?|hours?)\b", low)
    if m:
        return _act("health", "log_biometric", {"metric": "sleep_h", "value": float(m.group(1)), "unit": "h"})

    # lab/health report analysis
    if re.search(r"\b(lab|labs|lab results|blood test|lab report|report|pdf|document)\b", low) and \
       re.search(r"\b(check|assess|analyze|interpret|tell me|worried?|worry|concern|anything wrong|anything to worry|need to worry|should i worry)\b", low):
        return _act("health", "analyze", {})

    # check-ins & fasting
    if re.search(r"\b(worked out|did (?:my|a) workout|finished (?:my )?(?:workout|run|gym)|went for a run|hit the gym)\b", low):
        return _act("health", "checkin", {"kind": "workout", "value": "yes"})
    if re.search(r"\b(kept|did|completed|finished)\s+(?:my|the)\s+fast\b|\bfast(?:ed|ing)\s+(?:done|complete)\b", low):
        return _act("health", "log_fasting", {"kept": True})
    if re.search(r"\b(broke|skipped)\s+(?:my|the)\s+fast\b", low):
        return _act("health", "log_fasting", {"kept": False})
    m = re.search(r"\b(?:mood|feeling)\s+(?:is\s+)?(\w+)\b", low)
    if m and m.group(1) not in ("like",):
        return _act("health", "checkin", {"kind": "mood", "value": m.group(1)})

    # chores
    m = re.search(r"\b(?:chore|assign)\b.*?\bfor\s+([A-Z][a-z]+)\b|\b([A-Z][a-z]+)(?:'s)?\s+chore\b", c)
    if m or re.search(r"\b(every|each)\s+(day|morning|night|week|weekday)\b.*\b(bed|dishes|trash|homework|room|laundry|feed|clean)\b", low):
        name = (m.group(1) or m.group(2)) if m else None
        if not name:
            nm = re.search(r"\b([A-Z][a-z]+)\s+(?:should|must|has to|needs to|will)\b", c)
            name = nm.group(1) if nm else None
        title = re.sub(r"\b(add|assign|a|chore|for|every|each|day|week|daily|weekly|morning|night|weekday|should|must|has to|needs to|will|to)\b", " ", c, flags=re.I)
        if name:
            title = title.replace(name, "")
        title = re.sub(r"\s+", " ", title).strip(" .,:")
        rec = "weekdays" if "weekday" in low else ("weekly" if "week" in low else "daily")
        return _act("family", "add_chore", {"title": title or "Chore", "member_name": name, "recurrence": rec})

    # milestones
    m = re.search(r"\b([A-Z][a-z]+)\s+(?:just\s+)?(?:learned|learnt|can now|started|finished|won|read|rode|lost|got|scored|passed|made)\b(.*)", c)
    if m and re.search(r"\b(milestone|first|learned|learnt|can now|won|passed)\b", low):
        return _act("family", "add_milestone", {"member_name": m.group(1), "title": c, "category": "general"})

    # reminders (before calendar so "remind me to call the dentist" isn't an appointment)
    if re.search(r"\bremind\b|\breminder\b|\bdon'?t forget\b|\bping me\b", low):
        when = _resolve_datetime(c, now) or (datetime.now() + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        title = re.sub(r"^.*?\b(?:remind me to|remind me|reminder to|reminder|don'?t forget to|don'?t forget|ping me to)\s*", "", c, flags=re.I)
        title = _strip_time_words(title)
        return _act("reminder", "add", {"title": (title[:1].upper() + title[1:]) if title else "Reminder", "due_at": when.isoformat()})

    # calendar
    if re.search(r"\b(schedule|book|appointment|meeting|practice|recital|game|dentist|doctor|pediatrician|playdate|party|class|lesson|pickup|pick up|drop ?off|hosting|birthday|dinner with|lunch with|call with|interview|flight|conference)\b", low) and _resolve_datetime(c, now):
        when = _resolve_datetime(c, now)
        who = re.search(r"\b(?:for|with)\s+([A-Z][a-z]+)\b", c)
        title = _strip_time_words(re.sub(r"^(?:schedule|book|add|put|set up)\s+", "", c, flags=re.I))
        title = re.sub(r"\b(?:on|for|to) (?:the |my )?calendar\b", "", title, flags=re.I)
        title = re.sub(r"\s+", " ", title).strip(" .,")
        if not title:
            title = "Event"
        return _act("calendar", "add_event", {"title": title[:1].upper() + title[1:], "starts_at": when.isoformat(),
                                              "member_name": who.group(1) if who else None, "kind": "appointment" if re.search(r"dentist|doctor|pediatrician|appointment", low) else "event"})

    # finance queries (read-only)
    if re.search(r"\b(recurring|subscriptions?|monthly\s+(?:charges?|bills?|payments?)|repeat\s+charges?)\b", low) and \
       re.search(r"\b(what|which|list|show|find|tell|all|have|got|my)\b", low):
        return _act("finance", "list_recurring_transactions", {})

    # transactions
    m = re.search(r"\b(?:spent|paid)\s+\$?(\d+(?:\.\d{2})?)\s+(?:at|on|for|to)\s+(.+)", low)
    if m:
        return _act("finance", "add_transaction", {"amount": float(m.group(1)), "merchant": m.group(2).strip().title(), "category": "other"})

    # generic task
    if re.search(r"^(?:add (?:a )?task|todo|to-do|task:|i need to|need to|have to|must)\b", low):
        title = re.sub(r"^(?:add (?:a )?task|todo|to-do|task:|i need to|need to|have to|must)\s*(?:to\s+)?", "", c, flags=re.I)
        due = _resolve_datetime(c, now)
        return _act("tasks", "add", {"title": _strip_time_words(title).capitalize(), "due_date": due.isoformat() if due else None, "category": "task"})

    return None


def _act(domain: str, name: str, params: dict) -> dict:
    return {"domain": domain, "action": name, "params": params, "safe": f"{domain}.{name}" in SAFE_ACTIONS}


def _low_confidence(action: dict, clause: str) -> bool:
    """Heuristics for when the regex parse is probably too greedy."""
    if action["domain"] == "calendar":
        title = action["params"].get("title", "")
        if len(title) > 70 or re.search(r"\band\b", title) or len(re.findall(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|\bthe \d{1,2}(?:st|nd|rd|th)\b", clause, re.I)) > 1:
            return True
    return False


def parse_utterance(text: str, now: Optional[datetime] = None, strict: bool = False) -> tuple[list[dict], list[str]]:
    """Split into clauses and parse each. Returns (actions, unparsed_clauses).

    strict=True pushes low-confidence parses into `unparsed` so the LLM can redo them.
    """
    actions, leftovers = [], []
    for clause in _SPLIT.split(text):
        clause = clause.strip().strip(",;.").strip()
        if not clause or len(clause) < 3:
            continue
        r = parse_clause(clause, now)
        if r is None:
            leftovers.append(clause)
        elif "multi" in r:
            actions.extend(r["multi"])
        elif strict and _low_confidence(r, clause):
            leftovers.append(clause)
        else:
            actions.append(r)
    return actions, leftovers


async def llm_parse(clauses: list[str], now: Optional[datetime] = None) -> list[dict]:
    """Ask the fast model to map remaining clauses to actions."""
    if not clauses:
        return []
    now = now or datetime.now()
    prompt = f"""You convert a user's spoken request into structured actions for a personal-assistant app.
Current local time: {now.isoformat(timespec='minutes')} ({now.strftime('%A')}).

Available actions and their params:
{DOMAINS_DOC}

Clauses:
{chr(10).join(f'- {c}' for c in clauses)}

Return ONLY a JSON array. Each element: {{"domain": "...", "action": "...", "params": {{...}}}}.
Use ISO 8601 for all dates/times. If a clause is not actionable (small talk, question), skip it."""
    data = await generate_json(prompt, task="fast", timeout=45)
    out = []
    if isinstance(data, dict):
        data = data.get("actions") or [data]
    for it in data or []:
        if isinstance(it, dict) and it.get("domain") and it.get("action"):
            key = f"{it['domain']}.{it['action']}"
            if key not in VALID_ACTIONS:
                continue  # drop hallucinated actions; clause falls back to chat reply
            out.append(_act(it["domain"], it["action"], it.get("params") or {}))
    return out


AVIRA_SYSTEM = """You are Avira, a warm, quick-witted British personal assistant. Speak in 1-2 short sentences.
Be specific about what you did. Light dry humour is welcome; never sarcastic about the user. Never use emojis."""


async def spoken_summary(actions: list[dict], leftovers: list[str], applied: bool) -> str:
    if not actions and not leftovers:
        return "I didn't catch anything actionable there. Try again?"
    bits = []
    analyses = []
    for a in actions:
        p = a.get("params", {})
        k = f"{a['domain']}.{a['action']}"
        if k == "shopping.add_items":
            bits.append("added " + ", ".join(i["name"] for i in p.get("items", [])) + " to the shopping list")
        elif k == "reminder.add":
            bits.append(f"set a reminder to {p.get('title', '').lower()} for {_nice(p.get('due_at'))}")
        elif k == "calendar.add_event":
            bits.append(f"put {p.get('title')} on the calendar for {_nice(p.get('starts_at'))}")
        elif k == "health.log_biometric":
            bits.append(f"logged {p.get('metric')} {p.get('value'):g} {p.get('unit') or ''}".strip())
        elif k == "health.log_medication":
            bits.append(f"marked {p.get('name')} as {'taken' if p.get('taken', True) else 'skipped'}")
        elif k == "health.add_medication":
            bits.append(f"added {p.get('name')} at {', '.join(p.get('times', []))}")
        elif k == "health.checkin":
            bits.append(f"checked in {p.get('kind')}: {p.get('value')}")
        elif k == "health.log_fasting":
            bits.append("logged today's fast as " + ("kept" if p.get("kept", True) else "broken"))
        elif k == "family.add_chore":
            bits.append(f"gave {p.get('member_name') or 'the family'} the chore '{p.get('title')}'")
        elif k == "family.add_milestone":
            bits.append(f"saved a milestone for {p.get('member_name')}")
        elif k == "tasks.add":
            bits.append(f"added the task '{p.get('title')}'")
        elif k == "finance.add_transaction":
            bits.append(f"recorded ${p.get('amount'):.2f} at {p.get('merchant')}")
        elif k == "finance.list_recurring_transactions":
            res = a.get("result") or {}
            recs = res.get("recurring") or []
            if res.get("error"):
                bits.append(res["error"])
            elif recs:
                bits.append(f"found {len(recs)} recurring charge{'s' if len(recs) != 1 else ''}")
                analyses.append("Recurring charges:\n" + "\n".join(
                    f"- {r['merchant']}: {r['count']}x, ${r['total']:,.2f} total (~${r['avg']:,.2f} each)"
                    for r in recs[:15]))
            else:
                bits.append("found no recurring charges")
        elif k == "finance.find_transactions":
            res = a.get("result") or {}
            txns = res.get("transactions") or []
            if res.get("error"):
                bits.append(res["error"])
            elif txns:
                bits.append(f"found {len(txns)} matching transaction{'s' if len(txns) != 1 else ''}")
                analyses.append("Matching transactions:\n" + "\n".join(
                    f"- {t.get('date')}: {t.get('description')} — ${t.get('amount', 0):,.2f}"
                    for t in txns[:15]))
            else:
                bits.append("found no matching transactions")
        elif k == "pantry.add_items":
            bits.append(f"stocked {len(p.get('items', []))} items in the pantry")
        elif k == "pantry.consume":
            bits.append("marked " + ", ".join(p.get("items", [])) + " as used up")
        elif k == "health.analyze":
            bits.append("analyzed your latest health report")
            result = a.get("result", {}) or {}
            analysis_obj = result.get("analysis") or {}
            analysis_text = analysis_obj.get("analysis") if isinstance(analysis_obj, dict) else str(analysis_obj)
            if analysis_text:
                analyses.append(analysis_text)
        else:
            bits.append(k.replace(".", " "))
    lead = "Done — " if applied else "Ready for your go-ahead: "
    text = lead + "; ".join(bits) + "."
    if leftovers:
        text += " I wasn't sure what to do with: " + "; ".join(f"“{l}”" for l in leftovers) + "."
    if analyses:
        text += "\n\n" + "\n\n".join(analyses)
    return text


def _nice(iso: Optional[str]) -> str:
    if not iso:
        return "later"
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        return iso
    today = datetime.now().date()
    d = "today" if dt.date() == today else ("tomorrow" if dt.date() == today + timedelta(days=1) else dt.strftime("%a %b %-d"))
    return f"{d} at {dt.strftime('%-I:%M %p').lower()}"


async def understand(text: str, use_llm: bool = True, now: Optional[datetime] = None) -> dict:
    """Full pipeline: parse deterministically, LLM-fill leftovers, return actions + reply."""
    actions, leftovers = parse_utterance(text, now, strict=use_llm)
    if leftovers and use_llm:
        extra = await llm_parse(leftovers, now)
        if extra:
            actions.extend(extra)
            leftovers = []
        else:
            # LLM unavailable: fall back to the greedy regex result rather than dropping the clause
            fallback, leftovers = parse_utterance(" , ".join(leftovers), now, strict=False)
            actions.extend(fallback)
    return {"actions": actions, "unparsed": leftovers}


async def chat_reply(text: str, context: str = "") -> str:
    """Conversational reply in the Avira persona (used when nothing is actionable)."""
    prompt = f"{context}\n\nUser: {text}\nAvira:" if context else f"User: {text}\nAvira:"
    out = await generate(prompt, task="assistant", system=AVIRA_SYSTEM, timeout=40, temperature=0.6)
    return out.strip() or "I'm here. What would you like me to handle?"
