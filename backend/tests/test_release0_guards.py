"""Release 0 guards: regex-fallback masking, LLM limit clamping, scoped cache,
feature flags and the autonomous-trading gate."""
import asyncio

import pytest

from app.config import settings
from app.services import llm_client
from app.services.privacy_masking import PrivacyMaskingService


@pytest.fixture
def masker():
    return PrivacyMaskingService()


@pytest.mark.parametrize("text,secret", [
    ("Contact me at john.smith@example.com for details.", "john.smith@example.com"),
    ("Call me at (555) 123-4567 anytime.", "(555) 123-4567"),
    ("Call +91 98765 43210 after 6.", "98765 43210"),
    ("Pay with card 4111-1111-1111-1111 please.", "4111-1111-1111-1111"),
    ("Aadhaar 2345 6789 0123 on file.", "2345 6789 0123"),
    ("PAN ABCDE1234F for tax.", "ABCDE1234F"),
    ("IFSC HDFC0001234 branch.", "HDFC0001234"),
    ("SSN 123-45-6789", "123-45-6789"),
])
def test_regex_fallback_masks_baseline_pii(masker, text, secret):
    """Masking must work even when Presidio/spaCy are unavailable."""
    out = masker.mask_text(text, "doc", "user")
    assert secret not in out["masked_text"], out["masked_text"]
    assert out["entity_count"] >= 1


def test_masking_reports_no_false_success_on_plain_text(masker):
    out = masker.mask_text("Add milk and eggs to the list", "doc", "user")
    assert out["entity_count"] == 0
    assert out["masked_text"] == "Add milk and eggs to the list"


def test_output_tokens_cannot_exceed_ceiling():
    ceiling = llm_client._MAX_OUTPUT_TOKENS
    assert llm_client.clamp_output_tokens(ceiling * 10) == ceiling
    assert llm_client.clamp_output_tokens(None) == ceiling
    assert llm_client.clamp_output_tokens(0) == ceiling
    assert llm_client.clamp_output_tokens(64) == 64


def test_cache_key_is_scoped_per_user_and_model():
    args = ("same prompt", "fast", None, 0.2, 256, False)
    tok = llm_client.set_actor("user-a")
    try:
        k_a = llm_client.cache_key(*args)
    finally:
        llm_client.current_actor.reset(tok)
    tok = llm_client.set_actor("user-b")
    try:
        k_b = llm_client.cache_key(*args)
    finally:
        llm_client.current_actor.reset(tok)
    k_anon = llm_client.cache_key(*args)
    k_model = llm_client.cache_key(*args, model="other-model")
    assert len({k_a, k_b, k_anon, k_model}) == 4


def test_cache_never_serves_other_users_response():
    args = ("shared prompt", "fast", None, 0.2, 256, False)
    tok = llm_client.set_actor("user-a")
    try:
        llm_client.cache_set(llm_client.cache_key(*args), "private answer for A")
    finally:
        llm_client.current_actor.reset(tok)
    tok = llm_client.set_actor("user-b")
    try:
        assert llm_client.cache_get(llm_client.cache_key(*args)) is None
    finally:
        llm_client.current_actor.reset(tok)


def test_feature_flags_default_to_safe_local_behaviour():
    assert settings.ai_cloud_enabled is False
    assert settings.ai_byok_enabled is False
    assert settings.auto_trading_enabled is False
    assert settings.payments_live_enabled is False


def test_auto_trading_loops_are_noops_when_disabled(monkeypatch):
    from app.services import scheduler
    monkeypatch.setattr(settings, "auto_trading_enabled", False)
    monkeypatch.setattr(scheduler, "_is_us_market_hours", lambda: True)
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("trading scanner must not be invoked")

    import app.services.day_trading_scanner as scanner
    monkeypatch.setattr(scanner, "auto_scan_and_trade", boom, raising=False)
    asyncio.run(scheduler._run_auto_trades())
    asyncio.run(scheduler._run_testuser01_auto_trades())
    assert called["n"] == 0


def test_no_real_money_order_path_in_scheduler():
    import inspect
    from app.services import scheduler
    src = inspect.getsource(scheduler._run_auto_trades)
    assert "place_order" not in src
    assert "get_robinhood_client" not in src
