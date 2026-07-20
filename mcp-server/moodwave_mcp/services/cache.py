from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from threading import Event, Lock
from time import monotonic
from typing import TypeVar


T = TypeVar("T")


@dataclass
class _InFlight:
    event: Event = field(default_factory=Event)
    value: object | None = None
    error: BaseException | None = None


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[object, tuple[float, object]] = {}
        self._inflight: dict[object, _InFlight] = {}
        self._lock = Lock()

    def get_or_create(self, key: object, factory: Callable[[], T]) -> T:
        while True:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry[0] > monotonic():
                    return entry[1]  # type: ignore[return-value]
                waiting_for = self._inflight.get(key)
                if waiting_for is None:
                    waiting_for = self._inflight[key] = _InFlight()
                    break
            waiting_for.event.wait()
            if waiting_for.error is not None:
                raise waiting_for.error
            return waiting_for.value  # type: ignore[return-value]

        try:
            value = factory()
            with self._lock:
                self._entries[key] = (monotonic() + self.ttl_seconds, value)
                waiting_for.value = value
            return value
        except BaseException as error:
            with self._lock:
                waiting_for.error = error
            raise
        finally:
            with self._lock:
                self._inflight.pop(key).event.set()

    def discard(self, key: object, value: object) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry[1] is value:
                self._entries.pop(key)


async def get_or_create_async(
    cache: TTLCache,
    key: object,
    factory: Callable[[], Awaitable[T]],
) -> T:
    loop = asyncio.get_running_loop()
    while True:
        task = cache.get_or_create(key, lambda: loop.create_task(factory()))
        if task.get_loop() is loop:
            break
        cache.discard(key, task)

    def discard_failure(done: asyncio.Task[T]) -> None:
        if done.cancelled() or done.exception() is not None:
            cache.discard(key, done)

    task.add_done_callback(discard_failure)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if task.cancelled():
            cache.discard(key, task)
        raise
    except BaseException:
        cache.discard(key, task)
        raise
