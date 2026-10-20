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
            CREATE TABLE IF NOT EXISTS broadcast_groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Existing installations may have an older broadcast_groups table
        # containing only chat_id/added_at. Migrate it in-place so existing
        # registered groups are preserved instead of deleting the database.
        cursor = await db.execute("PRAGMA table_info(broadcast_groups)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "title" not in columns:
            await db.execute(
                "ALTER TABLE broadcast_groups "
                "ADD COLUMN title TEXT NOT NULL DEFAULT 'Unnamed group'"
            )

        await db.commit()


async def track_group_chat(update, context: ContextTypes.DEFAULT_TYPE):
    """Remember group chats the bot has received an update from."""
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    await init_broadcast_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO broadcast_groups(chat_id, title)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title
            """,
            (chat.id, chat.title or "Unnamed group"),
        )
        await db.commit()


async def get_broadcast_targets():
    """Return known group chats for group-only broadcasts."""
    await init_broadcast_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT chat_id, title FROM broadcast_groups ORDER BY title COLLATE NOCASE"
        )
        return await cursor.fetchall()


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
            "📢 **𝗕ʀᴏᴀᴅᴄᴀsᴛ 𝗚ᴜɪᴅᴇ**\n\n"
            "➤ `/broadcast Your message here`\n\n"
            "➤ Kisi message ko reply karke `/broadcast` bhejo.\n\n"
            "💗 **𝗗ᴇᴇᴘ 𝗘ᴍᴏᴛɪᴏɴ**",
            parse_mode="Markdown",
        )
        return

    targets = await get_broadcast_targets()

    if not targets:
        await update.message.reply_text(
            "📢 Abhi koi GC registered nahi hai. Bot ko GC mein add karke wahan koi message bhejo."
        )
        return

    status = await update.message.reply_text(
        f"📢 GC broadcast start...\n👥 Groups: {len(targets)}"
    )

    sent = 0
    failed = 0
    sent_groups = []
    failure_details = []

    for chat_id, group_title in targets:
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
            sent_groups.append(f"{group_title} (ID: {chat_id})")

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
                sent_groups.append(f"{group_title} (ID: {chat_id})")
            except Exception as retry_exc:
                failed += 1
                detail = f"{type(retry_exc).__name__}: {retry_exc}"
                failure_details.append(f"{group_title} (ID: {chat_id}) — {detail}")
                logger.warning("Broadcast retry failed for group=%s chat_id=%s: %s", group_title, chat_id, detail)

        except Exception as exc:
            failed += 1
            detail = f"{type(exc).__name__}: {exc}"
            failure_details.append(f"{group_title} (ID: {chat_id}) — {detail}")
            logger.warning("Broadcast failed for group=%s chat_id=%s: %s", group_title, chat_id, detail)

        # Stay comfortably below Telegram's normal broadcast rate.
        await asyncio.sleep(0.05)

    summary = (
        "📢 GC Broadcast completed\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total GCs: {len(targets)}"
    )
    if sent_groups:
        summary += "\n\n✅ Sent to these GCs:\n" + "\n".join(
            f"• {name[:100]}" for name in sent_groups[:20]
        )
        if len(sent_groups) > 20:
            summary += f"\n• ...and {len(sent_groups) - 20} more"
    if failure_details:
        summary += "\n\n❌ Failed GCs (with reason):\n" + "\n".join(
            f"• {detail[:220]}" for detail in failure_details[:10]
        )
        if len(failure_details) > 10:
            summary += f"\n• ...and {len(failure_details) - 10} more"
    await status.edit_text(summary)


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
    BotCommand("broadcast", "Send a broadcast to groups"),
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
