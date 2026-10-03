# ==========================================================
# DEEP EMOTIONS — TELEGRAM HANDLERS
# Step 1–8
# ==========================================================

import re
import time
from pathlib import Path
from collections import defaultdict, deque

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    MessageEntity,
)

from telegram.constants import ChatAction

from telegram.ext import ContextTypes

from config import OWNER_ID

from bot.social_engine import (
    should_reply_group,
    mark_group_reply,
    social_game,
)

from bot.ai import (
    generate_reply,
    extract_memories,
    ai_tool,
    transcribe_voice,
)

from bot.database import (
    add_message,
    get_history,
    clear_history,
    count_messages,

    add_memory,
    get_memories,
    delete_memory,
    clear_memories,
    count_memories,

    add_group_message,
    get_group_context,
    clear_group_context,
    count_group_messages,
)


# ==========================================================
# RATE LIMIT
# ==========================================================

user_requests = defaultdict(deque)

WINDOW_SECONDS = 20
MAX_REQUESTS = 5

# Reply to normal group messages without requiring a mention/reply.
# Change to False for mention/reply-only group behavior.
GROUP_REPLY_ALWAYS = True


def allowed(user_id):

    now = time.monotonic()

    q = user_requests[user_id]

    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()

    if len(q) >= MAX_REQUESTS:
        return False

    q.append(now)

    return True


# ==========================================================
# STEP 4 — ANTI SPAM
# ==========================================================

spam_tracker = defaultdict(deque)
warnings = defaultdict(int)

SPAM_WINDOW_SECONDS = 10
SPAM_MESSAGE_LIMIT = 6

MAX_WARNINGS = 3
MUTE_SECONDS = 300

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE,
)


async def is_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return False

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id,
        )

        return member.status in (
            "administrator",
            "creator",
        )

    except Exception as exc:

        print(
            "Admin check error:",
            repr(exc),
        )

        return False


async def moderate_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return False

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return False

    if user.is_bot:
        return False

    if await is_admin(
        update,
        context,
    ):
        return False

    text = update.message.text or ""

    key = (
        chat.id,
        user.id,
    )

    now = time.monotonic()

    q = spam_tracker[key]

    while q and now - q[0] > SPAM_WINDOW_SECONDS:
        q.popleft()

    q.append(now)

    flood_detected = (
        len(q) > SPAM_MESSAGE_LIMIT
    )

    link_detected = bool(
        LINK_PATTERN.search(text)
    )

    if not flood_detected and not link_detected:
        return False

    try:

        await update.message.delete()

    except Exception as exc:

        print(
            "Message delete error:",
            repr(exc),
        )

    warnings[key] += 1

    current_warning = warnings[key]

    if current_warning < MAX_WARNINGS:

        try:

            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    f"⚠️ {user.first_name or 'User'}, "
                    f"spam/link detected.\n\n"
                    f"Warning "
                    f"{current_warning}/{MAX_WARNINGS}."
                ),
            )

        except Exception as exc:

            print(
                "Warning message error:",
                repr(exc),
            )

        return True

    try:

        permissions = ChatPermissions(
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
        )

        until_date = int(
            time.time() + MUTE_SECONDS
        )

        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until_date,
        )

        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"🔇 {user.first_name or 'User'} "
                f"ko 5 minutes ke liye mute kiya gaya.\n\n"
                f"Reason: repeated spam/link activity."
            ),
        )

    except Exception as exc:

        print(
            "Mute error:",
            repr(exc),
        )

    warnings[key] = 0
    spam_tracker[key].clear()

    return True


# ==========================================================
# STEP 6 — AI TOOL STATE
# ==========================================================

pending_ai_tools = {}


# ==========================================================
# STEP 5 — MAIN MENU
# ==========================================================

WELCOME_IMAGE_URL = (
    "https://raw.githubusercontent.com/"
    "AashishTechs/Deep-Emotion/main/Welcome.jpg"
)


def _btn(text, *, callback_data=None, url=None, style="primary"):
    return InlineKeyboardButton(
        text,
        callback_data=callback_data,
        url=url,
        style=style,
    )


