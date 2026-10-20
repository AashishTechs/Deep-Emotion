# ==========================================================
# DEEP EMOTION — PRIVATE GROUP JOIN REQUEST PANEL
# ==========================================================

import asyncio
import html
import logging
from pathlib import Path

import aiosqlite
from telegram import (
    BotCommand,
    BotCommandScopeChatAdministrators,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import OWNER_ID

logger = logging.getLogger(__name__)
DB_PATH = Path("data/deep_emotions.db")

GROUP_ADMIN_COMMANDS = [
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
    BotCommand("joinpanel_on", "Admin: turn join panel ON"),
    BotCommand("joinpanel_off", "Admin: turn join panel OFF"),
    BotCommand("joinpanel", "Admin: turn join panel on/off"),
]


async def _configure_group_admin_commands(bot, chat_id: int):
    """Expose /joinpanel in this GC's command menu only to its admins."""
    try:
        await bot.set_my_commands(
            GROUP_ADMIN_COMMANDS,
            scope=BotCommandScopeChatAdministrators(chat_id=chat_id),
        )
    except TelegramError:
        logger.exception("Could not configure admin command menu for chat_id=%s", chat_id)


async def configure_join_panel_command_menus(bot):
    """Apply admin-only /joinpanel menu scope to groups already tracked by the bot."""
    if not DB_PATH.exists():
        return
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='broadcast_groups'"
            )
            if not await cursor.fetchone():
                return
            cursor = await db.execute("SELECT chat_id FROM broadcast_groups")
            rows = await cursor.fetchall()
        for (chat_id,) in rows:
            await _configure_group_admin_commands(bot, int(chat_id))
    except aiosqlite.Error:
        logger.exception("Could not load tracked groups for join-panel command menu")



async def _ensure_settings_table():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS join_panel_settings (
                chat_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.commit()


async def _panel_enabled(chat_id: int) -> bool:
    await _ensure_settings_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT enabled FROM join_panel_settings WHERE chat_id = ?", (chat_id,)
        )
        row = await cur.fetchone()
    return row is None or bool(row[0])


async def _set_panel_enabled(chat_id: int, enabled: bool):
    await _ensure_settings_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO join_panel_settings(chat_id, enabled) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled
        """, (chat_id, int(enabled)))
        await db.commit()


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


async def _delete_command_message(message):
    # Keep /joinpanel commands from appearing in the group's message history.
    try:
        await message.delete()
    except TelegramError:
        logger.debug("Could not delete joinpanel command message (bot may lack delete rights).")


async def _send_private_status(bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramError:
        logger.info("Could not DM joinpanel status to user_id=%s; user may need to /start the bot", user_id)


async def _handle_join_panel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    forced_option: str | None = None,
):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        if chat.type == ChatType.PRIVATE:
            await message.reply_text("Ye command apne GC mein admin ke roop mein use karo.")
        return

    # Keep the command menu scoped to administrators for this group.
    await _configure_group_admin_commands(context.bot, chat.id)

    # Silently remove non-admin attempts; don't reveal the command or reply to members.
    if not await _is_group_admin(context.bot, chat.id, user.id):
        await _delete_command_message(message)
        return

    option = forced_option or (context.args[0].lower().strip() if context.args else "")
    await _delete_command_message(message)

    if option not in ("on", "off"):
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "💗 Join Request Panel commands:\\n"
                "/joinpanel_on — panel ON karo\\n"
                "/joinpanel_off — panel OFF karo"
            ),
        )
        return

    enabled = option == "on"
    await _set_panel_enabled(chat.id, enabled)
    status = (
        "✅ Join Request Panel ON ho gaya hai."
        if enabled
        else "🔕 Join Request Panel OFF ho gaya hai."
    )
    await context.bot.send_message(chat_id=chat.id, text=status)


async def join_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Backward-compatible /joinpanel on|off command."""
    await _handle_join_panel_command(update, context)


async def join_panel_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable the join-request panel and confirm in the group."""
    await _handle_join_panel_command(update, context, forced_option="on")


async def join_panel_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable the join-request panel and confirm in the group."""
    await _handle_join_panel_command(update, context, forced_option="off")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    if not request:
        return

    chat = request.chat
    user = request.from_user
    await _configure_group_admin_commands(context.bot, chat.id)
    if not await _panel_enabled(chat.id):
        logger.info("Join request panel disabled for chat_id=%s; request from %s left pending", chat.id, user.id)
        return

    # Post a minimal panel in the GC itself. Applicant identity/details are not
    # exposed in the public message; only the callback payload contains the ID.
    panel = (
        "💗 <b>𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴ | 𝐍ᴇᴡ 𝐉ᴏɪɴ 𝐑ᴇǫᴜᴇsᴛ</b>\\n\\n"
        f"<b>GC:</b> {html.escape(chat.title or str(chat.id))}\\n"
        "📨 A new member is waiting for approval.\\n"
        "👑 Only this group's admins/owner can use the buttons below."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"joinreq:approve:{chat.id}:{user.id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"joinreq:decline:{chat.id}:{user.id}"),
    ]])

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=panel,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except TelegramError:
        logger.exception("Could not post join request panel in chat_id=%s", chat.id)



async def join_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return
    try:
        _, action, raw_chat_id, raw_user_id = query.data.split(":", 3)
        chat_id, user_id = int(raw_chat_id), int(raw_user_id)
    except (ValueError, TypeError):
        await query.answer("Invalid request button.", show_alert=True)
        return

    if action not in ("approve", "decline"):
        await query.answer("Unknown action.", show_alert=True)
        return
    if not await _is_group_admin(context.bot, chat_id, query.from_user.id):
        await query.answer("Sirf is GC ke admin/owner ye request handle kar sakte hain.", show_alert=True)
        return

    try:
        if action == "approve":
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            result, label = "✅ Request accepted.", "✅ ACCEPTED"
        else:
            await context.bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            result, label = "❌ Request declined.", "❌ DECLINED"

        if query.message:
            original = query.message.text_html or "Join request handled."
            await query.edit_message_text(
                f"{original}\n\n<b>{label}</b> by {html.escape(query.from_user.full_name)}",
                parse_mode="HTML",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        await query.answer(result)
    except TelegramError as exc:
        logger.warning("Join request %s failed for chat=%s user=%s: %s", action, chat_id, user_id, exc)
        await query.answer(f"Action failed: {str(exc)[:180]}", show_alert=True)
