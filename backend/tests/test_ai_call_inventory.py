"""Acceptance 14: every AI path either uses the gateway/facade or is on the
documented exception list. Fails when a new direct provider call appears."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
DIRECT = re.compile(r"(api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis|api\.moonshot|api\.deepseek|api\.x\.ai|api\.mistral\.ai|/api/generate|/api/chat\b)")

# Allowed: the adapters themselves, the local-only facade, and documented pending rows
# from docs/ai-migration-checklist.md (each must be removed when migrated).
ALLOWLIST = {
    "ai/providers/ollama.py", "ai/providers/openai_compat.py", "ai/providers/anthropic.py", "ai/providers/gemini.py",
    "services/llm_client.py",                    # local-only anonymous path
    "integrations/ollama_client.py",             # legacy facade (local only)
    "router_ai.py",                              # row 4 gated by AVIRA_AI_CLOUD, row 5 pending stream migration
    "routes/bills.py", "services/smart_shopping.py", "services/document_ocr.py",   # rows 7–9 pending, local Ollama only
    "main.py",                                   # health probe GET only
}


def test_no_undocumented_direct_provider_calls():
    offenders = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if "__pycache__" in rel or rel in ALLOWLIST:
            continue
        src = p.read_text(errors="ignore")
        if DIRECT.search(src):
            offenders.append(rel)
    assert not offenders, f"Direct provider calls outside the gateway: {offenders}. Migrate them or document an exception."


def test_pending_rows_are_local_only():
    """Pending legacy paths may only talk to the local Ollama host, never a hosted API."""
    hosted = re.compile(r"(api\.openai\.com|api\.anthropic\.com|generativelanguage|api\.moonshot|api\.deepseek|api\.x\.ai|api\.mistral)")
    for rel in ("routes/bills.py", "services/smart_shopping.py", "services/document_ocr.py", "integrations/ollama_client.py"):
        src = (ROOT / rel).read_text(errors="ignore")
        assert not hosted.search(src), f"{rel} reaches a hosted provider outside the gateway"