def main_menu_keyboard(bot_username="deep_emotions_01"):
    username = (bot_username or "deep_emotions_01").lstrip("@")
    return InlineKeyboardMarkup(
        [
            [_btn("💬 ᴄʜᴀᴛ ᴡɪᴛʜ ᴍᴇ", callback_data="chat", style="danger")],
            [
                _btn("📢 ᴜᴘᴅᴀᴛs", url="https://t.me/deep_emotions_01", style="success"),
                _btn("🆘 ꜱᴜᴘᴘᴏʀᴛ", url="https://t.me/deep_emotions_01", style="success"),
            ],
            [_btn("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url=f"https://t.me/{username}?startgroup=true", style="primary")],
            [_btn("❓ ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_main", style="danger")],
        ]
    )


def help_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                _btn("💬 ᴄʜᴀᴛ", callback_data="help_chat", style="danger"),
                _btn("🧠 ᴍᴇᴍᴏʀʏ", callback_data="help_memory", style="danger"),
                _btn("🛠️ ᴀɪ ᴛᴏᴏʟs", callback_data="help_ai_tools", style="danger"),
            ],
            [
                _btn("🎙️ ᴠᴏɪᴄᴇ", callback_data="help_voice", style="primary"),
                _btn("👥 ɢʀᴏᴜᴘ", callback_data="help_group", style="primary"),
                _btn("🔒 ᴘʀɪᴠᴀᴄʏ", callback_data="help_privacy", style="primary"),
            ],
            [
                _btn("🎮 ɢᴀᴍᴇs", callback_data="help_games", style="success"),
                _btn("📊 sᴛᴀᴛs", callback_data="help_stats", style="success"),
                _btn("📖 ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_commands", style="success"),
            ],
            [_btn("ʙᴀᴄᴋ", callback_data="back", style="danger")],
        ]
    )


HELP_SECTION_TEXT = {
    "help_chat": "💬 **Chat With Me**\n\nPrivate chat mein directly baat karo. 🌸\nGroup mein normal messages par bhi AI reply kar sakti hoon, aur @mention/reply par definitely respond karungi.\n\nUse: /ask your question",
    "help_memory": "🧠 **Memory**\n\nMain useful conversation memories save kar sakti hoon.\n\n/memory — saved memories\n/forget ID — ek memory delete\n/forget_all — all memories delete",
    "help_ai_tools": "🛠️ **AI Tools**\n\nRewrite • Summarize • Translate • Explain • Study Help.\n\nNeeche Open AI Tools dabao.",
    "help_voice": "🎙️ **Voice AI**\n\nVoice message bhejo aur main usse transcribe karke AI response dungi.",
    "help_group": "👥 **Group Chats**\n\nNormal group text par AI reply kar sakti hoon. Reply ya @mention bhi supported hai.\n\nAdmins moderation aur group controls use kar sakte hain.",
    "help_privacy": "🔒 **Privacy**\n\nUse /privacy to see memory and group-data information.\n\nPersonal memories ko group AI context mein automatically include nahi kiya jata.",
    "help_games": "🎮 **Games**\n\nSocial game mode available hai.\n\nUse /game to start or explore the available game.",
    "help_stats": "📊 **Stats**\n\nUse /stats to see your conversation statistics.",
    "help_commands": "📖 **Commands**\n\n/start — welcome panel\n/help — help center\n/ask — ask AI\n/game — social game\n/memory — memories\n/forget — delete one memory\n/forget_all — delete all memories\n/clear — clear chat history\n/stats — statistics\n/privacy — privacy",
}


def help_section_keyboard(section):
    rows = []
    if section == "help_ai_tools":
        rows.append([_btn("🛠️ ᴏᴘᴇɴ ᴀɪ ᴛᴏᴏʟs", callback_data="ai_tools", style="success")])
    rows.append([_btn("ʙᴀᴄᴋ", callback_data="help_main", style="danger")])
    return InlineKeyboardMarkup(rows)


def back_button():
    return InlineKeyboardMarkup([[_btn("ʙᴀᴄᴋ", callback_data="back", style="danger")]])


# ==========================================================
# STEP 6 — AI TOOLS MENU
# ==========================================================

def ai_tools_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                _btn("✍️ Rewrite", callback_data="tool_rewrite", style="danger"),
                _btn("📝 Summarize", callback_data="tool_summarize", style="danger"),
            ],
            [
                _btn("🌐 Translate", callback_data="tool_translate", style="primary"),
                _btn("💡 Explain", callback_data="tool_explain", style="primary"),
            ],
            [_btn("📚 Study Help", callback_data="tool_study", style="success")],
            [_btn("ʙᴀᴄᴋ", callback_data="help_main", style="danger")],
        ]
    )


