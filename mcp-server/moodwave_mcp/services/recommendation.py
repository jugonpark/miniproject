from __future__ import annotations

from collections.abc import Iterable

from moodwave_mcp.models import MusicRequest, PlaylistDraft, RecommendedTrack, VerifiedTrack

from .normalization import normalize_tags
from .constraints import enforce_track_constraints
from .youtube_link import create_youtube_music_url
from .scoring import evaluate_tracks


def compose_playlist(
    tracks: Iterable[VerifiedTrack],
    request: MusicRequest,
    familiar_ratio: float = 0.6,
    max_tracks_per_artist: int = 2,
    selected_candidates: list[dict] | None = None,
) -> PlaylistDraft:
    conditions = set(normalize_tags(request.conditions))
    familiar_artists = set(normalize_tags(request.familiar_artists))
    unique_tracks: list[VerifiedTrack] = []
    seen_recordings: set[str] = set()
    for track in enforce_track_constraints(list(tracks), request):
        if track.recording_id not in seen_recordings:
            seen_recordings.add(track.recording_id)
            unique_tracks.append(track)
    scored = evaluate_tracks(unique_tracks, request.recommendation_intent) if request.recommendation_intent else []
    eligible_tracks = [item.track for item in scored] if request.recommendation_intent else unique_tracks
    selection = {item.get("candidateId"): item for item in (selected_candidates or [])}
    selected_order = {item.get("candidateId"): index for index, item in enumerate(selected_candidates or [])}
    ranked = sorted((track for track in eligible_tracks if track.candidate_id in selected_order), key=lambda track: selected_order[track.candidate_id]) if selected_order else (eligible_tracks if request.recommendation_intent else sorted(unique_tracks, key=lambda track: (-len(conditions & set(normalize_tags(track.tags))), -track.popularity)))
    features = {item.track.recording_id: item.features for item in scored}
    familiar = [track for track in ranked if track.artist.strip().casefold() in familiar_artists]
    discovery = [track for track in ranked if track.artist.strip().casefold() not in familiar_artists]
    selected: list[VerifiedTrack] = []
    selected_recordings: set[str] = set()
    artist_counts: dict[str, int] = {}

    def add_from(candidates: Iterable[VerifiedTrack], limit: int, artist_cap: int) -> None:
        for track in candidates:
            artist = track.artist.strip().casefold()
            if (
                len(selected) >= limit
                or track.recording_id in selected_recordings
                or artist_counts.get(artist, 0) >= artist_cap
                or (selected and selected[-1].artist.strip().casefold() == artist)
            ):
                continue
            selected.append(track)
            selected_recordings.add(track.recording_id)
            artist_counts[artist] = artist_counts.get(artist, 0) + 1

    if selected_candidates:
        add_from(ranked, request.count, 1)
        add_from(ranked, request.count, max_tracks_per_artist)
    else:
        familiar_target = round(request.count * familiar_ratio)
        add_from(familiar, familiar_target, 1)
        add_from(discovery, familiar_target + (request.count - familiar_target), 1)
        add_from(ranked, request.count, 1)
        add_from(ranked, request.count, max_tracks_per_artist)
    roles = ["EMPATHY", "GROUNDING", "TRANSITION", "TARGET", "CLOSURE"]
    recommended = [
        RecommendedTrack(
            position=position,
            recording_id=track.recording_id,
            candidate_id=track.candidate_id,
            title=track.title,
            artist=track.artist,
            artist_id=track.artist_id,
            release_id=track.release_id,
            release_title=track.release_title,
            release_year=track.release_year,
            cover_url=track.cover_url,
            tags=track.tags,
            discovery_type=("familiar" if track.artist.strip().casefold() in familiar_artists else "discovery"),
            recommendation_reason=(selection.get(track.candidate_id, {}).get("reason") or (" · ".join(features[track.recording_id].score_reasons) if track.recording_id in features and features[track.recording_id].score_reasons else f"{', '.join(track.tags[:2]) or '검증된 음악 특성'} 근거를 반영했습니다.")),
            youtube_music_url=create_youtube_music_url(track.title, track.artist),
            familiar=track.artist.strip().casefold() in familiar_artists,
            role=selection.get(track.candidate_id, {}).get("role") or (roles[round((position - 1) * 4 / max(1, len(selected) - 1))] if request.recommendation_intent else None),
        )
        for position, track in enumerate(selected, start=1)
    ]
    return PlaylistDraft(
        title=f"Moodwave: {', '.join(request.conditions)}",
        request=request,
        tracks=recommended,
        recommendation_status="SUCCESS" if len(recommended) >= request.count else "PARTIAL",
    )
