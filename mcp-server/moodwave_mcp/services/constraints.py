from __future__ import annotations

from hashlib import sha256

from moodwave_mcp.models import MusicRequest, VerifiedTrack
from .normalization import normalize_music_name

KOREAN_INDIE_TAGS = ["korean indie", "k-indie", "korean singer-songwriter", "korean indie rock", "korean dream pop", "korean acoustic"]
_DISCOVERY_TAGS = {
    "blocked": ["introspective", "moody", "atmospheric"],
    "calm": ["calm", "mellow", "soft"],
    "focus": ["focus", "instrumental", "ambient"],
    "energetic": ["energetic", "upbeat", "exciting", "danceable"],
}
LASTFM_STATE_TAG_MAP = {
    "LOW": (["melancholic", "mellow"], ["acoustic", "piano"], ["high energy", "dance"]), "UNSETTLED": (["ambient", "downtempo"], ["alternative", "electronic"], ["high energy", "aggressive"]), "COMPLEX": (["alternative", "indie", "electronic"], ["experimental", "ambient"], []), "BLOCKED": (["melancholic", "downtempo"], ["ambient", "instrumental"], ["dance", "high energy"]), "CALM": (["mellow", "ambient", "downtempo"], ["acoustic", "instrumental", "piano"], ["high energy", "aggressive"]), "ENERGETIC": (["energetic", "high energy", "dance"], ["rock", "electronic", "pop"], ["melancholic", "downtempo"]),
}
LASTFM_GOAL_TAG_MAP = {
    "SOLACE": (["mellow", "acoustic", "piano"], ["melancholic"], ["high energy", "aggressive"]), "RELAXATION": (["ambient", "downtempo", "chillout"], ["instrumental", "piano"], ["high energy", "aggressive"]), "DIVERSION": (["dance", "pop", "electronic"], ["indie", "rock"], ["melancholic"]), "REVIVAL": (["energetic", "high energy", "dance"], ["rock", "electronic", "inspiring"], ["melancholic", "downtempo"]), "FOCUS": (["instrumental", "ambient", "downtempo"], ["piano", "acoustic", "electronic"], ["high energy", "aggressive"]), "MAINTENANCE": ([], [], []),
}
LASTFM_ACTIVITY_TAG_MAP = {
    "STUDY": (["instrumental", "ambient", "downtempo"], ["piano", "acoustic"]), "CODING": (["electronic", "ambient", "instrumental"], ["downtempo"]), "READING": (["acoustic", "piano", "ambient"], ["instrumental", "mellow"]), "WORKOUT": (["energetic", "high energy", "dance"], ["rock", "electronic", "hip-hop"]), "COMMUTE": (["pop", "indie", "electronic"], ["rock"]), "REST": (["ambient", "chillout", "downtempo"], ["mellow", "instrumental"]), "SLEEP": (["ambient", "instrumental", "piano"], ["downtempo"]),
}
LASTFM_TAG_ALLOWLIST = {tag for mapping in [LASTFM_STATE_TAG_MAP, LASTFM_GOAL_TAG_MAP] for value in mapping.values() for tags in value for tag in tags} | {tag for value in LASTFM_ACTIVITY_TAG_MAP.values() for tags in value for tag in tags} | set(KOREAN_INDIE_TAGS) | {"indie", "hip-hop", "rock", "pop", "electronic", "alternative", "r&b"}
INTENSITY_WEIGHTS = {1: (.5, .3, .2), 2: (.4, .35, .25), 3: (.3, .45, .25), 4: (.2, .55, .25), 5: (.15, .6, .25)}
_CURATED_KR = {
    normalize_music_name(name)
    for name in ["혁오", "HYUKOH", "검정치마", "The Black Skirts", "새소년", "SE SO NEON", "잔나비", "JANNABI", "ADOY", "wave to earth", "카더가든", "Car, the garden", "10CM", "쏜애플", "THORNAPPLE", "치즈", "CHEEZE", "우효", "OOHYO", "선우정아", "Sunwoojunga", "소수빈", "SURL", "Lacuna", "Meaningful Stone", "aespa", "NewJeans", "ILLIT", "BTS", "BLACKPINK", "LE SSERAFIM", "TWICE", "Stray Kids", "SEVENTEEN", "IU", "PSY", "Red Velvet"]
}

def is_domestic_request(region: str, values: list[str]) -> bool:
    text = " ".join(values).casefold()
    return region == "domestic" or any(token in text for token in ["국내", "한국", "korean", "k-indie", "k indie"])

