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
    ContextTypes,
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
# RENDER HEALTH CHECK SERVER
# ==========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
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
# BOT MAIN
# ==========================================================

async def main():

    # Initialize database
    await init_db()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("ask", ask)
    )

    application.add_handler(
        CommandHandler("clear", clear_memory)
    )

    application.add_handler(
        CommandHandler("stats", stats)
    )

    # Normal text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat_message,
        )
    )

    logger.info(
        "Deep Emotions is running..."
    )

    # Start Telegram application
    await application.initialize()
    await application.start()

    # Start polling
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES
    )

    # Keep bot alive
    while True:
        await asyncio.sleep(3600)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    # Start Render health server
    health_thread = Thread(
        target=start_health_server,
        daemon=True,
    )

    health_thread.start()

    # Start Telegram bot
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info(
            "Deep Emotions stopped."
        )

    except Exception:
        logger.exception(
            "Bot crashed."
        )
        raise