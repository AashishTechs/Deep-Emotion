"""Group-admin /utag member tagging for Deep Emotion."""

import asyncio
import html
import logging

from telegram import BotCommand
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.join_requests import GROUP_ADMIN_COMMANDS

logger = logging.getLogger(__name__)

GROUP_ADMIN_COMMANDS.extend([
    BotCommand("utag", "Tag group members with your message"),
    BotCommand("cancel", "Stop the active /utag"),
])


def _is_group(chat) -> bool:
    return bool(chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP))


async def _is_group_admin(update, context) -> bool:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return False
    if not _is_group(chat):
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
    except TelegramError:
        await message.reply_text("⚠️ Admin permission verify nahi ho paayi.")
        return False
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
        await message.reply_text(
            "❌ You don't have permission to use this command. Only group administrators can use it."
        )
        return False
    return True


async def _cached_members(update, context):
    chat = update.effective_chat
    cache = context.application.bot_data.setdefault("moderation_members", {})
    members = dict(cache.get(chat.id, {}))

    # Add current administrators too; they may not have been cached yet.
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            user = admin.user
            if getattr(user, "is_bot", False):
                continue
            members[user.id] = {
                "id": user.id,
                "full_name": user.full_name or user.first_name or str(user.id),
                "username": user.username,
                "is_bot": False,
            }
    except TelegramError:
        logger.exception("Could not load group administrators for /utag")

    # Telegram Bot API does not expose a general get-all-members endpoint.
    # The existing moderation cache therefore contains members the bot has seen.
    return [item for item in members.values() if not item.get("is_bot")]


def _mention(item) -> str:
    name = html.escape(item.get("full_name") or "Member")
    return f'<a href="tg://user?id={int(item["id"])}">{name}</a>'


async def utag_command(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    if not _is_group(chat):
        return
    if not await _is_group_admin(update, context):
        return

    text = " ".join(context.args or []).strip()
    if not text:
        await message.reply_text("Usage: /utag Your message here")
        return

    active = context.application.bot_data.setdefault("utag_tasks", {})
    old_task = active.get(chat.id)
    if old_task and not old_task.done():
        await message.reply_text("⚠️ An /utag is already running. Use /cancel to stop it.")
        return

    members = await _cached_members(update, context)
    if not members:
        await message.reply_text(
            "⚠️ I don't have any cached group members yet. Members need to send a message first."
        )
        return

    # Keep Telegram messages safely below the message length limit.
    chunks = []
    current = f"{html.escape(text)}\n\n"
    for item in members:
        mention = _mention(item) + " "
        if len(current) + len(mention) > 3500:
            chunks.append(current.rstrip())
            current = mention
        else:
            current += mention
    if current.strip():
        chunks.append(current.rstrip())

    async def run_tagging():
        try:
            for index, chunk in enumerate(chunks, start=1):
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=chunk,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                if index < len(chunks):
                    await asyncio.sleep(0.4)
        except asyncio.CancelledError:
            raise
        except TelegramError:
            logger.exception("/utag failed in chat %s", chat.id)
            await context.bot.send_message(chat.id, "❌ Tagging stopped because Telegram rejected a message.")
        finally:
            active.pop(chat.id, None)

    task = asyncio.create_task(run_tagging())
    active[chat.id] = task
    await message.reply_text(f"📢 Tagging started — {len(members)} members.")


async def cancel_utag_command(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not _is_group(chat):
        return
    if not await _is_group_admin(update, context):
        return

    active = context.application.bot_data.setdefault("utag_tasks", {})
    task = active.get(chat.id)
    if not task or task.done():
        active.pop(chat.id, None)
        await message.reply_text("ℹ️ No active /utag is running.")
        return

    task.cancel()
    active.pop(chat.id, None)
    await message.reply_text("🛑 /utag stopped successfully.")
