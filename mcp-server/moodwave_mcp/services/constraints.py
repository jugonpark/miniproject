from __future__ import annotations

from hashlib import sha256

from moodwave_mcp.models import MusicRequest, VerifiedTrack
from .normalization import normalize_music_name

KOREAN_INDIE_TAGS = ["korean indie", "k-indie", "korean singer-songwriter", "korean indie rock", "korean dream pop", "korean acoustic"]
_DISCOVERY_TAGS = {
    "blocked": ["introspective", "moody", "atmospheric"],
    "calm": ["calm", "mellow", "soft"],
    "focus": ["focus", "instrumental", "ambient"],
}
_CURATED_KR = {
    normalize_music_name(name)
    for name in ["혁오", "HYUKOH", "검정치마", "The Black Skirts", "새소년", "SE SO NEON", "잔나비", "JANNABI", "ADOY", "wave to earth", "카더가든", "Car, the garden", "10CM", "쏜애플", "THORNAPPLE", "치즈", "CHEEZE", "우효", "OOHYO", "선우정아", "Sunwoojunga", "소수빈", "SURL", "Lacuna", "Meaningful Stone"]
}

def is_domestic_request(region: str, values: list[str]) -> bool:
    text = " ".join(values).casefold()
    return region == "domestic" or any(token in text for token in ["국내", "한국", "korean", "k-indie", "k indie"])

def is_korean_indie_request(values: list[str]) -> bool:
    text = " ".join(values).casefold()
    return any(token in text for token in ["국내 인디", "한국 인디", "korean indie", "k-indie", "k indie"])

def discovery_tags(region: str, values: list[str]) -> list[str]:
    text = " ".join(values).casefold()
    tags = list(KOREAN_INDIE_TAGS[:4]) if region == "domestic" else []
    groups = {
        "blocked": ["blocked", "막힌", "답답"],
        "calm": ["calm", "차분", "평온"],
        "focus": ["focus", "study", "공부", "집중"],
    }
    for group, tokens in groups.items():
        if any(token in text for token in tokens):
            tags.extend(_DISCOVERY_TAGS[group])
    if not tags:
        tags = [value for value in values if value and value.isascii()]
    return list(dict.fromkeys(tags))

def curated_origin(artist: str) -> str:
    return "VERIFIED_KR" if normalize_music_name(artist) in _CURATED_KR else "UNKNOWN"

def candidate_id(track: VerifiedTrack) -> str:
    raw = f"{track.recording_id}|{normalize_music_name(track.artist_name)}|{normalize_music_name(track.track_title)}"
    return "candidate:" + sha256(raw.encode("utf-8")).hexdigest()[:16]

def enforce_track_constraints(tracks: list[VerifiedTrack], request: MusicRequest) -> list[VerifiedTrack]:
    if not request.strict_country_filter:
        return tracks
    return [track for track in tracks if track.origin_status == "VERIFIED_KR" and track.artist_country == "KR" and (request.scene != "KOREAN_INDIE" or track.scene_match == "KOREAN_INDIE")]
