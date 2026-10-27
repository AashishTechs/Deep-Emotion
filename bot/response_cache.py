"""Persistent shared cache for generic, context-free AI chat replies."""
import hashlib
import os
import re
import sqlite3
import threading
import unicodedata

_DB_PATH = os.getenv("AI_RESPONSE_CACHE_PATH", os.path.join(os.path.dirname(__file__), "response_cache.sqlite3"))
_LOCK = threading.RLock()
_SKIP = re.compile(
    r"\b(i am|i'm|my |me |mine|mera|meri|mere|mujhe|mujhko|main |mai |"
    r"hamara|meri life|my life|my name|mera naam|password|otp|api key|token|"
    r"address|phone number|sad|depressed|hurt myself|personal|family|parents)\b",
    re.IGNORECASE,
)
_DETAIL = re.compile(r"\b(detail|detailed|step by step|long answer|elaborate|vistar|detail mein)\b", re.IGNORECASE)

def normalize_message(message):
    text = unicodedata.normalize("NFKC", str(message or "")).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"([!?.,])\1+", r"\1", text)

def is_cacheable_message(message):
    text = normalize_message(message)
    if not text or len(text) > 240 or len(text.split()) > 35:
        return False
    if _SKIP.search(text) or _DETAIL.search(text):
        return False
    if re.search(r"\b(should i|can i|do i|am i|kya main|mujhe kya|mere saath|my friend|crush|relationship)\b", text):
        return False
    return True

def _key(message):
    return hashlib.sha256(normalize_message(message).encode("utf-8")).hexdigest()

def _connect():
    os.makedirs(os.path.dirname(os.path.abspath(_DB_PATH)), exist_ok=True)
    db = sqlite3.connect(_DB_PATH, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS responses (cache_key TEXT PRIMARY KEY, normalized_message TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    return db

def get_cached_response(message):
    if not is_cacheable_message(message):
        return None
    with _LOCK:
        db = _connect()
        try:
            row = db.execute("SELECT response FROM responses WHERE cache_key = ?", (_key(message),)).fetchone()
            return row[0] if row else None
        finally:
            db.close()

def save_cached_response(message, response):
    if not is_cacheable_message(message):
        return False
    response = str(response or "").strip()
    if not response or len(response) > 2000:
        return False
    with _LOCK:
        db = _connect()
        try:
            db.execute("INSERT OR REPLACE INTO responses (cache_key, normalized_message, response) VALUES (?, ?, ?)", (_key(message), normalize_message(message), response))
            db.commit()
            return True
        finally:
            db.close()