def is_korean_indie_request(values: list[str]) -> bool:
    text = " ".join(values).casefold()
    return any(token in text for token in ["국내 인디", "한국 인디", "korean indie", "k-indie", "k indie"])

def discovery_tags(region: str, values: list[str]) -> list[str]:
    text = " ".join(values).casefold()
    tags = []
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

def discovery_tags_by_category(region: str, values: list[str], intent: dict | None = None) -> dict[str, list[str]]:
    intent = intent or {}
    hard = intent.get("hardConstraints") or {}
    preferences = intent.get("preferences") or {}
    text = " ".join([*values, *map(str, preferences.get("moods") or [])]).casefold()
    scene = list(KOREAN_INDIE_TAGS[:4]) if "KOREAN_INDIE" in (hard.get("requiredScenes") or []) else []
    mood = []
    for group, tokens in {
        "blocked": ["blocked", "막힌", "답답"],
        "calm": ["calm", "차분", "평온"],
        "energetic": ["energetic", "upbeat", "exciting", "에너지가 넘쳐", "들뜸", "기분 전환", "신나는"],
    }.items():
        if any(token in text for token in tokens):
            mood.extend(_DISCOVERY_TAGS[group])
    activities = " ".join(map(str, preferences.get("activities") or values)).casefold()
    activity = ["focus", "study", "ambient"] if any(token in activities for token in ["study", "focus", "공부", "집중"]) else (["energetic", "upbeat", "danceable"] if any(token in activities for token in ["workout", "revival", "운동", "활력"]) else [])
    genres = [str(value).casefold() for value in preferences.get("genres") or [] if str(value).isascii()]
    vocal = ["instrumental", "ambient"] if preferences.get("vocalAmount") in {"none", "low"} else []
    current = intent.get("currentState") or {}; target = intent.get("targetState") or {}
    state_tags = LASTFM_STATE_TAG_MAP.get(str(current.get("broadState") or "").upper(), ([], [], [])); goal_tags = LASTFM_GOAL_TAG_MAP.get(str(target.get("goal") or "").upper(), ([], [], [])); activity_tags = LASTFM_ACTIVITY_TAG_MAP.get(str(intent.get("activity") or "").upper(), (activity, []))
    intensity = max(1, min(5, int(target.get("changeIntensity") or 3))); current_weight, target_weight, transition_weight = INTENSITY_WEIGHTS[intensity]
    weighted = {
        "current_state": [(tag, current_weight if tag in state_tags[0] else current_weight * .6) for tag in [*state_tags[0], *state_tags[1]]],
        "target_state": [(tag, target_weight if tag in goal_tags[0] else target_weight * .6) for tag in [*goal_tags[0], *goal_tags[1]]],
        "transition": [(tag, transition_weight) for tag in set(state_tags[1]) & set(goal_tags[1])],
        "activity": [(tag, .7 if tag in activity_tags[0] else .4) for tag in [*activity_tags[0], *activity_tags[1]]],
        "scene": [(tag, .8) for tag in scene], "genre": [(tag, .7) for tag in genres if tag in LASTFM_TAG_ALLOWLIST], "vocal": [(tag, .5) for tag in vocal],
        "negative": [(tag, -.7) for tag in dict.fromkeys([*state_tags[2], *goal_tags[2]])],
    }
    intent["lastFmTagPlan"] = {group: [{"tag": tag, "weight": weight, "cluster": tag} for tag, weight in tags] for group, tags in weighted.items()}
    return {name: list(dict.fromkeys(tag for tag, _ in tags)) for name, tags in weighted.items() if tags and name != "negative"}

def curated_origin(artist: str) -> str:
    return "VERIFIED_KR" if normalize_music_name(artist) in _CURATED_KR else "UNKNOWN"

def candidate_id(track: VerifiedTrack) -> str:
    raw = f"{normalize_music_name(track.artist_name)}::{normalize_music_name(track.track_title)}"
    return "candidate:" + sha256(raw.encode("utf-8")).hexdigest()[:16]

def enforce_track_constraints(tracks: list[VerifiedTrack], request: MusicRequest) -> list[VerifiedTrack]:
    if not request.strict_country_filter:
        return tracks
    return [track for track in tracks if track.origin_status != "VERIFIED_FOREIGN" and track.artist_country != "JP" and (track.origin_status in {None, "UNKNOWN"} or request.scene != "KOREAN_INDIE" or track.scene_match == "KOREAN_INDIE")]
