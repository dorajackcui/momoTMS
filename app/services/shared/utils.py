from __future__ import annotations

from datetime import datetime, timezone
import hashlib


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def src_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
