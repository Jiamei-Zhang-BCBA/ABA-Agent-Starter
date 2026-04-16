"""
Simple math CAPTCHA service.
Generates arithmetic questions, stores answers in memory with expiration.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

_store: dict[str, dict] = {}
_lock = Lock()

# Auto-cleanup threshold: don't let store grow unbounded
_MAX_STORE_SIZE = 10000


def generate_captcha() -> dict:
    """Generate a math CAPTCHA question. Returns {captcha_id, question}."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    captcha_id = str(uuid.uuid4())
    answer = str(a + b)

    with _lock:
        # Cleanup expired entries if store is getting large
        if len(_store) > _MAX_STORE_SIZE:
            _cleanup_expired()

        _store[captcha_id] = {
            "answer": answer,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        }

    return {"captcha_id": captcha_id, "question": f"{a} + {b} = ?"}


def verify_captcha(captcha_id: str, answer: str) -> bool:
    """Verify a CAPTCHA answer. Consumes the entry (one-time use)."""
    with _lock:
        entry = _store.pop(captcha_id, None)

    if entry is None:
        return False

    if entry["expires_at"] < datetime.now(timezone.utc):
        return False

    return entry["answer"] == answer.strip()


def _cleanup_expired() -> None:
    """Remove expired entries from the store. Must be called with _lock held."""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _store.items() if v["expires_at"] < now]
    for k in expired:
        del _store[k]
