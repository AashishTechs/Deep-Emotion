"""Multi-provider text generation with automatic rate-limit/error fallback.

Provider order is configurable with AI_PROVIDER_ORDER. Exact remaining quotas are
not exposed consistently by all providers, so this router learns from failures
and temporarily cools down providers that return rate-limit/server errors.
"""
import asyncio
import json
import os
import threading
import time
import urllib.error
import urllib.request

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    CEREBRAS_API_KEY,
    CEREBRAS_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)

_lock = threading.Lock()
_cooldown_until = {}
_last_error = {}
_COOLDOWN_SECONDS = int(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "90"))

_DEFAULT_ORDER = ["groq", "gemini", "cerebras", "openrouter"]
_order_setting = os.getenv("AI_PROVIDER_ORDER", ",".join(_DEFAULT_ORDER))
_PROVIDER_ORDER = [p.strip().lower() for p in _order_setting.split(",") if p.strip()]
_PROVIDER_ORDER = [p for p in _PROVIDER_ORDER if p in _DEFAULT_ORDER]
for _provider in _DEFAULT_ORDER:
    if _provider not in _PROVIDER_ORDER:
        _PROVIDER_ORDER.append(_provider)

_GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def _available(provider):
    return {
        "groq": bool(GROQ_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "cerebras": bool(CEREBRAS_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
    }.get(provider, False)

def _request_openai_compatible(provider, prompt, system_instruction, temperature):
    settings = {
        "groq": {
            "key": GROQ_API_KEY,
            "model": GROQ_MODEL,
            "url": "https://api.groq.com/openai/v1/chat/completions",
        },
        "cerebras": {
            "key": CEREBRAS_API_KEY,
            "model": CEREBRAS_MODEL,
            "url": "https://api.cerebras.ai/v1/chat/completions",
        },
        "openrouter": {
            "key": OPENROUTER_API_KEY,
            "model": OPENROUTER_MODEL,
            "url": "https://openrouter.ai/api/v1/chat/completions",
        },
    }[provider]
    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 100,
    }
    headers = {
        "Authorization": f"Bearer {settings['key']}",
        "Content-Type": "application/json",
        "User-Agent": "Deep-Emotion-Telegram-Bot",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/AashishTechs/Deep-Emotion"
        headers["X-Title"] = "Deep Emotion"
    request = urllib.request.Request(
        settings["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{provider} HTTP {exc.code}: {detail}") from exc
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"{provider} returned no choices")
    return str((choices[0].get("message") or {}).get("content") or "").strip()

def _generate_sync(provider, prompt, system_instruction, temperature):
    if provider == "gemini":
        if not _GEMINI_CLIENT:
            raise RuntimeError("Gemini API key is not configured")
        response = _GEMINI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=100,
            ),
        )
        return (response.text or "").strip()
    return _request_openai_compatible(provider, prompt, system_instruction, temperature)

def _mark_success(provider):
    with _lock:
        _cooldown_until.pop(provider, None)
        _last_error.pop(provider, None)

def _mark_failure(provider, error):
    message = str(error).lower()
    # Quota/rate-limit, transient server, timeout, and network failures cool
    # down a provider. Bad requests/auth errors are logged but not repeatedly
    # retried during the same call.
    cooldown = _COOLDOWN_SECONDS
    if any(token in message for token in ("429", "rate limit", "quota", "resource_exhausted", "503", "502", "504", "timeout", "timed out", "connection")):
        with _lock:
            _cooldown_until[provider] = time.monotonic() + cooldown
    with _lock:
        _last_error[provider] = str(error)[:300]

async def generate_text(prompt, system_instruction, temperature=0.8):
    """Try configured providers in priority order until one returns a reply."""
    configured = [p for p in _PROVIDER_ORDER if _available(p)]
    if not configured:
        raise RuntimeError(
            "No AI provider API key configured. Set GROQ_API_KEY, GEMINI_API_KEY, "
            "CEREBRAS_API_KEY, or OPENROUTER_API_KEY in .env."
        )

    with _lock:
        now = time.monotonic()
        ready = [p for p in configured if _cooldown_until.get(p, 0) <= now]
    # If all are cooling down, still try the provider whose cooldown expires first.
    candidates = ready or sorted(configured, key=lambda p: _cooldown_until.get(p, 0))

    errors = []
    for provider in candidates:
        try:
            reply = await asyncio.to_thread(
                _generate_sync, provider, prompt, system_instruction, temperature
            )
            if not reply:
                raise RuntimeError(f"{provider} returned an empty response")
            _mark_success(provider)
            print(f"[AI PROVIDER] {provider} succeeded")
            return reply
        except Exception as exc:
            _mark_failure(provider, exc)
            errors.append(f"{provider}: {str(exc)[:180]}")
            print(f"[AI PROVIDER] {provider} failed; trying next provider ({str(exc)[:180]})")

    raise RuntimeError("All configured AI providers failed: " + " | ".join(errors))
