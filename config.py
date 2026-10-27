# ==========================================================
# DEEP EMOTIONS — CONFIGURATION
# ==========================================================

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# AI providers (all optional individually; at least one must be configured).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free").strip()

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing. Put BOT_TOKEN in your .env file.")

if not any((GROQ_API_KEY, GEMINI_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY)):
    raise RuntimeError(
        "No AI provider key configured. Add at least one of GROQ_API_KEY, "
        "GEMINI_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY to .env."
    )

print("Deep Emotions config loaded | AI providers: " + ", ".join(
    name for name, key in (
        ("Groq", GROQ_API_KEY), ("Gemini", GEMINI_API_KEY),
        ("Cerebras", CEREBRAS_API_KEY), ("OpenRouter", OPENROUTER_API_KEY)
    ) if key
))
