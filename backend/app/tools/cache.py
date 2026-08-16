"""Small in-memory cache for tool results.

Prevents identical RPC calls within a single investigation (e.g. the
indexer, the interaction scanner and the evidence builder all need the
same transaction) and makes re-plans cheap.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Any


class ToolCache:
    def __init__(self) -> None:
        self._store: dict[tuple, Any] = {}
        self._lock = Lock()

    def key(self, tool: str, **kwargs: Any) -> tuple:
        return (tool, tuple(sorted(kwargs.items())))

    def get(self, key: tuple) -> Any:
        with self._lock:
            return self._store.get(key)

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            self._store[key] = value

    def memoize(self, key: tuple, produce: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = produce()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()