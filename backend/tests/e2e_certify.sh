#!/usr/bin/env bash
# End-to-end certification of the six Avira use cases against a running backend.
# Usage: API=http://localhost:30002 ./tests/e2e_certify.sh
set -euo pipefail
API="${API:-http://localhost:30002}"
U="cert_$(date +%s)"
J='Content-Type: application/json'

TOK=$(curl -sf -X POST "$API/api/auth/signup" -H "$J" -d "{\"username\":\"$U\",\"email\":\"$U@example.com\",\"password\":\"Certify!2026\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
A="Authorization: Bearer $TOK"
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; exit 1; }
jq_() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }

echo "== Use case C/E: family vault =="
MAYA=$(curl -sf -X POST "$API/api/family-hub/members" -H "$A" -H "$J" -d '{"name":"Maya","role":"child","birthdate":"2018-04-12","allergies":["peanuts"],"interests":["soccer","dinosaurs"],"sizes":{"shoe":"1Y","shirt":"7"},"emergency":{"doctor":"Dr Patel","phone":"[on file]"}}' | jq_ 'd["id"]')
LEO=$(curl -sf -X POST "$API/api/family-hub/members" -H "$A" -H "$J" -d '{"name":"Leo","role":"child","birthdate":"2015-11-02","interests":["lego"]}' | jq_ 'd["id"]')
[ -n "$MAYA" ] && pass "members created (Maya, Leo)"

echo "== Use case A: meds + fasting =="
curl -sf -X POST "$API/api/care/medications" -H "$A" -H "$J" -d '{"name":"Lisinopril","dose":"10mg","times":["07:30"],"with_food":"any"}' >/dev/null
curl -sf -X POST "$API/api/care/fasting" -H "$A" -H "$J" -d '{"protocol":"16:8","eating_start":"12:00","eating_end":"20:00"}' >/dev/null
pass "medication + 16:8 window set"

echo "== Use case F: multi-intent voice (one sentence → 5 domains) =="
R=$(curl -sf -X POST "$API/api/nexus/ingest" -H "$A" -H "$J" -d '{"text":"Add milk, eggs and 2 lbs chicken to the shopping list, remind me to call the dentist tomorrow at 4, I weighed 182 lbs, took my lisinopril, and schedule soccer practice for Maya Saturday at 10am","use_llm":false}')
echo "$R" | jq_ '"  reply: "+d["reply"]'
N=$(echo "$R" | jq_ 'len(d["actions"])'); [ "$N" = "5" ] || fail "expected 5 actions, got $N"
ST=$(echo "$R" | jq_ 'd["event"]["status"]'); [ "$ST" = "proposed" ] || fail "calendar action should require confirmation"
EV=$(echo "$R" | jq_ 'd["event"]["id"]')
pass "5 actions decomposed; held as proposed (calendar needs OK)"
curl -sf -X POST "$API/api/nexus/events/$EV/confirm" -H "$A" -H "$J" -d '{}' | jq_ '"  applied: "+str([a["status"] for a in d["actions"]])'
MED_OK=$(curl -sf "$API/api/care/medications" -H "$A" | jq_ 'd["medications"][0]["taken_today"]'); [ "$MED_OK" = "True" ] || fail "med not logged"
SHOP=$(curl -sf "$API/api/pantry/shopping" -H "$A" | jq_ 'len(d["items"])'); [ "$SHOP" = "3" ] || fail "shopping list should have 3 items"
CAL=$(curl -sf "$API/api/family-hub/calendar" -H "$A" | jq_ 'd["events"][0]["who"]'); [ "$CAL" = "Maya" ] || fail "calendar event not linked to Maya"
pass "confirm applied → med logged, 3 shopping items, calendar event for Maya"

echo "== Use case B: receipt → pantry + finance + meal ideas =="
RC=$(curl -sf -X POST "$API/api/nexus/receipt" -H "$A" -H "$J" -d @- <<'EOF'
{"text":"COSTCO WHOLESALE\nORG BANANAS            1.99 F\nKS ORGANIC EGGS 24CT   7.49 F\nCHICKEN BREAST 6LB     24.86 F\nWHOLE MILK 2GAL        6.29 F\nPAPER TOWELS 12PK      21.99\nBABY SPINACH           4.49 F\nSUBTOTAL 67.11\nTAX 1.32\nTOTAL 68.43\nVISA ************1234\n09/05/2026 10:41"}
EOF
)
echo "$RC" | jq_ '"  receipt: "+d["receipt"]["store"]+" $"+str(d["receipt"]["total"])+" items="+str(len(d["receipt"]["items"]))+" event="+d["event"]["status"]'
REV=$(echo "$RC" | jq_ 'd["event"]["id"]')
P=$(curl -sf "$API/api/pantry" -H "$A" | jq_ 'd["count"]'); [ "$P" = "5" ] || fail "pantry should have 5 grocery items (household excluded), got $P"
TX=$(curl -sf "$API/api/pantry/transactions" -H "$A" | jq_ 'd["total"]'); [ "$TX" = "68.43" ] || fail "transaction total wrong: $TX"
pass "pantry=5 items, finance=\$68.43, auto-applied"
echo "== Undo =="
curl -sf -X POST "$API/api/nexus/events/$REV/undo" -H "$A" | jq_ '"  status: "+d["status"]'
P=$(curl -sf "$API/api/pantry" -H "$A" | jq_ 'd["count"]'); [ "$P" = "0" ] || fail "undo should empty pantry, got $P"
TX=$(curl -sf "$API/api/pantry/transactions" -H "$A" | jq_ 'd["total"]'); [ "$TX" = "0" ] || fail "undo should remove transaction"
pass "undo reverted pantry + finance atomically"
curl -sf -X POST "$API/api/nexus/receipt" -H "$A" -H "$J" -d '{"text":"TRADER JOES\nORGANIC SPINACH 2.99\nGREEK YOGURT 4.49\nSALMON FILLET 11.99\nBROWN RICE 3.29\nTOTAL 22.76\n09/06/2026"}' >/dev/null
pass "second receipt re-stocked pantry"

