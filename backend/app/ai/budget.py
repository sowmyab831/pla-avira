"""Spending controls that survive concurrency.

* Money is integer micro-USD. Never floats.
* Before a provider call: `reserve()` atomically checks and holds a conservative
  estimate on user, org and platform accounts inside one transaction using row
  locks (`SELECT ... FOR UPDATE` on PostgreSQL; a process-wide lock + the same
  SQL on SQLite for tests).
* After the call: `settle()` converts the reservation into spend (or `pending`
  when usage is ambiguous, e.g. stream disconnect) and releases the remainder.
* Unknown prices are not zero: managed (platform-funded) routing to a model
  without a recorded price raises QUOTA_EXHAUSTED-class error. BYOK is metered
  as an *estimate* with no hard cap unless the user sets one.
* All writes are idempotent on `ai_usage_events.idempotency_key`.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.ai.registry import ModelSpec
from app.ai.schemas import ActorContext, AIError, ErrorCode, Usage
from app.models.ai import AIBudgetAccountDB, AIUsageEventDB

_SQLITE_LOCKS: dict[int, asyncio.Lock] = {}
CHARS_PER_TOKEN = 4


def _sqlite_lock() -> asyncio.Lock:
    """One lock per running event loop (an asyncio.Lock cannot outlive its loop)."""
    loop_id = id(asyncio.get_running_loop())
    lock = _SQLITE_LOCKS.get(loop_id)
    if lock is None:
        _SQLITE_LOCKS.clear()
        lock = _SQLITE_LOCKS[loop_id] = asyncio.Lock()
    return lock          # conservative estimate for reservation
RESERVE_SAFETY = 1.5         # reserve 150% of the estimate


def period_now(now: Optional[datetime] = None) -> str:
    return (now or datetime.utcnow()).strftime("%Y-%m")


def estimate_tokens(chars: int) -> int:
    return max(1, math.ceil(chars / CHARS_PER_TOKEN))


def price_micro(spec: ModelSpec, usage: Usage) -> Optional[int]:
    """Exact integer cost for reported usage, or None when the price is unknown."""
    if not spec.price_known:
        return None
    inp = usage.input_tokens - usage.cached_input_tokens
    cost = inp * spec.input_micro_per_1m + usage.output_tokens * spec.output_micro_per_1m
    if usage.cached_input_tokens:
        cached_rate = spec.cached_input_micro_per_1m if spec.cached_input_micro_per_1m is not None else spec.input_micro_per_1m
        cost += usage.cached_input_tokens * cached_rate
    if usage.reasoning_tokens:
        cost += usage.reasoning_tokens * spec.output_micro_per_1m
    return math.ceil(cost / 1_000_000)


def estimate_micro(spec: ModelSpec, prompt_chars: int, max_output_tokens: int) -> Optional[int]:
    if not spec.price_known:
        return None
    est = Usage(input_tokens=estimate_tokens(prompt_chars), output_tokens=max_output_tokens)
    base = price_micro(spec, est) or 0
    return math.ceil(base * RESERVE_SAFETY)


@dataclass
class Reservation:
    event_id: str
    idempotency_key: str
    amount_micro: int
    funding: str
    accounts: list[str]          # account ids touched
    price_known: bool


class BudgetLedger:
    """All methods take an AsyncSession-like `db` (real or the test adapter)."""

    def __init__(self, db, *, is_sqlite: bool = False):
        self.db = db
        self.is_sqlite = is_sqlite

    async def _account(self, scope_kind: str, scope_id: str, funding: str, period: str, *, lock: bool) -> AIBudgetAccountDB:
        q = select(AIBudgetAccountDB).where(
            AIBudgetAccountDB.scope_kind == scope_kind, AIBudgetAccountDB.scope_id == scope_id,
            AIBudgetAccountDB.funding == funding, AIBudgetAccountDB.period == period)
        if lock and not self.is_sqlite:
            q = q.with_for_update()
        row = (await self.db.execute(q)).scalar_one_or_none()
        if row is None:
            row = AIBudgetAccountDB(scope_kind=scope_kind, scope_id=scope_id, funding=funding, period=period)
            self.db.add(row)
            await self.db.flush()
            if lock and not self.is_sqlite:
                row = (await self.db.execute(q)).scalar_one()
        return row

    async def set_limit(self, scope_kind: str, scope_id: str, limit_micro: Optional[int], *,
                        funding: str = "platform", period: Optional[str] = None) -> None:
        row = await self._account(scope_kind, scope_id, funding, period or period_now(), lock=False)
        row.limit_micro_usd = limit_micro
        row.updated_at = datetime.utcnow()
        await self.db.commit()

    async def reserve(self, actor: ActorContext, spec: ModelSpec, *, task: str, request_id: str,
                      idempotency_key: str, prompt_chars: int, max_output_tokens: int,
                      funding: str, connection_id: Optional[str], attempt: int = 1,
                      fallback_from: Optional[str] = None) -> Reservation:
        est = estimate_micro(spec, prompt_chars, max_output_tokens)
        if est is None and funding == "platform" and spec.locality.value == "cloud":
            raise AIError(ErrorCode.QUOTA_EXHAUSTED,
                          f"No verified price for {spec.key}; managed routing is blocked until an admin records one",
                          provider=spec.provider, model=spec.model_id, http_status=402)
        amount = est or 0
        period = period_now()

        async def _do() -> Reservation:
            # Idempotency: same key → same reservation.
            existing = (await self.db.execute(select(AIUsageEventDB).where(AIUsageEventDB.idempotency_key == idempotency_key))).scalar_one_or_none()
            if existing:
                return Reservation(existing.id, idempotency_key, existing.reserved_micro_usd, existing.funding, [], spec.price_known)

            scopes = [("user", actor.user_id)]
            if actor.tenant_id:
                scopes.append(("org", actor.tenant_id))
            if funding == "platform":
                scopes.append(("platform", "platform"))
            touched: list[str] = []
            for kind, sid in scopes:
                acct = await self._account(kind, sid, funding, period, lock=True)
                available = None if acct.limit_micro_usd is None else acct.limit_micro_usd - acct.spent_micro_usd - acct.reserved_micro_usd - acct.pending_micro_usd
                if available is not None and amount > available:
                    await self.db.rollback()
                    raise AIError(ErrorCode.QUOTA_EXHAUSTED,
                                  f"{'Your' if kind == 'user' else kind.capitalize()} AI allowance for {period} is exhausted",
                                  provider=spec.provider, model=spec.model_id, http_status=402)
                acct.reserved_micro_usd += amount
                acct.updated_at = datetime.utcnow()
                touched.append(acct.id)
            ev = AIUsageEventDB(request_id=request_id, idempotency_key=idempotency_key, user_id=actor.user_id,
                                tenant_id=actor.tenant_id, task=task, provider=spec.provider, model=spec.model_id,
                                locality=spec.locality.value, funding=funding, connection_id=connection_id,
                                state="reserved", reserved_micro_usd=amount, price_version=spec.price_version,
                                attempt=attempt, fallback_from=fallback_from)
            self.db.add(ev)
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()
                existing = (await self.db.execute(select(AIUsageEventDB).where(AIUsageEventDB.idempotency_key == idempotency_key))).scalar_one()
                return Reservation(existing.id, idempotency_key, existing.reserved_micro_usd, existing.funding, [], spec.price_known)
            return Reservation(ev.id, idempotency_key, amount, funding, touched, spec.price_known)

        if self.is_sqlite:
            async with _sqlite_lock():
                return await _do()
        return await _do()

    async def settle(self, res: Reservation, actor: ActorContext, spec: ModelSpec, usage: Usage, *,
                     latency_ms: int, provider_request_id: Optional[str] = None,
                     state: str = "settled") -> tuple[int, bool]:
        """Return (actual_micro, final). `state='pending'` keeps the reservation as pending spend."""
        actual = price_micro(spec, usage)
        final = actual is not None and not usage.estimated
        # Exact usage → exact charge. Unknown/estimated usage → keep the conservative hold
        # (never refund an ambiguous request; that would be an overspend loophole).
        charge = actual if final else max(actual or 0, res.amount_micro)
        period = period_now()

        async def _do():
            ev = await self.db.get(AIUsageEventDB, res.event_id)
            if ev is None or ev.state != "reserved":
                return
            scopes = [("user", actor.user_id)]
            if actor.tenant_id:
                scopes.append(("org", actor.tenant_id))
            if res.funding == "platform":
                scopes.append(("platform", "platform"))
            for kind, sid in scopes:
                acct = await self._account(kind, sid, res.funding, period, lock=True)
                acct.reserved_micro_usd = max(0, acct.reserved_micro_usd - res.amount_micro)
                if state == "pending":
                    acct.pending_micro_usd += charge
                elif state == "released":
                    pass
                else:
                    acct.spent_micro_usd += charge
                acct.updated_at = datetime.utcnow()
            ev.state = state
            ev.actual_micro_usd = None if state == "released" else charge
            ev.usage = usage.as_dict()
            ev.latency_ms = latency_ms
            ev.provider_request_id = provider_request_id
            ev.settled_at = datetime.utcnow()
            await self.db.commit()

        if self.is_sqlite:
            async with _sqlite_lock():
                await _do()
        else:
            await _do()
        return (0 if state == "released" else charge), final

    async def release(self, res: Reservation, actor: ActorContext, spec: ModelSpec) -> None:
        await self.settle(res, actor, spec, Usage(), latency_ms=0, state="released")

    async def snapshot(self, actor: ActorContext, period: Optional[str] = None) -> dict:
        period = period or period_now()
        out = {"period": period, "accounts": []}
        for funding in ("platform", "byok"):
            q = select(AIBudgetAccountDB).where(AIBudgetAccountDB.scope_kind == "user",
                                                AIBudgetAccountDB.scope_id == actor.user_id,
                                                AIBudgetAccountDB.funding == funding,
                                                AIBudgetAccountDB.period == period)
            row = (await self.db.execute(q)).scalar_one_or_none()
            if row:
                out["accounts"].append({
                    "funding": funding, "limit_micro_usd": row.limit_micro_usd,
                    "spent_micro_usd": row.spent_micro_usd, "reserved_micro_usd": row.reserved_micro_usd,
                    "pending_micro_usd": row.pending_micro_usd,
                    "remaining_micro_usd": None if row.limit_micro_usd is None else max(
                        0, row.limit_micro_usd - row.spent_micro_usd - row.reserved_micro_usd - row.pending_micro_usd),
                })
        return out
