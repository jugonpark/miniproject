from __future__ import annotations

import asyncio
from collections.abc import Iterable

from moodwave_mcp.models import CandidateArtist

from .cache import TTLCache
from .normalization import normalize_tags


class DiscoveryService:
    def __init__(self, provider, *, cache_ttl: float = 300, max_results: int = 50) -> None:
        self.provider = provider
        self.cache = TTLCache(cache_ttl)
        self.max_results = min(50, max(1, max_results))

    async def discover(self, tags: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        normalized = normalize_tags(tags)
        bounded = min(self.max_results, max(0, limit))
        task = self.cache.get_or_create(
            ("discover", tuple(normalized), bounded),
            lambda: asyncio.create_task(self.provider.discover(normalized, bounded)),
        )
        return list(await task)[:bounded]

    async def expand(self, artists: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        normalized = normalize_tags(artists)
        bounded = min(self.max_results, max(0, limit))
        task = self.cache.get_or_create(
            ("expand", tuple(normalized), bounded),
            lambda: asyncio.create_task(self.provider.similar(normalized, bounded)),
        )
        return list(await task)[:bounded]
