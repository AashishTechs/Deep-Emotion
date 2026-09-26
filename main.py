import asyncio
import logging
import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN

from bot.database import init_db

from bot.handlers import (
    start,
    help_command,
    ask,
    clear_memory,
    stats,
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


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


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

    application.add_handler(
        CommandHandler(
            "privacy",
            privacy_command,
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
            welcome_new_member,
        )
    )

    # ======================================================
    # GOODBYE MEMBERS
    # ======================================================

    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.LEFT_CHAT_MEMBER,
            goodbye_member,
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
            voice_message,
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
            moderate_message,
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
            chat_message,
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

    await application.start()

    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES
    )

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