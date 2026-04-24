"""Per-tool OAuth scope + TTL gate for MCP tools.

Architectural Rules §4: agents get scoped MCP tool access — minimum needed,
time-boxed. Enforced as a decorator; declarative scopes live next to each tool.

Design:
- Caller presents a JWT (or opaque token) via `MCP_TOKEN`.
- Token is verified against a local JWKS cache or HMAC secret.
- Token must contain the tool's required scope AND have not expired.
- Tokens are short-lived (≤15 min) — callers re-mint from the issuer.
- The verifier is injected so tests don't need real keys.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Awaitable, Any
from functools import wraps


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: str
    scopes: frozenset[str]
    expires_at: int  # unix seconds

    def has(self, scope: str, *, now: int) -> bool:
        return scope in self.scopes and now < self.expires_at


class TokenVerifier(Protocol):
    def verify(self, raw: str) -> TokenClaims: ...


class ScopeDenied(Exception):
    pass


# Module-level holder; production wires a real verifier at startup.
_verifier: TokenVerifier | None = None


def install_verifier(v: TokenVerifier) -> None:
    global _verifier
    _verifier = v


def require_scope(scope: str, *, header: str = "mcp_token", ttl_max_s: int = 900):
    """Decorate an MCP tool. Caller must pass the token in `kwargs[header]`
    (FastMCP threads auxiliary kwargs through). Absent or expired → ScopeDenied."""
    def decorator(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            if _verifier is None:
                raise ScopeDenied("no verifier configured — refusing")
            raw = kwargs.pop(header, None) or os.environ.get("MCP_TOKEN", "")
            if not raw:
                raise ScopeDenied(f"token missing for scope {scope}")
            claims = _verifier.verify(raw)
            now = int(time.time())
            if not claims.has(scope, now=now):
                raise ScopeDenied(f"token lacks scope {scope} or expired")
            if claims.expires_at - now > ttl_max_s:
                raise ScopeDenied(f"token TTL > {ttl_max_s}s (exceeds §4 policy)")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
