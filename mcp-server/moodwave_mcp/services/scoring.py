from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import BaseModel, Field

from moodwave_mcp.models import VerifiedTrack
from .normalization import normalize_music_name, normalize_tags


class HardConstraintResult(BaseModel):
    passed: bool
    failed_reasons: list[str] = Field(default_factory=list)


class TrackRecommendationFeatures(BaseModel):
    candidate_id: str
    hard_constraint_result: HardConstraintResult
    scene_score: float | None = None
    energy_score: float | None = None
    mood_score: float | None = None
    activity_score: float | None = None
    vocal_score: float | None = None
    novelty_score: float | None = None
    popularity_score: float | None = None
    chat_intent_score: float
    chat_intent_breakdown: dict[str, float]
    emotional_arc_score: float | None = None
    total_score: float
    available_dimensions: list[str]
    score_reasons: list[str]
    positive_tag_matches: list[str] = Field(default_factory=list)
    negative_tag_matches: list[str] = Field(default_factory=list)
    cluster_scores: dict[str, float] = Field(default_factory=dict)


@dataclass(frozen=True)
class ScoredTrack:
    track: VerifiedTrack
    features: TrackRecommendationFeatures


def hard_constraint_result(track: VerifiedTrack, intent: dict) -> HardConstraintResult:
    hard = intent.get("hardConstraints") or {}
    reasons: list[str] = []
    country = (track.artist_country or "").upper()
    if track.origin_status == "VERIFIED_FOREIGN":
        reasons.append("VERIFIED_FOREIGN_ARTIST")
    if country and country in {str(value).upper() for value in hard.get("excludedCountries") or []}:
        reasons.append("EXCLUDED_COUNTRY")
    allowed = {str(value).upper() for value in hard.get("allowedCountries") or []}
    if allowed and not country:
        reasons.append("UNKNOWN_ARTIST_ORIGIN")
    if allowed and country and country not in allowed:
        reasons.append("COUNTRY_NOT_ALLOWED")
    artist = normalize_music_name(track.artist_name)
    if artist in {normalize_music_name(value) for value in hard.get("excludedArtists") or []}:
        reasons.append("EXCLUDED_ARTIST")
    included = {normalize_music_name(value) for value in hard.get("includedArtists") or []}
    if included and artist not in included:
        reasons.append("ARTIST_NOT_INCLUDED")
    tags = set(normalize_tags(track.tags))
    if tags & set(normalize_tags(hard.get("excludedGenres") or [])):
        reasons.append("EXCLUDED_GENRE")
    title = normalize_music_name(track.track_title)
    if hard.get("excludeLiveRemix", True) and any(token in title for token in [" live", "remix", "remaster", "concert"]):
        reasons.append("EXCLUDED_VERSION")
    if hard.get("instrumentalOnly") and not tags & {"instrumental", "ambient"}:
        reasons.append("INSTRUMENTAL_NOT_VERIFIED")
    return HardConstraintResult(passed=not reasons, failed_reasons=reasons)


