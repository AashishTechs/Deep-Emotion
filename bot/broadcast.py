"""Owner-only, private-chat broadcast tools for Deep Emotion."""

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import ContextTypes

from config import OWNER_ID
from bot.database import (
    get_broadcast_groups,
    register_broadcast_group,
    unregister_broadcast_group,
)

logger = logging.getLogger(__name__)

# Small delay between recipients; RetryAfter is handled separately.
BROADCAST_DELAY_SECONDS = 0.12


async def broadcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Broadcast text or a replied-to Telegram message to registered groups."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    # Check both conditions before doing anything: no group usage and no
    # access for admins/owners of other groups.
    if chat.type != ChatType.PRIVATE:
        await message.reply_text(
            "🔒 /broadcast sirf bot ke private chat mein use ho sakta hai."
        )
        return

    if not OWNER_ID or user.id != OWNER_ID:
        await message.reply_text("⛔ Ye command sirf bot owner use kar sakta hai.")
        return

    source_message = message.reply_to_message
    text = " ".join(context.args).strip()

    if source_message is None and not text:
        await message.reply_text(
            "📣 Broadcast kaise bhejein:\n\n"
            "• Text: /broadcast Your message here\n"
            "• Photo/video/formatting: pehle message, photo ya video bhejein; "
            "phir us par reply karke /broadcast bhejein.\n\n"
            "🔗 Links aur emojis bhi supported hain."
        )
        return

    group_ids = await get_broadcast_groups()
    if not group_ids:
        await message.reply_text(
            "⚠️ Abhi koi group registered nahi hai. Bot ko group mein add karein; "
            "woh group registry mein automatically aa jayega."
        )
        return

    status = await message.reply_text(
        f"📣 Broadcast shuru ho raha hai…\n👥 Registered groups: {len(group_ids)}"
    )

    sent = 0
    failed = 0

    for chat_id in group_ids:
        try:
            if source_message is not None:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=chat.id,
                    message_id=source_message.message_id,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=False,
                )
            sent += 1

        except RetryAfter as exc:
            # Respect Telegram's flood control and retry once.
            await asyncio.sleep(float(exc.retry_after) + 1)
            try:
                if source_message is not None:
                    await context.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=chat.id,
                        message_id=source_message.message_id,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        disable_web_page_preview=False,
                    )
                sent += 1
            except (Forbidden, BadRequest, TelegramError) as retry_exc:
                failed += 1
                logger.warning(
                    "Broadcast retry failed for group %s: %s",
                    chat_id,
                    retry_exc,
                )
                if isinstance(retry_exc, Forbidden):
                    await unregister_broadcast_group(chat_id)

        except Forbidden as exc:
            failed += 1
            logger.info("Removing unreachable broadcast group %s: %s", chat_id, exc)
            await unregister_broadcast_group(chat_id)

        except (BadRequest, TelegramError) as exc:
            failed += 1
            logger.warning("Broadcast failed for group %s: %s", chat_id, exc)

        await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    try:
        await status.edit_text(
            "✅ Broadcast complete!\n\n"
            f"👥 Groups checked: {len(group_ids)}\n"
            f"📨 Sent: {sent}\n"
            f"⚠️ Failed: {failed}"
        )
    except TelegramError:
        logger.exception("Could not update broadcast summary message")


async def track_group_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Register groups whenever Telegram delivers a group message update."""
    chat = update.effective_chat
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await register_broadcast_group(chat.id)


async def track_bot_group_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Register the group when the bot is added; unregister when removed."""
    member_update = update.my_chat_member
    if not member_update:
        return

    chat = member_update.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    new_status = member_update.new_chat_member.status
    if new_status in ("member", "administrator"):
        await register_broadcast_group(chat.id)
    elif new_status in ("left", "kicked"):
        await unregister_broadcast_group(chat.id)
