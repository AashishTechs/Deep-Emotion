# ==========================================================
# DEEP EMOTIONS — BROADCAST
# ==========================================================

import asyncio
import logging
from pathlib import Path

import aiosqlite
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from config import OWNER_ID

logger = logging.getLogger(__name__)


# The owner and this additional trusted Telegram user can use /broadcast.
BROADCAST_ADMIN_IDS = {
    OWNER_ID,
    8877757796,
} - {0}

DB_PATH = Path("data/deep_emotions.db")


async def init_broadcast_table():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_users (
                user_id INTEGER PRIMARY KEY,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def track_private_user(update):
    """Remember private-chat users so future broadcasts can reach them."""
    message = update.message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat or chat.type != "private":
        return

    await init_broadcast_table()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO broadcast_users(user_id) VALUES (?)",
            (user.id,),
        )
        await db.commit()


async def get_broadcast_targets():
    """Return known private Telegram user IDs, including legacy users."""
    await init_broadcast_table()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id
            FROM broadcast_users
            """
        )
        rows = await cursor.fetchall()

        # Before broadcast_users existed, private chats were already stored
        # in messages with chat_id == user_id. Include those users too.
        legacy_cursor = await db.execute(
            """
            SELECT DISTINCT chat_id
            FROM messages
            WHERE chat_id = user_id
            """
        )
        legacy_rows = await legacy_cursor.fetchall()

    return sorted({row[0] for row in rows} | {row[0] for row in legacy_rows})


async def broadcast_command(
    update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.effective_user:
        return

    if update.effective_user.id not in BROADCAST_ADMIN_IDS:
        await update.message.reply_text("⛔ You are not allowed to use this command.")
        return

    message_to_copy = update.message.reply_to_message
    text = " ".join(context.args).strip()

    if not message_to_copy and not text:
        await update.message.reply_text(
            "📢 Broadcast use:\n\n"
            "`/broadcast Your message here`\n\n"
            "Ya kisi message ko reply karke `/broadcast` bhejo."
        , parse_mode="Markdown")
        return

    targets = await get_broadcast_targets()

    if not targets:
        await update.message.reply_text(
            "📢 Abhi broadcast ke liye koi private users registered nahi hain."
        )
        return

    status = await update.message.reply_text(
        f"📢 Broadcast start...\n👥 Recipients: {len(targets)}"
    )

    sent = 0
    failed = 0
    failure_details = []

    for chat_id in targets:
        try:
            if message_to_copy:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=message_to_copy.message_id,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                )

            sent += 1

        except RetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                if message_to_copy:
                    await context.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=update.effective_chat.id,
                        message_id=message_to_copy.message_id,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                    )
                sent += 1
            except Exception as retry_exc:
                failed += 1
                detail = f"{type(retry_exc).__name__}: {retry_exc}"
                failure_details.append(detail)
                logger.warning("Broadcast retry failed for chat_id=%s: %s", chat_id, detail)

        except Exception as exc:
            failed += 1
            detail = f"{type(exc).__name__}: {exc}"
            failure_details.append(detail)
            logger.warning("Broadcast failed for chat_id=%s: %s", chat_id, detail)

        # Stay comfortably below Telegram's normal broadcast rate.
        await asyncio.sleep(0.05)

    summary = (
        "📢 **Broadcast completed**\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total: {len(targets)}"
    )
    if failure_details:
        # Show a few distinct error messages so the owner can diagnose failures.
        unique_details = list(dict.fromkeys(failure_details))[:3]
        summary += "\n\n⚠️ **Failure reasons:**\n" + "\n".join(
            f"• `{detail[:180]}`" for detail in unique_details
        )
    await status.edit_text(summary, parse_mode="Markdown")


DEFAULT_COMMANDS = [
    BotCommand("start", "Welcome panel"),
    BotCommand("help", "Help & Commands"),
    BotCommand("ask", "Ask AI"),
    BotCommand("game", "Play a game"),
    BotCommand("truth", "Truth"),
    BotCommand("dare", "Dare"),
    BotCommand("td", "Truth or Dare"),
    BotCommand("memory", "View saved memories"),
    BotCommand("forget", "Delete one memory"),
    BotCommand("forget_all", "Delete all memories"),
    BotCommand("clear", "Clear chat history"),
    BotCommand("stats", "View your stats"),
    BotCommand("privacy", "Privacy information"),
]

ADMIN_COMMANDS = DEFAULT_COMMANDS + [
    BotCommand("broadcast", "Send a broadcast to users"),
]


async def configure_command_menu(bot):
    """Show /broadcast only to the owner and the second trusted user."""
    await bot.set_my_commands(
        DEFAULT_COMMANDS,
        scope=BotCommandScopeDefault(),
    )

    for user_id in BROADCAST_ADMIN_IDS:
        await bot.set_my_commands(
            ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=user_id),
        )
