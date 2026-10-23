"""Interactive category-based Help & Commands menu for Deep Emotion."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config import OWNER_ID

TRUSTED_ADMIN_ID = 8877757796


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _is_owner_or_trusted(user_id: int) -> bool:
    return user_id in {OWNER_ID, TRUSTED_ADMIN_ID}


def _categories_keyboard(*, show_owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            _button("🌸 Basic & AI", "help_cmd_basic"),
            _button("🎮 Games", "help_cmd_games"),
        ],
        [
            _button("🧠 Memory & Account", "help_cmd_memory"),
            _button("🛡️ Group Admin", "help_cmd_group"),
        ],
    ]
    if show_owner:
        rows.append([_button("👑 Owner & Trusted", "help_cmd_owner")])
    rows.append([_button("🔙 Back to Help", "help_main")])
    return InlineKeyboardMarkup(rows)


def _category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button("📚 All Categories", "help_commands")],
        [_button("🔙 Back to Help", "help_main")],
    ])


def _owner_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button("📚 All Categories", "help_commands")],
        [_button("🔙 Back to Help", "help_main")],
    ])


CATEGORY_TEXT = {
    "help_cmd_basic": (
        "🌸 BASIC & AI\n\n"
        "/start — Welcome panel\n"
        "/help — Open Help & Commands\n"
        "/ask question — Ask AI a question\n"
        "/clear — Clear conversation history\n\n"
        "💡 Example: /ask Python kya hai?"
    ),
    "help_cmd_games": (
        "🎮 FUN & GAMES\n\n"
        "/game truth — Start a truth challenge\n"
        "/game dare — Start a dare challenge\n"
        "/game wyr — Would You Rather\n"
        "/game joke — Get a joke\n"
        "/truth — Get a truth question\n"
        "/dare — Get a dare challenge\n"
        "/td — Open Truth or Dare buttons"
    ),
    "help_cmd_memory": (
        "🧠 MEMORY & ACCOUNT\n\n"
        "/memory — View saved memories\n"
        "/forget ID — Delete one saved memory\n"
        "/forget_all — Delete all saved memories\n"
        "/stats — View your activity and data stats\n"
        "/privacy — Read the privacy information\n\n"
        "🔐 Personal memories are not automatically shared with group AI context."
    ),
    "help_cmd_group": (
        "🛡️ GROUP & ADMIN COMMANDS\n\n"
        "/id — Show user/group IDs (groups only)\n"
        "/ban — Reply to a member, or /ban USER_ID [reason]\n"
        "/unban — Reply to a member, or /unban USER_ID\n"
        "/joinpanel — Join-request panel help/status\n"
        "/joinpanel_on — Enable the join panel\n"
        "/joinpanel_off — Disable the join panel\n\n"
        "⚠️ /ban and /unban require group-admin permissions. Join-panel controls are permission-checked too."
    ),
    "help_cmd_owner": (
        "👑 OWNER & TRUSTED COMMANDS\n\n"
        "/broadcast message — Send a broadcast to registered groups\n"
        "/groups — View registered groups\n\n"
        "🔒 These commands are restricted by the bot's existing access checks."
    ),
}


async def command_help_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Render the category menu and the selected command-help page."""
    query = update.callback_query
    if not query or not query.message:
        return

    data = query.data or ""
    user_id = query.from_user.id
    chat = query.message.chat

    if data == "help_cmd_owner" and (
        not _is_owner_or_trusted(user_id) or chat.type != "private"
    ):
        await query.answer(
            "🔒 Owner commands are only available to the owner/trusted user in private chat.",
            show_alert=True,
        )
        raise ApplicationHandlerStop

    await query.answer()

    if data == "help_commands":
        text = (
            "📖 DEEP EMOTION — COMMANDS\n\n"
            "Choose a category to see its commands and descriptions. 👇\n\n"
            "🌸 Basic & AI  ·  🎮 Games\n"
            "🧠 Memory & Account  ·  🛡️ Group Admin\n"
        )
        show_owner = _is_owner_or_trusted(user_id) and chat.type == "private"
        markup = _categories_keyboard(show_owner=show_owner)

    elif data in CATEGORY_TEXT:
        text = CATEGORY_TEXT[data]
        markup = _owner_keyboard() if data == "help_cmd_owner" else _category_keyboard()

    else:
        return

    try:
        if chat.type == "private" and query.message.photo:
            await query.edit_message_caption(
                caption=text,
                reply_markup=markup,
            )
        elif query.message.photo:
            await query.edit_message_caption(
                caption=text,
                reply_markup=markup,
            )
        else:
            await query.edit_message_text(
                text=text,
                reply_markup=markup,
            )
    except TelegramError:
        # Telegram may report "message is not modified" after a repeated tap.
        pass

    raise ApplicationHandlerStop
