# ==========================================================
# DEEP EMOTION — GROUP JOIN REQUEST PANEL
# ==========================================================

import html
import logging
from pathlib import Path

import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import ContextTypes

from config import OWNER_ID

logger = logging.getLogger(__name__)
DB_PATH = Path("data/deep_emotions.db")


async def _ensure_settings_table():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS join_panel_settings (
                chat_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        await db.commit()


async def _panel_enabled(chat_id: int) -> bool:
    await _ensure_settings_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT enabled FROM join_panel_settings WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cur.fetchone()
    # New groups have the panel enabled until an admin explicitly turns it off.
    return row is None or bool(row[0])


async def _set_panel_enabled(chat_id: int, enabled: bool):
    await _ensure_settings_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO join_panel_settings(chat_id, enabled) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled
            """,
            (chat_id, int(enabled)),
        )
        await db.commit()


async def _is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        # The configured bot owner is trusted, but still must be an admin in this GC.
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        except Exception:
            return False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def join_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text("Ye command apne GC mein admin ke roop mein use karo.")
        return
    if not await _is_group_admin(context.bot, chat.id, user.id):
        await message.reply_text("⛔ Sirf is GC ke admin/owner join panel setting badal sakte hain.")
        return

    option = (context.args[0].lower() if context.args else "").strip()
    if option not in ("on", "off"):
        await message.reply_text(
            "💗 Join Request Panel\n\n"
            "/joinpanel on — panel chalu karo\n"
            "/joinpanel off — panel band karo"
        )
        return

    enabled = option == "on"
    await _set_panel_enabled(chat.id, enabled)
    await message.reply_text(
        "✅ Join request panel is now ON." if enabled
        else "🔕 Join request panel is now OFF."
    )


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

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=panel,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Failed to post join-request panel for chat_id=%s user_id=%s", chat.id, user.id)


async def join_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return
    try:
        _, action, raw_chat_id, raw_user_id = query.data.split(":", 3)
        chat_id = int(raw_chat_id)
        user_id = int(raw_user_id)
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
            result = "✅ Request accepted."
            label = "✅ ACCEPTED"
        else:
            await context.bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            result = "❌ Request declined."
            label = "❌ DECLINED"

        original = query.message.text_html if query.message else "Join request handled."
        if query.message:
            await query.edit_message_text(
                f"{original}\n\n<b>{label}</b> by {html.escape(query.from_user.full_name)}",
                parse_mode="HTML",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        await query.answer(result)
    except Exception as exc:
        logger.warning("Join request %s failed for chat=%s user=%s: %s", action, chat_id, user_id, exc)
        await query.answer(f"Action failed: {str(exc)[:180]}", show_alert=True)
