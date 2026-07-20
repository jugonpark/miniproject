from __future__ import annotations

import json
import logging

from fastmcp import FastMCP

from .config import Settings
from .database import Database
from .models import CandidateArtist, MusicRequest, PlaylistDraft, VerifiedTrack
from .providers.cover_art import CoverArtProvider
from .providers.lastfm import LastFmProvider
from .providers.itunes import ITunesProvider
from .providers.musicbrainz import MusicBrainzProvider
from .postgres_database import PostgresDatabase
from .services.discovery import DiscoveryService
from .services.recommendation import compose_playlist as compose
from .services.verification import VerificationService
from .services.scoring import evaluate_tracks
from .services.constraints import curated_origin, discovery_tags_by_category, is_domestic_request, is_korean_indie_request

settings = Settings.from_env()
logging.getLogger("moodwave").setLevel(logging.INFO)
database = PostgresDatabase(settings.database_path) if settings.database_path.startswith(("postgres://", "postgresql://")) else Database(settings.database_path)
database.initialize()
mcp = FastMCP("MOODWAVE")


def _discovery() -> DiscoveryService | None:
    return DiscoveryService(LastFmProvider(settings.lastfm_api_key)) if settings.lastfm_api_key else None


def _verification() -> VerificationService | None:
    if not settings.musicbrainz_user_agent:
        return None
    itunes = ITunesProvider(base_url=settings.itunes_search_base_url, country=settings.itunes_search_country, timeout=settings.itunes_search_timeout) if settings.itunes_search_enabled else None
    track_provider = LastFmProvider(settings.lastfm_api_key) if settings.lastfm_api_key else None
    return VerificationService(MusicBrainzProvider(settings.musicbrainz_user_agent), CoverArtProvider(), itunes=itunes, track_provider=track_provider)


@mcp.tool
async def discover_music_candidates(
    moods: list[str], activities: list[str], vocal_preference: str | None = None,
    region: str = "mixed", limit: int = 20, recommendation_intent: dict | None = None, request_id: str = "",
) -> list[CandidateArtist]:
    """Find artists related to the requested mood and activity."""
    service = _discovery()
    if service is None:
        raise RuntimeError("LASTFM_API_KEY is required")
    values = [*moods, *activities, *([vocal_preference] if vocal_preference else [])]
    groups = discovery_tags_by_category(region, values, recommendation_intent)
    quotas = {"current_state": 6, "target_state": 10, "transition": 4, "activity": 6, "scene": 8, "genre": 6, "vocal": 4}
    candidates = await service.discover_grouped(groups, quotas, limit)
    if region == "domestic" and not groups.get("scene") and not groups.get("genre"):
        country_candidates = await service.discover_country("Korea, Republic of", limit)
        merged = {candidate.name.casefold(): candidate for candidate in candidates}
        for candidate in country_candidates:
            key = candidate.name.casefold()
            current = merged.get(key)
            merged[key] = candidate if current is None else current.model_copy(update={"matched_categories": list(dict.fromkeys([*current.matched_categories, "country_seed"])), "appearance_count": current.appearance_count + 1, "popularity": max(current.popularity, candidate.popularity)})
        candidates = sorted(merged.values(), key=lambda candidate: (-(curated_origin(candidate.name) == "VERIFIED_KR"), -("country_seed" in candidate.matched_categories), -candidate.appearance_count, -candidate.popularity))[:limit]
    logging.getLogger("moodwave").warning(
        "discovery_summary=%s",
        json.dumps({"requestId": request_id, "requestedTagsByCategory": groups, "lastFmTagPlan": (recommendation_intent or {}).get("lastFmTagPlan", {}), "rawRequest": (recommendation_intent or {}).get("rawRequest", ""), "hardConstraints": (recommendation_intent or {}).get("hardConstraints", {}), "preferences": (recommendation_intent or {}).get("preferences", {}), "emotionalArc": (recommendation_intent or {}).get("emotionalArc", {}), "priorityOrder": (recommendation_intent or {}).get("priorityOrder", []), "rawCandidates": len(candidates), "deduplicatedCandidates": len(candidates), "candidatesBeforeDomesticFilter": len(candidates), "candidatesAfterDomesticFilter": len(candidates)}, ensure_ascii=False),
    )
    return candidates


@mcp.tool
async def expand_similar_artists(
    seed_artists: list[str], tags: list[str], limit: int = 10,
) -> list[CandidateArtist]:
    """Expand artist candidates when discovery variety is insufficient."""
    service = _discovery()
    if service is None:
        raise RuntimeError("LASTFM_API_KEY is required")
    return await service.expand(seed_artists, limit)


