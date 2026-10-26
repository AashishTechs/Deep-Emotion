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
    ChatMemberHandler,
    ChatJoinRequestHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN

from bot.database import init_db, cleanup_old_data
from bot.proactive import proactive_group_loop
from bot.broadcast import (
    broadcast_command,
    groups_command,
    track_group_chat,
    configure_command_menu,
)
from bot.join_requests import (
    join_panel_command,
    join_panel_on_command,
    join_panel_off_command,
    handle_join_request,
    join_request_callback,
    configure_join_panel_command_menus,
)
from bot.moderation import (
    ban_command,
    unban_command,
    mute_command,
    unmute_command,
    cache_group_member,
    configure_moderation_command_menus,
)

from bot.sticker_filters import (
    filter_command,
    unfilter_command,
    handle_filtered_mentions,
)

from bot.command_help import command_help_callback
from bot.word_game import (
    init_word_game_db, wordgame_command, word_game_callback, word_guess_handler,
    new_word_command, new4_command, new5_command, new6_command,
    end_word_command, helpwords_command, daily_word_command, pause_daily_command, seekauth_command, score_command,
)

from bot.handlers import (
    start,
    help_command,
    ask,
    game_command,
    clear_memory,
    stats,
    chat_message,
    memory_command,
    forget_memory,
    forget_all,
    welcome_new_member,
    goodbye_member,
    goodbye_chat_member_update,
    moderate_message,
    button_handler,
    voice_message,
    privacy_command,
    id_command,
)

from bot.truth_dare import (
    truth_command,
    dare_command,
    truth_dare_command,
    truth_dare_callback,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def periodic_db_cleanup():
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            await cleanup_old_data()
            logger.info("Periodic database cleanup completed.")
        except Exception:
            logger.exception("Periodic database cleanup failed.")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Deep Emotions is alive!")

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server running on port {port}")
    server.serve_forever()

async def main():
    await init_db()
    await init_word_game_db()

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ask", ask))
    application.add_handler(CommandHandler("game", game_command))
    application.add_handler(CommandHandler("wordgame", wordgame_command))
    application.add_handler(CommandHandler("new", new_word_command))
    application.add_handler(CommandHandler("new4", new4_command))
    application.add_handler(CommandHandler("new5", new5_command))
    application.add_handler(CommandHandler("new6", new6_command))
    application.add_handler(CommandHandler("end", end_word_command))
    application.add_handler(CommandHandler("seekauth", seekauth_command))
    application.add_handler(CommandHandler("score", score_command))
    application.add_handler(CommandHandler("helpwords", helpwords_command))
    application.add_handler(CommandHandler("daily", daily_word_command))
    application.add_handler(CommandHandler("pausedaily", pause_daily_command))
    application.add_handler(CommandHandler("truth", truth_command))
    application.add_handler(CommandHandler("dare", dare_command))
    application.add_handler(CommandHandler("td", truth_dare_command))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("forget", forget_memory))
    application.add_handler(CommandHandler("forget_all", forget_all))
    application.add_handler(CommandHandler("clear", clear_memory))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("privacy", privacy_command))
    application.add_handler(CommandHandler("id", id_command))

    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("filter", filter_command))
    application.add_handler(CommandHandler("unfilter", unfilter_command))

    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("groups", groups_command))

    application.add_handler(CommandHandler("joinpanel", join_panel_command))
    application.add_handler(CommandHandler("joinpanel_on", join_panel_on_command))
    application.add_handler(CommandHandler("joinpanel_off", join_panel_off_command))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(
        CallbackQueryHandler(join_request_callback, pattern=r"^joinreq:"),
        group=-1,
    )

    application.add_handler(
        CallbackQueryHandler(
            command_help_callback,
            pattern=r"^help_commands$|^help_cmd_",
        ),
        group=-1,
    )

    # Cache group members as soon as they send messages. This lets moderation
    # commands resolve both @username and display name without an API search.
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS, cache_group_member),
        group=-3,
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_filtered_mentions,
        ),
        group=-1,
    )

    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS, track_group_chat),
        group=-2,
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, word_guess_handler),
        group=-4,
    )
    application.add_handler(CallbackQueryHandler(word_game_callback, pattern=r"^wg:"))
    application.add_handler(
        CallbackQueryHandler(truth_dare_callback, pattern=r"^td:")
    )
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member)
    )
    application.add_handler(
        ChatMemberHandler(
            goodbye_chat_member_update,
            ChatMemberHandler.CHAT_MEMBER,
        ),
        group=1,
    )

    application.add_handler(
        MessageHandler(filters.VOICE, voice_message),
        group=0,
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, moderate_message),
        group=1,
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message),
        group=2,
    )

    logger.info("Deep Emotions is running...")

    await application.initialize()
    await configure_command_menu(application.bot)
    await configure_join_panel_command_menus(application.bot)
    await configure_moderation_command_menus(application.bot)
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    asyncio.create_task(proactive_group_loop(application.bot))
    asyncio.create_task(periodic_db_cleanup())

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    health_thread = Thread(target=start_health_server, daemon=True)
    health_thread.start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Deep Emotions stopped.")
    except Exception:
        logger.exception("Bot crashed.")
        raise
