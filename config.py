import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing. Put it in .env")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY missing. Put it in .env")
