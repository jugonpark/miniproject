from __future__ import annotations

from collections.abc import Iterable

from moodwave_mcp.models import MusicRequest, PlaylistDraft, RecommendedTrack, VerifiedTrack

from .normalization import normalize_tags
from .youtube_link import create_youtube_music_url


def compose_playlist(
    tracks: Iterable[VerifiedTrack],
    request: MusicRequest,
    familiar_ratio: float = 0.6,
    max_tracks_per_artist: int = 2,
) -> PlaylistDraft:
    conditions = set(normalize_tags(request.conditions))
    familiar_artists = set(normalize_tags(request.familiar_artists))
    unique_tracks: list[VerifiedTrack] = []
    seen_recordings: set[str] = set()
    for track in tracks:
        if track.recording_id not in seen_recordings:
            seen_recordings.add(track.recording_id)
            unique_tracks.append(track)
    ranked = sorted(
        unique_tracks,
        key=lambda track: (-len(conditions & set(normalize_tags(track.tags))), -track.popularity),
    )
    familiar = [track for track in ranked if track.artist.strip().casefold() in familiar_artists]
    discovery = [track for track in ranked if track.artist.strip().casefold() not in familiar_artists]
    selected: list[VerifiedTrack] = []
    selected_recordings: set[str] = set()
    artist_counts: dict[str, int] = {}

    def add_from(candidates: Iterable[VerifiedTrack], limit: int) -> None:
        for track in candidates:
            artist = track.artist.strip().casefold()
            if (
                len(selected) >= limit
                or track.recording_id in selected_recordings
                or artist_counts.get(artist, 0) >= max_tracks_per_artist
            ):
                continue
            selected.append(track)
            selected_recordings.add(track.recording_id)
            artist_counts[artist] = artist_counts.get(artist, 0) + 1

    familiar_target = round(request.count * familiar_ratio)
    add_from(familiar, familiar_target)
    add_from(discovery, familiar_target + (request.count - familiar_target))
    add_from(ranked, request.count)
    recommended = [
        RecommendedTrack(
            recording_id=track.recording_id,
            title=track.title,
            artist=track.artist,
            artist_id=track.artist_id,
            release_id=track.release_id,
            release_title=track.release_title,
            cover_url=track.cover_url,
            youtube_music_url=create_youtube_music_url(track.title, track.artist),
            familiar=track.artist.strip().casefold() in familiar_artists,
        )
        for track in selected
    ]
    return PlaylistDraft(
        title=f"Moodwave: {', '.join(request.conditions)}",
        request=request,
        tracks=recommended,
    )
