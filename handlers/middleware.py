from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from keyboards.keyboards import MENU_KEYS
from services.localization import labels, normalize_language
from services.recipe_service import get_or_create_user
from database import database as db

MENU_TEXTS = {text for row in MENU_KEYS for key in row for text in labels(key)}


class NavigationMiddleware(BaseMiddleware):
    """Clear old search state before navigation and acknowledge every callback."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        if isinstance(event, CallbackQuery):
            await event.answer()
            if not isinstance(event.message, Message):
                return None
            if state:
                await state.clear()
        elif isinstance(event, Message) and event.text in MENU_TEXTS:
            if state:
                await state.clear()
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            async with db.SessionFactory() as session:
                user = await get_or_create_user(
                    session, event.from_user.id, normalize_language(event.from_user.language_code)
                )
                data["language"] = user.language
        try:
            return await handler(event, data)
        except TelegramBadRequest as error:
            if isinstance(event, CallbackQuery) and "message is not modified" in error.message:
                return None
            raise
