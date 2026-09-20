"""Local-first lookup, validation and transactional caching."""
import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select, text

from database import database as db
from database.models import Recipe, RecipeLookup
from data.recipe_translations import recipe_text, LOCAL_NAME_ALIASES
from services.recipe_service import search_by_name
from services.external_recipe_provider import (
    RecipePayload, RecipeProvider, ProviderError, ProviderNotConfigured, configured_provider,
)

logger = logging.getLogger(__name__)


def normalize_query(query: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', query).casefold().replace('ё', 'е').split())


@dataclass
class LookupResult:
    recipe: Recipe | None = None
    status: str = 'not_found'
    matches: list[Recipe] = field(default_factory=list)


async def local_recipe(session, query: str, *, strong: bool = True) -> Recipe | None:
    cached = await session.scalar(select(Recipe).join(RecipeLookup).where(RecipeLookup.query == query))
    if cached:
        return cached
    recipes = list(await session.scalars(select(Recipe).order_by(Recipe.id)))
    for recipe in recipes:
        names = {normalize_query(recipe_text(recipe, 'name', lang)) for lang in ('en', 'ru')}
        if query in names:
            return recipe
        if strong and LOCAL_NAME_ALIASES.get(query) == recipe.name:
            return recipe
    return None


async def find_or_fetch_recipe(query: str, provider: RecipeProvider | None = None) -> LookupResult:
    query = normalize_query(query)
    if not 2 <= len(query) <= 200 or not any(char.isalpha() for char in query) or re.search(r'[<>\x00-\x1f]', query):
        return LookupResult(status='invalid_query')
    async with db.SessionFactory() as session:
        local = await local_recipe(session, query)
        if local:
            return LookupResult(local, 'local')
        matches = await search_by_name(session, query)
        if matches:
            return LookupResult(status='matches', matches=matches)
    try:
        provider = provider if provider is not None else configured_provider()
        async with asyncio.timeout(20):
            raw = await provider.fetch(query)
        if raw is None:
            return LookupResult()
        payload = RecipePayload.model_validate(raw.model_dump() if isinstance(raw, RecipePayload) else raw)
    except ProviderNotConfigured:
        logger.info('External recipe lookup is not configured.')
        return LookupResult(status='unavailable')
    except (ProviderError, TimeoutError, ValidationError, ValueError, TypeError):
        # Deliberately omit exception text: remote bodies can contain credentials.
        logger.warning('External recipe lookup failed or returned invalid data.')
        return LookupResult(status='provider_error')

    async with db.SessionFactory() as session:
        # No transaction is held during network calls. Serialize competing cache writes,
        # then recheck both the requested alias and the returned canonical name.
        await session.execute(text('BEGIN IMMEDIATE'))
        recipe = await local_recipe(session, query, strong=False)
        if recipe is None:
            recipe = await local_recipe(session, normalize_query(payload.name), strong=False)
        if recipe is None:
            recipe = Recipe(**payload.recipe_values())
            session.add(recipe)
            await session.flush()
        alias = await session.get(RecipeLookup, query)
        if alias is None:
            session.add(RecipeLookup(query=query, recipe_id=recipe.id))
        await session.commit()
        return LookupResult(recipe, 'cached')
