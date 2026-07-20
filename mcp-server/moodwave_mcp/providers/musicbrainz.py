from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic

import httpx

from moodwave_mcp.models import VerifiedTrack

from .base import JsonRequester


class MusicBrainzProvider:
    base_url = "https://musicbrainz.org/ws/2"

    def __init__(
        self,
        user_agent: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
        min_interval: float = 1.0,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("MusicBrainz User-Agent is required")
        self.user_agent = user_agent.strip()
        self.requester = JsonRequester(client or httpx.AsyncClient(), timeout=timeout)
        self.min_interval = max(0.0, min_interval)
        self.clock = clock
        self.sleep = sleep
        self._last_request_at: float | None = None
        self._spacing_lock = asyncio.Lock()

    async def verify_artist_tracks(self, artist: str, limit: int = 10) -> list[VerifiedTrack]:
        name = artist.strip()
        if not name:
            return []
        bounded = min(25, max(0, limit))
        if not bounded:
            return []
        artist_payload = await self._get(
            "/artist",
            params={"query": f'artist:"{name}"', "fmt": "json", "limit": 1},
        )
        artists = artist_payload.get("artists", [])
        if not isinstance(artists, list) or not artists:
            return []
        artist_item = artists[0]
        if not isinstance(artist_item, dict) or not artist_item.get("id"):
            return []
        artist_id = str(artist_item["id"])
        normalized_name = str(artist_item.get("name") or name).strip()
        recording_payload = await self._get(
            "/recording",
            params={
                "query": f"arid:{artist_id}",
                "fmt": "json",
                "inc": "releases+release-groups",
                "limit": bounded,
            },
        )
        recordings = recording_payload.get("recordings", [])
        if not isinstance(recordings, list):
            return []
        tracks: list[VerifiedTrack] = []
        seen: set[str] = set()
        for item in recordings:
            if not isinstance(item, dict):
                continue
            recording_id = str(item.get("id", "")).strip()
            title = str(item.get("title", "")).strip()
            if not recording_id or not title or recording_id in seen:
                continue
            seen.add(recording_id)
            release = _best_release(item.get("releases"))
            release_group = release.get("release-group", {}) if release else {}
            tracks.append(
                VerifiedTrack(
                    recording_id=recording_id,
                    track_title=title,
                    artist_name=normalized_name,
                    artist_mbid=artist_id,
                    album_title=str(release.get("title")) if release and release.get("title") else None,
                    release_year=_release_year(release),
                    release_id=str(release.get("id")) if release and release.get("id") else None,
                    release_group_id=(
                        str(release_group.get("id"))
                        if isinstance(release_group, dict) and release_group.get("id")
                        else None
                    ),
                )
            )
            if len(tracks) >= bounded:
                break
        return tracks

    async def _get(self, path: str, *, params: dict[str, object]) -> dict:
        async with self._spacing_lock:
            if self._last_request_at is not None:
                remaining = self.min_interval - (self.clock() - self._last_request_at)
                if remaining > 0:
                    await self.sleep(remaining)
            self._last_request_at = self.clock()
            payload = await self.requester.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
        return payload or {}


def _best_release(value: object) -> dict:
    releases = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    return min(releases, key=lambda item: str(item.get("date") or "9999"), default={})


def _release_year(release: dict) -> int | None:
    year = str(release.get("date") or "")[:4]
    return int(year) if len(year) == 4 and year.isdigit() else None