# ==========================================================
# START
# ==========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = (
        "💗 **𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴs**\n\n"
        "Hey, I'm Deep Emotions 💗\n\n"
        "Not your average bot — I remember useful things, "
        "talk naturally, and stay with the conversation. 🌸\n\n"
        "💬 Tap Chat With Me to talk.\n"
        "❓ Tap Help & Commands to see everything.\n\n"
        "Updates: @deep_emotions_01"
    )

    await update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(
            getattr(context.bot, "username", None)
        ),
    )


# ==========================================================
# HELP
# ==========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    text = (
        "❓ **Deep Emotions — Help & Commands**\n\n"
        "Choose a category below. 👇\n\n"
        "🔴 AI & memory\n"
        "🔵 Voice, groups & privacy\n"
        "🟢 Games, stats & commands"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=help_menu_keyboard(),
    )

# ==========================================================
# STEP 8 — PRIVACY
# ==========================================================

async def privacy_command(
    update: Update,    context: ContextTypes.DEFAULT_TYPE,):

    if not update.message:
        return

    privacy_text = (
        "🔒 **𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴs — Privacy**\n\n"

        "🧠 **Memory**\n"
        "Main useful non-sensitive information ko "
        "future conversations ko better banane ke liye "
        "save kar sakti hoon.\n\n"

        "👤 **Personal Memory**\n"
        "Personal memories private conversations ke liye hain "
        "aur group conversation mein automatically share nahi hoti.\n\n"

        "👥 **Group Chat**\n"
        "Group mein AI recent group conversation ka context "
        "use kar sakti hai, lekin personal memory ko group "
        "AI prompt mein include nahi kiya jata.\n\n"

        "🧹 **Clear Chat**\n"
        "`/clear` se conversation history clear kar sakte ho.\n\n"

        "🗑️ **Delete Memory**\n"
        "`/forget ID` se specific memory delete kar sakte ho.\n\n"

        "🗑️ **Delete All Memories**\n"
        "`/forget_all` se saari saved memories delete kar sakte ho.\n\n"

        "📖 **View Memory**\n"
        "`/memory` se saved memories dekh sakte ho."
    )

    await update.message.reply_text(
        privacy_text,
        parse_mode="Markdown",
        reply_markup=back_button(),
    )


# ==========================================================
# GROUP GAMES
# ==========================================================

async def game_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    game = (context.args[0] if context.args else "joke").lower()

    if game not in {"truth", "dare", "wyr", "would", "would_you_rather", "joke"}:
        await update.message.reply_text(
            "🎮 Games: /game truth | /game dare | /game wyr | /game joke"
        )
        return

    await update.message.reply_text(social_game(game))


# ==========================================================
# ASK
# ==========================================================

async def ask(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = " ".join(
        context.args
    ).strip()

    if not text:

        await update.message.reply_text(
            "💬 Example:\n\n"
            "`/ask Python kya hai?`",
            parse_mode="Markdown",
        )

        return

    await process_ai(
        update,
        text,
        context,
    )


# ==========================================================
# CLEAR CHAT
# ==========================================================

async def clear_memory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await clear_history(
        update.effective_chat.id,
        update.effective_user.id,
    )

    await update.message.reply_text(
        "🧹 Tumhari conversation history clear kar di.\n\n"
        "🧠 Long-term memories safe hain."
    )


# ==========================================================
# MEMORY
# ==========================================================

async def memory_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id

    memories = await get_memories(
        user_id,
        limit=10,
    )

    if not memories:

        await update.message.reply_text(
            "🧠 Abhi meri memory mein tumhare baare mein "
            "kuch saved nahi hai.",
            reply_markup=back_button(),
        )

        return

    lines = [
        "🧠 **Tumhari Long-Term Memories**\n"
    ]

    for memory_id, memory in memories:

        lines.append(
            f"**{memory_id}.** {memory}"
        )

    lines.append(
        "\nDelete karne ke liye:"
        "\n`/forget ID`"
        "\n\nSab delete karne ke liye:"
        "\n`/forget_all`"
    )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=back_button(),
    )


# ==========================================================
# FORGET ONE
# ==========================================================

