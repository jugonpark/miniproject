from __future__ import annotations

from collections.abc import Iterable

from moodwave_mcp.models import CandidateArtist

from .cache import TTLCache, get_or_create_async
from .normalization import normalize_tags


class DiscoveryService:
    def __init__(self, provider, *, cache_ttl: float = 300, max_results: int = 50) -> None:
        self.provider = provider
        self.cache = TTLCache(cache_ttl)
        self.max_results = min(50, max(1, max_results))

    async def discover(self, tags: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        normalized = normalize_tags(tags)
        bounded = min(self.max_results, max(0, limit))
        result = await get_or_create_async(
            self.cache,
            ("discover", tuple(normalized), bounded),
            lambda: self.provider.discover(normalized, bounded),
        )
        return list(result)[:bounded]

    async def expand(self, artists: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        normalized = normalize_tags(artists)
        bounded = min(self.max_results, max(0, limit))
        result = await get_or_create_async(
            self.cache,
            ("expand", tuple(normalized), bounded),
            lambda: self.provider.similar(normalized, bounded),
        )
        return list(result)[:bounded]
