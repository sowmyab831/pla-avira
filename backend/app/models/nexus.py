"""Persistent models for the cross-module Nexus and the domains it connects.

Every table is keyed by `user_id` (matches `UserDB.user_id`). Sensitive raw
content (email bodies, full receipts) is never stored — only masked metadata.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, JSON, String, Text

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Nexus core ───────────────────────────────────────────────────────────────
class NexusEventDB(Base):
    """One trigger (receipt scanned, email seen, voice command) and the fan-out
    of actions it proposed. Actions are applied atomically and can be undone."""
    __tablename__ = "nexus_events"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    source_domain = Column(String, nullable=False)          # voice, email, receipt, health, ...
    event_type = Column(String, nullable=False)             # receipt.parsed, email.bill, intent.batch
    summary = Column(String, nullable=True)                 # human-readable one-liner
    payload = Column(JSON, nullable=True)                   # masked trigger data
    actions = Column(JSON, nullable=False, default=list)    # [{domain, action, params, result, status}]
    status = Column(String, nullable=False, default="proposed")  # proposed, applied, undone, rejected
    auto_applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    applied_at = Column(DateTime, nullable=True)
    undone_at = Column(DateTime, nullable=True)


# ── Life Admin Radar (email metadata only) ───────────────────────────────────
class EmailAccountDB(Base):
    __tablename__ = "email_accounts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False)
    provider = Column(String, nullable=False, default="gmail")  # gmail, outlook, icloud, custom
    imap_host = Column(String, nullable=False)
    imap_port = Column(Integer, default=993)
    secret_enc = Column(Text, nullable=False)                   # Fernet-encrypted app password
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    last_uid = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailSignalDB(Base):
    """A single actionable email, reduced to metadata + a deep link."""
    __tablename__ = "email_signals"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=False, index=True)
    message_id = Column(String, nullable=True, index=True)
    uid = Column(Integer, nullable=True)
    sender_domain = Column(String, nullable=True)
    sender_name = Column(String, nullable=True)
    subject = Column(String, nullable=True)                 # masked
    received_at = Column(DateTime, nullable=True)
    category = Column(String, nullable=False, default="other")  # bill, appointment, school, delivery, renewal, travel, refund, action, promo, other
    amount = Column(Float, nullable=True)
    due_date = Column(Date, nullable=True)
    priority = Column(String, default="medium")
    deep_link = Column(String, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    status = Column(String, default="open")                 # open, done, snoozed, dismissed
    nexus_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Health: meds, fasting, biometrics, check-ins ────────────────────────────
class MedicationDB(Base):
    __tablename__ = "medications"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True, index=True)   # null = the user
    name = Column(String, nullable=False)
    dose = Column(String, nullable=True)
    times = Column(JSON, nullable=False, default=list)      # ["07:30", "20:00"]
    with_food = Column(String, nullable=True)               # before, with, after, any
    notes = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    refill_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MedicationLogDB(Base):
    __tablename__ = "medication_logs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    medication_id = Column(String, nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False)
    taken = Column(Boolean, nullable=True)                  # None = pending, True/False = answered
    answered_at = Column(DateTime, nullable=True)
    source = Column(String, default="app")                  # app, voice, telegram


class FastingWindowDB(Base):
    __tablename__ = "fasting_windows"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    protocol = Column(String, nullable=False, default="16:8")
    eating_start = Column(String, nullable=False, default="12:00")
    eating_end = Column(String, nullable=False, default="20:00")
    days = Column(JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FastingLogDB(Base):
    __tablename__ = "fasting_logs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    day = Column(Date, nullable=False)
    kept = Column(Boolean, nullable=True)
    note = Column(String, nullable=True)
    answered_at = Column(DateTime, nullable=True)


class BiometricDB(Base):
    __tablename__ = "biometrics"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True)
    metric = Column(String, nullable=False)                 # weight, bp_sys, bp_dia, glucose, steps, sleep_h, hr, waist
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String, default="manual")


class CheckInDB(Base):
    """Binary / 1-tap daily check-ins: mood, energy, workout done, water."""
    __tablename__ = "checkins"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    kind = Column(String, nullable=False)                   # workout, water, mood, stretch, sleep
    value = Column(String, nullable=True)                   # "yes"/"no"/"7"
    answered_at = Column(DateTime, default=datetime.utcnow)


# ── Pantry / receipts / finance ─────────────────────────────────────────────
class ReceiptDB(Base):
    __tablename__ = "receipts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    store = Column(String, nullable=True)
    purchased_on = Column(Date, nullable=True)
    total = Column(Float, nullable=True)
    category = Column(String, default="grocery")
    items = Column(JSON, nullable=False, default=list)      # [{name, qty, unit, price, category, perishable_days}]
    raw_hash = Column(String, nullable=True)
    nexus_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PantryItemDB(Base):
    __tablename__ = "pantry_items"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    normalized = Column(String, nullable=False, index=True)
    quantity = Column(Float, default=1)
    unit = Column(String, default="count")
    category = Column(String, default="pantry")             # produce, dairy, meat, pantry, frozen, household
    purchased_on = Column(Date, nullable=True)
    expires_on = Column(Date, nullable=True)
    receipt_id = Column(String, nullable=True)
    status = Column(String, default="in_stock")             # in_stock, low, used, expired
    created_at = Column(DateTime, default=datetime.utcnow)


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    occurred_on = Column(Date, nullable=False, index=True)
    merchant = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    category = Column(String, default="other")
    source = Column(String, default="manual")               # receipt, statement, email, manual
    source_id = Column(String, nullable=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShoppingItemDB(Base):
    __tablename__ = "shopping_items"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    quantity = Column(String, nullable=True)
    reason = Column(String, nullable=True)                  # "low in pantry", "for Tuesday dinner", "voice"
    store_hint = Column(String, nullable=True)
    checked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Family, chores, calendar, reminders ─────────────────────────────────────
class FamilyMemberDB(Base):
    __tablename__ = "family_members"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="child")                  # parent, child, partner, pet, other
    birthdate = Column(Date, nullable=True)
    school = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    sizes = Column(JSON, nullable=True)                     # {shoe, shirt, pants, jacket}
    allergies = Column(JSON, nullable=True)                 # ["peanuts"]
    wishlist = Column(JSON, nullable=True)                  # [{item, note, url}]
    interests = Column(JSON, nullable=True)
    emergency = Column(JSON, nullable=True)                 # {doctor, phone, insurance_note}
    notes = Column(Text, nullable=True)
    # Lifecycle: invited → active → removed. Rows are never hard-deleted so
    # linked documents/history stay attributable. `invited` members exist but
    # are excluded from active lists until accepted.
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)


class ChoreDB(Base):
    __tablename__ = "chores"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    recurrence = Column(String, default="daily")            # daily, weekdays, weekly:mon, once
    points = Column(Integer, default=1)
    due_time = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChoreLogDB(Base):
    __tablename__ = "chore_logs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    chore_id = Column(String, nullable=False, index=True)
    day = Column(Date, nullable=False)
    done = Column(Boolean, default=True)
    done_at = Column(DateTime, default=datetime.utcnow)


class CalendarEventDB(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=True)
    location = Column(String, nullable=True)
    kind = Column(String, default="event")                  # event, appointment, school, sport, travel, bill_due
    source = Column(String, default="manual")               # manual, voice, email, nexus
    source_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReminderDB(Base):
    __tablename__ = "reminders"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    due_at = Column(DateTime, nullable=False, index=True)
    channel = Column(String, default="app")                 # app, telegram, voice
    kind = Column(String, default="general")                # general, med, bill, pickup, refill
    source_id = Column(String, nullable=True)
    status = Column(String, default="pending")              # pending, sent, done, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)


class MilestoneDB(Base):
    __tablename__ = "milestones"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    member_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, default="general")            # academic, social, physical, creative, health
    achieved_on = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
