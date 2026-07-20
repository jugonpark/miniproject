from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable

from moodwave_mcp.models import CandidateArtist, VerifiedTrack

from .cache import TTLCache, get_or_create_async
from .normalization import normalize_music_name
from .constraints import candidate_id, curated_origin

logger = logging.getLogger("moodwave.verification")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


class VerificationService:
    def __init__(
        self,
        musicbrainz,
        cover_art,
        *,
        itunes=None,
        track_provider=None,
        cache_ttl: float = 300,
        max_results: int = 50,
    ) -> None:
        self.musicbrainz = musicbrainz
        self.cover_art = cover_art
        self.itunes = itunes
        self.track_provider = track_provider
        self.cache = TTLCache(cache_ttl)
        self.max_results = min(50, max(1, max_results))

    async def verify(
        self,
        artists: Iterable[CandidateArtist],
        tracks_per_artist: int = 5,
        strict_country_filter: bool = False,
        korean_indie: bool = False,
    ) -> list[VerifiedTrack]:
        bounded_per_artist = min(2, max(0, tracks_per_artist))
        artist_list = list(artists)[:8]
        verified: list[VerifiedTrack] = []
        seen: set[str] = set()
        seen_names: set[tuple[str, str]] = set()
        stats = {"similarArtists": sum(artist.source == "lastfm:similar" for artist in artist_list), "topTracks": 0, "rawCandidates": 0, "deduplicatedCandidates": 0, "verifiedKoreanArtists": 0, "foreignArtists": 0, "unknownOriginArtists": 0, "iTunesStrongMatches": 0, "iTunesWeakMatches": 0, "iTunesNotFound": 0, "musicBrainzMatches": 0, "musicBrainzNotFound": 0, "finalVerifiedCandidates": 0}
        rejections: list[dict[str, str]] = []
        for artist in artist_list:
            origin_status, artist_country = "UNKNOWN", None
            if strict_country_filter:
                origin_status = curated_origin(artist.name)
                artist_country = "KR" if origin_status == "VERIFIED_KR" else None
                if origin_status == "UNKNOWN":
                    origin_lookup = getattr(self.musicbrainz, "artist_origin", None)
                    if origin_lookup:
                        try:
                            origin_status, artist_country = await origin_lookup(artist.name)
                        except Exception as error:
                            logger.warning("artist origin lookup failed artist=%s error=%s", artist.name, type(error).__name__)
                if origin_status == "VERIFIED_FOREIGN":
                    stats["foreignArtists"] += 1
                    rejections.append({"artist": artist.name, "reason": "VERIFIED_FOREIGN_ARTIST"})
                    continue
                if origin_status != "VERIFIED_KR":
                    stats["unknownOriginArtists"] += 1
                    rejections.append({"artist": artist.name, "reason": "UNKNOWN_ARTIST_ORIGIN"})
                    continue
                stats["verifiedKoreanArtists"] += 1
            try:
                if self.track_provider is None:
                    tracks = await get_or_create_async(self.cache, ("verify", artist.name.strip().casefold(), bounded_per_artist), lambda artist=artist: self.musicbrainz.verify_artist_tracks(artist.name, bounded_per_artist))
                    stats["musicBrainzMatches"] += len(tracks)
                    stats["musicBrainzNotFound"] += not tracks
                else:
                    candidates = await self.track_provider.top_tracks(artist.name, bounded_per_artist)
                    stats["topTracks"] += len(candidates)
                    stats["rawCandidates"] += len(candidates)
                    unique_candidates = []
                    candidate_keys: set[tuple[str, str]] = set()
                    for candidate in candidates:
                        key = (normalize_music_name(candidate.artist), normalize_music_name(candidate.title))
                        if key not in candidate_keys:
                            candidate_keys.add(key)
                            unique_candidates.append(candidate)
                    stats["deduplicatedCandidates"] += len(unique_candidates)
                    tracks = []
                    for candidate in unique_candidates:
                        track = None
                        try:
                            track = await self.musicbrainz.verify_track(candidate)
                        except Exception as error:
                            logger.warning("musicbrainz track lookup failed artist=%s track=%s error=%s", candidate.artist, candidate.title, type(error).__name__)
                        if track is None:
                            stats["musicBrainzNotFound"] += 1
                            rejections.append({"artist": candidate.artist, "track": candidate.title, "reason": "MUSICBRAINZ_NOT_FOUND"})
                        else:
                            stats["musicBrainzMatches"] += 1
                        if track is None and self.itunes is not None:
                            alias_lookup = getattr(self.musicbrainz, "artist_aliases", None)
                            try:
                                aliases = await alias_lookup(candidate.artist) if alias_lookup else []
                            except Exception:
                                aliases = []
                            detailed_lookup = getattr(self.itunes, "search_track_detailed", None)
                            if detailed_lookup:
                                track, rejection_reason = await detailed_lookup(candidate.artist, candidate.title, aliases=aliases)
                            else:
                                track, rejection_reason = await self.itunes.search_track(candidate.artist, candidate.title, aliases=aliases), "ITUNES_NOT_FOUND"
                            if track is None:
                                weak = rejection_reason in {"LOW_TITLE_SCORE", "LOW_ARTIST_SCORE", "VERSION_CONFLICT"}
                                stats["iTunesWeakMatches" if weak else "iTunesNotFound"] += 1
                                rejections.append({"artist": candidate.artist, "track": candidate.title, "reason": rejection_reason or "ITUNES_NOT_FOUND"})
                            else:
                                stats["iTunesStrongMatches"] += 1
                        if track is not None:
                            tracks.append(track)
            except Exception as error:
                logger.warning("track verification failed artist=%s error=%s detail=%s", artist.name, type(error).__name__, error)
                continue
            if self.track_provider is None and self.itunes is not None and len(tracks) < bounded_per_artist:
                try:
                    tracks = [*tracks, *await self.itunes.search_artist_tracks(artist.name, bounded_per_artist - len(tracks))]
                except Exception as error:
                    logger.warning("itunes fallback failed artist=%s error=%s detail=%s", artist.name, type(error).__name__, error)
            covers = await asyncio.gather(
                *(self.cover_art.find_cover(track.release_id, track.release_group_id) for track in tracks),
                return_exceptions=True,
            )
            for track, cover in zip(tracks, covers, strict=True):
                if isinstance(cover, Exception):
                    logger.warning("cover lookup failed recording_id=%s error=%s detail=%s", track.recording_id, type(cover).__name__, cover)
                if track.recording_id in seen:
                    continue
                name_key = (normalize_music_name(track.artist_name), normalize_music_name(track.track_title))
                if name_key in seen_names:
                    continue
                seen.add(track.recording_id)
                seen_names.add(name_key)
                cover_url = track.cover_image_url if isinstance(cover, Exception) or cover is None else cover
                enriched = VerifiedTrack.model_validate(
                        {
                            **track.model_dump(),
                            "cover_image_url": cover_url,
                            "tags": artist.tags,
                            "popularity_score": artist.popularity,
                            "artist_country": artist_country,
                            "origin_status": origin_status,
                            "scene_match": "KOREAN_INDIE" if korean_indie else None,
                        }
                    )
                verified.append(enriched.model_copy(update={"candidate_id": candidate_id(enriched)}))
                stats["finalVerifiedCandidates"] = len(verified)
                if len(verified) >= self.max_results:
                    logger.info("verification_summary=%s rejection_reasons=%s", json.dumps(stats, ensure_ascii=False), json.dumps(rejections[:50], ensure_ascii=False))
                    return verified
        logger.info("verification_summary=%s rejection_reasons=%s", json.dumps(stats, ensure_ascii=False), json.dumps(rejections[:50], ensure_ascii=False))
        return verified
