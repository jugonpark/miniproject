from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock
from time import monotonic
from typing import TypeVar


T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[object, tuple[float, object]] = {}
        self._inflight: dict[object, Event] = {}
        self._lock = Lock()

    def get_or_create(self, key: object, factory: Callable[[], T]) -> T:
        while True:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry[0] > monotonic():
                    return entry[1]  # type: ignore[return-value]
                waiting_for = self._inflight.get(key)
                if waiting_for is None:
                    waiting_for = self._inflight[key] = Event()
                    break
            waiting_for.wait()

        try:
            value = factory()
            with self._lock:
                self._entries[key] = (monotonic() + self.ttl_seconds, value)
            return value
        finally:
            with self._lock:
                self._inflight.pop(key).set()
