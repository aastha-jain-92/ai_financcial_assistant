import time
from typing import Any


class YahooCache:

    def __init__(
        self,
        ttl_seconds: int = 60,
    ):
        self.ttl_seconds = ttl_seconds

        self._cache: dict[
            str,
            tuple[float, Any]
        ] = {}

    def get(self, key: str):

        item = self._cache.get(key)

        if item is None:
            return None

        timestamp, value = item

        if time.time() - timestamp > self.ttl_seconds:

            self._cache.pop(key, None)

            return None

        return value

    def set(
        self,
        key: str,
        value: Any,
    ):

        self._cache[key] = (
            time.time(),
            value,
        )