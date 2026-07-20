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
        "f1", "f2", "f4", "d1", "d2", "d3", "d4",
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

    assert [item.recording_id for item in draft.tracks] == ["only-1", "only-2"]
