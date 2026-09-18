from services.localization import tr, labels
from data.recipe_translations import recipe_text
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.database import SessionFactory
from database.models import Recipe
from handlers.states import SearchStates
from keyboards.keyboards import recipe_list_keyboard, back_keyboard, find_recipe_keyboard
from services.recipe_service import search_by_ingredients, search_by_name

router = Router()


async def send_search_results(message: Message, recipes: list[Recipe], language: str = "en") -> bool:
    if not recipes:
        await message.answer(tr("no_matches", language),
                             reply_markup=back_keyboard(language))
        return False
    await message.answer(
        tr("results", language, count=len(recipes)),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes], language),
    )
    return True


@router.message(F.text.in_(labels("find") | labels("search_name") | {"🔎 Search by recipe name"}))
async def ask_recipe_name(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_name)
    await message.answer(tr("ask_name", language), reply_markup=find_recipe_keyboard(language))


@router.message(F.text.in_(labels("ingredients_search")))
async def ask_ingredients(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_ingredients)
    await message.answer(tr("ask_ingredients", language))


@router.callback_query(F.data == "search_name")
async def ask_recipe_name_callback(callback: CallbackQuery, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_name)
    await callback.message.answer(tr("ask_name", language))


@router.message(SearchStates.waiting_for_name, F.text)
async def search_name(message: Message, state: FSMContext, language: str = "en") -> None:
    async with SessionFactory() as session:
        recipes = await search_by_name(session, message.text or "")
    if await send_search_results(message, recipes, language):
        await state.clear()


@router.message(SearchStates.waiting_for_ingredients, F.text)
async def search_ingredients(message: Message, state: FSMContext, language: str = "en") -> None:
    ingredients = (message.text or "").split(",")
    async with SessionFactory() as session:
        recipes = await search_by_ingredients(session, ingredients)
    if await send_search_results(message, recipes, language):
        await state.clear()
