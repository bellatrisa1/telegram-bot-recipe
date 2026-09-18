import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError

from config import BOT_TOKEN, validate_config
from database.database import engine, init_db
from handlers.middleware import NavigationMiddleware
from aiogram.fsm.storage.memory import SimpleEventIsolation
from handlers import favorites, recipes, search, start


class SecretSafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return rendered.replace(BOT_TOKEN, "[REDACTED]") if BOT_TOKEN else rendered


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    dispatcher.message.outer_middleware(NavigationMiddleware())
    dispatcher.callback_query.outer_middleware(NavigationMiddleware())
    dispatcher.include_routers(start.router, favorites.router, recipes.router, search.router, start.fallback_router)
    return dispatcher


async def main() -> None:
    validate_config()
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dispatcher = create_dispatcher()

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    handler = logging.StreamHandler()
    handler.setFormatter(SecretSafeFormatter("%(asctime)s | %(levelname)s | %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
    except TelegramNetworkError:
        logging.error("Cannot connect to Telegram. Check internet access and DNS for api.telegram.org.")
        raise SystemExit(1) from None
    except TelegramUnauthorizedError:
        logging.error("Telegram rejected BOT_TOKEN. Check the token in your private .env file.")
        raise SystemExit(1) from None
    except RuntimeError as error:
        logging.error("%s", error)
        raise SystemExit(1) from None
