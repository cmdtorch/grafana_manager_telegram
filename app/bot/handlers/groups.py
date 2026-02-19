from html import escape

from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import ChatMemberUpdated

from app.config import settings

router = Router()

# Only fire for group/supergroup joins, never for private chats.
router.my_chat_member.filter(
    ChatMemberUpdatedFilter(JOIN_TRANSITION)
)


@router.my_chat_member()
async def bot_added_to_group(event: ChatMemberUpdated, bot: Bot) -> None:
    # Ignore events that are not from a group/supergroup (e.g. channels).
    if event.chat.type not in ("group", "supergroup"):
        return

    chat = event.chat
    adder_id = event.from_user.id

    if adder_id not in settings.TELEGRAM_CREATOR_IDS:
        await bot.send_message(chat.id, "Access denied.")
        await bot.leave_chat(chat.id)
        return

    group_name = escape(chat.title or str(chat.id))
    await bot.send_message(
        settings.TELEGRAM_ADMIN_CHAT_ID,
        f"New group added!\n"
        f"Group name: <b>{group_name}</b>\n"
        f"Chat ID: <code>{chat.id}</code>\n\n"
        f"To create a project run:\n"
        f"/create_project &lt;project_name&gt; {chat.id}",
    )
