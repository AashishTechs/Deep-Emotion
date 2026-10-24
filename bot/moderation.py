"""Admin-only /ban and /unban commands for Deep Emotion groups."""

import logging
import re
import unicodedata

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

GROUP_ADMIN_COMMANDS.extend([
    BotCommand("ban", "Ban a member (reply or user ID)"),
    BotCommand("unban", "Unban a member (reply or user ID)"),
    BotCommand("filter", "Save a sticker for a username"),
    BotCommand("unfilter", "Remove a username sticker"),
    BotCommand("mute", "Mute a member (reply, username or name)"),
    BotCommand("unmute", "Unmute a member (reply, username or name)"),
])


def _is_group(chat) -> bool:
    return bool(chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP))


def _normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(
        char for char in value
        if not unicodedata.category(char).startswith("C")
        and unicodedata.category(char) not in {"Mn", "Me"}
    )
    return " ".join(value.split())


def _member_key(user) -> tuple[str, str]:
    username = (getattr(user, "username", None) or "").casefold()
    name = _normalize_name(getattr(user, "full_name", None) or getattr(user, "first_name", None) or "")
    return username, name


async def cache_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remember users seen in group messages so username/display-name targets can resolve."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or not _is_group(chat):
        return
    username, name = _member_key(user)
    if not username and not name:
        return
    cache = context.application.bot_data.setdefault("moderation_members", {})
    group_cache = cache.setdefault(chat.id, {})
    group_cache[user.id] = {
        "id": user.id,
        "username": username,
        "name": name,
        "full_name": getattr(user, "full_name", None) or getattr(user, "first_name", None) or str(user.id),
        "is_bot": bool(getattr(user, "is_bot", False)),
    }


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
    await configure_moderation_command_menu(context.bot, chat.id)
    return True


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message:
        return None, []

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target:
            return target, list(context.args or [])
        return None, []

    args = list(context.args or [])
    if not args:
        return None, args

    raw_target = args.pop(0).strip()
    target_id = int(raw_target) if raw_target.isdigit() else None
    cache = context.application.bot_data.get("moderation_members", {})
    group_cache = cache.get(chat.id, {}) if chat else {}

    if target_id is not None:
        try:
            target = await context.bot.get_chat(target_id)
            return target, args
        except TelegramError:
            return type("UserTarget", (), {
                "id": target_id,
                "full_name": f"User {target_id}",
                "username": None,
                "is_bot": False,
            })(), args

    wanted_username = raw_target.lstrip("@").casefold()
    wanted_name = _normalize_name(raw_target)
    matches = []
    for item in group_cache.values():
        if wanted_username and item.get("username") == wanted_username:
            matches.append(item)
        elif wanted_name and item.get("name") == wanted_name:
            matches.append(item)

    unique = {item["id"]: item for item in matches}
    if len(unique) == 1:
        item = next(iter(unique.values()))
        return type("UserTarget", (), item)(), args
    if len(unique) > 1:
        return type("AmbiguousTarget", (), {"id": None, "full_name": "ambiguous", "matches": list(unique.values())})(), args
    return None, [raw_target] + args


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not await _require_group_admin(update, context):
        return
    target, extra_args = await _resolve_target(update, context)
    if not target or getattr(target, "id", None) is None:
        await message.reply_text("Usage:\n• Reply to a user's message: /ban [reason]\n• Or use: /ban USER_ID [reason]\n\nUsername se user resolve nahi hota; reply ya numeric Telegram ID use karo.")
        return
    if target.id in {context.bot.id, OWNER_ID} or getattr(target, "is_bot", False):
        await message.reply_text("⛔ Main bots, apne aap ko, ya bot owner ko ban nahi kar sakti.")
        return
    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("⛔ Kisi group admin/owner ko is command se ban nahi kar sakte.")
            return
    except TelegramError:
        pass
    reason = " ".join(extra_args).strip()
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target.id)
        reply = "𝐂𝐡𝐚𝐥 𝐍𝐢𝐤𝐚𝐥 𝐘𝐚𝐡𝐚 𝐒𝐞...! 😡 𝐁𝐀𝐍𝐍𝐄𝐃. — 𝐃 𝐄 𝐌 ◯ 𝇙 𝐈 𝐄 🌷"
        if reason:
            reply += f"\n📝 Reason: {reason[:500]}"
        await message.reply_text(reply)
    except TelegramError as exc:
        logger.warning("Ban failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text("❌ Ban nahi ho paaya. Check karo ki bot admin hai aur uske paas Ban users permission hai.")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not await _require_group_admin(update, context):
        return
    target, _ = await _resolve_target(update, context)
    if not target or getattr(target, "id", None) is None:
        await message.reply_text("Usage:\n• Reply: /mute\n• Username: /mute @username\n• Display name: /mute Name\n• User ID: /mute USER_ID")
        return
    if getattr(target, "matches", None):
        names = ", ".join(item.get("full_name", str(item["id"])) for item in target.matches[:5])
        await message.reply_text(f"⚠️ Ye display name multiple members ka hai: {names}\nReply karke /mute use karo.")
        return
    if target.id in {context.bot.id, OWNER_ID} or getattr(target, "is_bot", False):
        await message.reply_text("⛔ Bot, bots, ya bot owner ko mute nahi kar sakte.")
        return
    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("⛔ Group admin/owner ko mute nahi kar sakte.")
            return
        if target_member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
            await message.reply_text("ℹ️ Ye user is GC ka active member nahi hai.")
            return
    except TelegramError:
        await message.reply_text("❌ Member verify nahi ho paaya. Reply, username ya sahi USER_ID use karo.")
        return
    try:
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target.id, permissions=ChatPermissions(
            can_send_messages=False, can_send_audios=False, can_send_documents=False,
            can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
            can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
            can_add_web_page_previews=False,
        ))
        await message.reply_text("🔇 User Muted Successfully!\n\nThis user can no longer send messages in this group.")
    except TelegramError as exc:
        logger.warning("Mute failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text("❌ Mute nahi ho paaya. Check karo bot admin hai aur uske paas Restrict members permission hai.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not await _require_group_admin(update, context):
        return
    target, _ = await _resolve_target(update, context)
    if not target or getattr(target, "id", None) is None:
        await message.reply_text("Usage:\n• Reply: /unban\n• Or use: /unban USER_ID\n\nUsername se user resolve nahi hota; reply ya numeric Telegram ID use karo.")
        return
    if target.id == context.bot.id:
        await message.reply_text("⛔ Bot ko unban karne ki zaroorat nahi hai.")
        return
    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target.id, only_if_banned=True)
        await message.reply_text("𝐂𝐡𝐚𝐥 𝐊𝐨𝐢 𝐍𝐚 𝐌𝐚𝐚𝐟 𝐊𝐢𝐲𝐚...! 😌 𝐔𝐍𝐁𝐀𝐍𝐍𝐄𝐃. — 𝐃 𝐄 𝐌 ◯ 𝇙 𝐈 𝐄 🌷")
    except TelegramError as exc:
        logger.warning("Unban failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text("❌ Unban nahi ho paaya. User ID check karo aur bot ki admin permission verify karo.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not await _require_group_admin(update, context):
        return
    target, _ = await _resolve_target(update, context)
    if not target or getattr(target, "id", None) is None:
        await message.reply_text("Usage:\n• Reply: /unmute\n• Username: /unmute @username\n• Display name: /unmute Name\n• User ID: /unmute USER_ID")
        return
    if getattr(target, "matches", None):
        names = ", ".join(item.get("full_name", str(item["id"])) for item in target.matches[:5])
        await message.reply_text(f"⚠️ Ye display name multiple members ka hai: {names}\nReply karke /unmute use karo.")
        return
    if target.id == context.bot.id or getattr(target, "is_bot", False):
        await message.reply_text("ℹ️ Bot ko unmute karne ki zaroorat nahi hai.")
        return
    try:
        target_member = await context.bot.get_chat_member(chat.id, target.id)
        if target_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, "creator"):
            await message.reply_text("ℹ️ Group admin/owner pe mute restriction nahi lagti.")
            return
        if target_member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
            await message.reply_text("ℹ️ Ye user is GC ka active member nahi hai.")
            return
    except TelegramError:
        await message.reply_text("❌ Member verify nahi ho paaya. Reply, username ya sahi USER_ID use karo.")
        return
    try:
        group_chat = await context.bot.get_chat(chat.id)
        default_permissions = group_chat.permissions or ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target.id, permissions=default_permissions)
        await message.reply_text("🔊 User Unmuted Successfully!\n\nThis user can now send messages in this group.")
    except TelegramError as exc:
        logger.warning("Unmute failed in chat %s for user %s: %s", chat.id, target.id, exc)
        await message.reply_text("❌ Unmute nahi ho paaya. Check karo bot admin hai aur uske paas Restrict members permission hai.")