def score_track(track: VerifiedTrack, intent: dict) -> TrackRecommendationFeatures:
    hard = hard_constraint_result(track, intent)
    preferences = intent.get("preferences") or {}
    required_scenes = set((intent.get("hardConstraints") or {}).get("requiredScenes") or [])
    requested_genres = set(normalize_tags([*(preferences.get("genres") or []), *((intent.get("hardConstraints") or {}).get("includedGenres") or [])]))
    tags = set(normalize_tags(track.tags))
    plan = intent.get("lastFmTagPlan") or {}
    positive_plan_tags = {str(item.get("tag")) for group, items in plan.items() if group != "negative" for item in items if isinstance(item, dict)}
    negative_plan_tags = {str(item.get("tag")) for item in plan.get("negative") or [] if isinstance(item, dict)}
    positive_matches = sorted(tags & positive_plan_tags); negative_matches = sorted(tags & negative_plan_tags)
    clusters = {"ENERGY_HIGH": {"energetic", "high energy", "dance"}, "ENERGY_LOW": {"mellow", "downtempo", "chillout"}, "CALM_TEXTURE": {"ambient", "instrumental", "piano", "acoustic"}, "DARK_MOOD": {"melancholic"}, "POP_ACCESSIBLE": {"pop", "dance"}, "ELECTRONIC_TEXTURE": {"electronic", "ambient"}, "ROCK_ENERGY": {"rock", "alternative"}}
    cluster_scores = {name: max((track.tag_evidence.get(tag, .3) for tag in tags & members), default=0.0) for name, members in clusters.items()}
    reasons: list[str] = []

    scene_score = None
    if required_scenes or requested_genres:
        scene_score = 15.0 if track.scene_match in required_scenes or bool(tags & requested_genres) or ("indie" in requested_genres and bool(tags & {"korean indie", "k-indie", "indie"})) else 0.0
        if scene_score: reasons.append("required scene matched")

    energy_score = None
    if preferences.get("energy") is not None:
        positive_energy = tags & {"energetic", "upbeat", "exciting", "danceable", "powerful", "lively", "rock", "dance"}
        negative_energy = tags & {"mellow", "melancholic", "slow", "quiet", "low-energy", "soft"}
        if positive_energy or negative_energy:
            energy_score = 30.0 if positive_energy and not negative_energy else 0.0
            if energy_score: reasons.append("high-energy evidence matched")

    mood_terms = " ".join(map(str, preferences.get("moods") or [])).casefold()
    mood_targets = set()
    if any(token in mood_terms for token in ["차분", "평온", "calm"]): mood_targets |= {"calm", "mellow", "soft", "ambient"}
    if any(token in mood_terms for token in ["답답", "막힌", "blocked"]): mood_targets |= {"introspective", "moody", "atmospheric"}
    mood_score = (20.0 if tags & mood_targets else 0.0) if mood_targets and tags else None

    activities = {str(value).upper() for value in preferences.get("activities") or []}
    activity_targets = {"focus", "study", "instrumental", "ambient"} if "STUDY" in activities else ({"upbeat", "energetic", "rock", "dance"} if "WORKOUT" in activities else set())
    activity_score = (15.0 if tags & activity_targets else 0.0) if activity_targets and tags else None
    if activity_score: reasons.append("activity evidence matched")

    vocal_preference = preferences.get("vocalAmount")
    vocal_evidence = tags & {"instrumental", "ambient", "acoustic", "vocal", "singer-songwriter"}
    vocal_score = None
    if vocal_preference in {"none", "low"} and vocal_evidence:
        vocal_score = 10.0 if vocal_evidence & {"instrumental", "ambient", "acoustic"} else 0.0
        if vocal_score: reasons.append("low-vocal evidence matched")
    elif vocal_preference == "prominent" and vocal_evidence:
        vocal_score = 10.0 if vocal_evidence & {"vocal", "singer-songwriter"} else 0.0

    popularity_value = track.popularity_score
    popularity_preference = preferences.get("popularity", "balanced")
    popularity_unit = min(1.0, math.log1p(popularity_value) / math.log1p(100000)) if popularity_value > 0 else None
    popularity_score = None if popularity_unit is None else round(5 * (1 - popularity_unit if popularity_preference == "hidden_gems" else popularity_unit), 3)
    novelty_score = None if popularity_unit is None else round(5 * (1 - popularity_unit if preferences.get("familiarity") == "discovery" else popularity_unit), 3)

    arc = intent.get("emotionalArc") or {}
    arc_targets = {"focus", "study", "ambient", "calm"} if "focus" in str(arc.get("end", "")).casefold() else mood_targets
    emotional_arc_score = (20.0 if tags & arc_targets else 0.0) if arc_targets and tags else None

    # Popularity cannot become the primary fallback when no musical evidence
    # supports the requested state, goal, activity, or scene.
    has_music_evidence = bool(positive_matches) or any(value is not None for value in (energy_score, mood_score, activity_score, scene_score, vocal_score))
    if not has_music_evidence:
        popularity_score = None
        novelty_score = None

    chat_breakdown = {
        "scene_genre": 6.0 if scene_score and scene_score > 0 else 0.0,
        "activity": 4.0 if activity_score and activity_score > 0 else 0.0,
        "vocal_lyrics": 4.0 if vocal_score and vocal_score > 0 else 0.0,
        "familiarity_popularity": 3.0 if novelty_score is not None else 0.0,
        "explicit_alignment": 3.0 if hard.passed else 0.0,
    }
    chat_intent_score = sum(chat_breakdown.values())
    dimensions = {"energy": energy_score, "scene": scene_score, "chat": chat_intent_score, "activity": activity_score, "vocal": vocal_score, "novelty": novelty_score, "popularity": popularity_score}
    available = {name: value for name, value in dimensions.items() if value is not None}
    max_scores = {"energy": 30, "scene": 15, "chat": 20, "activity": 15, "vocal": 10, "novelty": 5, "popularity": 5}
    denominator = sum(max_scores[name] for name in available)
    total = round(sum(available.values()) / denominator * 100, 2) if hard.passed and denominator else 0.0
    if negative_matches and total: total = max(0.0, round(total - min(20.0, len(negative_matches) * 8.0), 2))
    return TrackRecommendationFeatures(candidate_id=track.candidate_id or track.recording_id, hard_constraint_result=hard, scene_score=scene_score, energy_score=energy_score, mood_score=mood_score, activity_score=activity_score, vocal_score=vocal_score, novelty_score=novelty_score, popularity_score=popularity_score, chat_intent_score=chat_intent_score, chat_intent_breakdown=chat_breakdown, emotional_arc_score=emotional_arc_score, total_score=total, available_dimensions=list(available), score_reasons=reasons, positive_tag_matches=positive_matches, negative_tag_matches=negative_matches, cluster_scores=cluster_scores)


def evaluate_tracks(tracks: list[VerifiedTrack], intent: dict) -> list[ScoredTrack]:
    scored = [ScoredTrack(track, score_track(track, intent)) for track in tracks]
    return sorted(
        (item for item in scored if item.features.hard_constraint_result.passed),
        key=lambda item: (
            len(item.features.negative_tag_matches),
            -len(item.features.positive_tag_matches),
            -sum(item.features.cluster_scores.values()),
            -item.features.total_score,
            item.track.recording_id,
        ),
    )
