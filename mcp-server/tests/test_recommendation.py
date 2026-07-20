from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

import pytest

from moodwave_mcp.models import MusicRequest, VerifiedTrack
from moodwave_mcp.services.cache import TTLCache
from moodwave_mcp.services.normalization import dedupe_candidates, normalize_tags
from moodwave_mcp.services.recommendation import compose_playlist
from moodwave_mcp.services.youtube_link import create_youtube_music_url


def track(
    recording_id: str,
    artist: str,
    *,
    tags: list[str] | None = None,
    popularity: int = 0,
) -> VerifiedTrack:
    return VerifiedTrack(
        recording_id=recording_id,
        title=f"Song {recording_id}",
        artist=artist,
        tags=tags or [],
        popularity=popularity,
    )


def test_normalize_tags_and_dedupe_candidates_keep_first_values_in_order():
    assert normalize_tags([" Calm ", "CALM", "focus", " ", "Focus"]) == ["calm", "focus"]
    assert dedupe_candidates(["first", "second", "first", "third", "second"]) == [
        "first",
        "second",
        "third",
    ]


def test_youtube_music_url_encodes_unicode_and_spaces():
    assert create_youtube_music_url("밤 산책", "아이유") == (
        "https://music.youtube.com/search?q=%EB%B0%A4+%EC%82%B0%EC%B1%85+%EC%95%84%EC%9D%B4%EC%9C%A0"
    )


def test_ttl_cache_returns_hit_until_expiry():
    cache = TTLCache(ttl_seconds=0.01)
    calls = 0

    def create():
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_create("key", create) == 1
    assert cache.get_or_create("key", create) == 1
    sleep(0.02)
    assert cache.get_or_create("key", create) == 2


def test_ttl_cache_shares_same_key_concurrent_call():
    cache = TTLCache(ttl_seconds=60)
    calls = 0

    def create():
        nonlocal calls
        calls += 1
        sleep(0.02)
        return "shared"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: cache.get_or_create("key", create), range(2)))

    assert results == ["shared", "shared"]
    assert calls == 1


def test_ttl_cache_shares_same_key_factory_failure():
    cache = TTLCache(ttl_seconds=60)
    started = Event()
    release = Event()
    calls = 0

    def create():
        nonlocal calls
        calls += 1
        started.set()
        release.wait()
        raise ValueError("shared failure")

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_create, "key", create)
        assert started.wait(timeout=1)
        second = executor.submit(cache.get_or_create, "key", create)
        sleep(0.02)
        release.set()
        with pytest.raises(ValueError, match="shared failure"):
            first.result()
        with pytest.raises(ValueError, match="shared failure"):
            second.result()

    assert calls == 1


def test_compose_playlist_honors_limits_ratio_unique_recordings_and_artist_cap():
    candidates = [
        track("f1", "Familiar", tags=["calm"], popularity=10),
        track("f2", "Familiar", tags=["calm"], popularity=9),
        track("f3", "Familiar", tags=["calm"], popularity=8),
        track("f4", "Friend", tags=["calm"], popularity=7),
        track("d1", "Discovery", tags=["calm"], popularity=10),
        track("d2", "Discovery", tags=["calm"], popularity=9),
        track("d3", "Explorer", tags=["calm"], popularity=8),
        track("d4", "Explorer", tags=["calm"], popularity=7),
        track("d1", "Other", tags=["calm"], popularity=99),
    ]
    request = MusicRequest(conditions=["calm"], familiar_artists=["familiar", "friend"], count=10)

    draft = compose_playlist(candidates, request)

    assert len(draft.tracks) == 7
    assert [item.recording_id for item in draft.tracks] == [
        "f1", "f4", "d1", "d3", "f2", "d2", "d4",
    ]
    assert [item.position for item in draft.tracks] == list(range(1, len(draft.tracks) + 1))
    assert sum(item.familiar for item in draft.tracks) == 3
    assert len({item.recording_id for item in draft.tracks}) == len(draft.tracks)
    assert max(sum(item.artist == artist for item in draft.tracks) for artist in {item.artist for item in draft.tracks}) <= 2


def test_compose_playlist_uses_sixty_forty_when_candidates_permit():
    candidates = [
        *(track(f"f{index}", f"F{index}", tags=["calm"], popularity=index) for index in range(6)),
        *(track(f"d{index}", f"D{index}", tags=["calm"], popularity=index) for index in range(4)),
    ]
    request = MusicRequest(conditions=["calm"], familiar_artists=[f"F{index}" for index in range(6)], count=10)

    draft = compose_playlist(candidates, request)

    assert len(draft.tracks) == 10
    assert [item.position for item in draft.tracks] == list(range(1, 11))
    assert sum(item.familiar for item in draft.tracks) == 6


