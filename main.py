import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN
from bot.handlers import start, help_command, ask, clear_memory, stats, chat_message
from bot.database import init_db

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

async def post_init(application):
    await init_db()

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("clear", clear_memory))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
    print("Deep Emotions is running...")
    app.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
