"""UI translations; callback identifiers stay independent of display language."""
SUPPORTED_LANGUAGES = ('en', 'ru')
TEXTS = {
    'find': ('🍳 Find a recipe', '🍳 Найти рецепт'),
    'ingredients_search': ('🥕 Search by ingredients', '🥕 Поиск по ингредиентам'),
    'categories': ('📚 Categories', '📚 Категории'),
    'random': ('🎲 Random recipe', '🎲 Случайный рецепт'),
    'favorites': ('❤️ Favorites', '❤️ Избранное'),
    'help': ('ℹ️ Help', 'ℹ️ Помощь'),
    'language': ('🌐 Language', '🌐 Язык'),
    'menu': ('🏠 Main menu', '🏠 Главное меню'),
    'back': ('⬅️ Back', '⬅️ Назад'),
    'browse': ('📖 Browse all recipes', '📖 Все рецепты'),
    'search_name': ('🔎 Search by name', '🔎 Поиск по названию'),
    'add': ('❤️ Add to favorites', '❤️ В избранное'),
    'remove': ('💔 Remove from favorites', '💔 Удалить из избранного'),
    'another': ('🎲 Another recipe', '🎲 Другой рецепт'),
    'welcome': ('👋 Welcome to Recipe Helper!\n\nFind something delicious, search your ingredients, and save recipes you love.', '👋 Добро пожаловать!\n\nНаходите вкусные рецепты, ищите по ингредиентам и сохраняйте любимые блюда.'),
    'help_text': ('Use the buttons to browse recipes. Search by name or send ingredients separated by commas, for example: chicken, rice, tomato.\n\n/start — main menu\n/language — change language', 'Выбирайте рецепты с помощью кнопок. Ищите по названию или отправьте ингредиенты через запятую, например: курица, рис, помидор.\n\n/start — главное меню\n/language — сменить язык'),
    'unknown': ('Please choose an option from the menu below.', 'Выберите действие в меню ниже.'),
    'choose_language': ('Choose your language / Выберите язык:', 'Выберите язык / Choose your language:'),
    'language_saved': ('Language set to English.', 'Выбран русский язык.'),
    'no_matches': ('No matching recipes. Try another search or return to the menu.', 'Рецепты не найдены. Попробуйте другой запрос или вернитесь в меню.'),
    'results_limit': ('Showing the first 10. Refine your search for more specific results.', 'Показаны первые 10. Уточните запрос, чтобы сузить поиск.'),
    'results': ('Recipes found: {count}. Choose one:', 'Найдено рецептов: {count}. Выберите рецепт:'),
    'ask_name': ('Type a recipe name or part of a name:', 'Введите название рецепта или его часть:'),
    'ask_ingredients': ('Send ingredients separated by commas, for example: chicken, rice, tomato', 'Отправьте ингредиенты через запятую, например: курица, рис, помидор'),
    'empty_favorites': ('Your favorites list is empty yet. Add recipes you love!', 'В избранном пока пусто. Добавьте любимые рецепты!'),
    'your_favorites': ('Your favorite recipes:', 'Ваши любимые рецепты:'),
    'missing': ('That recipe could not be found.', 'Этот рецепт не найден.'),
    'choose_recipe': ('Choose a recipe:', 'Выберите рецепт:'),
    'choose_category': ('Choose a category:', 'Выберите категорию:'),
    'category_recipes': ('Recipes in <b>{category}</b>:', 'Рецепты в категории <b>{category}</b>:'),
    'empty': ('There are no recipes yet.', 'Рецептов пока нет.'),
    'time': ('Cooking time', 'Время приготовления'),
    'minutes': ('minutes', 'мин.'),
    'servings': ('Servings', 'Порции'),
    'difficulty': ('Difficulty', 'Сложность'),
    'ingredients': ('Ingredients', 'Ингредиенты'),
    'instructions': ('Instructions', 'Приготовление'),
}
CATEGORIES = dict(zip(
    ['Breakfast', 'Soups', 'Salads', 'Pasta', 'Main dishes', 'Desserts', 'Drinks', 'Meat', 'Chicken', 'Fish', 'Sides', 'Appetizers', 'Baking'],
    ['Завтраки', 'Супы', 'Салаты', 'Паста', 'Основные блюда', 'Десерты', 'Напитки', 'Мясо', 'Курица', 'Рыба', 'Гарниры', 'Закуски', 'Выпечка'],
))


def normalize_language(value: str | None) -> str:
    return 'ru' if (value or '').lower().split('-')[0] == 'ru' else 'en'


def tr(key: str, language: str = 'en', **values: object) -> str:
    return TEXTS[key][language == 'ru'].format(**values)


def labels(key: str) -> set[str]:
    return set(TEXTS[key])


def category_name(category: str, language: str = 'en') -> str:
    canonical = canonical_category(category)
    return CATEGORIES.get(canonical, canonical) if language == 'ru' else canonical


def difficulty_name(difficulty: str, language: str = 'en') -> str:
    translations = {'Easy': 'Легко', 'Medium': 'Средне', 'Hard': 'Сложно'}
    return translations.get(difficulty, difficulty) if language == 'ru' else difficulty


def canonical_category(category: str) -> str:
    return next((key for key, value in CATEGORIES.items() if value == category), category)
