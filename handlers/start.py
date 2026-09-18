from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database.database import SessionFactory
from services.recipe_service import get_or_create_user, set_user_language
from services.localization import tr, labels
from keyboards.keyboards import main_menu_keyboard, language_keyboard

router = Router()
fallback_router = Router()


@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.clear()
    async with SessionFactory() as session:
        await get_or_create_user(session, message.from_user.id, language)
    await message.answer(tr("welcome", language), reply_markup=main_menu_keyboard(language))


@router.message(Command("language"))
@router.message(F.text.in_(labels("language")))
async def choose_language(message: Message, state: FSMContext, language: str = "en") -> None:
    await state.clear()
    await message.answer(tr("choose_language", language), reply_markup=language_keyboard())


@router.callback_query(F.data.in_({"language:en", "language:ru"}))
async def change_language(callback: CallbackQuery, state: FSMContext) -> None:
    language = callback.data.split(":")[1]
    async with SessionFactory() as session:
        await set_user_language(session, callback.from_user.id, language)
    await state.clear()
    await callback.message.answer(tr("language_saved", language), reply_markup=main_menu_keyboard(language))


@router.callback_query(F.data == "menu")
async def return_to_menu(callback: CallbackQuery, state: FSMContext, language: str = "en") -> None:
    await state.clear()
    await callback.message.answer(tr("menu", language), reply_markup=main_menu_keyboard(language))


@router.message(F.text.in_(labels("help")))
async def help_message(message: Message, language: str = "en") -> None:
    await message.answer(tr("help_text", language))


@fallback_router.message()
async def unknown_message(message: Message, language: str = "en") -> None:
    await message.answer(tr("unknown", language), reply_markup=main_menu_keyboard(language))
