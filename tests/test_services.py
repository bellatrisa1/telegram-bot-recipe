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
            self.assertEqual(len(await service.get_categories(session)), 12)
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Pasta')), 14)
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
            self.assertEqual(results[0].name, 'Паста Карбонара')
            self.assertIn('Spaghetti Carbonara', [recipe.name for recipe in results])
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
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Завтраки')), 12)
            self.assertEqual(len(await service.get_recipes_by_category(session, 'Паста')), 14)
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
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES))
            self.assertEqual((await session.get(Recipe, original_id)).description, 'User edited description')
            self.assertEqual((await session.get(Recipe, existing_id)).description, 'User edited borscht')
            self.assertEqual(len(await service.get_favorite_recipes(session, 123)), 2)
            self.assertEqual(await session.scalar(select(func.count(User.id))), 1)

    async def test_lookup_local_and_invalid_queries_skip_provider(self):
        from unittest.mock import AsyncMock
        from services.recipe_lookup import find_or_fetch_recipe, normalize_query
        provider = AsyncMock()
        self.assertEqual(normalize_query('  ТИРАМИСУ   '), 'тирамису')
        for query in ['Борщ', '  БОРЩ  ', 'блины', 'carbonara']:
            result = await find_or_fetch_recipe(query, provider)
            self.assertEqual(result.status, 'local')
            self.assertIsNotNone(result.recipe)
        for query in ['', '1', '<script>', 'x' * 201]:
            self.assertEqual((await find_or_fetch_recipe(query, provider)).status, 'invalid_query')
        provider.fetch.assert_not_called()

    async def test_lookup_caches_validated_recipe_and_favorites(self):
        from unittest.mock import AsyncMock
        from services.recipe_lookup import find_or_fetch_recipe
        payload = {**SAMPLE_RECIPES[-1], 'name': 'Новое тестовое блюдо',
                   'ingredients': ['сыр — 50 г', 'яйца — 2 шт.'],
                   'instructions': ['Смешайте ингредиенты.', 'Приготовьте до готовности.'],
                   'source': 'external'}
        provider = AsyncMock()
        provider.fetch.return_value = payload
        first = await find_or_fetch_recipe('  Новое   тестовое блюдо ', provider)
        self.assertEqual(first.status, 'cached')
        for query in ['НОВОЕ ТЕСТОВОЕ БЛЮДО', ' новое тестовое блюдо  ']:
            second = await find_or_fetch_recipe(query, provider)
            self.assertEqual(second.recipe.id, first.recipe.id)
            self.assertEqual(second.status, 'local')
        provider.fetch.assert_awaited_once_with('новое тестовое блюдо')
        async with self.sessions() as session:
            self.assertEqual(first.recipe.source, 'external')
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES) + 1)
            await service.add_favorite(session, 999, first.recipe.id)
            await service.add_favorite(session, 999, first.recipe.id)
            self.assertEqual([r.id for r in await service.get_favorite_recipes(session, 999)], [first.recipe.id])
            await service.clear_favorite(session, 999, first.recipe.id)
            self.assertFalse(await service.is_favorite(session, 999, first.recipe.id))
            self.assertIn(first.recipe.id, [r.id for r in await service.search_by_ingredients(session, ['яйца', 'сыр'])])

    async def test_lookup_failure_and_validation_never_cache(self):
        from unittest.mock import AsyncMock
        from services.recipe_lookup import find_or_fetch_recipe
        from services.external_recipe_provider import ProviderError
        provider = AsyncMock()
        for failure in [ProviderError('do not log secret response'), TimeoutError()]:
            provider.fetch.side_effect = failure
            self.assertEqual((await find_or_fetch_recipe('Неизвестное блюдо', provider)).status, 'provider_error')
        provider.fetch.side_effect = None
        for invalid in [{}, {'name': 'Incomplete'}, [], {'name': '<b>Блюдо</b>'}]:
            provider.fetch.return_value = invalid
            self.assertEqual((await find_or_fetch_recipe('Неизвестное блюдо', provider)).status, 'provider_error')
        provider.fetch.return_value = None
        self.assertEqual((await find_or_fetch_recipe('Неизвестное блюдо', provider)).status, 'not_found')
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES))

    async def test_lookup_concurrent_aliases_share_one_recipe(self):
        import asyncio
        from unittest.mock import AsyncMock
        from services.recipe_lookup import find_or_fetch_recipe
        from database.models import RecipeLookup
        provider = AsyncMock()
        provider.fetch.return_value = {**SAMPLE_RECIPES[-1], 'name': 'Новое блюдо',
                                      'ingredients': ['яйца — 2 шт.'], 'instructions': ['Приготовьте яйца.']}
        results = await asyncio.gather(*(find_or_fetch_recipe(q, provider) for q in ['new dish', 'новое блюдо', ' NEW DISH ']))
        self.assertEqual(len({result.recipe.id for result in results}), 1)
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES) + 1)
            self.assertEqual(await session.scalar(select(func.count(RecipeLookup.query))), 2)
        again = await find_or_fetch_recipe('new dish', provider)
        self.assertEqual(again.status, 'local')

    async def test_source_migration_preserves_existing_recipes(self):
        async with self.engine.begin() as connection:
            await connection.execute(text('ALTER TABLE recipes DROP COLUMN source'))
        await db.init_db()
        await db.init_db()
        async with self.sessions() as session:
            recipes = await service.get_all_recipes(session)
            self.assertEqual(len(recipes), len(SAMPLE_RECIPES))
            self.assertTrue(all(recipe.source == 'bundled' for recipe in recipes))

    async def test_http_provider_contract_with_mocked_network(self):
        from unittest.mock import AsyncMock, MagicMock
        from services.external_recipe_provider import HttpRecipeProvider, ProviderError
        response = MagicMock(status=200)
        async def chunks():
            yield b'{"recipe":'
            yield b'null}'
        response.content.iter_chunked.return_value = chunks()
        response_context = MagicMock()
        response_context.__aenter__ = AsyncMock(return_value=response)
        session = MagicMock()
        session.post.return_value = response_context
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        with patch('services.external_recipe_provider.aiohttp.ClientSession', return_value=session_context):
            self.assertIsNone(await HttpRecipeProvider('https://example.invalid/recipes').fetch('борщ'))
            self.assertEqual(session.post.call_args.kwargs['json'], {'query': 'борщ', 'language': 'ru'})
            response.status = 500
            with self.assertRaises(ProviderError):
                await HttpRecipeProvider('https://example.invalid/recipes').fetch('борщ')

    async def test_popular_catalog_coverage_and_plain_html(self):
        from data.popular_recipes import POPULAR_RECIPES
        from data.recipe_search import EXISTING_EQUIVALENTS
        from handlers.recipes import format_recipe
        import xml.etree.ElementTree as ET
        import re
        self.assertEqual(len(POPULAR_RECIPES), 93)
        self.assertEqual(len(POPULAR_RECIPES) + len(EXISTING_EQUIVALENTS), 100)
        self.assertEqual(len({r['name'] for r in SAMPLE_RECIPES}), len(SAMPLE_RECIPES))
        async with self.sessions() as session:
            for requested, stored_name in EXISTING_EQUIVALENTS.items():
                self.assertIn(stored_name, [r.name for r in await service.search_by_name(session, requested)])
            for sample in POPULAR_RECIPES:
                recipe = (await service.search_by_name(session, sample['name']))[0]
                self.assertEqual(recipe.name, sample['name'])
                self.assertGreaterEqual(len(recipe.instructions.splitlines()), 4)
                self.assertGreater(recipe.cooking_time, 0)
                self.assertGreater(recipe.servings, 0)
                for ingredient in recipe.ingredients.splitlines():
                    self.assertIn(' — ', ingredient)
                    self.assertTrue(re.search(r'\d|[¼½¾]|по вкусу', ingredient), ingredient)
                self.assertNotRegex(recipe.instructions, r'<b>|\*\*|^1\.')
                card = format_recipe(recipe, 'ru')
                ET.fromstring('<root>' + card + '</root>')
                self.assertLess(len(card.encode('utf-16-le')) // 2, 4096)
            selected = await service.get_random_recipe(session)
            self.assertIsNotNone(selected)
            self.assertEqual(len(await service.get_categories(session)), 12)

    async def test_ranked_russian_queries_and_ingredients(self):
        from services.recipe_lookup import find_or_fetch_recipe
        from unittest.mock import AsyncMock
        expected = {
            'борщ': 'Борщ', 'блины': 'Блины на молоке', 'блинчики': 'Блины на молоке',
            'пельмени': 'Домашние пельмени', 'карбонара': 'Паста Карбонара',
            'курица': 'Курица с грибами', 'курица грибы': 'Курица с грибами',
            'картошка с мясом': 'Жаркое с картошкой', 'фарш': 'Макароны по-флотски',
            'творог': 'Сырники', 'сырники': 'Сырники', 'оливье': 'Оливье',
            'шарлотка': 'Шарлотка с яблоками', 'плов': 'Плов',
            'сырник': 'Сырники', 'суп курица': 'Куриный суп с лапшой',
            'макароны с фаршем': 'Макароны по-флотски', 'котлеты': 'Котлеты домашние',
        }
        async with self.sessions() as session:
            for query, name in expected.items():
                results = await service.search_by_name(session, '  ' + query.upper() + '  ')
                self.assertIn(name, [r.name for r in results[:10]], query)
            self.assertEqual((await service.search_by_name(session, 'борщ'))[0].name, 'Борщ')
            self.assertEqual((await service.search_by_name(session, '  ЕЖИКИ   с рисом '))[0].name, 'Ёжики с рисом')
            for query, name in [('курица картошка', 'Курица с картошкой в духовке'),
                                ('фарш картошка', 'Картофельная запеканка с фаршем'),
                                ('грибы курица', 'Паста с курицей и грибами'),
                                ('творог', 'Печенье из творога')]:
                self.assertIn(name, [r.name for r in await service.search_by_ingredients(session, [query])])
            self.assertEqual(await service.search_by_name(session, 'соль'), [])
            self.assertEqual(await service.search_by_ingredients(session, ['вода', 'соль']), [])
        provider = AsyncMock()
        result = await find_or_fetch_recipe('курица грибы', provider)
        self.assertEqual(result.status, 'matches')
        self.assertIn('Курица с грибами', [r.name for r in result.matches])
        provider.fetch.assert_not_called()

    async def test_equivalent_seed_names_and_legacy_repair(self):
        from data.recipe_repairs import GREEK_SALAD_ORIGINAL, GREEK_SALAD_COMPLETE
        async with self.sessions() as session:
            pancakes = (await service.search_by_name(session, 'Блины на молоке'))[0]
            pancakes.name = 'Блины'
            salad = (await service.search_by_name(session, 'Greek Salad'))[0]
            for key, value in GREEK_SALAD_ORIGINAL.items():
                setattr(salad, key, value)
            await session.commit()
            salad_id = salad.id
            await service.add_favorite(session, 678, salad.id)
        await db.init_db()
        await db.init_db()
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count(Recipe.id))), len(SAMPLE_RECIPES))
            salad = await session.get(Recipe, salad_id)
            self.assertEqual(salad.ingredients, GREEK_SALAD_COMPLETE['ingredients'])
            self.assertTrue(await service.is_favorite(session, 678, salad_id))
            salad.description = 'Пользовательский текст'
            salad.ingredients = GREEK_SALAD_ORIGINAL['ingredients']
            await session.commit()
        await db.init_db()
        async with self.sessions() as session:
            salad = await session.get(Recipe, salad_id)
            self.assertEqual(salad.description, 'Пользовательский текст')
            self.assertEqual(salad.ingredients, GREEK_SALAD_ORIGINAL['ingredients'])