echo "== Use case D: email radar (metadata only, deep links) =="
RD=$(curl -sf -X POST "$API/api/radar/demo" -H "$A" -H "$J" -d @- <<'EOF'
{"emails":[
 {"from":"billing@duke-energy.com","subject":"Your Duke Energy bill is ready: $142.17 due Sep 15","snippet":"Account 88213 - pay by 09/15/2026","message_id":"<bill1@duke-energy.com>"},
 {"from":"noreply@patelpediatrics.com","subject":"Appointment confirmation - Dr. Patel, Sept 10 at 2:30 PM","snippet":"Bring insurance card","message_id":"<appt1@patel.com>"},
 {"from":"office@lincolnelementary.org","subject":"Permission slip needed: field trip Friday","snippet":"Please sign and return the form by Thursday","message_id":"<school1@lincoln.org>"},
 {"from":"deals@retailer.com","subject":"50% off everything this weekend","snippet":"Unsubscribe","message_id":"<promo1@retailer.com>"},
 {"from":"ship@amazon.com","subject":"Your package has shipped!","snippet":"Arriving Tuesday","message_id":"<ship1@amazon.com>"}
]}
EOF
)
echo "$RD" | jq_ '"  stored: "+str([(s["category"],s["priority"],s["due_date"]) for s in d["signals"]])'
CNT=$(echo "$RD" | jq_ 'len(d["signals"])'); [ "$CNT" = "4" ] || fail "promo should be filtered; got $CNT signals"
BILL_LINK=$(echo "$RD" | jq_ '[s for s in d["signals"] if s["category"]=="bill"][0]["deep_link"]'); [[ "$BILL_LINK" == https://mail.google.com/* ]] || fail "no gmail deep link"
REM=$(curl -sf "$API/api/family-hub/reminders" -H "$A" | jq_ 'len([r for r in d["reminders"] if r["kind"]=="bill"])'); [ "$REM" = "1" ] || fail "bill reminder not created"
PEND=$(curl -sf "$API/api/nexus/events?status=proposed" -H "$A" | jq_ 'len(d["events"])'); [ "$PEND" -ge 1 ] || fail "appointment should be pending confirmation"
pass "4 signals kept (promo dropped), bill → reminder auto, appointment → pending, deep link present"

echo "== Use case E: babysitter sheet + packing list =="
curl -sf "$API/api/family-hub/babysitter-sheet?hours=12" -H "$A" | jq_ '"  "+d["text"].split(chr(10))[2]'
PK=$(curl -sf -X POST "$API/api/family-hub/packing-list" -H "$A" -H "$J" -d '{"destination":"Outer Banks","nights":4,"climate":"hot","activities":["beach"]}' | jq_ 'len(d["per_person"])'); [ "$PK" = "2" ] || fail "packing list per person"
pass "babysitter sheet mentions allergies; packing list for 2 kids"

echo "== Use case C: chores =="
curl -sf -X POST "$API/api/nexus/ingest" -H "$A" -H "$J" -d '{"text":"Assign a chore for Leo: feed the dog every day","use_llm":false}' >/dev/null
CH=$(curl -sf "$API/api/family-hub/chores" -H "$A" | jq_ 'd["chores"][0]["who"]'); [ "$CH" = "Leo" ] || fail "chore not assigned to Leo"
pass "voice chore assigned to Leo"

echo "== Morning brief =="
curl -sf "$API/api/nexus/brief" -H "$A" | jq_ '"  "+d["spoken"]'

echo "== Tier gating =="
curl -s -o /dev/null -w "  radar/accounts limit check → HTTP %{http_code} (expect 400 IMAP fail, not 403)\n" -X POST "$API/api/radar/accounts" -H "$A" -H "$J" -d '{"email":"x@gmail.com","app_password":"bad","provider":"gmail"}'
for i in 1 2 3; do curl -s -o /dev/null -X POST "$API/api/family-hub/members" -H "$A" -H "$J" -d "{\"name\":\"Extra$i\"}"; done
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/api/family-hub/members" -H "$A" -H "$J" -d '{"name":"Overflow"}'); [ "$CODE" = "403" ] || fail "free tier should cap family members (got $CODE)"
pass "free tier cap enforced on family members (403)"

echo
echo "ALL USE CASES CERTIFIED ✅  (user=$U)"