async def configure_moderation_command_menu(bot, chat_id: int):
    commands = list(GROUP_ADMIN_COMMANDS)
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChatAdministrators(chat_id=chat_id))
    except TelegramError:
        logger.exception("Could not configure moderation command menu for chat %s", chat_id)


async def configure_moderation_command_menus(bot):
    if not DB_PATH.exists():
        return
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='broadcast_groups'")
            if not await cursor.fetchone():
                return
            cursor = await db.execute("SELECT chat_id FROM broadcast_groups")
            rows = await cursor.fetchall()
        for (chat_id,) in rows:
            await configure_moderation_command_menu(bot, int(chat_id))
    except aiosqlite.Error:
        logger.exception("Could not load tracked groups for moderation command menus")


async def moderation_commands_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    text = (
        "📖 ALL BOT COMMANDS\n\n"
        "🌸 BASIC & AI\n/start — Welcome panel\n/help — Help & Commands\n/ask question — AI se question poochho\n/clear — Chat history clear karo\n\n"
        "🎮 GAMES\n/game truth | /game dare | /game wyr | /game joke\n/truth — Truth challenge\n/dare — Dare challenge\n/td — Truth or Dare buttons\n\n"
        "🧠 MEMORY & ACCOUNT\n/memory — Saved memories dekho\n/forget ID — Ek memory delete karo\n/forget_all — Saari memories delete karo\n/stats — Apne stats dekho\n/privacy — Privacy details\n/id — User/group IDs (groups only)\n\n"
        "🛡️ GROUP ADMIN COMMANDS\n/ban — Reply to a member's message, or /ban USER_ID [reason]\n/unban — Reply to a member's message, or /unban USER_ID\n/filter <target> — Sticker filter\n/unfilter <target> — Remove sticker filter\n/mute — Reply, @username, display name or USER_ID\n/unmute — Reply, @username, display name or USER_ID\n/joinpanel — Join request panel help/status\n/joinpanel_on — Join panel ON karo\n/joinpanel_off — Join panel OFF karo\n\n"
        "👑 OWNER / TRUSTED ADMIN ONLY\n/broadcast message — Groups mein broadcast bhejo\n/groups — Registered groups ki list\n\n💡 Example: /ask Python kya hai?"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ", callback_data="help_main")]])
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text, reply_markup=keyboard)
    except TelegramError:
        logger.exception("Could not update Commands help panel")
    raise ApplicationHandlerStop
