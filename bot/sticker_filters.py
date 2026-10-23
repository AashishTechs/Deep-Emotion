"""Group-admin sticker filters keyed by Telegram username.

Admins can reply to a sticker with /filter @username. Whenever that username
is mentioned in the same group, the bot sends the saved sticker.
"""
import logging
import re

import aiosqlite
from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.join_requests import DB_PATH

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{5,32})")


async def _ensure_filter_table():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sticker_filters (
                chat_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                sticker_file_id TEXT NOT NULL,
                added_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, username)
            )
            """
        )
        await db.commit()


def _is_group(chat) -> bool:
    return bool(chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP))


async def _is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            "creator",
        )
    except TelegramError:
        return False


async def _admin_command_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return None

    if not _is_group(chat):
        if chat.type == ChatType.PRIVATE:
            await message.reply_text("Ye command sirf group mein use karo.")
        return None

    if not await _is_group_admin(context.bot, chat.id, user.id):
        # Keep admin-only commands out of regular members' chat history.
        try:
            await message.delete()
        except TelegramError:
            pass
        return None

    return message, chat


def _normalize_username(value: str) -> str | None:
    username = value.strip()
    if username.startswith("@"):
        username = username[1:]
    if not USERNAME_RE.fullmatch(username):
        return None
    return username.casefold()


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the sticker being replied to for a username in this group."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    username_arg = (context.args or [None])[0]
    username = _normalize_username(username_arg or "")
    if not username:
        await message.reply_text(
            "Usage: kisi sticker par reply karke /filter @username bhejo.\n"
            "Example: /filter @username"
        )
        return

    replied = message.reply_to_message
    sticker = getattr(replied, "sticker", None) if replied else None
    if not sticker:
        await message.reply_text(
            "Pehle sticker wale message par reply karo, phir /filter @username bhejo."
        )
        return

    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sticker_filters(chat_id, username, sticker_file_id, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, username) DO UPDATE SET
                sticker_file_id = excluded.sticker_file_id,
                added_by = excluded.added_by,
                created_at = CURRENT_TIMESTAMP
            """,
            (chat.id, username, sticker.file_id, update.effective_user.id),
        )
        await db.commit()

    await message.reply_text(f"✅ Sticker saved in “{chat.title}” for @{username}!")


async def unfilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a username's saved sticker from this group."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    username_arg = (context.args or [None])[0]
    username = _normalize_username(username_arg or "")
    if not username:
        await message.reply_text("Usage: /unfilter @username")
        return

    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sticker_filters WHERE chat_id = ? AND username = ?",
            (chat.id, username),
        )
        await db.commit()

    if cursor.rowcount:
        await message.reply_text(
            f"🗑️ Sticker filter for @{username} removed from “{chat.title}”."
        )
    else:
        await message.reply_text(
            f"ℹ️ No sticker filter for @{username} in “{chat.title}”."
        )


async def handle_filtered_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the configured sticker when a group message mentions its username."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not _is_group(chat):
        return

    text = message.text or ""
    if not text:
        return

    usernames = list(dict.fromkeys(match.casefold() for match in MENTION_RE.findall(text)))
    if not usernames:
        return

    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        for username in usernames:
            cursor = await db.execute(
                "SELECT sticker_file_id FROM sticker_filters WHERE chat_id = ? AND username = ?",
                (chat.id, username),
            )
            row = await cursor.fetchone()
            if not row:
                continue
            try:
                await context.bot.send_sticker(
                    chat_id=chat.id,
                    sticker=row[0],
                    reply_to_message_id=message.message_id,
                    allow_sending_without_reply=True,
                )
            except TelegramError:
                logger.exception(
                    "Could not send filtered sticker for @%s in chat %s",
                    username,
                    chat.id,
                )
            # One sticker per message avoids excessive spam when several filtered
            # usernames are mentioned together.
            break