@mcp.tool
async def verify_music_tracks(
    artist_candidates: list[dict | str], region: str = "mixed", limit_per_artist: int = 5,
    conditions: list[str] | None = None, original_request: str = "", recommendation_intent: dict | None = None, request_id: str = "", target_count: int = 10,
) -> list[VerifiedTrack]:
    """Verify real recordings with MusicBrainz and attach cover art when available."""
    service = _verification()
    if service is None:
        raise RuntimeError("MUSICBRAINZ_USER_AGENT is required")
    candidates = [
        CandidateArtist.model_validate(candidate)
        if isinstance(candidate, dict)
        else CandidateArtist(name=candidate, source="agent")
        for candidate in artist_candidates
    ]
    values = [*(conditions or []), original_request]
    strict = is_domestic_request(region, values)
    return await service.verify(candidates, limit_per_artist, strict_country_filter=strict, korean_indie=is_korean_indie_request(values), target_count=target_count)


@mcp.tool
def compose_playlist(
    verified_tracks: list[VerifiedTrack], conditions: list[str], region: str = "mixed",
    track_count: int = 10, original_request: str = "", familiar_artists: list[str] | None = None, recommendation_intent: dict | None = None, selected_candidates: list[dict] | None = None, request_id: str = "",
) -> PlaylistDraft | dict:
    """Compose the final playlist exclusively from verified track input."""
    if not verified_tracks:
        return {"success": False, "code": "EMPTY_TRACK_LIST", "message": "플레이리스트를 구성할 검증된 곡이 없습니다.", "retryable": False}
    values = [*conditions, original_request]
    domestic = is_domestic_request(region, values)
    korean_indie = is_korean_indie_request(values)
    request = MusicRequest(
        conditions=conditions, region=region, free_text=original_request or None,
        familiar_artists=familiar_artists or [], count=track_count,
        artist_origin_country="KR" if domestic else None,
        scene="KOREAN_INDIE" if korean_indie else None,
        strict_country_filter=domestic,
        allow_foreign_artists=not domestic,
        recommendation_intent=recommendation_intent,
    )
    allowed = {track.candidate_id for track in verified_tracks if track.candidate_id}
    seen: set[str] = set()
    valid_roles = {"EMPATHY", "GROUNDING", "TRANSITION", "TARGET", "CLOSURE"}
    selected = []
    for item in selected_candidates or []:
        candidate = item.get("candidateId") if isinstance(item, dict) else None
        if candidate in allowed and candidate not in seen and item.get("role") in valid_roles and isinstance(item.get("reason"), str):
            seen.add(candidate)
            selected.append(item)
    scored = evaluate_tracks(verified_tracks, recommendation_intent or {}) if recommendation_intent else []
    draft = compose(verified_tracks, request, selected_candidates=selected)
    logging.getLogger("moodwave").warning("recommendation_summary=%s", json.dumps({"requestId": request_id, "topScoredCandidates": [{"candidateId": item.features.candidate_id, "artist": item.track.artist_name, "track": item.track.track_title, "totalScore": item.features.total_score, "chatIntentScore": item.features.chat_intent_score, "chatIntentBreakdown": item.features.chat_intent_breakdown, "availableDimensions": item.features.available_dimensions, "scoreReasons": item.features.score_reasons} for item in scored[:20]], "finalCandidateIds": [track.candidate_id for track in draft.tracks], "finalPlaylistTracks": [{"artist": track.artist, "track": track.title, "role": track.role} for track in draft.tracks], "status": draft.recommendation_status}, ensure_ascii=False))
    logging.getLogger("moodwave").warning("recommendation_evidence=%s", json.dumps({"requestId": request_id, "trackEvidence": [{"candidateId": item.track.candidate_id, "trackTopTags": item.track.track_top_tags, "discoveryTags": item.track.discovery_tags, "positiveTagMatches": item.features.positive_tag_matches, "negativeTagMatches": item.features.negative_tag_matches, "clusterScores": item.features.cluster_scores, "finalTrackScore": item.features.total_score} for item in scored], "artistDiversityResult": len({track.artist.casefold() for track in draft.tracks}), "finalCandidateIds": [track.candidate_id for track in draft.tracks]}, ensure_ascii=False))
    if not draft.tracks:
        return {"success": False, "code": "INSUFFICIENT_VERIFIED_CANDIDATES", "message": "조건에 맞는 국내 인디 음악을 충분히 확인하지 못했어요. 확인된 곡만 만나보거나 검색 범위를 조금 넓힐 수 있어요.", "choices": ["확인된 국내 인디 곡만 보기", "다른 국내 장르까지 넓히기", "선택 수정하기"]}
    return draft


@mcp.tool
def save_playlist(draft: PlaylistDraft, idempotency_key: str) -> dict:
    """Persist a playlist only after an explicit user save action."""
    return database.save_playlist(draft, idempotency_key).model_dump(mode="json")


@mcp.tool
def list_playlists(limit: int = 20, offset: int = 0) -> list[dict]:
    """List saved playlists newest first."""
    return [item.model_dump(mode="json") for item in database.list_playlists(limit, offset)]


@mcp.tool
def get_playlist(playlist_id: int) -> dict:
    """Get one saved playlist and its ordered tracks."""
    return database.get_playlist(playlist_id).model_dump(mode="json")


@mcp.tool
def delete_playlist(playlist_id: int) -> dict:
    """Delete a playlist and its tracks."""
    database.delete_playlist(playlist_id)
    return {"deleted": True, "playlist_id": playlist_id}


def main() -> None:
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
