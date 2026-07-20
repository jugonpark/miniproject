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

    async def discover_grouped(self, groups: dict[str, list[str]], quotas: dict[str, int], limit: int = 25) -> list[CandidateArtist]:
        bounded = min(self.max_results, max(0, limit))
        normalized = {category: normalize_tags(tags) for category, tags in groups.items() if tags}
        result = await get_or_create_async(self.cache, ("discover_grouped", tuple((key, tuple(value)) for key, value in normalized.items()), tuple(sorted(quotas.items())), bounded), lambda: self.provider.discover_grouped(normalized, quotas, bounded))
        return list(result)[:bounded]

    async def discover_country(self, country: str, limit: int = 25, required_tags: Iterable[str] = ()) -> list[CandidateArtist]:
        bounded = min(self.max_results, max(0, limit))
        tags = normalize_tags(required_tags)
        result = await get_or_create_async(self.cache, ("discover_country", country, tuple(tags), bounded), lambda: self.provider.discover_country(country, bounded, tags))
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
