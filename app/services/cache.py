import threading
import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """Small thread-safe in-process cache with a fixed TTL and max size."""

    def __init__(self, ttl_seconds: int = 60, max_entries: int = 512):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:

        with self._lock:
            entry = self._store.get(key)

            if entry is None:
                return None

            expires_at, value = entry

            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None

            return value

    def set(self, key: str, value: Any) -> None:

        with self._lock:
            if len(self._store) >= self.max_entries:
                self._evict_locked()

            self._store[key] = (
                time.monotonic() + self.ttl_seconds,
                value,
            )

    def invalidate_prefix(self, prefix: str) -> None:

        with self._lock:
            for key in [
                key
                for key in self._store
                if key.startswith(prefix)
            ]:
                self._store.pop(key, None)

    def clear(self) -> None:

        with self._lock:
            self._store.clear()

    def _evict_locked(self) -> None:

        now = time.monotonic()

        for key, (expires_at, _) in list(self._store.items()):
            if expires_at < now:
                self._store.pop(key, None)

        while len(self._store) >= self.max_entries:
            self._store.pop(next(iter(self._store)))
