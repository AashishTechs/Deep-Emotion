# ==========================================================
# DEEP EMOTION — PRIVATE GROUP JOIN REQUEST PANEL
# ==========================================================

import asyncio
import html
import logging
from pathlib import Path

import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import OWNER_ID

logger = logging.getLogger(__name__)
DB_PATH = Path("data/deep_emotions.db")


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


async def join_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        if chat.type == ChatType.PRIVATE:
            await message.reply_text("Ye command apne GC mein admin ke roop mein use karo.")
        return

    # Silently remove non-admin attempts; don't reveal the command or reply to members.
    if not await _is_group_admin(context.bot, chat.id, user.id):
        await _delete_command_message(message)
        return

    option = (context.args[0].lower() if context.args else "").strip()
    await _delete_command_message(message)

    if option not in ("on", "off"):
        await _send_private_status(
            context.bot, user.id,
            "💗 Join Request Panel\n\n"
            "/joinpanel on — panel chalu karo\n"
            "/joinpanel off — panel band karo\n\n"
            "Settings ka result sirf aapko DM mein milega."
        )
        return

    enabled = option == "on"
    await _set_panel_enabled(chat.id, enabled)
    status = "✅ Join request panel is now ON." if enabled else "🔕 Join request panel is now OFF."
    await _send_private_status(context.bot, user.id, f"{status}\nGC: {html.escape(chat.title or str(chat.id))}")


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    if not request:
        return

    chat = request.chat
    user = request.from_user
    if not await _panel_enabled(chat.id):
        logger.info("Join request panel disabled for chat_id=%s; request from %s left pending", chat.id, user.id)
        return

    name = html.escape(user.full_name or "Unknown")
    username = f"@{html.escape(user.username)}" if user.username else "Not set"
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'
    scam_status = "⚠️ Reported as Scam" if getattr(user, "is_scam", False) else "Not reported as scam"
    panel = (
        "💗 <b>𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴ | 𝐍ᴇᴡ 𝐉ᴏɪɴ 𝐑ᴇǫᴜᴇsᴛ</b>\n\n"
        f"<b>GC:</b> {html.escape(chat.title or str(chat.id))}\n"
        "╭━━━「 📨 <b>𝐑ᴇǫᴜᴇsᴛ 𝐃ᴇᴛᴀɪʟs</b> 」━━━╮\n\n"
        f"👤 <b>Name:</b> {name}\n"
        f"🔗 <b>Mention:</b> {mention}\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📛 <b>Username:</b> {username}\n"
        f"🛡️ <b>Scam Status:</b> {scam_status}\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"joinreq:approve:{chat.id}:{user.id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"joinreq:decline:{chat.id}:{user.id}"),
    ]])

    # Send private details to each human GC admin. Admins must have started the bot.
    admins = await context.bot.get_chat_administrators(chat.id)
    delivered = 0
    for admin in admins:
        if admin.user.is_bot:
            continue
        try:
            await context.bot.send_message(
                chat_id=admin.user.id,
                text=panel,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            delivered += 1
        except TelegramError:
            logger.info("Cannot DM join request to admin_id=%s in chat_id=%s", admin.user.id, chat.id)

    if delivered == 0:
        # Never leak applicant details to group members, even when DMs are unavailable.
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "📨 Ek nayi join request pending hai. GC admins/owner, "
                    "request panel privately paane ke liye bot ko DM mein /start karein."
                ),
            )
        except TelegramError:
            logger.exception("Could not notify admins about join request for chat_id=%s", chat.id)


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
