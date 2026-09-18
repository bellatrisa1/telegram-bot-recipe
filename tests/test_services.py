import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data.sample_recipes import SAMPLE_RECIPES
from database import database as db
from database.models import Favorite, Recipe, User
from services import recipe_service as service


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{Path(self.temp.name) / 'test.db'}")
        from sqlalchemy import event
        event.listen(self.engine.sync_engine, 'connect', db.enable_foreign_keys)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.patches = [patch.object(db, 'engine', self.engine), patch.object(db, 'SessionFactory', self.sessions)]
        for item in self.patches:
            item.start()
        await db.init_db()

    async def asyncTearDown(self):
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()
        self.temp.cleanup()

    async def test_initialization_and_schema(self):
        await db.init_db()
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES))
            self.assertEqual(await session.scalar(text('PRAGMA foreign_keys')), 1)
            indexes = (await session.execute(text("PRAGMA index_list('recipes')"))).all()
            self.assertEqual(sum(row[1] == 'ix_recipes_category' for row in indexes), 1)

    async def test_search(self):
        async with self.sessions() as session:
            self.assertEqual((await service.search_by_name(session, '  CARBONARA  '))[0].name, 'Spaghetti Carbonara')
            self.assertEqual(await service.search_by_name(session, '  '), [])
            self.assertEqual(await service.search_by_name(session, '%'), [])
            self.assertEqual(await service.search_by_name(session, 'nonexistent'), [])
            self.assertEqual(service.normalize_ingredient('  CHICKEN   breast '), 'chicken breast')
            results = await service.search_by_ingredients(session, [' CHICKEN  ', 'rice', 'tomato'])
            self.assertEqual([r.name for r in results], ['Chicken Rice Bowl'])
            self.assertEqual(await service.search_by_ingredients(session, ['', ' ']), [])
            self.assertEqual(len(await service.get_categories(session)), 7)
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Pasta')), 6)
            self.assertIsNotNone(await service.get_random_recipe(session))

    async def test_users_favorites_and_cascade(self):
        async with self.sessions() as session:
            user = await service.get_or_create_user(session, 123)
            self.assertEqual(user.id, (await service.get_or_create_user(session, 123)).id)
            recipe = await service.get_random_recipe(session)
            await service.add_favorite(session, 123, recipe.id)
            await service.add_favorite(session, 123, recipe.id)
            self.assertEqual(await session.scalar(select(func.count(Favorite.id))), 1)
            self.assertTrue(await service.is_favorite(session, 123, recipe.id))
            self.assertEqual(len(await service.get_favorite_recipes(session, 123)), 1)
            self.assertEqual(await service.get_favorite_recipes(session, 456), [])
            await service.clear_favorite(session, 123, recipe.id)
            await service.clear_favorite(session, 123, recipe.id)
            self.assertFalse(await service.is_favorite(session, 123, recipe.id))
            await service.add_favorite(session, 123, recipe.id)
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
            self.assertEqual(await session.scalar(select(func.count(Favorite.id))), 0)

    async def test_navigation_and_start_registration(self):
        from datetime import datetime, UTC
        from unittest.mock import AsyncMock
        from aiogram import Bot
        from aiogram.types import CallbackQuery, Chat, Message, Update, User as TelegramUser
        from bot import create_dispatcher
        from handlers import favorites, recipes, search, start
        from handlers.states import SearchStates
        dispatcher = create_dispatcher()
        bot = Bot('123456:TEST_ONLY_NOT_A_REAL_TOKEN')
        fake_session = AsyncMock(return_value=True)
        bot.session = fake_session
        try:
            with patch.object(start, 'SessionFactory', self.sessions), patch.object(search, 'SessionFactory', self.sessions), patch.object(recipes, 'SessionFactory', self.sessions), patch.object(favorites, 'SessionFactory', self.sessions):
                state = dispatcher.fsm.get_context(bot=bot, chat_id=123, user_id=123)
                for index, (message_text, expected) in enumerate([
                    ('🍳 Find a recipe', SearchStates.waiting_for_name.state),
                    ('/start', None), ('/start', None),
                    ('🥕 Search by ingredients', SearchStates.waiting_for_ingredients.state),
                    ('📚 Categories', None),
                    ('🍳 Find a recipe', SearchStates.waiting_for_name.state),
                    ('not a recipe', SearchStates.waiting_for_name.state),
                    ('carbonara', None),
                    ('🥕 Search by ingredients', SearchStates.waiting_for_ingredients.state),
                    ('❤️ Favorites', None),
                ]):
                    message = Message(message_id=index+1, date=datetime.now(UTC), chat=Chat(id=123, type='private'), from_user=TelegramUser(id=123, is_bot=False, first_name='Test'), text=message_text)
                    await dispatcher.feed_update(bot, Update(update_id=index, message=message))
                    self.assertEqual(await state.get_state(), expected)
                await state.set_state(SearchStates.waiting_for_name)
                for index, payload in enumerate(['favorite:add:1', 'favorite:add:1', 'favorite:remove:1', 'menu'], start=100):
                    callback = CallbackQuery(id=str(index), from_user=message.from_user, chat_instance='test', message=message, data=payload)
                    await dispatcher.feed_update(bot, Update(update_id=index, callback_query=callback))
                    self.assertIsNone(await state.get_state())
                    async with self.sessions() as session:
                        self.assertEqual(await service.is_favorite(session, 123, 1), payload == 'favorite:add:1')
                # Switch while searching, then exercise Russian buttons and recipe callbacks.
                await state.set_state(SearchStates.waiting_for_name)
                callback = CallbackQuery(id='ru', from_user=message.from_user, chat_instance='test', message=message, data='language:ru')
                await dispatcher.feed_update(bot, Update(update_id=200, callback_query=callback))
                self.assertIsNone(await state.get_state())
                self.assertEqual(fake_session.call_args.args[1].text, 'Выбран русский язык.')
                for index, message_text in enumerate(['🍳 Найти рецепт', 'карбонара', '📚 Категории', '❤️ Избранное', 'ℹ️ Помощь', '/start'], start=201):
                    translated = message.model_copy(update={'text': message_text, 'message_id': index})
                    await dispatcher.feed_update(bot, Update(update_id=index, message=translated))
                self.assertIn('Добро пожаловать', fake_session.call_args.args[1].text)
                for index, payload in enumerate(['category:Pasta', 'recipe:1', 'favorite:add:1', 'favorite:remove:1', 'menu'], start=220):
                    translated = callback.model_copy(update={'id': str(index), 'data': payload})
                    await dispatcher.feed_update(bot, Update(update_id=index, callback_query=translated))
                    self.assertNotIn('Choose', fake_session.call_args.args[1].text)
                callback = callback.model_copy(update={'id': 'en', 'data': 'language:en'})
                await dispatcher.feed_update(bot, Update(update_id=250, callback_query=callback))
                self.assertEqual(fake_session.call_args.args[1].text, 'Language set to English.')
                async with self.sessions() as session:
                    self.assertEqual((await service.get_or_create_user(session, 123)).language, 'en')
                    self.assertEqual(await session.scalar(select(func.count(User.id))), 1)
        finally:
            await dispatcher.storage.close()
            await bot.session.close()

    async def test_bilingual_search_and_saved_preferences(self):
        from services.localization import normalize_language
        from handlers.recipes import format_recipe
        from data.recipe_translations import RUSSIAN_RECIPES, recipe_text
        self.assertEqual(normalize_language('ru-RU'), 'ru')
        self.assertEqual(normalize_language('fr'), 'en')
        async with self.sessions() as session:
            user = await service.get_or_create_user(session, 987, 'ru')
            self.assertEqual(user.language, 'ru')
            await service.set_user_language(session, 987, 'en')
        async with self.sessions() as session:
            self.assertEqual((await service.get_or_create_user(session, 987, 'ru')).language, 'en')
            results = await service.search_by_name(session, '  КАРБОНАРА ')
            self.assertEqual(results[0].name, 'Spaghetti Carbonara')
            self.assertIn('Приготовление', format_recipe(results[0], 'ru'))
            self.assertIn('Instructions', format_recipe(results[0], 'en'))
            results = await service.search_by_ingredients(session, ['КУРИЦА', ' рис ', 'помидор'])
            self.assertEqual([r.name for r in results], ['Chicken Rice Bowl'])
            self.assertEqual(len(await service.search_by_ingredients(session, ['chicken', 'рис'])), 1)
            for recipe in await service.get_all_recipes(session):
                if recipe.name in RUSSIAN_RECIPES:
                    self.assertNotEqual(recipe_text(recipe, 'name', 'ru'), recipe.name)
                else:
                    self.assertEqual(recipe_text(recipe, 'name', 'ru'), recipe.name)

    async def test_legacy_user_migration_is_idempotent(self):
        async with self.engine.begin() as connection:
            await connection.execute(text('DROP TABLE favorites'))
            await connection.execute(text('DROP TABLE users'))
            await connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE NOT NULL, created_at DATETIME NOT NULL)'))
            await connection.execute(text("INSERT INTO users VALUES (5, 555, '2026-01-01 00:00:00')"))
        await db.init_db()
        await db.init_db()
        async with self.sessions() as session:
            user = await service.get_or_create_user(session, 555)
            self.assertEqual(user.id, 5)
            self.assertEqual(user.language, 'en')
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES))


    async def test_new_recipe_search_and_presentation(self):
        from handlers.recipes import format_recipe
        async with self.sessions() as session:
            for query in ['блины', 'борщ', 'вареники', 'пельмени', 'паста']:
                self.assertTrue(await service.search_by_name(session, query), query)
            for query in ['тунец', 'грибы', 'сыр', 'яйца', 'лосось', 'шпинат']:
                self.assertTrue(await service.search_by_ingredients(session, [query]), query)
            for query, expected in [
                (['тунец', 'черри'], 'Паста с тунцом и томатами черри'),
                (['яйца', 'шпинат'], 'Омлет с черри и шпинатом'),
                (['грибы', 'сливки'], 'Паста с грибами в сливочном соусе'),
            ]:
                self.assertIn(expected, [r.name for r in await service.search_by_ingredients(session, query)])
            self.assertEqual(await service.search_by_ingredients(session, ['тунец', 'шпинат']), [])
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Завтраки')), 5)
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Паста')), 6)
            for sample in SAMPLE_RECIPES[7:]:
                recipe = (await service.search_by_name(session, sample['name']))[0]
                for field, value in sample.items():
                    self.assertEqual(getattr(recipe, field), value)
                card = format_recipe(recipe, 'ru')
                self.assertIn('<b>Приготовление:</b>\n\n1. ', card)
                self.assertNotIn('1\\.', card)
                self.assertLess(len(card), 4096)
                self.assertNotIn('<b>', recipe.instructions)
            unsafe = Recipe(**{**SAMPLE_RECIPES[-1], 'name': '<unsafe>', 'description': 'A & B',
                               'ingredients': '<milk>', 'instructions': '<mix>'})
            card = format_recipe(unsafe, 'ru')
            for value in ['&lt;unsafe&gt;', 'A &amp; B', '&lt;milk&gt;', '&lt;mix&gt;']:
                self.assertIn(value, card)

    async def test_seed_preserves_existing_data_and_favorites(self):
        async with self.sessions() as session:
            original = (await service.search_by_name(session, 'Spaghetti Carbonara'))[0]
            original.description = 'User edited description'
            # Keep an already present new recipe; missing ones must still be inserted.
            existing = (await service.search_by_name(session, 'Борщ'))[0]
            existing.name = '  БОРЩ  '
            existing.description = 'User edited borscht'
            await session.commit()
            await service.add_favorite(session, 123, original.id)
            await service.add_favorite(session, 123, existing.id)
            new_names = [item['name'] for item in SAMPLE_RECIPES[7:] if item['name'] != 'Борщ']
            await session.execute(delete(Recipe).where(Recipe.name.in_(new_names)))
            await session.commit()
            original_id, existing_id = original.id, existing.id
        await db.init_db()
        await db.init_db()
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), 19)
            self.assertEqual((await session.get(Recipe, original_id)).description, 'User edited description')
            self.assertEqual((await session.get(Recipe, existing_id)).description, 'User edited borscht')
            self.assertEqual(len(await service.get_favorite_recipes(session, 123)), 2)
            self.assertEqual(await session.scalar(select(func.count(User.id))), 1)
