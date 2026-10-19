"""Safe, deterministic replies for common low-context chat messages.

Only generic greetings and acknowledgements are cached. Personal, emotional,
or context-dependent messages are deliberately sent to the AI engine instead.
"""

import json
import re
from pathlib import Path


_CACHE_FILE = Path(__file__).with_name("response_cache.json")


def _normalize(text: str) -> str:
    """Normalize case, punctuation, emoji, and repeated whitespace."""
    value = (text or "").casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _load_cache() -> dict[str, str]:
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    responses: dict[str, str] = {}
    for category in data.get("categories", []):
        reply = category.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            continue
        for alias in category.get("aliases", []):
            if isinstance(alias, str):
                key = _normalize(alias)
                if key:
                    responses[key] = reply.strip()
    return responses


_RESPONSE_CACHE = _load_cache()


def get_cached_response(text: str) -> str | None:
    """Return a safe generic reply for a known short message, otherwise None."""
    key = _normalize(text)
    if not key or len(key) > 80:
        return None
    return _RESPONSE_CACHE.get(key)
