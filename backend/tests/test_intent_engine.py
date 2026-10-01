"""Gold-file tests for the deterministic multi-intent parser (no LLM, no DB)."""
from datetime import datetime

import pytest

from app.services.intent_engine import parse_utterance, parse_clause

NOW = datetime(2026, 9, 6, 14, 0)  # Sunday 2pm


def keys(actions):
    return [f"{a['domain']}.{a['action']}" for a in actions]


def test_multi_intent_six_way():
    text = ("Add milk, eggs and 2 lbs chicken to the shopping list, remind me to call the dentist tomorrow at 4, "
            "I weighed 182 lbs, took my lisinopril, and schedule soccer practice for Maya Saturday at 10am")
    actions, leftovers = parse_utterance(text, NOW)
    assert leftovers == []
    assert keys(actions) == ["shopping.add_items", "reminder.add", "health.log_biometric",
                             "health.log_medication", "calendar.add_event"]
    shop = actions[0]["params"]["items"]
    assert [i["name"] for i in shop] == ["milk", "eggs", "chicken"]
    assert shop[2]["quantity"] == "2 lbs"
    assert actions[1]["params"]["due_at"] == "2026-09-07T16:00:00"
    assert actions[1]["params"]["title"].lower().startswith("call the dentist")
    assert actions[2]["params"] == {"metric": "weight", "value": 182.0, "unit": "lb"}
    assert actions[3]["params"] == {"name": "lisinopril", "taken": True}
    cal = actions[4]["params"]
    assert cal["starts_at"] == "2026-09-12T10:00:00"
    assert cal["member_name"] == "Maya"


def test_blood_pressure_expands_to_two_metrics():
    actions, _ = parse_utterance("bp 128 over 82", NOW)
    assert keys(actions) == ["health.log_biometric", "health.log_biometric"]
    assert actions[0]["params"]["value"] == 128 and actions[1]["params"]["value"] == 82


def test_chore_and_milestone():
    actions, left = parse_utterance("Assign a chore for Leo: feed the dog every day. Leo learned to ride a bike today", NOW)
    assert "family.add_chore" in keys(actions)
    chore = next(a for a in actions if a["action"] == "add_chore")["params"]
    assert chore["member_name"] == "Leo" and "feed the dog" in chore["title"].lower()
    assert "family.add_milestone" in keys(actions)


def test_fasting_and_workout_checkins():
    actions, _ = parse_utterance("kept my fast, worked out, slept 7 hours", NOW)
    assert keys(actions) == ["health.log_fasting", "health.checkin", "health.log_biometric"]
    assert actions[0]["params"]["kept"] is True
    assert actions[2]["params"]["metric"] == "sleep_h"


def test_new_medication_with_schedule():
    a = parse_clause("start medication metformin 500mg twice a day with food", NOW)
    assert a["action"] == "add_medication"
    assert a["params"]["name"].startswith("metformin")
    assert a["params"]["times"] == ["08:00", "20:00"]
    assert a["params"]["with_food"] == "with"


def test_spent_transaction():
    a = parse_clause("spent $42.50 at Costco", NOW)
    assert a["domain"] == "finance" and a["params"]["amount"] == 42.5 and a["params"]["merchant"] == "Costco"


def test_reminder_relative_time():
    a = parse_clause("remind me in 30 minutes to move the laundry", NOW)
    assert a["action"] == "add"
    assert a["params"]["due_at"] == "2026-09-06T14:30:00"


def test_unknown_clause_is_left_for_llm():
    actions, left = parse_utterance("what's the weather like in Paris", NOW)
    assert actions == [] and left == ["what's the weather like in Paris"]


def test_safe_flags():
    actions, _ = parse_utterance("add bread to the list and book the pediatrician Tuesday at 9am", NOW)
    assert actions[0]["safe"] is True
    assert actions[1]["safe"] is False
