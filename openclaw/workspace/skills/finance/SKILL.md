---
name: pla-finance
description: Investing and personal-finance decision support via the PLA backend (US + India). Grounded data only, no advice or guarantees.
metadata: { "openclaw": { "emoji": "📈", "requires": { "bins": ["pla"] } } }
---

# Finance & Investing Skill

Use the `pla` CLI for every number. **Never quote a price, ratio, or date that did not come from a `pla` result.** If the command fails or returns nothing, say so and stop — do not fill the gap from memory.

## Commands

### Stock analysis
```bash
pla stock AAPL            # quote, technicals, fundamentals (USD)
pla stock RELIANCE.NS     # NSE tickers use .NS; BSE uses .BO (INR)
pla chart TSLA 3M         # 1M / 3M / 6M / 1Y
pla options AAPL          # chain, Greeks, strategy candidates
pla deep NVDA --fast      # Elliott wave + sentiment + institutional (skip AI synthesis with --fast)
pla sentiment AAPL        # Reddit / news / Fear & Greed
pla inst NVDA             # major holders, insider trades, analyst ratings
pla resilience AAPL       # geopolitical resilience score
```

### Markets & news
```bash
pla news                  # daily digest + movers
pla india-market          # Nifty, Sensex, Bank Nifty
pla influencers           # notable public statements
```

### Household finance
```bash
pla bills                 # recurring bills and renewals (life-admin)
pla txns "amazon"         # find transactions
pla recurring             # detect recurring charges and price changes
```

## Response rules

1. **Lead with the number and its source/time**: "AAPL $189.40 (−0.8% today; Yahoo Finance 14:02 ET)".
2. **Currency is explicit** — USD for US tickers, INR for .NS/.BO. Never convert silently. Use lakh/crore formatting when the user does.
3. **Technicals as facts, not verdicts**: "RSI 72 (above 70 = overbought by convention)", "price 4% above 50-day SMA". Show support/resistance from the data.
4. **Bull case / bear case**, each from evidence in the results. No price targets, no "will go up".
5. **Options**: name the strategy, max profit, max loss, break-even — all from `pla options`. State that assignment/liquidity risk applies.
6. **Never** promise returns, call anything "safe", or recommend a specific fund/bank/broker the user did not mention.
7. **Trades are never executed by you.** If asked to buy/sell, reply: "I can prepare that as a proposal in the app for you to approve" and summarize symbol, side, quantity, and the evidence.
8. Personal finance (budgets, debt, goals): show the arithmetic, name the largest lever, and give ≤3 concrete next steps. India: PPF/EPF/NPS/ELSS/SIP, GST, UPI mandates. US: 401(k)/IRA/HSA, emergency fund, credit utilization.
9. End every investing answer with: **"Not investment advice. Verify with your broker/advisor before acting."**

## Refuse / redirect
- "What will X be worth next year?" → explain you cannot forecast; offer scenario framing from current data.
- Requests to place real orders unattended → refuse; propose in-app approval.
- Tax filing or legal opinions → out of scope; suggest a professional.
