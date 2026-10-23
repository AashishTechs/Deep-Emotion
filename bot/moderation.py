"""Admin-only /ban and /unban commands for Deep Emotion groups."""

import logging

import aiosqlite
from telegram import (
    BotCommand,
    BotCommandScopeChatAdministrators,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config import OWNER_ID
from bot.join_requests import DB_PATH, GROUP_ADMIN_COMMANDS

logger = logging.getLogger(__name__)

# Extend the shared admin-menu list so /joinpanel updates keep these commands too.
GROUP_ADMIN_COMMANDS.extend([
    BotCommand("ban", "Ban a member (reply or user ID)"),
    BotCommand("unban", "Unban a member (reply or user ID)"),
    BotCommand("filter", "Save a sticker for a username"),
    BotCommand("unfilter", "Remove a username sticker"),
    BotCommand("mute", "Mute a member (reply or user ID)"),
    BotCommand("unmute", "Unmute a member (reply or user ID)"),
])


def _is_group(chat) -> bool:
    return bool(chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP))


async def _require_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return False
    if not _is_group(chat):
        await message.reply_text("Ye command sirf group/supergroup mein use karo.")
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("⛔ Sirf group admins /ban, /unban, /mute aur /unmute use kar sakte hain.")
            return False

        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("⚠️ Pehle mujhe group admin banao aur Ban users / Restrict members permission do.")
            return False
        if not getattr(bot_member, "can_restrict_members", False) and bot_member.status not in (ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("⚠️ Mere paas Ban users / Restrict members permission nahi hai.")
            return False
    except TelegramError:
        logger.exception("Could not verify moderation permissions in chat %s", chat.id)
        await message.reply_text("⚠️ Admin permissions verify nahi ho paayi. Bot ko admin permissions check karo.")
        return False

    # Keep the admin command menu up to date for this group.
    await configure_moderation_command_menu(context.bot, chat.id)
    return True


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return None, []

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target:
            return target, list(context.args or [])
        return None, []

    args = list(context.args or [])
    if not args or not args[0].isdigit():
        return None, args

    target_id = int(args.pop(0))
    try:
        target = await context.bot.get_chat(target_id)
        return target, args
    except TelegramError:
        # Telegram can still ban/unban a numeric ID even if get_chat cannot
        # return a Chat object for that user.
        return type("UserTarget", (), {"id": target_id, "full_name": f"User {target_id}", "username": None, "is_bot": False})(), args


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a group member by replying to them or supplying their numeric Telegram user ID."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    if not await _require_group_admin(update, context):
        return

    target, extra_args = await _resolve_target(update, context)
    if not target:
        await message.reply_text(
            "Usage:\n• Reply to a user's message: /ban [reason]\n"
            "• Or use: /ban USER_ID [reason]\n\n"
            "Username se user resolve nahi hota; reply ya numeric Telegram ID use karo."
        )
        return

    if target.id in {context.bot.id, OWNER_ID} or getattr(target, "is_bot", False):
        await message.reply_text("⛔ Main bots, apne aap ko, ya bot owner ko ban nahi kar sakti.")
        return

    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            "creator",
        ):
            await message.reply_text("⛔ Kisi group admin/owner ko is command se ban nahi kar sakte.")
            return
    except TelegramError:
        # Non-members can still be banned by numeric ID, so let Telegram
        # perform the final validation in ban_chat_member below.
        pass

    reason = " ".join(extra_args).strip()
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target.id)
        display_name = getattr(target, "full_name", None) or getattr(target, "first_name", None) or str(target.id)
        reply = "𝐂𝐡𝐚𝐥 𝐍𝐢𝐤𝐚𝐥 𝐘𝐚𝐡𝐚 𝐒𝐞...! 😡 𝐁𝐀𝐍𝐍𝐄𝐃. — 𝐃 𝐄 𝐌 ◯ 𝇙 𝐈 𝐄 🌷"
        if reason:
            reply += f"\n📝 Reason: {reason[:500]}"
        await message.reply_text(reply)
    except TelegramError as exc:
        logger.warning("Ban failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text(
            "❌ Ban nahi ho paaya. Check karo ki bot admin hai aur uske paas Ban users permission hai."
        )


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a non-admin group member until an admin explicitly unmutes them."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    if not await _require_group_admin(update, context):
        return

    target, _ = await _resolve_target(update, context)
    if not target:
        await message.reply_text(
            "Usage:\\n• Reply to a member's message: /mute\\n"
            "• Or use: /mute USER_ID\\n\\n"
            "Username se user resolve nahi hota; reply ya numeric Telegram ID use karo."
        )
        return

    if target.id in {context.bot.id, OWNER_ID} or getattr(target, "is_bot", False):
        await message.reply_text("⛔ Bot, bots, ya bot owner ko mute nahi kar sakte.")
        return

    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            "creator",
        ):
            await message.reply_text("⛔ Group admin/owner ko mute nahi kar sakte.")
            return
        if target_member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
            await message.reply_text("ℹ️ Ye user is GC ka active member nahi hai.")
            return
    except TelegramError:
        await message.reply_text("❌ Member verify nahi ho paaya. Reply ya sahi USER_ID use karo.")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
        )
        await message.reply_text(
            "🔇 User Muted Successfully!\n\n"
            "This user can no longer send messages in this group."
        )
    except TelegramError as exc:
        logger.warning("Mute failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text(
            "❌ Mute nahi ho paaya. Check karo bot admin hai aur uske paas Restrict members permission hai."
        )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user by replying to their message or supplying their numeric Telegram user ID."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    if not await _require_group_admin(update, context):
        return

    target, _ = await _resolve_target(update, context)
    if not target:
        await message.reply_text(
            "Usage:\n• Reply to the user's message: /unban\n"
            "• Or use: /unban USER_ID\n\n"
            "Username se user resolve nahi hota; reply ya numeric Telegram ID use karo."
        )
        return

    if target.id == context.bot.id:
        await message.reply_text("⛔ Bot ko unban karne ki zaroorat nahi hai.")
        return

    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target.id, only_if_banned=True)
        display_name = getattr(target, "full_name", None) or getattr(target, "first_name", None) or str(target.id)
        await message.reply_text("𝐂𝐡𝐚𝐥 𝐊𝐨𝐢 𝐍𝐚 𝐌𝐚𝐚𝐟 𝐊𝐢𝐲𝐚...! 😌 𝐔𝐍𝐁𝐀𝐍𝐍𝐄𝐃. — 𝐃 𝐄 𝐌 ◯ 𝇙 𝐈 𝐄 🌷")
    except TelegramError as exc:
        logger.warning("Unban failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text(
            "❌ Unban nahi ho paaya. User ID check karo aur bot ki admin permission verify karo."
        )


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restore send permissions for a previously muted non-admin group member."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    if not await _require_group_admin(update, context):
        return

    target, _ = await _resolve_target(update, context)
    if not target:
        await message.reply_text(
            "Usage:\\n• Reply to a member's message: /unmute\\n"
            "• Or use: /unmute USER_ID\\n\\n"
            "Username se user resolve nahi hota; reply ya numeric Telegram ID use karo."
        )
        return

    if target.id == context.bot.id or getattr(target, "is_bot", False):
        await message.reply_text("ℹ️ Bot ko unmute karne ki zaroorat nahi hai.")
        return

    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            "creator",
        ):
            await message.reply_text("ℹ️ Group admin/owner pe mute restriction nahi lagti.")
            return
        if target_member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
            await message.reply_text("ℹ️ Ye user is GC ka active member nahi hai.")
            return
    except TelegramError:
        await message.reply_text("❌ Member verify nahi ho paaya. Reply ya sahi USER_ID use karo.")
        return

    try:
        group_chat = await context.bot.get_chat(chat.id)
        default_permissions = group_chat.permissions or ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=default_permissions,
        )
        await message.reply_text(
            "🔊 User Unmuted Successfully!\n\n"
            "This user can now send messages in this group."
        )
    except TelegramError as exc:
        logger.warning("Unmute failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text(
            "❌ Unmute nahi ho paaya. Check karo bot admin hai aur uske paas Restrict members permission hai."
        )


