from html import escape

from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import ChatMemberUpdated

from app.config import settings

router = Router()


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added_to_group(event: ChatMemberUpdated, bot: Bot) -> None:
    chat = event.chat
    group_name = escape(chat.title or str(chat.id))
    chat_id = chat.id

    await bot.send_message(
        settings.TELEGRAM_ADMIN_CHAT_ID,
        f"New group added!\n"
        f"Group name: <b>{group_name}</b>\n"
        f"Chat ID: <code>{chat_id}</code>"
    )