async def forget_memory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not context.args:

        await update.message.reply_text(
            "Example:\n"
            "`/forget 3`\n\n"
            "Pehle `/memory` se memory ID dekho.",
            parse_mode="Markdown",
        )

        return

    try:

        memory_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Memory ID number mein do.\n\n"
            "Example: `/forget 3`",
            parse_mode="Markdown",
        )

        return

    deleted = await delete_memory(
        update.effective_user.id,
        memory_id,
    )

    if deleted:

        await update.message.reply_text(
            f"🗑️ Memory #{memory_id} delete kar di."
        )

    else:

        await update.message.reply_text(
            "❌ Ye memory ID tumhari memory mein nahi mili."
        )


# ==========================================================
# FORGET ALL
# ==========================================================

async def forget_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id

    total = await count_memories(
        user_id
    )

    if total == 0:

        await update.message.reply_text(
            "🧠 Tumhari memory already empty hai."
        )

        return

    await clear_memories(
        user_id
    )

    await update.message.reply_text(
        "🧹 Tumhari saari long-term memories delete kar di."
    )


# ==========================================================
# STATS
# ==========================================================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    total_messages = await count_messages(
        chat_id,
        user_id,
    )

    total_memories = await count_memories(
        user_id
    )

    group_messages = 0

    if update.effective_chat.type != "private":

        group_messages = await count_group_messages(
            chat_id
        )

    await update.message.reply_text(
        "📊 **Deep Emotions Stats**\n\n"
        f"💬 Saved messages: {total_messages}\n"
        f"🧠 Long-term memories: {total_memories}\n"
        f"👥 Group context messages: {group_messages}",
        parse_mode="Markdown",
    )


# ==========================================================
# SAVE GROUP CONTEXT
# ==========================================================

