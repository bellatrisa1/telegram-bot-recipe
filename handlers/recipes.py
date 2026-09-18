from services.localization import tr, labels, category_name, difficulty_name
from data.recipe_translations import recipe_text
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from database.models import Recipe
from aiogram.types import CallbackQuery, Message

from database.database import SessionFactory
from keyboards.keyboards import (
    category_keyboard,
    recipe_actions_keyboard,
    recipe_list_keyboard,
)
from services.recipe_service import (
    get_all_recipes,
    get_categories,
    get_random_recipe,
    get_recipe,
    get_recipes_by_category,
    is_favorite,
)

router = Router()


def format_recipe(recipe: Recipe, language: str = "en") -> str:
    ingredients = "\n".join(f"• {escape(item)}" for item in recipe_text(recipe, "ingredients", language).splitlines())
    instructions = "\n".join(
        f"{index}. {escape(instruction)}" for index, instruction in enumerate(recipe_text(recipe, "instructions", language).splitlines(), start=1)
    )
    return (
        f"🍽 <b>{escape(recipe_text(recipe, "name", language))}</b>\n\n"
        f"{escape(recipe_text(recipe, "description", language))}\n\n"
        f"⏱ {tr("time", language)}: {recipe.cooking_time} {tr("minutes", language)}\n"
        f"👤 {tr("servings", language)}: {recipe.servings}\n"
        f"⭐ {tr("difficulty", language)}: {escape(difficulty_name(recipe.difficulty, language))}\n\n"
        f"🥕 <b>{tr("ingredients", language)}:</b>\n{ingredients}\n\n"
        f"👩‍🍳 <b>{tr("instructions", language)}:</b>\n\n{instructions}"
    )


async def send_recipe(target: Message | CallbackQuery, recipe_id: int, language: str = "en") -> None:
    telegram_id = target.from_user.id
    async with SessionFactory() as session:
        recipe = await get_recipe(session, recipe_id)
        if recipe is None:
            text = tr("missing", language)
            keyboard = None
        else:
            favorite = await is_favorite(session, telegram_id, recipe_id)
            text = format_recipe(recipe, language)
            keyboard = recipe_actions_keyboard(recipe.id, favorite, language)

    if isinstance(target, CallbackQuery):
        if isinstance(target.message, Message):
            try:
                await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except TelegramBadRequest as error:
                if "message is not modified" not in error.message:
                    raise
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "browse_recipes")
async def browse_recipes(callback: CallbackQuery, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipes = await get_all_recipes(session)
    await callback.message.edit_text(
        tr("choose_recipe", language),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes], language),
    )


@router.message(F.text.in_(labels("categories")))
async def show_categories(message: Message, language: str = "en") -> None:
    async with SessionFactory() as session:
        categories = await get_categories(session)
    await message.answer(tr("choose_category", language), reply_markup=category_keyboard(categories, language))


@router.callback_query(F.data == "categories")
async def categories_callback(callback: CallbackQuery, language: str = "en") -> None:
    async with SessionFactory() as session:
        categories = await get_categories(session)
    await callback.message.edit_text(tr("choose_category", language), reply_markup=category_keyboard(categories, language))


@router.callback_query(F.data.startswith("category:"))
async def category_recipes(callback: CallbackQuery, language: str = "en") -> None:
    category = callback.data.split(":", 1)[1]
    async with SessionFactory() as session:
        recipes = await get_recipes_by_category(session, category)
    await callback.message.edit_text(
        tr("category_recipes", language, category=escape(category_name(category, language))),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes], language),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("recipe:"))
async def recipe_callback(callback: CallbackQuery, language: str = "en") -> None:
    value = callback.data.split(":", 1)[1]
    if value.isdecimal():
        await send_recipe(callback, int(value), language)


@router.message(F.text.in_(labels("random")))
async def random_recipe(message: Message, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipe = await get_random_recipe(session)
    if recipe:
        await send_recipe(message, recipe.id, language)
    else:
        await message.answer(tr("empty", language))


@router.callback_query(F.data == "random")
async def random_callback(callback: CallbackQuery, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipe = await get_random_recipe(session)
    if recipe:
        await send_recipe(callback, recipe.id, language)
    else:
        await callback.answer(tr("empty", language), show_alert=True)


@router.callback_query(F.data == "back_recipes")
async def back_to_recipes(callback: CallbackQuery, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipes = await get_all_recipes(session)
    await callback.message.edit_text(
        tr("choose_recipe", language),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes], language),
    )
