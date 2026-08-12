class YahooFinanceError(Exception):
    """Base Yahoo Finance error."""
    pass


class YahooFinanceUnavailable(YahooFinanceError):
    """Yahoo Finance data could not be retrieved."""
    pass


class InvalidTicker(YahooFinanceError):
    """Ticker is invalid or unavailable."""
    pass