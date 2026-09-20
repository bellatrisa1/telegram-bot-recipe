"""Small deterministic Russian/English ranking; no network or Telegram dependencies."""
import re
import unicodedata

from data.recipe_search import RECIPE_ALIASES
from data.recipe_translations import recipe_text
from database.models import Recipe

STOP_WORDS = {'с', 'со', 's', 'и', 'из', 'на', 'в', 'по', 'для', 'под', 'the', 'with', 'and'}
COMMON_WORDS = {'соль', 'вода', 'масло', 'мука', 'сахар', 'перец', 'черный', 'растительное',
                'salt', 'water', 'oil', 'flour', 'sugar', 'pepper'}
# Explicit families avoid destructive general stemming (e.g. сырники are not сыр).
WORD_FAMILIES = (
    (('куриц', 'курин'), 'курица'), (('картош', 'картоф'), 'картофель'),
    (('гриб', 'шампиньон'), 'гриб'), (('творог', 'творож'), 'творог'),
    (('яйц', 'яич'), 'яйцо'), (('лосос',), 'лосось'), (('тунец', 'тунц'), 'тунец'),
    (('помидор', 'томат'), 'помидор'), (('говяд',), 'говядина'),
    (('свинин', 'свиной', 'свиного'), 'свинина'), (('мяс',), 'мясо'),
    (('котлет',), 'котлета'), (('сырник',), 'сырник'),
    (('макарон', 'спагетти', 'паста', 'пасту', 'пастой', 'пасты'), 'паста'),
    (('фарш',), 'фарш'), (('сыром', 'сыра', 'сыру'), 'сыр'),
    (('капуст',), 'капуста'), (('свекл',), 'свекла'), (('огур',), 'огурец'),
    (('сливк',), 'сливки'), (('сметан',), 'сметана'), (('молок',), 'молоко'),
)


def normalize(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().replace('ё', 'е').split())


def tokens(value: str) -> set[str]:
    result = set()
    for word in re.findall(r'[a-zа-я]+', normalize(value)):
        if word in STOP_WORDS:
            continue
        canonical = next((key for prefixes, key in WORD_FAMILIES if word.startswith(prefixes)), word)
        result.add(canonical)
    return result


def ingredient_tokens(recipe: Recipe) -> set[str]:
    # Quantities and preparation instructions must not create ingredient matches.
    lines = []
    for language in ('en', 'ru'):
        lines.extend(line.split(' — ', 1)[0] for line in recipe_text(recipe, 'ingredients', language).splitlines())
    return tokens(' '.join(lines))


def ingredient_match(recipe: Recipe, requested: list[str]) -> bool:
    wanted = tokens(' '.join(requested))
    return bool(wanted - COMMON_WORDS) and wanted <= ingredient_tokens(recipe)


def rank(recipe: Recipe, query: str) -> tuple[int, float] | None:
    query = normalize(query)
    wanted = tokens(query)
    if not wanted or not query or not (wanted - COMMON_WORDS):
        return None
    names = [normalize(recipe_text(recipe, 'name', lang)) for lang in ('en', 'ru')]
    if query in names:
        return (0, 0)
    if any(query in name or wanted <= tokens(name) for name in names):
        return (1, min(len(name) for name in names))
    aliases = RECIPE_ALIASES.get(recipe.name, ())
    if any(query == normalize(alias) or wanted <= tokens(alias) for alias in aliases):
        return (2, 0)
    distinct = wanted - COMMON_WORDS
    available = ingredient_tokens(recipe)
    if distinct and wanted <= available:
        return (3, len(available - COMMON_WORDS) / len(distinct))
    context = tokens(recipe_text(recipe, 'description', 'ru') + ' ' + recipe.category)
    if distinct and wanted <= context:
        return (4, 0)
    return None
