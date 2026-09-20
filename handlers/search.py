from services.localization import tr, labels
from data.recipe_translations import recipe_text
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.database import SessionFactory
from database.models import Recipe
from handlers.states import SearchStates
from keyboards.keyboards import recipe_list_keyboard, back_keyboard
from services.recipe_service import search_by_ingredients
from services.recipe_lookup import find_or_fetch_recipe
from handlers.recipes import send_recipe
from aiogram.utils.chat_action import ChatActionSender
from keyboards.keyboards import retry_recipe_keyboard

router = Router()
NAME_PROMPT = ('🔎 Какое блюдо хотите приготовить?\n\n'
               'Напишите название блюда — например:\n«Лазанья», «Сырники» или «Том Ям».')


async def send_search_results(message: Message, recipes: list[Recipe], language: str = "en") -> bool:
    if not recipes:
        await message.answer(tr("no_matches", language),
                             reply_markup=back_keyboard(language))
        return False
    await message.answer(
        tr("results", language, count=len(recipes)) + ("\n" + tr("results_limit", language) if len(recipes) > 10 else ""),
        reply_markup=recipe_list_keyboard([(recipe.id, recipe_text(recipe, "name", language)) for recipe in recipes[:10]], language),
    )
    return True


@router.message(F.text.in_(labels("find") | labels("search_name") | {"🔎 Search by recipe name"}))
async def ask_recipe_name(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_name)
    await message.answer(NAME_PROMPT, reply_markup=back_keyboard("ru"))


@router.message(F.text.in_(labels("ingredients_search")))
async def ask_ingredients(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_ingredients)
    await message.answer(tr("ask_ingredients", language))


@router.callback_query(F.data == "search_name")
async def ask_recipe_name_callback(callback: CallbackQuery, state: FSMContext, language: str = "en") -> None:
    await state.set_state(SearchStates.waiting_for_name)
    await callback.message.answer(NAME_PROMPT, reply_markup=back_keyboard("ru"))


@router.message(SearchStates.waiting_for_name, F.text)
async def search_name(message: Message, state: FSMContext, language: str = "en") -> None:
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        result = await find_or_fetch_recipe(message.text or "")
    if result.matches:
        await send_search_results(message, result.matches, "ru")
        await state.clear()
        return
    if result.recipe:
        await send_recipe(message, result.recipe.id, "ru")
        await state.clear()
        return
    if result.status == "invalid_query":
        text = "Напишите название блюда длиной от 2 до 200 символов."
    elif result.status == "unavailable":
        text = ("🤔 Этого блюда пока нет в сохранённых рецептах. Внешний поиск ещё не подключён."
                "\n\nПопробуйте другое название, например «Борщ» или «Блины на молоке».")
    elif result.status == "provider_error":
        text = "🤔 Сервис рецептов временно недоступен. Попробуйте ещё раз немного позже."
    else:
        text = f"🤔 Не удалось найти рецепт «{message.text}».\n\nПопробуйте уточнить название блюда или написать его немного иначе."
    await message.answer(text, reply_markup=retry_recipe_keyboard(), parse_mode=None)


@router.message(SearchStates.waiting_for_name)
async def invalid_dish_input(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте название блюда текстом.", reply_markup=retry_recipe_keyboard())


@router.message(SearchStates.waiting_for_ingredients, F.text)
async def search_ingredients(message: Message, state: FSMContext, language: str = "en") -> None:
    ingredients = (message.text or "").split(",")
    async with SessionFactory() as session:
        recipes = await search_by_ingredients(session, ingredients)
    if await send_search_results(message, recipes, language):
        await state.clear()
