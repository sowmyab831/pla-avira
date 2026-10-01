"""Credential resolution and at-rest encryption for provider keys.

Resolution order for a (actor, provider):
  1. Explicit connection id requested by the caller (must be owned/visible)
  2. User BYOK connection (if AVIRA_AI_BYOK)
  3. Organization connection
  4. Platform connection (env var or platform-owned DB row)

Secrets are Fernet-encrypted with a wrapping key derived from AVIRA_VAULT_KEY.
`encryption_version` is recorded so keys can be rotated. Plaintext never leaves
this module except inside the provider HTTP call.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

ENCRYPTION_VERSION = "v1"
_REDACT = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{20,}|xai-[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,})")


def redact(text: str) -> str:
    """Strip anything that looks like a bearer/API key from error text and logs."""
    if not text:
        return text
    return _REDACT.sub("[redacted]", text)[:200]


def _fernet(version: str = ENCRYPTION_VERSION) -> Fernet:
    raw = settings.avira_vault_key
    if not raw:
        raise RuntimeError("AVIRA_VAULT_KEY is required to store provider credentials")
    digest = hashlib.sha256(f"{version}:{raw}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> tuple[str, str, str]:
    """Return (ciphertext, hint, version). Hint is last 4 chars for display."""
    token = _fernet().encrypt(plain.encode()).decode()
    return token, plain[-4:] if len(plain) >= 8 else "", ENCRYPTION_VERSION


def decrypt_secret(ciphertext: str, version: str = ENCRYPTION_VERSION) -> str:
    try:
        return _fernet(version).decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Stored credential cannot be decrypted with the current vault key") from e


@dataclass(frozen=True)
class ResolvedCredential:
    provider: str
    api_key: Optional[str]
    connection_id: Optional[str]      # None for env-backed platform keys
    owner_kind: str                   # platform | org | user
    funding: str                      # platform | byok
    base_url: Optional[str] = None    # only for compat endpoints

    @property
    def configured(self) -> bool:
        return bool(self.api_key) or self.provider == "ollama"


def env_key_for(provider: str) -> Optional[str]:
    return {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
        "moonshot": settings.moonshot_api_key,
        "deepseek": settings.deepseek_api_key,
        "xai": settings.xai_api_key,
        "mistral": settings.mistral_api_key,
    }.get(provider)


def platform_credential(provider: str) -> ResolvedCredential:
    if provider == "ollama":
        return ResolvedCredential("ollama", None, None, "platform", "platform")
    return ResolvedCredential(provider, env_key_for(provider), None, "platform", "platform")


def credential_from_row(row, *, funding: str) -> ResolvedCredential:
    key = decrypt_secret(row.secret_ciphertext, row.encryption_version) if row.secret_ciphertext else None
    return ResolvedCredential(row.provider, key, row.id, row.owner_kind, funding, base_url=None)
