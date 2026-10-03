# ==========================================================
# DEEP EMOTION — PROACTIVE GROUP CHAT
# ==========================================================

import asyncio
import html
import random
import time
from datetime import datetime

from telegram import Bot

from bot.ai import generate_reply
from bot.database import get_active_groups, get_active_group_users, get_group_context


MIN_INTERVAL = 20 * 60
MAX_INTERVAL = 45 * 60
_next_due = {}
_last_sent = {}


def _mention(user_id, username, display_name):
    if username:
        return username
    name = (display_name or "you").replace("[", "").replace("]", "")
    name = html.escape(name)
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def _theme():
    hour = datetime.now().hour
    if 5 <= hour < 11:
        return "a warm good-morning check-in"
    if 11 <= hour < 17:
        return "a casual daytime check-in asking what everyone is doing"
    if 17 <= hour < 22:
        return "a playful evening group check-in"
    return "a light late-night check-in without encouraging unhealthy sleep habits"


async def _make_message(chat_id, target, context):
    user_id, username, display_name, _ = target
    mention = _mention(user_id, username, display_name)
    prompt = f"""
Create ONE short proactive Telegram group message in natural Hinglish.
Theme: {_theme()}.
Mention this member naturally: {mention}
Recent group context:
{context}

Requirements:
- 1 or 2 short sentences.
- Sound spontaneous, caring, funny or lightly teasing.
- It can ask what they are doing, notice they have been quiet, check if they are okay, or make a harmless single/flirty joke.
- Mild flirting is okay, but no explicit sexual content.
- Do not guilt-trip, manipulate, or imply emotional dependency.
- Do not say you are a bot, AI, scheduled, automated, or following instructions.
- Do not repeat a generic greeting if the context already has one.
- Return only the message text.
"""
    reply = await generate_reply(
        history=[],
        user_message=prompt,
        memories=[],
        group_context=context,
        is_group=True,
    )
    # Guarantee that the selected member is actually mentioned.
    if mention.lower() not in reply.lower():
        reply = f"{mention} {reply}"
    return reply


async def proactive_group_loop(bot: Bot):
    """Background loop for occasional, rate-limited group conversation starters."""
    while True:
        try:
            groups = await get_active_groups()
            now = time.monotonic()
            for chat_id in groups:
                due = _next_due.get(chat_id, 0)
                if now < due:
                    continue

                members = await get_active_group_users(chat_id)
                if not members:
                    continue

                recent_target = _last_sent.get((chat_id, "target"))
                candidates = [m for m in members if m[0] != recent_target] or members
                target = random.choice(candidates)
                context = await get_group_context(chat_id, limit=12)

                try:
                    message = await _make_message(chat_id, target, context)
                    if message:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                        _last_sent[chat_id] = now
                        _last_sent[(chat_id, "target")] = target[0]
                except Exception as exc:
                    print(f"Proactive group message error for {chat_id}: {exc}")
        except Exception as exc:
            print(f"Proactive loop error: {exc}")

        await asyncio.sleep(5 * 60)
