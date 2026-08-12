import asyncio
import json
from typing import Any, Dict, List, Optional

import yfinance as yf

from .exceptions import (
    InvalidTicker,
    YahooFinanceError,
    YahooFinanceUnavailable,
)
from .mapper import map_quote


class YahooFinanceClient:

    def __init__(
        self,
        timeout: int = 10,
    ):
        self.timeout = timeout

        # yfinance supports retries for transient network errors.
        yf.config.network.retries = 2

    async def get_quote(
        self,
        ticker: str,
    ) -> Dict[str, Any]:

        ticker = self._normalize_ticker(ticker)

        try:

            result = await asyncio.to_thread(
                self._get_quote_sync,
                ticker,
            )

            return result

        except Exception as exc:

            raise YahooFinanceUnavailable(
                f"Unable to retrieve quote for {ticker}"
            ) from exc

    def _get_quote_sync(
        self,
        ticker: str,
    ) -> Dict[str, Any]:

        stock = yf.Ticker(ticker)

        info = stock.get_info()

        if not info:
            raise InvalidTicker(
                f"No Yahoo Finance data found for {ticker}"
            )

        return map_quote(
            ticker=ticker,
            info=info,
        )

    async def get_history(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
    ):

        ticker = self._normalize_ticker(ticker)

        try:

            return await asyncio.to_thread(
                self._get_history_sync,
                ticker,
                period,
                interval,
            )

        except Exception as exc:

            raise YahooFinanceUnavailable(
                f"Unable to retrieve history for {ticker}"
            ) from exc

    def _get_history_sync(
        self,
        ticker: str,
        period: str,
        interval: str,
    ):

        stock = yf.Ticker(ticker)

        history = stock.history(
            period=period,
            interval=interval,
            timeout=self.timeout,
        )

        if history.empty:
            raise InvalidTicker(
                f"No historical data found for {ticker}"
            )

        return json.loads(
            history.reset_index().to_json(
                orient="records",
                date_format="iso"
            )
        )

    async def get_financials(
        self,
        ticker: str,
    ) -> Dict[str, Any]:

        ticker = self._normalize_ticker(ticker)

        try:

            return await asyncio.to_thread(
                self._get_financials_sync,
                ticker,
            )

        except Exception as exc:

            raise YahooFinanceUnavailable(
                f"Unable to retrieve financials for {ticker}"
            ) from exc

    def _get_financials_sync(
        self,
        ticker: str,
    ):

        stock = yf.Ticker(ticker)

        return {
            "income_statement": json.loads(
                stock.get_income_stmt(freq="yearly").to_json(date_format="iso")
            ),

            "balance_sheet": json.loads(
                stock.get_balance_sheet(freq="yearly").to_json(date_format="iso")
            ),

            "cash_flow": json.loads(
                stock.get_cashflow(freq="yearly").to_json(date_format="iso")
            ),
        }

    async def get_news(
        self,
        ticker: str,
        count: int = 5,
    ) -> List[Dict[str, Any]]:

        ticker = self._normalize_ticker(ticker)

        try:

            return await asyncio.to_thread(
                self._get_news_sync,
                ticker,
                count,
            )

        except Exception as exc:

            raise YahooFinanceUnavailable(
                f"Unable to retrieve news for {ticker}"
            ) from exc

    def _get_news_sync(
        self,
        ticker: str,
        count: int,
    ):

        stock = yf.Ticker(ticker)

        news = stock.get_news(
            count=count,
            tab="news",
        )

        if not news:
            return []

        return news

    async def get_research(
        self,
        ticker: str,
    ) -> Dict[str, Any]:

        ticker = self._normalize_ticker(ticker)

        try:

            return await asyncio.to_thread(
                self._get_research_sync,
                ticker,
            )

        except Exception as exc:

            raise YahooFinanceUnavailable(
                f"Unable to retrieve research for {ticker}"
            ) from exc

    def _get_research_sync(
        self,
        ticker: str,
    ):

        search = yf.Search(
            ticker,
            news_count=5,
            include_research=True,
        )

        return {
            "quotes": search.quotes,
            "news": search.news,
            "research": search.research,
        }

    @staticmethod
    def _normalize_ticker(
        ticker: str,
    ) -> str:

        ticker = ticker.strip().upper()

        if not ticker:
            raise InvalidTicker(
                "Ticker cannot be empty"
            )

        # Basic protection against malformed input.
        if len(ticker) > 20:
            raise InvalidTicker(
                "Ticker is too long"
            )

        return ticker