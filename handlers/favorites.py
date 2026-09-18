from services.localization import tr, labels
from data.recipe_translations import recipe_text
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.database import SessionFactory
from handlers.recipes import send_recipe
from keyboards.keyboards import main_menu_keyboard, recipe_list_keyboard
from services.recipe_service import add_favorite, clear_favorite, get_recipe, get_favorite_recipes

router = Router()


@router.message(F.text.in_(labels("favorites")))
async def show_favorites(message: Message, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipes = await get_favorite_recipes(session, message.from_user.id)
    if not recipes:
        await message.answer(tr("empty_favorites", language), reply_markup=main_menu_keyboard(language))
        return
    await message.answer(
        tr("your_favorites", language),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes], language),
    )


@router.callback_query(F.data.startswith("favorite:"))
async def change_recipe_favorite(callback: CallbackQuery, language: str = "en") -> None:
    parts = callback.data.split(":")
    if len(parts) != 3 or parts[1] not in {"add", "remove"} or not parts[2].isdecimal():
        return  # Old cards can be reopened from the menu.
    recipe_id = int(parts[2])
    async with SessionFactory() as session:
        if await get_recipe(session, recipe_id) is None:
            return
        if parts[1] == "add":
            await add_favorite(session, callback.from_user.id, recipe_id)
        else:
            await clear_favorite(session, callback.from_user.id, recipe_id)
    await send_recipe(callback, recipe_id, language)
