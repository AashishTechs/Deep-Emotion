# 𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴs

Telegram + Gemini AI chatbot.

## Install
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

## Configure
Copy `.env.example` to `.env` and add your own:
BOT_TOKEN
GEMINI_API_KEY
OWNER_ID (optional)

Never share `.env`.

## Run
python main.py

Groups: mention the bot or reply to its message.
Private chat: normal text works.

For 24/7 operation, deploy it later to an always-on VPS/cloud server.
