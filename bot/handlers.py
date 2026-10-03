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


def main_menu_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🧠 Memory",
                callback_data="memory",
            ),
            InlineKeyboardButton(
                "💬 Ask AI",
                callback_data="ask",
            ),
        ],

        [
            InlineKeyboardButton(
                "🛠️ AI Tools",
                callback_data="ai_tools",
            ),
        ],

        [
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help",
            ),
            InlineKeyboardButton(
                "🧹 Clear Chat",
                callback_data="clear",
            ),
        ],

    ]

    return InlineKeyboardMarkup(
        keyboard
    )


# ==========================================================
# BACK BUTTON
# ==========================================================

def back_button():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back",
                )
            ]
        ]
    )


# ==========================================================
# STEP 6 — AI TOOLS MENU
# ==========================================================

def ai_tools_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "✍️ Rewrite",
                callback_data="tool_rewrite",
            ),
            InlineKeyboardButton(
                "📝 Summarize",
                callback_data="tool_summarize",
            ),
        ],

        [
            InlineKeyboardButton(
                "🌐 Translate",
                callback_data="tool_translate",
            ),
            InlineKeyboardButton(
                "💡 Explain",
                callback_data="tool_explain",
            ),
        ],

        [
            InlineKeyboardButton(
                "📚 Study Help",
                callback_data="tool_study",
            ),
        ],

        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back",
            )
        ],

    ]

    return InlineKeyboardMarkup(
        keyboard
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
        "✨ Your personal AI assistant\n\n"
        "Mujhse normal chat karo, "
        "ya neeche se koi option choose karo. 🌸"
    )

    await update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
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
        "✨ **Deep Emotions — Help**\n\n"

        "💬 **AI Chat**\n"
        "Private chat mein directly message bhejo.\n"
        "Group mein normal chat par bhi smartly reply karungi, "
        "aur @mention/reply par definitely respond karungi.\n\n"

        "🎙️ **Voice AI**\n"
        "Voice message bhejo aur main usse samajhkar "
        "AI response dungi.\n\n"

        "🧠 **Memory**\n"
        "/memory — saved memories\n"
        "/forget ID — ek memory delete\n"
        "/forget_all — all memories delete\n\n"

        "🛠️ **AI Tools**\n"
        "Rewrite, Summarize, Translate, "
        "Explain aur Study Help.\n\n"

        "🔒 **Privacy**\n"
        "/privacy — privacy information\n\n"

        "🧹 **Chat**\n"
        "/clear — conversation history clear\n"
        "/stats — statistics\n\n"

        "🤖 **Ask AI**\n"
        "/ask your question\n\n"

        "Example:\n"
        "`/ask Python kya hai?`"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=back_button(),
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

    if not query:
        return

    await query.answer()

    data = query.data

    # ======================================================
    # BACK
    # ======================================================

    if data == "back":

        pending_ai_tools.pop(
            (
                query.message.chat.id,
                query.from_user.id,
            ),
            None,
        )

        text = (
            "💗 **𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴs**\n\n"
            "✨ Your personal AI assistant\n\n"
            "Neeche se koi option choose karo. 🌸"
        )

        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        await context.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=WELCOME_IMAGE_URL,
            caption=text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

        return

    # ======================================================
    # AI TOOLS
    # ======================================================

    if data == "ai_tools":

        text = (
            "🛠️ **AI Tools**\n\n"
            "Neeche se koi tool choose karo. ✨\n\n"
            "Tool select karne ke baad "
            "apna text bhejna."
        )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=ai_tools_keyboard(),
        )

        return

    # ======================================================
    # TOOL SELECTION
    # ======================================================

    tool_map = {

        "tool_rewrite": (
            "rewrite",
            "✍️ **Rewrite**",
            "Apna text bhejo. "
            "Main usse clearer aur natural bana dungi.",
        ),

        "tool_summarize": (
            "summarize",
            "📝 **Summarize**",
            "Apna long text bhejo. "
            "Main important points ka summary bana dungi.",
        ),

        "tool_translate": (
            "translate",
            "🌐 **Translate**",
            "Text bhejo. "
            "Target language bhi likh sakte ho.",
        ),

        "tool_explain": (
            "explain",
            "💡 **Explain**",
            "Koi topic ya concept bhejo. "
            "Main simple language mein explain karungi.",
        ),

        "tool_study": (
            "study",
            "📚 **Study Help**",
            "Apna study question bhejo. "
            "Main student-friendly explanation dungi.",
        ),
    }

    if data in tool_map:

        tool_name, title, instruction = (
            tool_map[data]
        )

        pending_ai_tools[
            (
                query.message.chat.id,                query.from_user.id,
            )
        ] = tool_name

        await query.edit_message_text(
            f"{title}\n\n"
            f"{instruction}\n\n"            "🔙 Cancel karne ke liye "
            "Back dabao.",
            parse_mode="Markdown",
            reply_markup=back_button(),
        )

        return

    # ======================================================
    # MEMORY
    # ======================================================

    if data == "memory":

        user_id = query.from_user.id

        memories = await get_memories(
            user_id,
            limit=10,
        )

        if not memories:

            text = (
                "🧠 **Memory**\n\n"
                "Abhi meri memory mein tumhare "
                "baare mein kuch saved nahi hai."
            )

        else:

            lines = [
                "🧠 **Tumhari Long-Term Memories**\n"
            ]

            for memory_id, memory in memories:

                lines.append(
                    f"**{memory_id}.** {memory}"
                )

            text = "\n".join(
                lines
            )

        keyboard = [

            [
                InlineKeyboardButton(
                    "🗑️ Forget All",
                    callback_data="forget_all_confirm",
                )
            ],

            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back",
                )
            ],

        ]

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return

    # ======================================================
    # ASK AI
    # ======================================================

    if data == "ask":

        text = (
            "💬 **Ask AI**\n\n"
            "Bas apna question message mein bhejo. 😊\n\n"
            "Example:\n"
            "`Python kya hai?`\n\n"
            "Group mein mujhe @mention karna."
        )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=back_button(),
        )

        return

    # ======================================================
    # HELP
    # ======================================================

    if data == "help":

        text = (
            "❓ **Deep Emotions Help**\n\n"

            "💬 Private chat → directly message karo.\n"
            "👥 Group → @mention ya reply.\n"
            "🎙️ Voice → voice message bhejo.\n"
            "🧠 Memory → saved information.\n"
            "🛠️ AI Tools → Rewrite, Summarize, "
            "Translate, Explain, Study Help.\n"
            "🧹 Clear Chat → conversation history.\n"
            "🔒 Privacy → `/privacy`\n\n"

            "Commands:\n"
            "/start\n"
            "/help\n"
            "/ask\n"
            "/memory\n"
            "/forget\n"
            "/forget_all\n"
            "/clear\n"
            "/stats\n"
            "/privacy"
        )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=back_button(),
        )

        return

    # ======================================================
    # CLEAR CONFIRMATION
    # ======================================================

    if data == "clear":

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ Yes, Clear",
                    callback_data="clear_confirm",
                ),

                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="back",
                ),
            ]

        ]

        await query.edit_message_text(
            "🧹 **Clear Conversation?**\n\n"
            "Tumhari current conversation history "
            "delete ho jayegi.\n\n"
            "🧠 Long-term memories delete nahi hongi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return

    # ======================================================
    # CLEAR CONFIRM
    # ======================================================

    if data == "clear_confirm":

        await clear_history(
            query.message.chat.id,
            query.from_user.id,
        )

        await query.edit_message_text(
            "🧹 **Conversation cleared!**\n\n"
            "🧠 Tumhari long-term memories safe hain.",
            parse_mode="Markdown",
            reply_markup=back_button(),
        )

        return

    # ======================================================
    # FORGET ALL CONFIRMATION
    # ======================================================

    if data == "forget_all_confirm":

        keyboard = [

            [
                InlineKeyboardButton(
                    "🗑️ Yes, Forget All",
                    callback_data="forget_all",
                ),

                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="memory",
                ),
            ]

        ]

        await query.edit_message_text(
            "⚠️ **Forget All Memories?**\n\n"
            "Isse tumhari saari long-term memories "
            "delete ho jayengi.\n\n"
            "Ye action undo nahi kiya ja sakta.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return

    # ======================================================
    # FORGET ALL
    # ======================================================

    if data == "forget_all":

        user_id = query.from_user.id

        await clear_memories(
            user_id
        )

        await query.edit_message_text(
            "🧹 **All memories deleted.**\n\n"
            "Ab main tumhare baare mein "
            "koi long-term memory nahi rakhungi.",
            parse_mode="Markdown",
            reply_markup=back_button(),
        )

        return


# ==========================================================
# STEP 7 — VOICE AI
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