async def configure_moderation_command_menu(bot, chat_id: int):
    """Expose moderation commands to group admins only."""
    commands = list(GROUP_ADMIN_COMMANDS)
    try:
        await bot.set_my_commands(
            commands,
            scope=BotCommandScopeChatAdministrators(chat_id=chat_id),
        )
    except TelegramError:
        logger.exception("Could not configure moderation command menu for chat %s", chat_id)


async def configure_moderation_command_menus(bot):
    """Configure admin command menus for groups already tracked by the bot."""
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
            await configure_moderation_command_menu(bot, int(chat_id))
    except aiosqlite.Error:
        logger.exception("Could not load tracked groups for moderation command menus")


async def moderation_commands_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the full Commands panel including moderation commands."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    text = (
        "📖 ALL BOT COMMANDS\n\n"
        "🌸 BASIC & AI\n"
        "/start — Welcome panel\n"
        "/help — Help & Commands\n"
        "/ask question — AI se question poochho\n"
        "/clear — Chat history clear karo\n\n"
        "🎮 GAMES\n"
        "/game truth | /game dare | /game wyr | /game joke\n"
        "/truth — Truth challenge\n"
        "/dare — Dare challenge\n"
        "/td — Truth or Dare buttons\n\n"
        "🧠 MEMORY & ACCOUNT\n"
        "/memory — Saved memories dekho\n"
        "/forget ID — Ek memory delete karo\n"
        "/forget_all — Saari memories delete karo\n"
        "/stats — Apne stats dekho\n"
        "/privacy — Privacy details\n"
        "/id — User/group IDs (groups only)\n\n"
        "🛡️ GROUP ADMIN COMMANDS\n"
        "/ban — Reply to a member's message, or /ban USER_ID [reason]\n"
        "/unban — Reply to a member's message, or /unban USER_ID\n"
        "/joinpanel — Join request panel help/status\n"
        "/joinpanel_on — Join panel ON karo\n"
        "/joinpanel_off — Join panel OFF karo\n\n"
        "👑 OWNER / TRUSTED ADMIN ONLY\n"
        "/broadcast message — Groups mein broadcast bhejo\n"
        "/groups — Registered groups ki list\n\n"
        "💡 Example: /ask Python kya hai?"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ", callback_data="help_main")
    ]])

    try:
        if query.message.photo:
            await query.edit_message_caption(
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                text=text,
                reply_markup=keyboard,
            )
    except TelegramError:
        logger.exception("Could not update Commands help panel")
    raise ApplicationHandlerStop
