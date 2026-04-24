"""Scope enforcement tests — §5 MCP schema/round-trip + scope compliance."""
import time
import asyncio
import base64
import hmac
import hashlib
import json
import pytest

from scopes import install_verifier, require_scope, ScopeDenied
from hmac_verifier import HmacVerifier


SECRET = b"test-secret"


def _mint(scopes, exp_offset=60):
    body = {"sub": "test", "scopes": list(scopes), "exp": int(time.time()) + exp_offset}
    body_b64 = base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode()
    sig = hmac.new(SECRET, body_b64.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{body_b64}.{sig_b64}"


def setup_module():
    install_verifier(HmacVerifier(SECRET))


@require_scope("x.read")
async def _needs_x_read():
    return "ok"


def test_allows_with_scope():
    token = _mint(["x.read"])
    assert asyncio.run(_needs_x_read(mcp_token=token)) == "ok"


def test_denies_without_scope():
    token = _mint(["other.scope"])
    with pytest.raises(ScopeDenied):
        asyncio.run(_needs_x_read(mcp_token=token))


def test_denies_expired():
    token = _mint(["x.read"], exp_offset=-1)
    with pytest.raises(ScopeDenied):
        asyncio.run(_needs_x_read(mcp_token=token))


def test_denies_ttl_exceeding_policy():
    # 1-hour token; default ttl_max_s in require_scope is 900s
    token = _mint(["x.read"], exp_offset=3600)
    with pytest.raises(ScopeDenied):
        asyncio.run(_needs_x_read(mcp_token=token))


def test_denies_missing_token():
    with pytest.raises(ScopeDenied):
        asyncio.run(_needs_x_read())
