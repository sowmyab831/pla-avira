"""Pure-function tests: Nexus rules, receipt parser, email radar classification."""
from datetime import date, datetime

from app.routes.nexus import parse_receipt_text
from app.services.imap_radar import classify, deep_link, mask, build_signals
from app.services.nexus_bus import rules_for, categorize_item

COSTCO = """COSTCO WHOLESALE
Member 111222333444
ORG BANANAS            1.99 F
KS ORGANIC EGGS 24CT   7.49 F
CHICKEN BREAST 6LB     24.86 F
WHOLE MILK 2GAL        6.29 F
PAPER TOWELS 12PK      21.99
BABY SPINACH           4.49 F
SUBTOTAL               67.11
TAX                    1.32
TOTAL                  68.43
VISA  ************1234
09/05/2026 10:41
"""


def test_receipt_parser_extracts_items_total_date():
    r = parse_receipt_text(COSTCO)
    assert r["store"] == "Costco"
    assert r["total"] == 68.43
    assert r["date"] == "2026-09-05"
    names = [i["name"] for i in r["items"]]
    assert "Org Bananas" in names and "Paper Towels 12Pk" in names
    assert not any("SUBTOTAL" in n.upper() or "VISA" in n.upper() for n in names)
    cats = {i["name"]: i["category"] for i in r["items"]}
    assert cats["Paper Towels 12Pk"] == "household"
    assert cats["Baby Spinach"] == "produce"


def test_receipt_rules_fan_out_to_pantry_and_finance():
    r = parse_receipt_text(COSTCO)
    summary, acts = rules_for("receipt.parsed", {**r, "receipt_id": "r1"})
    keys = [f"{a['domain']}.{a['action']}" for a in acts]
    assert keys == ["pantry.add_items", "finance.add_transaction"]
    pantry_names = [i["name"] for i in acts[0]["params"]["items"]]
    assert "Paper Towels 12Pk" not in pantry_names  # household stays out of the pantry
    assert acts[1]["params"]["amount"] == 68.43
    assert all(a["safe"] for a in acts)  # receipt fan-out auto-applies


def test_email_bill_rule_creates_reminder_and_calendar():
    _, acts = rules_for("email.signal", {"category": "bill", "subject": "Duke Energy bill", "due_date": "2026-09-15",
                                          "deep_link": "https://mail.google.com/x", "signal_id": "s1"})
    keys = [f"{a['domain']}.{a['action']}" for a in acts]
    assert keys == ["reminder.add", "calendar.add_event"]
    assert acts[0]["params"]["due_at"].startswith("2026-09-15")


def test_email_appointment_requires_confirmation():
    _, acts = rules_for("email.signal", {"category": "appointment", "subject": "Dentist visit", "due_date": "2026-09-10", "time": "14:30"})
    assert acts[0]["safe"] is False
    assert acts[0]["params"]["starts_at"] == "2026-09-10T14:30:00"


def test_radar_classification_gold():
    ref = datetime(2026, 9, 6)
    cases = [
        ("Your Duke Energy bill is ready: $142.17 due Sep 15", "Please pay by 09/15/2026", "bill", 142.17, date(2026, 9, 15)),
        ("Appointment confirmation - Dr. Patel, Sept 10 at 2:30 PM", "See you soon", "appointment", None, date(2026, 9, 10)),
        ("Permission slip needed: field trip Friday", "Please sign and return the form", "school", None, None),
        ("Your package has shipped!", "Tracking 1Z999", "delivery", None, None),
        ("Your Costco membership expires on 10/01/2026", "Renew today", "renewal", None, date(2026, 10, 1)),
        ("50% off everything this weekend", "Unsubscribe", "promo", None, None),
        ("Action required: verify your W-2 information", "Deadline 09/08/2026", "action", None, date(2026, 9, 8)),
    ]
    for subject, snippet, cat, amount, due in cases:
        c = classify(subject, snippet, "example.com", ref)
        assert c["category"] == cat, (subject, c)
        assert c["amount"] == amount, (subject, c)
        assert c["due_date"] == due, (subject, c)
    urgent = classify("Action required: verify your W-2 information", "Deadline 09/08/2026", "x", ref)
    assert urgent["priority"] == "high"


def test_masking_removes_pii():
    s = mask("Acct #: 12345678 for john.doe@gmail.com call 919-555-1234 card 4111 1111 1111 1111")
    assert "gmail.com" not in s and "919" not in s and "4111" not in s and "12345678" not in s


def test_gmail_deep_link_uses_rfc822msgid():
    link = deep_link("gmail", "<abc123@mail.duke-energy.com>", "me@gmail.com")
    from urllib.parse import urlparse, parse_qs, unquote
    parsed = urlparse(link)
    assert parsed.scheme == "https" and parsed.hostname == "mail.google.com"
    assert parse_qs(parsed.query)["authuser"] == ["me@gmail.com"]
    assert unquote(parsed.fragment) == "search/rfc822msgid:abc123@mail.duke-energy.com"
    assert "abc123" in link


def test_build_signals_masks_subject_and_sets_reply():
    raw = [{"uid": 1, "message_id": "<m1@x>", "sender_name": "Dr Office", "sender_domain": "clinic.com",
            "subject": "Appointment for john.doe@gmail.com on 09/10/2026 at 9am", "received_at": datetime(2026, 9, 6), "snippet": "", "is_list": False}]
    sig = build_signals(raw, "gmail", "me@gmail.com")[0]
    assert sig["category"] == "appointment"
    assert "[EMAIL]" in sig["subject"]
    assert sig["suggested_reply"]
    assert sig["time"] == "09:00"


def test_categorize_item():
    assert categorize_item("Organic Whole Milk") == "dairy"
    assert categorize_item("Ground Beef 80/20") == "meat"
    assert categorize_item("Dish Soap") == "household"
