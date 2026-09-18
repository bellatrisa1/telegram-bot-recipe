from collections.abc import AsyncIterator

import logging

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL
from database.models import Base, Recipe
from data.sample_recipes import SAMPLE_RECIPES


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
        columns = (await connection.execute(text("PRAGMA table_info(users)"))).all()
        if not any(column[1] == "language" for column in columns):
            await connection.execute(text(
                "ALTER TABLE users ADD COLUMN language VARCHAR(2) NOT NULL DEFAULT 'en'"
            ))

    async with SessionFactory() as session:
        # Serialize seed writers without imposing a new constraint on existing user data.
        await session.execute(text("BEGIN IMMEDIATE"))
        existing_names = {
            " ".join(name.split()).casefold()
            for name in await session.scalars(select(Recipe.name))
        }
        added = 0
        for recipe in SAMPLE_RECIPES:
            identity = " ".join(recipe["name"].split()).casefold()
            if identity not in existing_names:
                session.add(Recipe(**recipe))
                existing_names.add(identity)
                added += 1
        await session.commit()
        logging.getLogger(__name__).info("Missing sample recipes inserted: %s", added)

    logging.getLogger(__name__).info("Database initialized.")