def test_compose_playlist_supports_requested_counts():
    candidates = [track(str(index), f"Artist {index}", tags=["calm"], popularity=index) for index in range(15)]

    assert len(compose_playlist(candidates, MusicRequest(conditions=["calm"], count=5)).tracks) == 5
    assert len(compose_playlist(candidates, MusicRequest(conditions=["calm"], count=10)).tracks) == 10
    assert len(compose_playlist(candidates, MusicRequest(conditions=["calm"], count=15)).tracks) == 15


def test_compose_playlist_returns_honest_short_result_without_fabrication():
    candidates = [
        track("only-1", "Artist", tags=["calm"]),
        track("only-2", "Artist", tags=["calm"]),
        track("only-3", "Artist", tags=["calm"]),
    ]

    draft = compose_playlist(candidates, MusicRequest(conditions=["calm"], count=5))

    assert [item.recording_id for item in draft.tracks] == ["only-1"]


def test_intent_composition_keeps_candidate_ids_roles_and_partial_status():
    intent = {
        "rawRequest": "공부용 숨은 곡",
        "hardConstraints": {"requiredScenes": []},
        "preferences": {"activities": ["STUDY"], "popularity": "hidden_gems"},
        "emotionalArc": {"start": "답답함", "middle": "grounding", "end": "focus"},
    }
    candidates = [
        track("one", "Artist 1", tags=["focus", "ambient"], popularity=10).model_copy(update={"candidate_id": "candidate:one"}),
        track("two", "Artist 2", tags=["calm"], popularity=20).model_copy(update={"candidate_id": "candidate:two"}),
    ]
    request = MusicRequest(conditions=["공부"], count=5, recommendation_intent=intent)
    draft = compose_playlist(candidates, request)
    assert draft.recommendation_status == "PARTIAL"
    assert [item.candidate_id for item in draft.tracks] == ["candidate:one", "candidate:two"]
    assert [item.role for item in draft.tracks] == ["EMPATHY", "CLOSURE"]
    assert all(item.recommendation_reason for item in draft.tracks)


def test_nvidia_candidate_order_is_not_reordered_by_familiarity_ratio():
    candidates = [
        track("familiar", "Known", tags=["focus"]).model_copy(update={"candidate_id": "candidate:familiar"}),
        track("discovery", "New", tags=["focus"]).model_copy(update={"candidate_id": "candidate:discovery"}),
    ]
    request = MusicRequest(
        conditions=["focus"],
        familiar_artists=["Known"],
        count=5,
        recommendation_intent={"preferences": {"activities": ["STUDY"]}},
    )
    selections = [
        {"candidateId": "candidate:discovery", "role": "EMPATHY", "reason": "first"},
        {"candidateId": "candidate:familiar", "role": "TARGET", "reason": "second"},
    ]

    draft = compose_playlist(candidates, request, selected_candidates=selections)

    assert [item.candidate_id for item in draft.tracks] == ["candidate:discovery", "candidate:familiar"]


def test_nvidia_selection_cannot_restore_unknown_origin_under_strict_kr_intent():
    unknown = track("unknown", "Unknown", tags=["focus"]).model_copy(update={"candidate_id": "candidate:unknown", "origin_status": "UNKNOWN"})
    korean = track("kr", "Korean", tags=["focus"]).model_copy(update={"candidate_id": "candidate:kr", "origin_status": "VERIFIED_KR", "artist_country": "KR"})
    intent = {"hardConstraints": {"allowedCountries": ["KR"]}, "preferences": {"activities": ["STUDY"]}}
    request = MusicRequest(conditions=["focus"], region="domestic", count=5, recommendation_intent=intent)
    selections = [
        {"candidateId": "candidate:unknown", "role": "EMPATHY", "reason": "must be removed"},
        {"candidateId": "candidate:kr", "role": "TARGET", "reason": "allowed"},
    ]

    draft = compose_playlist([unknown, korean], request, selected_candidates=selections)

    assert [item.candidate_id for item in draft.tracks] == ["candidate:kr"]


def test_compose_prefers_one_track_per_artist_when_other_artists_are_available():
    candidates = [
        track("a1", "A", popularity=10),
        track("a2", "A", popularity=9),
        track("b1", "B", popularity=8),
        track("c1", "C", popularity=7),
        track("d1", "D", popularity=6),
        track("e1", "E", popularity=5),
    ]
    draft = compose_playlist(candidates, MusicRequest(conditions=["energetic"], count=5))
    assert len({item.artist for item in draft.tracks}) == 5
    assert sum(item.artist == "A" for item in draft.tracks) == 1
    assert all(left.artist != right.artist for left, right in zip(draft.tracks, draft.tracks[1:]))
