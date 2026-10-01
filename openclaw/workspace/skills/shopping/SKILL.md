---
name: pla-shopping
description: Evidence-backed price comparison, price watches, returns and refunds via PLA backend (US + India).
metadata: { "openclaw": { "emoji": "🛒", "requires": { "bins": ["pla"] } } }
---

# Shopping Skill

Only compare offers that `pla` actually returned. **No phantom products, coupons, or cashback.**

## Commands

```bash
pla shop "organic chicken"            # grocery
pla shop "laptop 16GB 512GB"          # electronics (include must-have specs)
pla shop "hershey syrup" --country IN # India merchants, INR
pla watch add "<product key>" 4999    # price watch with target (minor units not required)
pla watch list
pla wishlist
pla receipts                          # linked receipts, return windows, warranties
pla refund status                     # expected vs received refunds
```

## Comparison rules

1. **Match before you compare**: same variant, size/pack quantity, condition (new/refurb), seller type, warranty. If the results differ on any of these, say "not directly comparable" and show them separately.
2. **Totals**: item price + delivery + tax − *applied* immediate discounts. Conditional rewards (cashback "up to", card offers, coupons not marked eligible) are listed as *conditional*, never subtracted.
3. **Unknown stays unknown**: if shipping or tax is missing, mark "total unknown" and do not rank that offer as cheapest.
4. Phrase the winner as **"lowest verified total among these N merchants at HH:MM"**, never "best deal" or "cheapest anywhere".
5. Currency explicit — USD or INR; Indian grouping (₹1,04,999) for INR.
6. Include return window and warranty when present; flag when absent.
7. Produce: Dirty Dozen → suggest organic and say why; Clean 15 → conventional is fine. Only for produce.

## Response format

```
Lowest verified total among 3 merchants (14:05 ET):
1. <title / exact variant> — $X.XX total (item $A + ship $B + tax $C) · Seller · delivers <date> · returns 30d
2. …
Conditional: 5% card cashback on #2 (not applied).
Not comparable: <item> (refurbished).
Suggested actions: add to list · set price watch at $Y · save receipt after purchase
```

## Never
- Invent a price history or "usually costs" figure. Use `pla watch list` history only if present.
- Claim a purchase, return, or refund was submitted. Drafts require approval in the app.
- Hide that a merchant was not searched. Say which merchants were covered.
