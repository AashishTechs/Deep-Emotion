"""Single-message command list for Deep Emotion's Help & Commands panel."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config import OWNER_ID

TRUSTED_ADMIN_ID = 8877757796


def _is_owner_or_trusted(user_id: int) -> bool:
    return user_id in {OWNER_ID, TRUSTED_ADMIN_ID}


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ", callback_data="help_main")]]
    )


def _commands_text(*, show_owner: bool, show_group_admin: bool = False) -> str:
    """Build the complete command list as one HTML-formatted Telegram message."""
    text = (
        "📖 <b>ᴅᴇᴇᴘ ᴇᴍᴏᴛɪᴏɴ — ᴀʟʟ ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅs</b>\n"
        "\n"
        "╭━━━ 🌸 <b>BASIC &amp; AI</b> ━━━╮\n"
        "│ <code>/start</code> — Welcome panel\n"
        "│ <code>/help</code> — Help &amp; Commands\n"
        "│ <code>/ask &lt;question&gt;</code> — AI se baat karo\n"
        "│ <code>/clear</code> — Chat history clear karo\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n"
        "\n"
        "╭━━━ 🎮 <b>GAMES &amp; FUN</b> ━━━╮\n"
        "│ <code>/game truth</code> — Truth challenge\n"
        "│ <code>/game dare</code> — Dare challenge\n"
        "│ <code>/game wyr</code> — Would You Rather\n"
        "│ <code>/game joke</code> — Joke suno\n"
        "│ <code>/truth</code> — Truth challenge\n"
        "│ <code>/dare</code> — Dare challenge\n"
        "│ <code>/td</code> — Truth or Dare buttons\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n"
        "\n"
        "╭━━━ 🧠 <b>MEMORY &amp; ACCOUNT</b> ━━━╮\n"
        "│ <code>/memory</code> — Saved memories dekho\n"
        "│ <code>/forget &lt;ID&gt;</code> — Ek memory delete karo\n"
        "│ <code>/forget_all</code> — Saari memories delete karo\n"
        "│ <code>/stats</code> — Apne stats dekho\n"
        "│ <code>/privacy</code> — Privacy information\n"
        "│ <code>/id</code> — User/Group ID dekho (groups only)\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n"
        "\n"
        "╭━━━ 🛡️ <b>GROUP ADMIN</b> ━━━╮\n"
        "│ <code>/ban</code> — Reply karo ya <code>/ban USER_ID [reason]</code>\n"
        "│ <code>/unban</code> — Reply karo ya <code>/unban USER_ID</code>\n"
        "│ <code>/mute</code> — Reply karo ya <code>/mute USER_ID</code>\n"
        "│ <code>/unmute</code> — Reply karo ya <code>/unmute USER_ID</code>\n"
        "│ <code>/joinpanel</code> — Join panel status/help\n"
        "│ <code>/joinpanel_on</code> — Join panel ON karo\n"
        "│ <code>/joinpanel_off</code> — Join panel OFF karo\n"
        + ("│ <code>/filter @username</code> — Reply sticker ko username se save karo\n"
           "│ <code>/unfilter @username</code> — Saved sticker filter hatao\n"
           if show_group_admin else "")
        + "╰━━━━━━━━━━━━━━━━━━╯"
    )

    if show_owner:
        text += (
            "\n\n"
            "╭━━━ 👑 <b>OWNER &amp; TRUSTED</b> ━━━╮\n"
            "│ <code>/broadcast &lt;message&gt;</code> — Groups mein broadcast\n"
            "│ <code>/groups</code> — Registered groups ki list\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯"
        )

    text += (
        "\n\n"
        "💡 <b>EXAMPLE</b>\n"
        "<code>/ask Python kya hai?</code>\n\n"
        "✨ Commands ko message box mein type karke send karo.\n"
        "\n"
        "🖤 <b>Deep Emotion — Har baat, dil se.</b>"
    )
    return text


async def command_help_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Show every command in one message when the Commands button is tapped."""
    query = update.callback_query
    if not query or not query.message:
        return

    data = query.data or ""
    if data != "help_commands":
        return

    await query.answer()

    show_owner = (
        _is_owner_or_trusted(query.from_user.id)
        and query.message.chat.type == "private"
    )
    show_group_admin = False
    if query.message.chat.type in ("group", "supergroup"):
        try:
            member = await context.bot.get_chat_member(
                query.message.chat.id, query.from_user.id
            )
            show_group_admin = member.status in ("administrator", "creator")
        except TelegramError:
            show_group_admin = False
    text = _commands_text(
        show_owner=show_owner,
        show_group_admin=show_group_admin,
    )
    markup = _back_keyboard()

    try:
        if query.message.photo:
            # The complete list is longer than Telegram's photo-caption limit.
            # Replace the photo panel with one regular text message instead.
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        else:
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
    except TelegramError:
        # Ignore repeated taps or messages that can no longer be edited.
        pass

    raise ApplicationHandlerStop
