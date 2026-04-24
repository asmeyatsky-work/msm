"""HMAC-SHA256 token verifier. Payload = base64url(JSON).SIGNATURE.
JSON body: {"sub": ..., "scopes": [...], "exp": <unix_s>}

Kept tiny on purpose — production can swap in a JWT/JWKS verifier without
touching the scopes gate (it depends only on the TokenVerifier protocol)."""
from __future__ import annotations
import base64
import hmac
import hashlib
import json
from scopes import TokenClaims, TokenVerifier


class HmacVerifier(TokenVerifier):
    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def verify(self, raw: str) -> TokenClaims:
        try:
            body_b64, sig_b64 = raw.split(".", 1)
        except ValueError as e:
            raise ValueError("malformed token") from e
        expected = hmac.new(self._secret, body_b64.encode(), hashlib.sha256).digest()
        given = base64.urlsafe_b64decode(_pad(sig_b64))
        if not hmac.compare_digest(expected, given):
            raise ValueError("bad signature")
        body = json.loads(base64.urlsafe_b64decode(_pad(body_b64)))
        return TokenClaims(
            subject=str(body["sub"]),
            scopes=frozenset(body.get("scopes", [])),
            expires_at=int(body["exp"]),
        )


def _pad(s: str) -> str:
    return s + "=" * (-len(s) % 4)
