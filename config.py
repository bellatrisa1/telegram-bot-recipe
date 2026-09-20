import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'recipes.db'}"


def validate_config() -> None:
    """Stop early with a useful message when the bot token is missing."""
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it to the .env file before starting the bot."
        )

    from aiogram.utils.token import TokenValidationError, validate_token

    try:
        validate_token(BOT_TOKEN)
    except TokenValidationError:
        raise RuntimeError("BOT_TOKEN is invalid. Check your private .env file.") from None

# Optional external service; disabled until explicitly configured.
RECIPE_PROVIDER_URL = os.getenv("RECIPE_PROVIDER_URL", "").strip()
RECIPE_PROVIDER_API_KEY = os.getenv("RECIPE_PROVIDER_API_KEY", "").strip()
