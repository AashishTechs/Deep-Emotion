import asyncio
import logging
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    filters,
)

from config import BOT_TOKEN, OWNER_ID

from bot.database import init_db, cleanup_old_data
from bot.proactive import proactive_group_loop

from bot.handlers import (
    start,
    help_command,
    ask,
    game_command,
    clear_memory,
    stats,
    groups_command,
    chat_message,
    memory_command,
    forget_memory,
    forget_all,
    welcome_new_member,
    goodbye_member,
    moderate_message,
    button_handler,
    voice_message,
    privacy_command,
)

from bot.truth_dare import (
    truth_command,
    dare_command,
    truth_dare_command,
    truth_dare_callback,
)

from bot.broadcast import (
    broadcast_command,
    track_group_message,
    track_bot_group_membership,
)


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ==========================================================
# PERIODIC DATABASE CLEANUP
# ==========================================================

async def periodic_db_cleanup():
    """
    Periodically remove expired conversation and memory data.
    Startup cleanup is handled by init_db(); this keeps cleanup
    running while the bot stays online.
    """

    while True:

        await asyncio.sleep(6 * 60 * 60)

        try:

            await cleanup_old_data()

            logger.info(
                "Periodic database cleanup completed."
            )

        except Exception:

            logger.exception(
                "Periodic database cleanup failed."
            )


# ==========================================================
# RENDER HEALTH SERVER
# ==========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )

        self.end_headers()

        self.wfile.write(
            b"Deep Emotions is alive!"
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    port = int(
        os.environ.get("PORT", 10000)
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler,
    )

    logger.info(
        f"Health server running on port {port}"
    )

    server.serve_forever()


# ==========================================================
# MAIN BOT
# ==========================================================

async def main():

    # ------------------------------------------------------
    # INITIALIZE DATABASE
    # ------------------------------------------------------

    await init_db()

    # ------------------------------------------------------
    # CREATE TELEGRAM APPLICATION
    # ------------------------------------------------------

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ======================================================
    # COMMAND HANDLERS
    # ======================================================

    # Owner-only broadcast; the command itself enforces owner + private chat.
    application.add_handler(
        CommandHandler("broadcast", broadcast_command)
    )

    # Track groups as soon as the bot is added/removed. The low-priority
    # message tracker also discovers existing groups when updates are visible.
    application.add_handler(
        ChatMemberHandler(
            track_bot_group_membership,
            ChatMemberHandler.MY_CHAT_MEMBER,
        ),
        group=-1,
    )

    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS,
            track_group_message,
        ),
        group=-1,
    )


    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "ask",
            ask,
        )
    )

    application.add_handler(
        CommandHandler(
            "game",
            game_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "truth",
            truth_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "dare",
            dare_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "td",
            truth_dare_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "memory",
            memory_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "forget",
            forget_memory,
        )
    )

    application.add_handler(
        CommandHandler(
            "forget_all",
            forget_all,
        )
    )

    application.add_handler(
        CommandHandler(
            "clear",
            clear_memory,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats,
        )
    )

    # Restricted to the owner and @Aashish_0fficial inside private chat.
    application.add_handler(
        CommandHandler(
            "groups",
            groups_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "privacy",
            privacy_command,
        )
    )

    # ======================================================
    # TRUTH OR DARE BUTTONS
    # ======================================================

    application.add_handler(
        CallbackQueryHandler(
            truth_dare_callback,
            pattern=r"^td:",
        )
    )

    # ======================================================
    # INLINE BUTTONS
    # ======================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # ======================================================
    # WELCOME NEW MEMBERS
    # ======================================================

    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_member
        )
    )

    # ======================================================
    # GOODBYE MEMBERS
    # ======================================================

    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.LEFT_CHAT_MEMBER,
            goodbye_member
        )
    )

    # ======================================================
    # STEP 7 — VOICE AI
    # ======================================================
    #
    # Voice message
    #       ↓
    # voice_message()
    #       ↓
    # Gemini transcription
    #       ↓
    # AI response
    #

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            voice_message
        ),
        group=0,
    )

    # ======================================================
    # STEP 4 — ANTI SPAM
    # ======================================================
    #
    # Handles:
    # - Flood spam
    # - Links
    # - Warnings
    # - Temporary mute
    #

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            moderate_message
        ),
        group=1,
    )

    # ======================================================
    # AI CHAT
    # ======================================================
    #
    # Normal text
    #       ↓
    # chat_message()
    #       ↓
    # Memory / Group Context
    #       ↓
    # Gemini
    #       ↓
    # Response
    #

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat_message
        ),
        group=2,
    )

    # ======================================================
    # START BOT
    # ======================================================

    logger.info(
        "Deep Emotions is running..."
    )

    await application.initialize()

    # Register public commands so Telegram displays them in the chat Menu.
    # Keep owner-only /broadcast out of the public command list.
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Start Deep Emotion"),
            BotCommand("help", "Show available commands"),
            BotCommand("ask", "Ask the AI a question"),
            BotCommand("game", "Play a chat game"),
            BotCommand("truth", "Get a truth question"),
            BotCommand("dare", "Get a dare challenge"),
            BotCommand("td", "Start Truth or Dare"),
            BotCommand("memory", "View your saved memory"),
            BotCommand("forget", "Forget a saved memory"),
            BotCommand("forget_all", "Delete all your saved memories"),
            BotCommand("clear", "Clear the current conversation"),
            BotCommand("stats", "View bot statistics"),
            BotCommand("privacy", "Learn about privacy and data"),
        ]
    )

    # Show the private broadcast command only in the owner's bot chat.
    if OWNER_ID:
        await application.bot.set_my_commands(
            [
            BotCommand("start", "Start Deep Emotion"),
            BotCommand("help", "Show available commands"),
            BotCommand("ask", "Ask the AI a question"),
            BotCommand("game", "Play a chat game"),
            BotCommand("truth", "Get a truth question"),
            BotCommand("dare", "Get a dare challenge"),
            BotCommand("td", "Start Truth or Dare"),
            BotCommand("memory", "View your saved memory"),
            BotCommand("forget", "Forget a saved memory"),
            BotCommand("forget_all", "Delete all your saved memories"),
            BotCommand("clear", "Clear the current conversation"),
            BotCommand("stats", "View bot statistics"),
            BotCommand("privacy", "Learn about privacy and data"),
            BotCommand("broadcast", "Broadcast to registered groups"),
            BotCommand("groups", "List registered groups"),
        ],
            scope=BotCommandScopeChat(chat_id=OWNER_ID),
        )

    await application.start()

    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES
    )

    # Start slow, rate-limited proactive group engagement.
    asyncio.create_task(proactive_group_loop(application.bot))
    asyncio.create_task(periodic_db_cleanup())

    # ======================================================
    # KEEP BOT RUNNING
    # ======================================================

    while True:

        await asyncio.sleep(
            3600
        )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    health_thread = Thread(
        target=start_health_server,
        daemon=True,
    )

    health_thread.start()

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Deep Emotions stopped."
        )

    except Exception:

        logger.exception(
            "Bot crashed."
        )

        raise
