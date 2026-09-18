"""Russian content for the bundled recipes, keyed by their stable English names.

Unknown recipes retain their original content. IDs and favorites are never duplicated.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models import Recipe

INGREDIENT_ALIASES = {"курица": "куриная грудка", "грибы": "шампиньоны"}

RUSSIAN_RECIPES = {
    'Spaghetti Carbonara': {
        'name': 'Спагетти карбонара',
        'description': 'Итальянская паста с нежным соусом из яиц, сыра и панчетты.',
        'ingredients': 'спагетти\nяйца\nпармезан\nпанчетта\nчёрный перец',
        'instructions': 'Отварите пасту.\nСмешайте яйца и сыр.\nОбжарьте панчетту.\nСоедините все ингредиенты.\nДобавьте чёрный перец и подавайте.',
    },
    'Chicken Rice Bowl': {
        'name': 'Боул с курицей и рисом',
        'description': 'Сытный боул с нежной курицей, рисом и свежими овощами.',
        'ingredients': 'куриная грудка\nрис\nпомидор\nогурец\nоливковое масло\nсоль',
        'instructions': 'Отварите рис.\nПриправьте и обжарьте курицу.\nНарежьте овощи.\nВыложите всё в глубокую миску.',
    },
    'Tomato Soup': {
        'name': 'Томатный суп',
        'description': 'Согревающий нежный суп из спелых помидоров с зеленью.',
        'ingredients': 'помидоры\nлук\nчеснок\nовощной бульон\nбазилик\nоливковое масло',
        'instructions': 'Обжарьте лук и чеснок.\nДобавьте помидоры и бульон.\nВарите на слабом огне 20 минут.\nИзмельчите блендером и добавьте базилик.',
    },
    'Greek Salad': {
        'name': 'Греческий салат',
        'description': 'Свежий салат с огурцами, помидорами, оливками и фетой.',
        'ingredients': 'огурец\nпомидоры\nфета\nоливки\nкрасный лук\nоливковое масло',
        'instructions': 'Нарежьте овощи.\nДобавьте фету и оливки.\nЗаправьте оливковым маслом.\nАккуратно перемешайте и подавайте.',
    },
    'Berry Pancakes': {
        'name': 'Панкейки с ягодами',
        'description': 'Пышные панкейки со свежими ягодами на завтрак.',
        'ingredients': 'мука\nяйца\nмолоко\nразрыхлитель\nягоды\nкленовый сироп',
        'instructions': 'Смешайте сухие ингредиенты.\nДобавьте яйца и молоко, взбейте.\nИспеките панкейки на разогретой сковороде.\nПодавайте с ягодами и сиропом.',
    },
    'Chocolate Mousse': {
        'name': 'Шоколадный мусс',
        'description': 'Воздушный десерт с насыщенным шоколадным вкусом.',
        'ingredients': 'тёмный шоколад\nяйца\nжирные сливки\nсахар',
        'instructions': 'Растопите шоколад.\nВзбейте сливки.\nВзбейте яйца с сахаром.\nАккуратно соедините всё и охладите.',
    },
    'Strawberry Lemonade': {
        'name': 'Клубничный лимонад',
        'description': 'Яркий освежающий напиток из клубники и лимона.',
        'ingredients': 'клубника\nлимоны\nвода\nсахар\nлёд',
        'instructions': 'Измельчите клубнику блендером.\nВыжмите сок из лимонов.\nСмешайте с водой и сахаром.\nПодавайте со льдом.',
    },
}


def recipe_text(recipe: "Recipe", field: str, language: str = 'en') -> str:
    if language == 'ru':
        return RUSSIAN_RECIPES.get(recipe.name, {}).get(field, getattr(recipe, field))
    return getattr(recipe, field)
