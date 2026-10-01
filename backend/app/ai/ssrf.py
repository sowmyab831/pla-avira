"""Endpoint safety for provider base URLs.

Provider URLs are server-controlled constants. The only variable endpoints are:
  * the internal Ollama host (explicitly allowed, even if it is a private IP)
  * admin-allowlisted OpenAI-compatible endpoints (AVIRA_AI_COMPAT_ENDPOINTS)

Everything else is refused. Allowlisted hosts are additionally checked at call
time so DNS rebinding to a private/metadata address is rejected.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings

_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
CONNECT_TIMEOUT_S = 10.0


class UnsafeEndpoint(ValueError):
    pass


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified


def compat_endpoints() -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (settings.ai_compat_endpoints or "").split(","):
        part = part.strip()
        if "=" in part:
            name, url = part.split("=", 1)
            out[name.strip()] = url.strip().rstrip("/")
    return out


def ollama_base_url() -> str:
    return settings.ollama_host.rstrip("/")


def validate_outbound(url: str, *, allow_internal: bool = False) -> str:
    """Return the normalized URL or raise UnsafeEndpoint."""
    p = urlparse(url)
    if p.scheme not in ("https", "http"):
        raise UnsafeEndpoint("Only http(s) endpoints are permitted")
    if p.scheme == "http" and not allow_internal:
        raise UnsafeEndpoint("TLS is required for external endpoints")
    if not p.hostname:
        raise UnsafeEndpoint("Endpoint has no host")
    if p.username or p.password:
        raise UnsafeEndpoint("Credentials in URL are not permitted")
    host = p.hostname.lower()
    if host in _METADATA_HOSTS:
        raise UnsafeEndpoint("Metadata endpoints are blocked")
    if allow_internal:
        return url.rstrip("/")
    try:
        infos = socket.getaddrinfo(host, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeEndpoint(f"Endpoint host does not resolve: {host}") from e
    for info in infos:
        ip = info[4][0]
        if _is_private(ip):
            raise UnsafeEndpoint("Endpoint resolves to a private or reserved address")
    return url.rstrip("/")


def resolve_compat_endpoint(name: str) -> str:
    table = compat_endpoints()
    if name not in table:
        raise UnsafeEndpoint(f"Endpoint '{name}' is not allowlisted")
    return validate_outbound(table[name])
