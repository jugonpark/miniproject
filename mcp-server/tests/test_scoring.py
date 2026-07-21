from moodwave_mcp.models import VerifiedTrack
from moodwave_mcp.services.scoring import evaluate_tracks, hard_constraint_result, score_track


def track(**updates):
    data = {"recording_id": "r1", "title": "Quiet Study", "artist": "Korean Artist", "tags": ["korean indie", "focus", "instrumental"], "popularity": 20, "origin_status": "VERIFIED_KR", "artist_country": "KR"}
    data.update(updates)
    return VerifiedTrack(**data)


INTENT = {
    "rawRequest": "국내 인디, 일본곡 제외, 보컬 적게, 숨은 곡",
    "hardConstraints": {"region": "domestic", "allowedCountries": ["KR"], "excludedCountries": ["JP"], "requiredScenes": ["KOREAN_INDIE"], "excludedArtists": [], "excludedGenres": [], "excludeLiveRemix": True},
    "preferences": {"moods": ["차분함"], "activities": ["STUDY"], "genres": ["indie"], "vocalAmount": "low", "familiarity": "discovery", "popularity": "hidden_gems"},
    "emotionalArc": {"start": "답답함", "middle": "grounding", "end": "focus"},
    "priorityOrder": ["explicit_chat", "hard_constraints", "emotion"],
}


def test_foreign_is_rejected_and_unknown_is_only_retained_without_strict_country_requirement():
    foreign = track(origin_status="VERIFIED_FOREIGN", artist_country="JP")
    unknown = track(recording_id="r2", origin_status="UNKNOWN", artist_country=None)
    assert not hard_constraint_result(foreign, INTENT).passed
    strict_result = hard_constraint_result(unknown, INTENT)
    assert not strict_result.passed
    assert "UNKNOWN_ARTIST_ORIGIN" in strict_result.failed_reasons
    mixed_intent = {**INTENT, "hardConstraints": {**INTENT["hardConstraints"], "allowedCountries": []}}
    assert hard_constraint_result(unknown, mixed_intent).passed


def test_excluded_artist_and_live_version_are_hard_failures():
    intent = {**INTENT, "hardConstraints": {**INTENT["hardConstraints"], "excludedArtists": ["검정치마"]}}
    assert not hard_constraint_result(track(artist="검정치마"), intent).passed
    assert not hard_constraint_result(track(title="Quiet Study (Live)"), INTENT).passed


def test_chat_intent_score_has_explicit_twenty_point_breakdown():
    features = score_track(track(scene_match="KOREAN_INDIE"), INTENT)
    assert features.chat_intent_score == 20
    assert features.chat_intent_breakdown == {"scene_genre": 6, "activity": 4, "vocal_lyrics": 4, "familiarity_popularity": 3, "explicit_alignment": 3}
    assert features.total_score <= 100


def test_unknown_vocal_evidence_is_neutral_and_weights_are_renormalized():
    features = score_track(track(tags=["korean indie", "focus"], popularity=0), INTENT)
    assert features.vocal_score is None
    assert "vocal" not in features.available_dimensions
    assert 0 <= features.total_score <= 100


def test_hidden_gems_and_activity_change_track_order():
    popular = track(recording_id="popular", title="Popular", popularity=100000, tags=["korean indie"])
    focused = track(recording_id="focused", title="Focused", popularity=20, tags=["korean indie", "focus", "instrumental"])
    assert [item.track.recording_id for item in evaluate_tracks([popular, focused], INTENT)] == ["focused", "popular"]

    popular_intent = {**INTENT, "preferences": {**INTENT["preferences"], "activities": ["WORKOUT"], "popularity": "popular", "familiarity": "familiar", "vocalAmount": "prominent"}, "emotionalArc": {"start": "답답함", "middle": "transition", "end": "energy"}}
    assert score_track(popular, popular_intent).total_score > score_track(focused, popular_intent).total_score


def test_high_energy_evidence_beats_mellow_and_unspecified_scene_is_neutral():
    intent = {
        "hardConstraints": {"allowedCountries": ["KR"], "requiredScenes": []},
        "preferences": {"moods": ["energetic", "upbeat"], "activities": ["REVIVAL"], "genres": [], "energy": .85},
        "emotionalArc": {"start": "excited", "middle": "lift", "end": "revival"},
    }
    energetic = track(recording_id="energetic", tags=["energetic", "upbeat", "danceable"])
    mellow_indie = track(recording_id="mellow", tags=["korean indie", "mellow", "slow"], scene_match="KOREAN_INDIE")
    ranked = evaluate_tracks([mellow_indie, energetic], intent)
    assert [item.track.recording_id for item in ranked] == ["energetic", "mellow"]
    assert ranked[0].features.scene_score is None
    assert ranked[0].features.energy_score == 30
