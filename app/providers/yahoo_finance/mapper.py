from typing import Any, Dict


def safe_float(value: Any):
    try:
        if value is None:
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def map_quote(ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:

    return {
        "ticker": ticker.upper(),
        "company_name": info.get("longName")
        or info.get("shortName"),

        "currency": info.get("currency"),

        "exchange": info.get("exchange"),

        "sector": info.get("sector"),

        "industry": info.get("industry"),

        "market_cap": safe_float(
            info.get("marketCap")
        ),

        "current_price": safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
        ),

        "previous_close": safe_float(
            info.get("previousClose")
        ),

        "day_high": safe_float(
            info.get("dayHigh")
        ),

        "day_low": safe_float(
            info.get("dayLow")
        ),

        "fifty_two_week_high": safe_float(
            info.get("fiftyTwoWeekHigh")
        ),

        "fifty_two_week_low": safe_float(
            info.get("fiftyTwoWeekLow")
        ),

        "pe_ratio": safe_float(
            info.get("trailingPE")
        ),

        "forward_pe": safe_float(
            info.get("forwardPE")
        ),

        "eps": safe_float(
            info.get("trailingEps")
        ),

        "dividend_yield": safe_float(
            info.get("dividendYield")
        ),

        "beta": safe_float(
            info.get("beta")
        ),

        "website": info.get("website"),

        "business_summary": info.get(
            "longBusinessSummary"
        ),
    }