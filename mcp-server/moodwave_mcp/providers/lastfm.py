from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable

import httpx

from moodwave_mcp.models import CandidateArtist, TrackCandidate
from moodwave_mcp.services.normalization import normalize_tags

from .base import JsonRequester, ProviderError


class LastFmProvider:
    base_url = "https://ws.audioscrobbler.com/2.0/"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        if not api_key:
            raise ValueError("Last.fm API key is required")
        self.api_key = api_key
        self.requester = JsonRequester(client or httpx.AsyncClient(), timeout=timeout)

    async def discover(self, tags: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        bounded = min(50, max(0, limit))
        if not bounded:
            return []
        requested_tags = normalize_tags(tags)
        per_tag = min(10, max(3, (bounded + max(1, len(requested_tags)) - 1) // max(1, len(requested_tags))))
        payloads = await asyncio.gather(
            *(self._call("tag.gettopartists", tag=tag, limit=per_tag) for tag in requested_tags),
            return_exceptions=True,
        )
        results: list[CandidateArtist] = []
        seen: set[str] = set()
        counts: dict[str, int] = {}
        for tag, payload in zip(requested_tags, payloads):
            artists = [] if isinstance(payload, BaseException) else _nested_list(payload, "topartists", "artist")
            counts[tag] = len(artists)
            for item in artists:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                key = name.casefold()
                if not name or key in seen:
                    continue
                seen.add(key)
                results.append(
                    CandidateArtist(
                        name=name,
                        source="lastfm:tag",
                        tags=[tag],
                        popularity=_integer(item.get("listeners") or item.get("playcount")),
                    )
                )
        logging.getLogger("moodwave").warning(
            "lastfm_discovery=%s",
            json.dumps({"lastFmMethod": "tag.getTopArtists", "lastFmRequestedTags": requested_tags, "resultCountByTag": counts}, ensure_ascii=False),
        )
        return results[:bounded]

    async def similar(self, artists: Iterable[str], limit: int = 25) -> list[CandidateArtist]:
        bounded = min(50, max(0, limit))
        if not bounded:
            return []
        results: list[CandidateArtist] = []
        seen: set[str] = set()
        for artist in (value.strip() for value in artists if value.strip()):
            payload = await self._call("artist.getsimilar", artist=artist, limit=bounded)
            similar = _nested_list(payload, "similarartists", "artist")
            for item in similar:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                key = name.casefold()
                if not name or key in seen:
                    continue
                seen.add(key)
                results.append(
                    CandidateArtist(
                        name=name,
                        source="lastfm:similar",
                        tags=await self._top_tags(name),
                        popularity=round(_number(item.get("match")) * 1000),
                    )
                )
                if len(results) >= bounded:
                    return results
        return results

    async def top_tracks(self, artist: str, limit: int = 5) -> list[TrackCandidate]:
        bounded = min(10, max(0, limit))
        if not artist.strip() or not bounded:
            return []
        payload = await self._call("artist.gettoptracks", artist=artist.strip(), limit=bounded)
        results = []
        for item in _nested_list(payload, "toptracks", "track"):
            if not isinstance(item, dict):
                continue
            title = str(item.get("name") or "").strip()
            credited = item.get("artist")
            name = str(credited.get("name") if isinstance(credited, dict) else artist).strip()
            if title and name:
                results.append(TrackCandidate(artist=name, title=title, source="lastfm:toptracks"))
        return results

    async def _top_tags(self, artist: str) -> list[str]:
        payload = await self._call("artist.gettoptags", artist=artist)
        values = _nested_list(payload, "toptags", "tag")
        return normalize_tags(
            str(item.get("name", ""))
            for item in values[:10]
            if isinstance(item, dict)
        )

    async def _call(self, method: str, **params: object) -> dict:
        payload = await self.requester.get(
            self.base_url,
            params={"method": method, "api_key": self.api_key, "format": "json", **params},
        )
        if payload is None or "error" in payload:
            raise ProviderError("Last.fm request failed")
        return payload


def _number(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    return round(_number(value))


def _nested_list(payload: dict, container_name: str, values_name: str) -> list:
    container = payload.get(container_name)
    if not isinstance(container, dict):
        return []
    values = container.get(values_name)
    return values if isinstance(values, list) else []
