from __future__ import annotations

import hashlib
import hmac
import secrets

from .config import settings


def digest(value: str) -> str:
    return hmac.new(settings.secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


def otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
