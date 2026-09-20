from collections.abc import AsyncIterator

import logging

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL
from database.models import Base, Recipe
from data.sample_recipes import SAMPLE_RECIPES
from data.recipe_search import SEED_EQUIVALENTS
from data.recipe_repairs import GREEK_SALAD_ORIGINAL, GREEK_SALAD_COMPLETE
from services.recipe_search import normalize


engine = create_async_engine(DATABASE_URL, echo=False)
@event.listens_for(engine.sync_engine, "connect")
def enable_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        recipe_columns = (await connection.execute(text("PRAGMA table_info(recipes)"))).all()
        if not any(column[1] == "source" for column in recipe_columns):
            await connection.execute(text(
                "ALTER TABLE recipes ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'bundled'"
            ))
        columns = (await connection.execute(text("PRAGMA table_info(users)"))).all()
        if not any(column[1] == "language" for column in columns):
            await connection.execute(text(
                "ALTER TABLE users ADD COLUMN language VARCHAR(2) NOT NULL DEFAULT 'en'"
            ))

    async with SessionFactory() as session:
        # Serialize seed writers without imposing a new constraint on existing user data.
        await session.execute(text("BEGIN IMMEDIATE"))
        existing_names = {
            normalize(name)
            for name in await session.scalars(select(Recipe.name))
        }
        added = 0
        for recipe in SAMPLE_RECIPES:
            identity = normalize(recipe["name"])
            identities = {identity, *(normalize(alias) for alias in SEED_EQUIVALENTS.get(recipe["name"], ()))}
            if not identities & existing_names:
                session.add(Recipe(**recipe))
                existing_names.add(identity)
                added += 1
        legacy_salads = await session.scalars(select(Recipe).where(Recipe.name == "Greek Salad"))
        for salad in legacy_salads:
            if all(getattr(salad, key) == value for key, value in GREEK_SALAD_ORIGINAL.items()):
                for key, value in GREEK_SALAD_COMPLETE.items():
                    setattr(salad, key, value)
        await session.commit()
        logging.getLogger(__name__).info("Missing sample recipes inserted: %s", added)

    logging.getLogger(__name__).info("Database initialized.")
