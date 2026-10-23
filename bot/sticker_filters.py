"""Group-admin sticker filters keyed by Telegram username, ID, or display name."""
import logging
import re
import unicodedata
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


def _normalize_name(value: str) -> str:
    """Normalize decorated display names for matching in ordinary chat text."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(
        char for char in value
        if not unicodedata.category(char).startswith("C")
        and unicodedata.category(char) not in {"Mn", "Me"}
    )
    return " ".join(value.split())


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
        try:
            await message.delete()
        except TelegramError:
            pass
        return None

    return message, chat


def _normalize_target(value: str) -> str | None:
    """Use @username, numeric ID, or a normalized display name as the key."""
    target = value.strip()
    if target.startswith("@"):
        username = target[1:]
        return username.casefold() if USERNAME_RE.fullmatch(username) else None
    if USER_ID_RE.fullmatch(target):
        return f"id:{target}"

    # Unprefixed text is treated as a display name, not as a username.
    name = _normalize_name(target)
    if name and len(name) <= 100:
        return f"name:{name}"
    return None


def _target_label(target_key: str) -> str:
    if target_key.startswith("id:"):
        return f"user ID {escape(target_key[3:])}"
    if target_key.startswith("name:"):
        return f"display name <b>{escape(target_key[5:])}</b>"
    return f"@{escape(target_key)}"


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save a replied-to sticker for a username, numeric ID, or display name."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    raw_target = " ".join(context.args or []).strip()
    target_key = _normalize_target(raw_target)
    if not target_key:
        await message.reply_text(
            "Usage: sticker par reply karke /filter @username, USER_ID, ya display name bhejo.\n"
            "Example: /filter @Aashish_0fficial\n"
            "Note: display-name filter text mein us naam ke aane par trigger hota hai; same naam wale members mein farq nahi kar sakta."
        )
        return

    replied = message.reply_to_message
    sticker = getattr(replied, "sticker", None) if replied else None
    if not sticker:
        await message.reply_text(
            "Pehle sticker wale message par reply karo, phir /filter @username, USER_ID, ya display name bhejo."
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
    """Remove a username, numeric-ID, or display-name filter from this group."""
    resolved = await _admin_command_context(update, context)
    if not resolved:
        return
    message, chat = resolved

    raw_target = " ".join(context.args or []).strip()
    target_key = _normalize_target(raw_target)
    if not target_key:
        await message.reply_text("Usage: /unfilter @username, USER_ID, ya display name")
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
    """Send a saved sticker for username/user-ID mentions or display-name text."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not _is_group(chat):
        return

    text = message.text or ""
    if not text:
        return

    target_keys = [
        f"id:{entity.user.id}"
        for entity in (message.entities or [])
        if entity.type == MessageEntity.TEXT_MENTION and entity.user
    ]
    target_keys.extend(match.casefold() for match in MENTION_RE.findall(text))
    normalized_text = _normalize_name(text)
    await _ensure_filter_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username, sticker_file_id FROM sticker_filters WHERE chat_id = ? AND username LIKE 'name:%'",
            (chat.id,),
        )
        for key, _file_id in await cursor.fetchall():
            display_name = key[5:]
            if display_name and display_name in normalized_text:
                target_keys.append(key)

        target_keys = list(dict.fromkeys(target_keys))
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
            break
