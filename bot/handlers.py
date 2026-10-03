# ==========================================================
# DEEP EMOTIONS — TELEGRAM HANDLERS
# Step 1–8
# ==========================================================

import html
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
    "AashishTechs/Deep-Emotion/main/Welcome.jpg?v=2"
)



def _btn(text, *, callback_data=None, url=None, style="primary"):
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
        style=style,
    )


def main_menu_keyboard(bot_username="deepemotions01"):
    username = (bot_username or "deepemotions01").lstrip("@")
    return InlineKeyboardMarkup(
        [
            [_btn("💬 ᴄʜᴀᴛ ᴡɪᴛʜ ᴍᴇ", callback_data="chat", style="danger")],
            [_btn("💗 ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_main", style="danger")],
            [
                _btn("🔔 ᴜᴘᴅᴀᴛs", url="https://t.me/deep_emotions_01", style="success"),
                _btn("🛠️ ꜱᴜᴘᴘᴏʀᴛ", url="https://t.me/+cGoEVo7d8YtjOTI9", style="success"),
            ],
            [_btn("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url=f"https://t.me/{username}?startgroup=true", style="primary")],
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
                _btn("📊 ꜱᴛᴀᴛs", callback_data="help_stats", style="success"),
                _btn("📖 ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_commands", style="success"),
            ],
            [_btn("🔙 ʙᴀᴄᴋ", callback_data="home", style="danger")],
        ]
    )


HELP_SECTION_TEXT = {
    "help_chat": (
        "💬 **Chat With Me**\n\n"
        "Private chat mein directly baat karo. 🌸\n\n"
        "Group mein normal text par bhi AI reply karegi, "
        "aur @mention/reply par bhi response degi."
    ),
    "help_memory": (
        "🧠 **Memory**\n\n"
        "Useful long-term memories private chat mein save ho sakti hain.\n\n"
        "/memory — saved memories\n"
        "/forget ID — ek memory delete\n"
        "/forget_all — all memories delete\n"
        "/clear — chat history clear"
    ),
    "help_ai_tools": (
        "🛠️ **AI Tools**\n\n"
        "Rewrite • Summarize • Translate • Explain • Study Help.\n\n"
        "AI Tools open karke koi tool choose karo."
    ),
    "help_voice": (
        "🎙️ **Voice AI**\n\n"
        "Voice message bhejo aur main usse transcribe karke AI response dungi.\n\n"
        "Group voice ke liye bot ko reply ya @mention karo."
    ),
    "help_group": (
        "👥 **Group Chats**\n\n"
        "Normal group text par AI reply karegi.\n"
        "Reply/@mention bhi supported hai.\n\n"
        "Admins moderation aur group controls use kar sakte hain."
    ),
    "help_privacy": (
        "🔒 **Privacy**\n\n"
        "/privacy se memory aur group-data information dekho.\n\n"
        "Personal memories group AI context mein automatically include nahi hoti."
    ),
    "help_games": (
        "🎮 **Games**\n\n"
        "/game truth\n"
        "/game dare\n"
        "/game wyr\n"
        "/game joke\n\n"
        "Group mein social games play kar sakte ho."
    ),
    "help_stats": (
        "📊 **Stats**\n\n"
        "/stats se saved messages, memories aur group context stats dekho."
    ),
    "help_commands": (
        "📖 **Commands**\n\n"
        "/start — welcome panel\n"
        "/help — help center\n"
        "/ask — ask AI\n"
        "/game — social game\n"
        "/memory — saved memories\n"
        "/forget — delete one memory\n"
        "/forget_all — delete all memories\n"
        "/clear — clear chat history\n"
        "/stats — statistics\n"
        "/privacy — privacy"
    ),
}


def help_section_keyboard(section):
    rows = []
    if section == "help_ai_tools":
        rows.append([_btn("🛠️ ᴏᴘᴇɴ ᴀɪ ᴛᴏᴏʟs", callback_data="ai_tools", style="success")])
    rows.append([_btn("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ", callback_data="help_main", style="primary")])
    return InlineKeyboardMarkup(rows)


# ==========================================================
# BACK BUTTON
# ==========================================================

def back_button():
    return InlineKeyboardMarkup(
        [
            [
                _btn(
                    "🔙 ʙᴀᴄᴋ",
                    callback_data="home",
                    style="danger",
                )
            ]
        ]
    )


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
            [_btn("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ", callback_data="help_main", style="primary")],
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

    bot_username = getattr(context.bot, "username", None) or "deepemotions01"

    text = (
        "✨ **Hey, I'm Deep Emotions 💗**\n\n"
        "Not your average bot — I remember useful things, "
        "talk naturally, and stay with the conversation. 🌸\n\n"
        "🧠 I remember useful details from our private chats.\n"
        "💬 I talk naturally and can help with everyday questions.\n"
        "🔔 I can also reply in groups and react to conversations.\n\n"
        "🎮 Games • 🛠️ AI Tools • 🎙️ Voice AI • 📊 Stats\n\n"
        "Tap **Chat With Me** to start, or add me to your group 👇\n\n"
        "Updates: @deep_emotions_01"
    )

    await update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(bot_username),
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
        "💗 **Deep Emotions — Help & Commands**\n\n"
        "Choose a category below. 👇\n\n"
        "🔴 Chat, Memory & AI Tools\n"
        "🔵 Voice, Groups & Privacy\n"
        "🟢 Games, Stats & Commands"
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
    Telegram text_mention entities. No HTML is shown to users.
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
        user_id = int(match.group(1))
        name = re.sub(r"<[^>]+>", "", match.group(2)).strip()

        try:
            member = await bot.get_chat_member(
                update.effective_chat.id,
                user_id,
            )
            mentioned_user = member.user
        except Exception:
            mentioned_user = None

        if not mentioned_user:
            continue

        parts.append(text[last_end:match.start()])
        clean_text_so_far = "".join(parts)
        mention_offset = len(clean_text_so_far.encode("utf-16-le")) // 2
        parts.append(name)
        mention_length = len(name.encode("utf-16-le")) // 2

        entities.append(
            MessageEntity(
                type=MessageEntity.TEXT_MENTION,
                offset=mention_offset,
                length=mention_length,
                user=mentioned_user,
            )
        )

        last_end = match.end()

    parts.append(text[last_end:])
    clean_text = "".join(parts)

    if not entities:
        clean_text = re.sub(
            r'<a\s+href=["\']tg://user\?id=\d+["\']>(.*?)</a>',
            lambda m: re.sub(r"<[^>]+>", "", m.group(1)),
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        await update.message.reply_text(clean_text)
        return

    await update.message.reply_text(
        clean_text,
        entities=entities,
    )


# ==========================================================
# WELCOME
# ==========================================================

async def welcome_new_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    chat = update.effective_chat

    new_members = (
        update.message.new_chat_members
        or []
    )

    for member in new_members:

        if member.id == context.bot.id:
            continue

        name = (
            member.first_name
            or member.username
            or "Friend"
        )

        welcome_text = (
            f"👋 Welcome {name}!\n\n"
            f"💜 Welcome to {chat.title or 'our group'}!\n"
            f"✨ Glad to have you here.\n\n"
            f"💬 Feel free to chat with everyone "
            f"and enjoy your time here! 🌸"
        )

        name_offset = len("👋 Welcome ".encode("utf-16-le")) // 2
        name_length = len(name.encode("utf-16-le")) // 2

        await update.message.reply_text(
            welcome_text,
            entities=[
                MessageEntity(
                    type=MessageEntity.TEXT_MENTION,
                    offset=name_offset,
                    length=name_length,
                    user=member,
                )
            ],
        )


# ==========================================================
# GOODBYE
# ==========================================================

async def goodbye_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    chat = update.effective_chat

    member = (
        update.message.left_chat_member
    )

    if not member:
        return

    if member.id == context.bot.id:
        return

    name = (
        member.first_name
        or member.username
        or "Friend"
    )

    goodbye_text = (
        f"👋 {name} has left the group.\n\n"
        f"💔 We'll miss you!\n"
        f"Take care and have a great day. 🌸"
    )

    name_offset = len("👋 ".encode("utf-16-le")) // 2
    name_length = len(name.encode("utf-16-le")) // 2

    await update.message.reply_text(
        goodbye_text,
        entities=[
            MessageEntity(
                type=MessageEntity.TEXT_MENTION,
                offset=name_offset,
                length=name_length,
                user=member,
            )
        ],
    )


# ==========================================================
# BUTTON HANDLER
# ==========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    data = query.data

    async def edit_panel(text, markup):
        if query.message.photo:
            await query.edit_message_caption(
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup,
            )
        else:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=markup,
            )

    async def show_home():
        pending_ai_tools.pop(
            (query.message.chat.id, query.from_user.id),
            None,
        )

        text = (
            "✨ **Hey, I'm Deep Emotions 💗**\n\n"
            "Not your average bot — I remember useful things, "
            "talk naturally, and stay with the conversation. 🌸\n\n"
            "🧠 Memory • 💬 Chat • 🎮 Games • 🛠️ AI Tools • 🎙️ Voice AI\n\n"
            "Tap an option below to continue.\n\n"
            "Updates: @deepemotions01"
        )

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=WELCOME_IMAGE_URL,
            caption=text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(
                getattr(context.bot, "username", None)
            ),
        )

    if data in {"home", "back"}:
        await show_home()
        return

    if data == "help_main":
        await edit_panel(
            "💗 **Deep Emotions — Help & Commands**\n\n"
            "Choose a category below. 👇\n\n"
            "🔴 Chat, Memory & AI Tools\n"
            "🔵 Voice, Groups & Privacy\n"
            "🟢 Games, Stats & Commands",
            help_menu_keyboard(),
        )
        return

    if data in HELP_SECTION_TEXT:
        await edit_panel(
            HELP_SECTION_TEXT[data],
            help_section_keyboard(data),
        )
        return

    if data == "chat":
        await edit_panel(
            "💬 **Chat With Me**\n\n"
            "Bas apna message bhejo. 😊\n\n"
            "Private chat mein directly baat karo.\n"
            "Group mein normal text par bhi main reply karungi.",
            InlineKeyboardMarkup(
                [[_btn("🔙 ʙᴀᴄᴋ", callback_data="home", style="primary")]]
            ),
        )
        return

    if data == "ai_tools":
        await edit_panel(
            "🛠️ **AI Tools**\n\n"
            "Neeche se tool choose karo. Tool select karne ke baad apna text bhejo.",
            ai_tools_keyboard(),
        )
        return

    tool_map = {
        "tool_rewrite": (
            "rewrite",
            "✍️ **Rewrite**\n\n"
            "Apna text bhejo. Main usse clearer aur natural bana dungi.",
        ),
        "tool_summarize": (
            "summarize",
            "📝 **Summarize**\n\n"
            "Apna long text bhejo. Main important points ka summary bana dungi.",
        ),
        "tool_translate": (
            "translate",
            "🌐 **Translate**\n\n"
            "Text bhejo. Target language bhi likh sakte ho.",
        ),
        "tool_explain": (
            "explain",
            "💡 **Explain**\n\n"
            "Koi topic ya concept bhejo. Main simple language mein explain karungi.",
        ),
        "tool_study": (
            "study",
            "📚 **Study Help**\n\n"
            "Apna study question bhejo. Main student-friendly explanation dungi.",
        ),
    }

    if data in tool_map:
        tool_name, text = tool_map[data]
        pending_ai_tools[
            (query.message.chat.id, query.from_user.id)
        ] = tool_name

        await edit_panel(
            text + "\n\n🔙 Cancel karne ke liye Back dabao.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ᴀɪ ᴛᴏᴏʟs",
                        callback_data="ai_tools",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "memory":
        memories = await get_memories(
            query.from_user.id,
            limit=10,
        )

        if memories:
            lines = ["🧠 **Tumhari Long-Term Memories**\n"]
            for memory_id, memory in memories:
                lines.append(f"**{memory_id}.** {memory}")
            text = "\n".join(lines)
        else:
            text = (
                "🧠 **Memory**\n\n"
                "Abhi meri memory mein tumhare baare mein kuch saved nahi hai."
            )

        await edit_panel(
            text,
            InlineKeyboardMarkup(
                [
                    [
                        _btn(
                            "🗑️ ғᴏʀɢᴇᴛ ᴀʟʟ",
                            callback_data="forget_all_confirm",
                            style="danger",
                        )
                    ],
                    [
                        _btn(
                            "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                            callback_data="help_main",
                            style="primary",
                        )
                    ],
                ]
            ),
        )
        return

    if data == "forget_all_confirm":
        await clear_memories(query.from_user.id)

        await edit_panel(
            "🧹 **Memory cleared**\n\n"
            "Tumhari saari long-term memories delete kar di gayi.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "ask":
        await edit_panel(
            "💬 **Ask AI**\n\n"
            "Bas apna question message mein bhejo. 😊\n\n"
            "Example: Python kya hai?",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "clear":
        await clear_history(
            query.message.chat.id,
            query.from_user.id,
        )

        await edit_panel(
            "🧹 **Chat history cleared**\n\n"
            "Long-term memories safe hain.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "privacy":
        await edit_panel(
            "🔒 **Privacy**\n\n"
            "Personal memories private chats ke liye hain.\n"
            "Group AI context mein personal memories automatically include nahi hoti.\n\n"
            "Use /privacy for full details.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "voice":
        await edit_panel(
            "🎙️ **Voice AI**\n\n"
            "Voice message bhejo aur main usse transcribe karke AI response dungi.\n\n"
            "Group voice mein mujhe reply ya @mention karo.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "group":
        await edit_panel(
            "👥 **Group Chats**\n\n"
            "Normal group text par AI reply karegi.\n"
            "Reply/@mention bhi supported hai.\n\n"
            "Admins ke liye anti-spam/link moderation active hai.",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "games":
        await edit_panel(
            "🎮 **Games**\n\n"
            "Available:\n"
            "/game truth\n"
            "/game dare\n"
            "/game wyr\n"
            "/game joke",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "stats":
        user_id = query.from_user.id
        chat_id = query.message.chat.id

        total_messages = await count_messages(
            chat_id,
            user_id,
        )
        total_memories = await count_memories(
            user_id,
        )

        group_messages = 0
        if query.message.chat.type != "private":
            group_messages = await count_group_messages(
                chat_id,
            )

        await edit_panel(
            "📊 **Deep Emotions Stats**\n\n"
            f"💬 Saved messages: {total_messages}\n"
            f"🧠 Long-term memories: {total_memories}\n"
            f"👥 Group context messages: {group_messages}",
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return

    if data == "commands":
        await edit_panel(
            HELP_SECTION_TEXT["help_commands"],
            InlineKeyboardMarkup(
                [[
                    _btn(
                        "🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴇʟᴘ",
                        callback_data="help_main",
                        style="primary",
                    )
                ]]
            ),
        )
        return


# ==========================================================
# VOICE AI
# ==========================================================

async def voice_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Handle Telegram voice messages.

    Private:
        Voice → transcription → personal AI context

    Group:
        Voice → transcription → group context only
    """

    if not update.message:
        return

    if not update.message.voice:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # ------------------------------------------------------
    # GROUP BOT MENTION / REPLY CHECK
    # ------------------------------------------------------

    if chat.type in (
        "group",
        "supergroup",
    ):

        message = update.message

        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id
            == context.bot.id
        )

        bot_username = context.bot.username

        caption_text = (
            message.caption or ""
        )

        is_mentioned = (
            bot_username
            and f"@{bot_username.lower()}"
            in caption_text.lower()
        )

        if not is_reply_to_bot and not is_mentioned:
            return

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    status_message = await update.message.reply_text(
        "🎙️ **Voice sun rahi hoon...**",
        parse_mode="Markdown",
    )

    # ------------------------------------------------------
    # TEMP DIRECTORY
    # ------------------------------------------------------

    temp_dir = (
        Path("data") / "voice_cache"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    voice_file_path = (
        temp_dir
        / f"{chat.id}_{update.message.message_id}.ogg"
    )

    try:

        # --------------------------------------------------
        # DOWNLOAD VOICE
        # --------------------------------------------------

        telegram_file = await context.bot.get_file(
            update.message.voice.file_id
        )

        await telegram_file.download_to_drive(
            custom_path=str(
                voice_file_path
            )
        )

        await status_message.edit_text(
            "🧠 **Voice samajh rahi hoon...**",
            parse_mode="Markdown",
        )

        # --------------------------------------------------
        # TRANSCRIPTION
        # --------------------------------------------------

        transcribed_text = await transcribe_voice(
            str(voice_file_path)
        )

        if not transcribed_text:

            await status_message.edit_text(
                "😕 Voice clearly samajh nahi aayi.\n\n"
                "Please ek baar phir voice bhejo."
            )

            return

        # --------------------------------------------------
        # CHAT TYPE
        # --------------------------------------------------

        is_group = (
            chat.type in (
                "group",
                "supergroup",
            )
        )

        # --------------------------------------------------
        # HISTORY
        # --------------------------------------------------

        history = await get_history(
            chat.id,
            user.id,
        )

        # --------------------------------------------------
        # PERSONAL MEMORY
        # ------------------------------------------------------

        memories = []

        if not is_group:

            memories = await get_memories(
                user.id,
                limit=10,
            )

        # --------------------------------------------------
        # GROUP CONTEXT
        # ------------------------------------------------------

        group_context = []

        if is_group:

            group_context = await get_group_context(
                chat.id,
                limit=15,
            )

        try:
            await update.message.chat.send_action(ChatAction.TYPING)

            reply = await generate_reply(
                history=history,
                user_message=transcribed_text,
                memories=memories,
                group_context=group_context,
                is_group=is_group,
            )

            await add_message(chat.id, user.id, "user", transcribed_text)
            await add_message(chat.id, user.id, "model", reply)

            if not is_group:
                new_memories = await extract_memories(transcribed_text)
                for memory in new_memories:
                    saved = await add_memory(user.id, memory)
                    if saved:
                        print(f"New memory saved for user {user.id}: {memory}")

            await status_message.edit_text(reply)

        except Exception as exc:
            print("Voice AI error:", repr(exc))
            await status_message.edit_text(
                "Sorry 💗 voice AI mein abhi problem aa gayi. Thodi der baad try karo."
            )

        finally:
            try:
                if voice_file_path.exists():
                    voice_file_path.unlink()
            except Exception as exc:
                print("Voice cache cleanup error:", repr(exc))


    except Exception as exc:
        print("Voice handler error:", repr(exc))
        try:
            await status_message.edit_text(
                "Sorry 💗 voice process mein problem aa gayi. Thodi der baad try karo."
            )
        except Exception:
            pass

    finally:
        try:
            if voice_file_path.exists():
                voice_file_path.unlink()
        except Exception as exc:
            print("Voice cache cleanup error:", repr(exc))