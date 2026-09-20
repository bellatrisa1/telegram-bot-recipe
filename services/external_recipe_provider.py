"""Replaceable recipe provider boundary; no Telegram or database dependencies."""
import json
import re
from typing import Literal, Protocol
from urllib.parse import urlsplit

import aiohttp
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProviderError(Exception):
    """Expected provider failure. Never include response bodies or credentials."""


class ProviderNotConfigured(ProviderError):
    pass


class RecipePayload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=5, max_length=400)
    category: str = Field(min_length=2, max_length=50)
    cooking_time: int = Field(ge=1, le=10080)
    servings: int = Field(ge=1, le=100)
    difficulty: Literal['Легко', 'Средне', 'Сложно']
    ingredients: list[str] = Field(min_length=1, max_length=30)
    instructions: list[str] = Field(min_length=1, max_length=30)
    image_url: str | None = Field(default=None, max_length=500)
    source: Literal['external', 'generated'] = 'external'

    @field_validator('name', 'description', 'category')
    @classmethod
    def russian_plain_text(cls, value: str) -> str:
        if not re.search('[А-Яа-яЁё]', value) or re.search(r'<[^>]+>|\*\*|[\x00-\x1f]', value):
            raise ValueError('Russian plain text required')
        return value

    @field_validator('category')
    @classmethod
    def category_callback_size(cls, value: str) -> str:
        if len(('category:' + value).encode('utf-8')) > 64:
            raise ValueError('Category exceeds Telegram callback size')
        return value

    @field_validator('ingredients', 'instructions')
    @classmethod
    def lines(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        for value in cleaned:
            cls.russian_plain_text(value)
            if len(value) > 600 or re.match(r'^(?:[•*]|\d+[.)])\s', value):
                raise ValueError('Use unnumbered plain text entries')
        return cleaned

    @field_validator('image_url')
    @classmethod
    def image_url_is_http(cls, value: str | None) -> str | None:
        if value and (urlsplit(value).scheme not in {'https', 'http'} or not urlsplit(value).hostname):
            raise ValueError('Invalid image URL')
        return value

    @model_validator(mode='after')
    def telegram_size(self):
        # Bound the escaped card, including labels and numbered steps.
        from html import escape
        texts = [self.name, self.description, self.category, *self.ingredients, *self.instructions]
        if sum(len(escape(value)) for value in texts) + 500 > 4000:
            raise ValueError('Recipe is too long for a Telegram card')
        return self

    def recipe_values(self) -> dict:
        values = self.model_dump()
        values['ingredients'] = '\n'.join(self.ingredients)
        values['instructions'] = '\n'.join(self.instructions)
        return values


class RecipeProvider(Protocol):
    async def fetch(self, query: str) -> RecipePayload | dict | None: ...


class DisabledRecipeProvider:
    async def fetch(self, query: str) -> None:
        raise ProviderNotConfigured('External recipe provider is not configured')


class HttpRecipeProvider:
    """POST {query, language: ru}; expect {recipe: {...}} or {recipe: null}."""
    def __init__(self, url: str, api_key: str = '') -> None:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderError('Provider URL must use HTTPS without embedded credentials')
        self.url = url
        self.api_key = api_key

    async def fetch(self, query: str) -> dict | None:
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(self.url, json={'query': query, 'language': 'ru'},
                                        headers=headers, allow_redirects=False) as response:
                    if response.status != 200:
                        raise ProviderError('Provider HTTP failure')
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(8192):
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ProviderError('Provider response too large')
                    data = json.loads(body)
                    if not isinstance(data, dict) or 'recipe' not in data:
                        raise ProviderError('Invalid provider envelope')
                    return data['recipe']
        except (aiohttp.ClientError, TimeoutError, ValueError):
            raise ProviderError('Provider request failed') from None


def configured_provider() -> RecipeProvider:
    from config import RECIPE_PROVIDER_URL, RECIPE_PROVIDER_API_KEY
    if not RECIPE_PROVIDER_URL:
        return DisabledRecipeProvider()
    return HttpRecipeProvider(RECIPE_PROVIDER_URL, RECIPE_PROVIDER_API_KEY)
