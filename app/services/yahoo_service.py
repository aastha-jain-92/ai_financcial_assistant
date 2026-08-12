from typing import Any

from app.config import settings
from app.providers.yahoo_finance import (
    YahooFinanceClient,
)

from .yahoo_cache import YahooCache


class YahooFinanceService:

    def __init__(self):

        self.client = YahooFinanceClient(
            timeout=settings.YAHOO_TIMEOUT_SECONDS
        )

        self.cache = YahooCache(
            ttl_seconds=settings.YAHOO_CACHE_TTL_SECONDS
        )

    async def quote(
        self,
        ticker: str,
    ):

        key = f"quote:{ticker.upper()}"

        cached = self.cache.get(key)

        if cached is not None:
            return cached

        result = await self.client.get_quote(
            ticker
        )

        self.cache.set(
            key,
            result,
        )

        return result

    async def history(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
    ):

        key = (
            f"history:"
            f"{ticker.upper()}:"
            f"{period}:"
            f"{interval}"
        )

        cached = self.cache.get(key)

        if cached is not None:
            return cached

        result = await self.client.get_history(
            ticker,
            period,
            interval,
        )

        self.cache.set(
            key,
            result,
        )

        return result

    async def financials(
        self,
        ticker: str,
    ):

        key = f"financials:{ticker.upper()}"

        cached = self.cache.get(key)

        if cached is not None:
            return cached

        result = await self.client.get_financials(
            ticker
        )

        self.cache.set(
            key,
            result,
        )

        return result

    async def news(
        self,
        ticker: str,
        count: int = 5,
    ):

        key = (
            f"news:"
            f"{ticker.upper()}:"
            f"{count}"
        )

        cached = self.cache.get(key)

        if cached is not None:
            return cached

        result = await self.client.get_news(
            ticker,
            count,
        )

        self.cache.set(
            key,
            result,
        )

        return result

    async def research(
        self,
        ticker: str,
    ):

        key = f"research:{ticker.upper()}"

        cached = self.cache.get(key)

        if cached is not None:
            return cached

        result = await self.client.get_research(
            ticker
        )

        self.cache.set(
            key,
            result,
        )

        return result