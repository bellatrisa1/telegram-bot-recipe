# Recipe Telegram Bot

A beginner-friendly Telegram recipe bot built with Python, aiogram 3, asyncio, SQLAlchemy, and SQLite.

## Before you start

You need:

- Python 3.14 or newer
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Run on macOS with zsh

Open Terminal and move into this project folder:

```zsh
cd /Users/bellatrisamankieva/Documents/telegram-bot-recipe
```

For a fresh checkout, create a virtual environment (the existing `.venv` is already repaired and ready):

```zsh
python3 -m venv .venv
```

Activate it:

```zsh
source .venv/bin/activate
```

Install the dependencies:

```zsh
python3 -m pip install -r requirements.txt
```

Create your private environment file from the example:

```zsh
test -e .env || cp .env.example .env
```

Open `.env` and replace the placeholder with your Telegram bot token:

```dotenv
BOT_TOKEN=your_telegram_bot_token_here
```

Start the bot:

```zsh
python3 bot.py
```

The bot creates `recipes.db` automatically and inserts any missing bundled recipes on startup. Open your bot in Telegram and send `/start`.

To stop the bot, return to the Terminal window where it is running and press `Control-C`.

When you come back later, activate the environment again before starting:

```zsh
source .venv/bin/activate
python3 bot.py
```

## Project map

- `bot.py` starts polling, configures logging, and initializes the database.
- `config.py` loads `BOT_TOKEN` from `.env` and defines the SQLite connection.
- `database/` contains SQLAlchemy models and database setup.
- `data/sample_recipes.py` contains the recipes inserted for the first run.
- `handlers/` contains small Telegram routers for menus, recipes, searching, and favorites.
- `keyboards/` contains reusable Telegram reply and inline keyboards.
- `services/recipe_service.py` contains database operations and ingredient matching logic.
- `recipes.db` is the local SQLite database created at runtime.
- `.env` stores your secret token and must never be committed.

## Common commands

Check that the Python files compile:

```zsh
python3 -m compileall -q bot.py config.py data database handlers keyboards services tests
python3 -m unittest discover -s tests -v
```

Deactivate the virtual environment when you are finished:

```zsh
deactivate
```

## Using the bot

The six menu buttons offer name search, ingredient search, categories, random recipes,
favorites, and help. Name search ignores case and surrounding whitespace. Ingredient
search accepts comma-separated ingredients, ignores repeated whitespace and case, and
requires every supplied ingredient to match. Results with fewer additional ingredients
appear first. Select a result to open its recipe card and save or remove a favorite.
Use the Main menu button or `/start` to leave a search.

`recipes.db` stores recipes, registered Telegram users, and their favorites. Keep it to
preserve your data. Initialization inserts missing bundled recipes individually by normalized name;
existing records are left untouched and restarting does not duplicate them. Tests use temporary databases.

## Troubleshooting

- **BOT_TOKEN is missing or invalid:** Check that `.env` exists beside `config.py` and
  contains `BOT_TOKEN=...` with the token from BotFather. Never share its value or commit
  this file. The project loads this file by its absolute location, even when started from
  another working directory. Its value takes precedence over an old shell variable.
- **ModuleNotFoundError or externally-managed-environment:** Activate `.venv` and run
  `python3 -m pip install -r requirements.txt`. Verify `which python3` points inside this
  project's `.venv/bin`. If the folder was moved, run `python3 -m venv .venv` to refresh
  the existing environment's activation scripts, then activate and install again.
- **Cannot connect to api.telegram.org:** Check internet access, DNS, and any local
  firewall or proxy restrictions. Imports passing alone does not prove Telegram access.
- **Unauthorized:** Obtain the correct current token from BotFather and update only `.env`.
- **Conflict / another getUpdates request:** Stop the other running bot with Control+C.
  Run only one polling process for this token.
- **Webhook is active:** Polling cannot run alongside a configured webhook; remove the
  webhook deliberately before switching an existing deployment to polling.

The intended environment is `.venv` (Python 3.14). `.venv-1` contains Python 3.9 metadata
and is not used by these commands. It has been left untouched.

## English and Russian / Английский и русский

Use **🌐 Language / 🌐 Язык** in the main menu or send `/language`, then select
**English** or **Русский**. The choice is saved per Telegram user and survives restarts.
New users start in their Telegram language (Russian or English; other languages use
English). Existing users keep English until they select Russian.

Menus, prompts, categories, and the original seven sample recipes are translated. Search accepts
English or Russian names and ingredients regardless of the selected interface language,
including mixed queries such as `chicken, рис`. Russian `ё` and `е` are treated alike.
Changing language clears any active search; favorites remain attached to the same recipes.

Startup adds the language column to an older database automatically and preserves its
users, recipes, and favorites. UI text lives in `services/localization.py`; bundled
recipe translations live in `data/recipe_translations.py`, keyed by English recipe name.
Additional recipes without a translation display their original content.

The catalog also includes 12 Russian recipes (19 bundled recipes total). Their content
stays in Russian in either interface language. Russian and English category names are
grouped together. Cooking times are stored as integer minutes; recipe text stays plain
text, with HTML escaping and numbering applied only when a card is displayed.
