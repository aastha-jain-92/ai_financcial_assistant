"""LLM tool definitions backed by Yahoo Finance market data."""

from typing import Any, Dict, List

from app.services.tools.base import ToolSpec
from app.services.yahoo_service import YahooFinanceService

_TICKER_PARAM = {
    "type": "object",
    "properties": {
        "ticker": {
            "type": "string",
            "description": "Stock ticker symbol, e.g. AAPL or RELIANCE.NS",
        },
    },
    "required": ["ticker"],
}


def build_finance_tools(
    yahoo_service: YahooFinanceService,
) -> List[ToolSpec]:

    async def quote(arguments: Dict[str, Any]) -> Any:
        return await yahoo_service.quote(ticker=arguments["ticker"])

    async def history(arguments: Dict[str, Any]) -> Any:
        return await yahoo_service.history(
            ticker=arguments["ticker"],
            period=arguments.get("period", "1mo"),
            interval=arguments.get("interval", "1d"),
        )

    async def financials(arguments: Dict[str, Any]) -> Any:
        return await yahoo_service.financials(ticker=arguments["ticker"])

    async def news(arguments: Dict[str, Any]) -> Any:
        return await yahoo_service.news(ticker=arguments["ticker"])

    async def research(arguments: Dict[str, Any]) -> Any:
        return await yahoo_service.research(ticker=arguments["ticker"])

    return [
        ToolSpec(
            name="get_quote",
            description=(
                "Get the current stock price and quote details for a "
                "ticker symbol."
            ),
            parameters=_TICKER_PARAM,
            handler=quote,
        ),
        ToolSpec(
            name="get_history",
            description="Get historical stock price data for a ticker.",
            parameters={
                "type": "object",
                "properties": {
                    "ticker": _TICKER_PARAM["properties"]["ticker"],
                    "period": {
                        "type": "string",
                        "description": "Period, e.g. 1mo, 6mo, 1y.",
                    },
                    "interval": {
                        "type": "string",
                        "description": "Interval, e.g. 1d, 1wk.",
                    },
                },
                "required": ["ticker"],
            },
            handler=history,
        ),
        ToolSpec(
            name="get_financials",
            description="Get financial statements for a ticker.",
            parameters=_TICKER_PARAM,
            handler=financials,
        ),
        ToolSpec(
            name="get_news",
            description="Get the latest news for a ticker.",
            parameters=_TICKER_PARAM,
            handler=news,
        ),
        ToolSpec(
            name="get_research",
            description=(
                "Get research, analyst recommendations and sector "
                "information for a ticker."
            ),
            parameters=_TICKER_PARAM,
            handler=research,
        ),
    ]
