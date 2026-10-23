"""Group-admin sticker filters keyed by Telegram username or user ID.

Admins can reply to a sticker with /filter @username or /filter USER_ID.
The saved sticker is sent when that username is mentioned or that user is
selected as a text mention in the same group.
"""
import logging
import re
from html import escape

import aiosqlite
from telegram import MessageEntity, Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.join_requests import DB_PATH

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
USER_ID_RE = re.compile(r"^[0-9]{5,20}$")
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


def _normalize_target(value: str) -> str | None:
    """Return a stable key for either a Telegram username or numeric user ID."""
    target = value.strip()
    if target.startswith("@"):
        target = target[1:]
    if USER_ID_RE.fullmatch(target):
        return f"id:{target}"
    if USERNAME_RE.fullmatch(target):
        return target.casefold()
    return None


def _target_label(target_key: str) -> str:
    if target_key.startswith("id:"):
        return f"user ID {escape(target_key[3:])}"
    return f"@{escape(target_key)}"


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the sticker being replied to for a username or numeric user ID."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    target_arg = (context.args or [None])[0]
    target_key = _normalize_target(target_arg or "")
    if not target_key:
        await message.reply_text(
            "Usage: sticker par reply karke /filter @username ya /filter USER_ID bhejo.\n"
            "Bina username wale member ke liye uska numeric User ID use karo."
        )
        return

    replied = message.reply_to_message
    sticker = getattr(replied, "sticker", None) if replied else None
    if not sticker:
        await message.reply_text(
            "Pehle sticker wale message par reply karo, phir /filter @username ya /filter USER_ID bhejo."
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
            (chat.id, target_key, sticker.file_id, update.effective_user.id),
        )
        await db.commit()

    await message.reply_text(
        f"✅ Sticker saved in <b>{escape(chat.title or 'this group')}</b> for {_target_label(target_key)}!",
        parse_mode="HTML",
    )


async def unfilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a username's or user ID's saved sticker from this group."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    target_arg = (context.args or [None])[0]
    target_key = _normalize_target(target_arg or "")
    if not target_key:
        await message.reply_text("Usage: /unfilter @username ya /unfilter USER_ID")
        return

    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sticker_filters WHERE chat_id = ? AND username = ?",
            (chat.id, target_key),
        )
        await db.commit()

    if cursor.rowcount:
        await message.reply_text(
            f"🗑️ Sticker removed in <b>{escape(chat.title or 'this group')}</b> for {_target_label(target_key)}!",
            parse_mode="HTML",
        )
    else:
        await message.reply_text(
            f"ℹ️ No sticker filter in <b>{escape(chat.title or 'this group')}</b> for {_target_label(target_key)}!",
            parse_mode="HTML",
        )


async def handle_filtered_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a configured sticker when a username or user-ID mention appears."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not _is_group(chat):
        return

    text = message.text or ""
    if not text:
        return

    target_keys = [f"id:{entity.user.id}" for entity in (message.entities or [])
                   if entity.type == MessageEntity.TEXT_MENTION and entity.user]
    target_keys.extend(match.casefold() for match in MENTION_RE.findall(text))
    target_keys = list(dict.fromkeys(target_keys))
    if not target_keys:
        return

    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        for target_key in target_keys:
            cursor = await db.execute(
                "SELECT sticker_file_id FROM sticker_filters WHERE chat_id = ? AND username = ?",
                (chat.id, target_key),
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
                    "Could not send filtered sticker for target %s in chat %s",
                    target_key,
                    chat.id,
                )
            # One sticker per message avoids excessive spam when several filtered
            # usernames are mentioned together.
            break
