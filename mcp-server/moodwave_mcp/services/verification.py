from __future__ import annotations

from collections.abc import Iterable

from moodwave_mcp.models import CandidateArtist, VerifiedTrack

from .cache import TTLCache, get_or_create_async


class VerificationService:
    def __init__(
        self,
        musicbrainz,
        cover_art,
        *,
        cache_ttl: float = 300,
        max_results: int = 50,
    ) -> None:
        self.musicbrainz = musicbrainz
        self.cover_art = cover_art
        self.cache = TTLCache(cache_ttl)
        self.max_results = min(50, max(1, max_results))

    async def verify(
        self,
        artists: Iterable[CandidateArtist],
        tracks_per_artist: int = 5,
    ) -> list[VerifiedTrack]:
        bounded_per_artist = min(25, max(0, tracks_per_artist))
        verified: list[VerifiedTrack] = []
        seen: set[str] = set()
        for artist in list(artists)[: self.max_results]:
            try:
                tracks = await get_or_create_async(
                    self.cache,
                    ("verify", artist.name.strip().casefold(), bounded_per_artist),
                    lambda artist=artist: self.musicbrainz.verify_artist_tracks(
                        artist.name,
                        bounded_per_artist,
                    ),
                )
            except Exception:
                continue
            for track in tracks:
                if track.recording_id in seen:
                    continue
                seen.add(track.recording_id)
                try:
                    cover_url = await self.cover_art.find_cover(
                        track.release_id,
                        track.release_group_id,
                    )
                except Exception:
                    cover_url = None
                verified.append(
                    VerifiedTrack.model_validate(
                        {
                            **track.model_dump(),
                            "cover_image_url": cover_url,
                            "tags": artist.tags,
                            "popularity_score": artist.popularity,
                        }
                    )
                )
                if len(verified) >= self.max_results:
                    return verified
        return verified
