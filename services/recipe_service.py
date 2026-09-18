from __future__ import annotations

import re

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert

from database.models import Favorite, Recipe, User
from data.recipe_translations import INGREDIENT_ALIASES, recipe_text
from services.localization import normalize_language, canonical_category, CATEGORIES


def normalize_ingredient(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold().replace("ё", "е"))


def recipe_ingredients(recipe: Recipe) -> list[str]:
    return [normalize_ingredient(item) for item in recipe.ingredients.splitlines() if item.strip()]


def matches_ingredients(recipe: Recipe, requested: list[str]) -> bool:
    available = recipe_ingredients(recipe) + [
        normalize_ingredient(item) for item in recipe_text(recipe, "ingredients", "ru").splitlines()
    ]
    normalized_requested = [
        INGREDIENT_ALIASES.get(normalize_ingredient(item), normalize_ingredient(item))
        for item in requested if item.strip()
    ]
    return bool(normalized_requested) and all(
        any(ingredient in available_item or available_item in ingredient for available_item in available)
        for ingredient in normalized_requested
    )


async def get_or_create_user(session: AsyncSession, telegram_id: int, language: str = "en") -> User:
    existing = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if existing is not None:
        return existing
    await session.execute(
        insert(User).values(telegram_id=telegram_id, language=normalize_language(language)).on_conflict_do_nothing(
            index_elements=[User.telegram_id]
        )
    )
    await session.commit()
    return (await session.scalars(select(User).where(User.telegram_id == telegram_id))).one()


async def get_all_recipes(session: AsyncSession) -> list[Recipe]:
    result = await session.scalars(select(Recipe).order_by(Recipe.name))
    return list(result)


async def get_categories(session: AsyncSession) -> list[str]:
    result = await session.scalars(select(Recipe.category).distinct().order_by(Recipe.category))
    return sorted({canonical_category(category) for category in result})


async def get_recipes_by_category(session: AsyncSession, category: str) -> list[Recipe]:
    canonical = canonical_category(category)
    result = await session.scalars(
        select(Recipe).where(Recipe.category.in_({canonical, CATEGORIES.get(canonical, canonical)})).order_by(Recipe.name)
    )
    return list(result)


async def get_recipe(session: AsyncSession, recipe_id: int) -> Recipe | None:
    return await session.get(Recipe, recipe_id)


async def get_random_recipe(session: AsyncSession) -> Recipe | None:
    return await session.scalar(select(Recipe).order_by(func.random()).limit(1))


async def search_by_name(session: AsyncSession, query: str) -> list[Recipe]:
    normalized = normalize_ingredient(query).casefold()
    if not normalized:
        return []
    return [recipe for recipe in await get_all_recipes(session)
            if any(normalized in normalize_ingredient(recipe_text(recipe, "name", language))
                   for language in ("en", "ru"))]


async def search_by_ingredients(session: AsyncSession, ingredients: list[str]) -> list[Recipe]:
    recipes = await get_all_recipes(session)
    return sorted(
        [recipe for recipe in recipes if matches_ingredients(recipe, ingredients)],
        key=lambda recipe: (len(recipe_ingredients(recipe)), recipe.name),
    )


async def is_favorite(session: AsyncSession, telegram_id: int, recipe_id: int) -> bool:
    result = await session.scalar(
        select(Favorite.id)
        .join(User)
        .where(User.telegram_id == telegram_id, Favorite.recipe_id == recipe_id)
    )
    return result is not None


async def add_favorite(session: AsyncSession, telegram_id: int, recipe_id: int) -> None:
    user = await get_or_create_user(session, telegram_id)
    await session.execute(
        insert(Favorite).values(user_id=user.id, recipe_id=recipe_id)
        .on_conflict_do_nothing(index_elements=[Favorite.user_id, Favorite.recipe_id])
    )
    await session.commit()


async def get_favorite_recipes(session: AsyncSession, telegram_id: int) -> list[Recipe]:
    result = await session.scalars(
        select(Recipe)
        .join(Favorite)
        .join(User)
        .where(User.telegram_id == telegram_id)
        .order_by(Recipe.name)
    )
    return list(result)


async def clear_favorite(session: AsyncSession, telegram_id: int, recipe_id: int) -> None:
    await session.execute(
        delete(Favorite).where(
            Favorite.recipe_id == recipe_id,
            Favorite.user_id == select(User.id).where(User.telegram_id == telegram_id).scalar_subquery(),
        )
    )
    await session.commit()


async def set_user_language(session: AsyncSession, telegram_id: int, language: str) -> None:
    if language not in {"en", "ru"}:
        raise ValueError("Unsupported language")
    user = await get_or_create_user(session, telegram_id, language)
    user.language = language
    await session.commit()