async def save_group_context(
    update: Update,
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type == "private":
        return

    text = update.message.text

    if not text:
        return

    display_name = (
        user.full_name
        or "Unknown"
    )

    username = (
        f"@{user.username}"
        if user.username
        else None
    )

    await add_group_message(
        chat_id=chat.id,
        user_id=user.id,
        username=username,
        display_name=display_name,
        content=text,
    )


# ==========================================================
# CHAT MESSAGE
# ==========================================================

async def chat_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if not text:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    # ------------------------------------------------------
    # Save group context
    # ------------------------------------------------------

    if chat.type != "private":

        await save_group_context(
            update
        )

    # ------------------------------------------------------
    # Bot information
    # ------------------------------------------------------

    me = await context.bot.get_me()

    mentioned = (
        f"@{me.username}".lower() in text.lower()
        if me.username
        else False
    )

    replied_to_bot = (
        update.message.reply_to_message is not None
        and update.message.reply_to_message.from_user is not None
        and update.message.reply_to_message.from_user.id == me.id
    )

    # ------------------------------------------------------
    # Smart group mode
    # ------------------------------------------------------
    if chat.type != "private":
        if not should_reply_group(
            chat.id,
            text,
            mentioned=mentioned,
            replied_to_bot=replied_to_bot,
        ):
            return

        mark_group_reply(chat.id)

    # ------------------------------------------------------
    # Remove bot mention
    # ------------------------------------------------------

    if mentioned and me.username:

        text = re.sub(
            rf"@{re.escape(me.username)}",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    # ------------------------------------------------------
    # STEP 6 — Selected AI tool
    # ------------------------------------------------------

    tool_key = (
        chat.id,
        user.id,
    )

    selected_tool = pending_ai_tools.pop(
        tool_key,
        None,
    )

    if selected_tool:

        await process_ai_tool(
            update,
            context,
            selected_tool,
            text,
        )

        return

    # ------------------------------------------------------
    # Normal AI
    # ------------------------------------------------------

    await process_ai(
        update,
        text or "Hi",
        context,
    )


# ==========================================================
# STEP 6 — AI TOOL PROCESSOR
# ==========================================================

async def process_ai_tool(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tool: str,
    text: str,
):

    if not update.message:
        return

    text = text.strip()

    if not text:

        await update.message.reply_text(
            "🛠️ Pehle text bhejo jise main process karun."
        )

        return

    try:

        await update.message.chat.send_action(
            ChatAction.TYPING
        )

        reply = await ai_tool(
            tool,
            text,        )
        await send_text_with_user_mentions(
            update,
            context,
            reply,
        )

    except Exception as exc:

        print(
            "AI tool error:",
            repr(exc),
        )

        await update.message.reply_text(
            "Sorry 💗 AI Tool use karte waqt "
            "problem aa gayi. Thodi der baad try karo."
        )


# ==========================================================
# PROCESS NORMAL AI
# ==========================================================

async def process_ai(
    update,
    text,
    context: ContextTypes.DEFAULT_TYPE = None,
):

    user = update.effective_user

    if not user or not update.message:
        return

    # ------------------------------------------------------
    # Rate limit
    # ------------------------------------------------------

    if (
        not allowed(user.id)
        and user.id != OWNER_ID
    ):

        await update.message.reply_text(
            "⏳ Thoda slow... "
            "bahut requests aa gayi 😅"
        )

        return

    chat = update.effective_chat

    chat_id = chat.id
    user_id = user.id

    is_group = (
        chat.type in (
            "group",
            "supergroup",
        )
    )

    # ------------------------------------------------------
    # History
    # ------------------------------------------------------

    history = await get_history(
        chat_id,
        user_id,
    )

    # ------------------------------------------------------
    # Personal memories
    # ------------------------------------------------------
    #
    # IMPORTANT:
    # Private → allowed
    # Group   → blocked
    #

    memories = []

    if not is_group:

        memories = await get_memories(
            user_id,
            limit=10,
        )

    # ------------------------------------------------------
    # Group context
    # ------------------------------------------------------

    group_context = []

    if is_group:

        group_context = await get_group_context(
            chat_id,
            limit=15,
        )

    try:

        await update.message.chat.send_action(
            ChatAction.TYPING
        )

        reply = await generate_reply(
            history=history,
            user_message=text,
            memories=memories,
            group_context=group_context,
            is_group=is_group,
        )

        # --------------------------------------------------
        # Save user message
        # --------------------------------------------------

        await add_message(
            chat_id,
            user_id,
            "user",
            text,
        )

        # --------------------------------------------------
        # Save AI response
        # --------------------------------------------------

        await add_message(
            chat_id,
            user_id,
            "model",
            reply,
        )

        # --------------------------------------------------
        # Extract personal memories
        # --------------------------------------------------
        #
        # IMPORTANT:
        # Do NOT create personal memories from group chat.
        #

        if not is_group:

            new_memories = await extract_memories(
                text
            )

            for memory in new_memories:

                saved = await add_memory(
                    user_id,
                    memory,
                )

                if saved:

                    print(
                        f"New memory saved for "
                        f"user {user_id}: {memory}"
                    )

        # --------------------------------------------------
        # Send reply
        # --------------------------------------------------

        if context is not None:
            await send_text_with_user_mentions(
                update,
                context,
                reply,
            )
        else:
            await update.message.reply_text(reply)

    except Exception as exc:

        print(
            "AI error:",
            repr(exc),
        )

        await update.message.reply_text(
            "Sorry 💗 abhi AI service se connection "
            "nahi ho pa raha. Thodi der baad try karo."
        )


# ==========================================================
# TELEGRAM USER MENTION
# ==========================================================

async def send_text_with_user_mentions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
):
    """
    Convert AI-generated tg://user HTML mentions into native
    Telegram text_mention entities. Never expose raw HTML to users.
    """
    pattern = re.compile(
        r'<a\s+href=["\']tg://user\?id=(\d+)["\']>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    bot = context.bot if hasattr(context, "bot") else context
    parts = []
    entities = []
    last_end = 0

    for match in pattern.finditer(text):
        parts.append(html.unescape(text[last_end:match.start()]))

        user_id = int(match.group(1))
        name = html.unescape(
            re.sub(r"<[^>]+>", "", match.group(2))
        ).strip()

        mentioned_user = None
        try:
            member = await bot.get_chat_member(
                update.effective_chat.id,
                user_id,
            )
            mentioned_user = member.user
        except Exception:
            pass

        # If Telegram cannot resolve the user, still show only the
        # visible name instead of leaking the tg:// HTML.
        if not mentioned_user:
            parts.append(name)
            last_end = match.end()
            continue

        clean_so_far = "".join(parts)
        offset = len(clean_so_far.encode("utf-16-le")) // 2
        parts.append(name)
        length = len(name.encode("utf-16-le")) // 2

        entities.append(
            MessageEntity(
                type=MessageEntity.TEXT_MENTION,
                offset=offset,
                length=length,
                user=mentioned_user,
            )
        )
        last_end = match.end()

    parts.append(html.unescape(text[last_end:]))

    clean_text = "".join(parts)
    if not clean_text:
        return

    await update.message.reply_text(
        clean_text,
        entities=entities or None,
    )
