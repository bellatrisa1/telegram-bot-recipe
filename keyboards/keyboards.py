from services.localization import tr, category_name

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


MENU_KEYS = [["find", "ingredients_search"], ["categories", "random"],
             ["favorites", "help"], ["language"]]
MAIN_MENU_BUTTONS = [[tr(key) for key in row] for row in MENU_KEYS]


def main_menu_keyboard(language: str = "en") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tr(key, language)) for key in row] for row in MENU_KEYS],
        resize_keyboard=True,
    )


def back_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=tr("menu", language), callback_data="menu")]]
    )


def category_keyboard(categories: list[str], language: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=category_name(category, language), callback_data=f"category:{category}")]
        for category in categories
    ]
    buttons.append([InlineKeyboardButton(text=tr("menu", language), callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def recipe_list_keyboard(recipe_items: list[tuple[int, str]], language: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"recipe:{recipe_id}")]
        for recipe_id, name in recipe_items
    ]
    buttons.append([InlineKeyboardButton(text=tr("menu", language), callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def find_recipe_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("search_name", language), callback_data="search_name")],
            [InlineKeyboardButton(text=tr("menu", language), callback_data="menu")],
        ]
    )


def recipe_actions_keyboard(recipe_id: int, is_favorite: bool, language: str = "en") -> InlineKeyboardMarkup:
    favorite_text = tr("remove" if is_favorite else "add", language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=favorite_text, callback_data=f"favorite:{'remove' if is_favorite else 'add'}:{recipe_id}")],
            [InlineKeyboardButton(text=tr("another", language), callback_data="random")],
            [InlineKeyboardButton(text=tr("back", language), callback_data="categories")],
            [InlineKeyboardButton(text=tr("menu", language), callback_data="menu")],
        ]
    )


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="English", callback_data="language:en"),
        InlineKeyboardButton(text="Русский", callback_data="language:ru"),
    ]])


def retry_recipe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Попробовать снова", callback_data="search_name")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")],
    ])
