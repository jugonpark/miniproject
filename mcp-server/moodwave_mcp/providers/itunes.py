from __future__ import annotations

from difflib import SequenceMatcher

import httpx

from moodwave_mcp.models import VerifiedTrack
from moodwave_mcp.services.cache import TTLCache, get_or_create_async
from moodwave_mcp.services.normalization import music_version, normalize_music_name

from .base import JsonRequester


class ITunesProvider:
    def __init__(self, *, client: httpx.AsyncClient | None = None, base_url: str = "https://itunes.apple.com/search", country: str = "KR", timeout: float = 5.0, min_artist_score: float = 0.75, cache_ttl: float = 3600) -> None:
        self.base_url, self.country, self.min_artist_score = base_url, country, min_artist_score
        self.requester = JsonRequester(client or httpx.AsyncClient(), timeout=timeout, retries=1)
        self.cache = TTLCache(cache_ttl)

    async def search_artist_tracks(self, artist: str, limit: int = 10) -> list[VerifiedTrack]:
        return await self._search(artist, [artist], None, limit)

    async def search_track(self, artist: str, title: str, aliases: list[str] | None = None) -> VerifiedTrack | None:
        tracks = await self._search(f"{artist} {title}", [artist, *(aliases or [])], title, 10)
        return tracks[0] if tracks else None

    async def search_track_detailed(self, artist: str, title: str, aliases: list[str] | None = None) -> tuple[VerifiedTrack | None, str | None]:
        diagnostics: dict[str, int] = {}
        tracks = await self._search(f"{artist} {title}", [artist, *(aliases or [])], title, 10, diagnostics)
        reason = next((key for key in ("VERSION_CONFLICT", "LOW_ARTIST_SCORE", "LOW_TITLE_SCORE") if diagnostics.get(key)), "ITUNES_NOT_FOUND")
        return (tracks[0], None) if tracks else (None, reason)

    async def _search(self, term: str, artists: list[str], expected_title: str | None, limit: int, diagnostics: dict[str, int] | None = None) -> list[VerifiedTrack]:
        bounded = min(25, max(0, limit))
        if not term.strip() or not any(artist.strip() for artist in artists) or not bounded:
            return []
        payload = await get_or_create_async(self.cache, (self.country, "song", normalize_music_name(term), bounded), lambda: self.requester.get(self.base_url, params={"term": term.strip(), "country": self.country, "media": "music", "entity": "song", "limit": bounded})) or {}
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        expected, ranked = [normalize_music_name(artist) for artist in artists if artist.strip()], []
        for item in results:
            if not isinstance(item, dict) or item.get("wrapperType") != "track" or item.get("kind") != "song":
                continue
            track_id, item_title, found_artist = item.get("trackId"), item.get("trackName"), item.get("artistName")
            artist_score = max((SequenceMatcher(None, value, normalize_music_name(found_artist)).ratio() for value in expected), default=0) if isinstance(found_artist, str) else 0
            if not track_id or not isinstance(item_title, str) or not item_title.strip() or not isinstance(found_artist, str):
                continue
            if artist_score < self.min_artist_score:
                if diagnostics is not None: diagnostics["LOW_ARTIST_SCORE"] = diagnostics.get("LOW_ARTIST_SCORE", 0) + 1
                continue
            title_score = SequenceMatcher(None, normalize_music_name(expected_title or item_title), normalize_music_name(item_title)).ratio()
            if expected_title is not None and title_score < .80:
                if diagnostics is not None: diagnostics["LOW_TITLE_SCORE"] = diagnostics.get("LOW_TITLE_SCORE", 0) + 1
                continue
            if expected_title is not None and music_version(expected_title) != music_version(item_title):
                if diagnostics is not None: diagnostics["VERSION_CONFLICT"] = diagnostics.get("VERSION_CONFLICT", 0) + 1
                continue
            release_date = str(item.get("releaseDate") or "")
            track = VerifiedTrack(recording_id=f"itunes:{track_id}", track_title=item_title.strip(), artist_name=found_artist.strip(), album_title=str(item.get("collectionName") or "").strip() or None, release_year=int(release_date[:4]) if release_date[:4].isdigit() else None, cover_image_url=item.get("artworkUrl100") or None, tags=[str(item["primaryGenreName"])] if item.get("primaryGenreName") else [], source="itunes")
            ranked.append((title_score * .55 + artist_score * .40 + .05, track))
        return [track for _, track in sorted(ranked, key=lambda item: item[0], reverse=True)]
