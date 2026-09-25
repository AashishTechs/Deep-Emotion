import time
from collections import defaultdict, deque
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import OWNER_ID
from bot.ai import generate_reply
from bot.database import add_message, get_history, clear_history, count_messages

user_requests = defaultdict(deque)
WINDOW_SECONDS = 20
MAX_REQUESTS = 5

def allowed(user_id):
    now = time.monotonic()
    q = user_requests[user_id]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_REQUESTS:
        return False
    q.append(now)
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💗 𝐃ᴇᴇᴘ 𝐄ᴍᴏᴛɪᴏɴs online!\n\n"
        "Mujhse normal chat karo, ya /ask use karo. 😊\n"
        "Type /help for commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Deep Emotions Commands\n\n"
        "/start — bot start\n"
        "/help — commands\n"
        "/ask your question — AI se pucho\n"
        "/clear — conversation memory clear\n"
        "/stats — saved messages\n\n"
        "Group me mujhe @mention karo ya mere message ko reply karo."
    )

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Example: /ask Python kya hai?")
        return
    await process_ai(update, text)

async def clear_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await clear_history(update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text("🧹 Tumhari conversation memory clear kar di.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = await count_messages(update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text(f"📊 Tumhari saved messages: {total}")

async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    me = await context.bot.get_me()

    mentioned = f"@{me.username}".lower() in text.lower() if me.username else False
    replied_to_bot = (
        update.message.reply_to_message is not None
        and update.message.reply_to_message.from_user is not None
        and update.message.reply_to_message.from_user.id == me.id
    )

    if update.effective_chat.type != "private" and not (mentioned or replied_to_bot):
        return

    if mentioned and me.username:
        text = text.replace(f"@{me.username}", "").strip()

    await process_ai(update, text or "Hi")

async def process_ai(update, text):
    user = update.effective_user
    if not user or not update.message:
        return

    if not allowed(user.id) and user.id != OWNER_ID:
        await update.message.reply_text("⏳ Thoda slow... bahut requests aa gayi 😅")
        return

    chat_id = update.effective_chat.id
    user_id = user.id
    history = await get_history(chat_id, user_id)

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        reply = await generate_reply(history, text)
        await add_message(chat_id, user_id, "user", text)
        await add_message(chat_id, user_id, "model", reply)
        await update.message.reply_text(reply)
    except Exception as exc:
        print("AI error:", repr(exc))
        await update.message.reply_text(
            "Sorry 💗 abhi AI service se connection nahi ho pa raha. Thodi der baad try karo."
        )
