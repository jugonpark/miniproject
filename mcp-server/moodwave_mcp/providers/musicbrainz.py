from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic

import httpx

from difflib import SequenceMatcher

from moodwave_mcp.models import TrackCandidate, VerifiedTrack
from moodwave_mcp.services.normalization import music_version, normalize_music_name

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
        self.requester = JsonRequester(
            client or httpx.AsyncClient(),
            timeout=timeout,
            sleep=sleep,
        )
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

    async def verify_track(self, candidate: TrackCandidate) -> VerifiedTrack | None:
        payload = await self._get("/recording", params={"query": f'recording:"{candidate.title}" AND artist:"{candidate.artist}"', "fmt": "json", "inc": "releases+release-groups+artist-credits", "limit": 10})
        best: tuple[float, dict, dict] | None = None
        for item in payload.get("recordings", []) if isinstance(payload.get("recordings"), list) else []:
            if not isinstance(item, dict):
                continue
            credit = next((entry.get("artist") for entry in item.get("artist-credit", []) if isinstance(entry, dict) and isinstance(entry.get("artist"), dict)), {})
            title_score = SequenceMatcher(None, normalize_music_name(candidate.title), normalize_music_name(str(item.get("title") or ""))).ratio()
            artist_score = SequenceMatcher(None, normalize_music_name(candidate.artist), normalize_music_name(str(credit.get("name") or ""))).ratio()
            if music_version(candidate.title) != music_version(str(item.get("title") or "")):
                continue
            total = title_score * .55 + artist_score * .40 + .05
            if title_score >= .80 and artist_score >= .75 and total >= .82 and (best is None or total > best[0]):
                best = (total, item, credit)
        if best is None:
            return None
        _, item, credit = best
        release = _best_release(item.get("releases"))
        group = release.get("release-group", {}) if release else {}
        return VerifiedTrack(recording_id=str(item["id"]), track_title=str(item["title"]), artist_name=str(credit.get("name") or candidate.artist), artist_mbid=str(credit.get("id")) if credit.get("id") else None, album_title=str(release.get("title")) if release.get("title") else None, release_year=_release_year(release), release_id=str(release.get("id")) if release.get("id") else None, release_group_id=str(group.get("id")) if isinstance(group, dict) and group.get("id") else None)

    async def artist_aliases(self, artist: str) -> list[str]:
        payload = await self._get("/artist", params={"query": f'artist:"{artist}"', "fmt": "json", "limit": 1})
        items = payload.get("artists")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            return []
        item = items[0]
        aliases = [str(alias.get("name")) for alias in item.get("aliases", []) if isinstance(alias, dict) and alias.get("name")]
        return [str(item.get("name")), *aliases] if item.get("name") else aliases

    async def artist_origin(self, artist: str) -> tuple[str, str | None]:
        """Return origin from the Artist entity only; release countries never count."""
        payload = await self._get("/artist", params={"query": f'artist:"{artist}"', "fmt": "json", "limit": 3})
        items = payload.get("artists")
        if not isinstance(items, list):
            return "UNKNOWN", None
        expected = normalize_music_name(artist)
        for item in items:
            if not isinstance(item, dict) or SequenceMatcher(None, expected, normalize_music_name(str(item.get("name") or ""))).ratio() < .75:
                continue
            country = str(item.get("country") or "").upper()
            area = item.get("area") if isinstance(item.get("area"), dict) else {}
            begin_area = item.get("begin-area") if isinstance(item.get("begin-area"), dict) else {}
            codes = {country, *[str(code).upper() for code in area.get("iso-3166-1-codes", [])], *[str(code).upper() for code in begin_area.get("iso-3166-1-codes", [])]}
            if "KR" in codes:
                return "VERIFIED_KR", "KR"
            if any(code for code in codes if len(code) == 2):
                return "VERIFIED_FOREIGN", next(code for code in codes if len(code) == 2)
        return "UNKNOWN", None

    async def _get(self, path: str, *, params: dict[str, object]) -> dict:
        payload = await self.requester.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            before_attempt=self._pace_attempt,
        )
        return payload or {}

    async def _pace_attempt(self, _: int) -> None:
        async with self._spacing_lock:
            if self._last_request_at is not None:
                remaining = self.min_interval - (self.clock() - self._last_request_at)
                if remaining > 0:
                    await self.sleep(remaining)
            self._last_request_at = self.clock()


def _best_release(value: object) -> dict:
    releases = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    return min(releases, key=lambda item: str(item.get("date") or "9999"), default={})


def _release_year(release: dict) -> int | None:
    year = str(release.get("date") or "")[:4]
    return int(year) if len(year) == 4 and year.isdigit() else None
