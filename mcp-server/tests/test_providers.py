from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest

from moodwave_mcp.models import CandidateArtist
from moodwave_mcp.providers.base import JsonRequester, ProviderError
from moodwave_mcp.providers.cover_art import CoverArtProvider
from moodwave_mcp.providers.lastfm import LastFmProvider
from moodwave_mcp.providers.musicbrainz import MusicBrainzProvider
from moodwave_mcp.services.discovery import DiscoveryService
from moodwave_mcp.services.verification import VerificationService


def run(coro):
    return asyncio.run(coro)


def client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_lastfm_normalizes_tag_artists_and_bounds_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["method"] == "tag.gettopartists"
        assert request.url.params["tag"] == "dream pop"
        return httpx.Response(
            200,
            json={
                "topartists": {
                    "artist": [
                        {"name": " Beach House ", "listeners": "120"},
                        {"name": "beach house", "listeners": "999"},
                        {"name": "Slowdive", "playcount": "80"},
                        {"name": "Overflow", "listeners": "70"},
                    ]
                }
            },
        )

    async def scenario():
        async with client(handler) as http:
            return await LastFmProvider("secret", client=http).discover([" Dream Pop "], limit=2)

    artists = run(scenario())

    assert [(artist.name, artist.tags, artist.popularity) for artist in artists] == [
        ("Beach House", ["dream pop"], 120),
        ("Slowdive", ["dream pop"], 80),
    ]


def test_lastfm_normalizes_similar_artists_and_top_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.params["method"]
        if method == "artist.getsimilar":
            return httpx.Response(
                200,
                json={"similarartists": {"artist": [{"name": " M83 ", "match": "0.87"}]}},
            )
        assert method == "artist.gettoptags"
        return httpx.Response(
            200,
            json={"toptags": {"tag": [{"name": " Dream Pop "}, {"name": "DREAM POP"}, {"name": "Electronic"}]}},
        )

    async def scenario():
        async with client(handler) as http:
            return await LastFmProvider("secret", client=http).similar(["Beach House"], limit=5)

    assert run(scenario()) == [
        CandidateArtist(
            name="M83",
            source="lastfm:similar",
            tags=["dream pop", "electronic"],
            popularity=870,
        )
    ]


def test_lastfm_zero_limit_returns_empty_without_network_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("zero-limit requests must not reach the network")

    async def scenario():
        async with client(handler) as http:
            provider = LastFmProvider("secret", client=http)
            return await provider.discover(["calm"], limit=0), await provider.similar(
                ["Beach House"], limit=0
            )

    assert run(scenario()) == ([], [])


def test_musicbrainz_requires_user_agent():
    with pytest.raises(ValueError, match="User-Agent"):
        MusicBrainzProvider("")


def test_musicbrainz_normalizes_releases_and_dedupes_recording_ids():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/artist"):
            return httpx.Response(200, json={"artists": [{"id": "artist-1", "name": "Bjork"}]})
        return httpx.Response(
            200,
            json={
                "recordings": [
                    {
                        "id": "recording-1",
                        "title": "Joga",
                        "releases": [
                            {
                                "id": "release-1",
                                "title": "Homogenic",
                                "date": "1997-09-22",
                                "release-group": {"id": "group-1"},
                            }
                        ],
                    },
                    {"id": "recording-1", "title": "Duplicate", "releases": []},
                    {"id": "recording-2", "title": "Unravel", "releases": []},
                    {"id": "recording-3", "title": "Overflow", "releases": []},
                ]
            },
        )

    async def scenario():
        async with client(handler) as http:
            provider = MusicBrainzProvider("Moodwave/1.0 (test@example.com)", client=http, min_interval=0)
            return await provider.verify_artist_tracks(" Bjork ", limit=2)

    tracks = run(scenario())

    assert [track.recording_id for track in tracks] == ["recording-1", "recording-2"]
    assert tracks[0].model_dump(mode="json") == {
        "recording_id": "recording-1",
        "title": "Joga",
        "artist": "Bjork",
        "artist_id": "artist-1",
        "release_id": "release-1",
        "release_title": "Homogenic",
        "cover_url": None,
        "tags": [],
        "popularity": 0,
        "region": None,
    }
    assert all(request.headers["user-agent"] == "Moodwave/1.0 (test@example.com)" for request in requests)


def test_musicbrainz_enforces_injected_request_spacing():
    now = 0.0
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        nonlocal now
        sleeps.append(delay)
        now += delay

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/artist"):
            return httpx.Response(200, json={"artists": [{"id": "artist-1", "name": "B"}]})
        return httpx.Response(200, json={"recordings": []})

    async def scenario():
        async with client(handler) as http:
            provider = MusicBrainzProvider(
                "Moodwave/1.0",
                client=http,
                min_interval=1.0,
                clock=lambda: now,
                sleep=sleep,
            )
            await provider.verify_artist_tracks("B")

    run(scenario())

    assert sleeps == [1.0]


def test_musicbrainz_zero_limit_returns_empty_without_network_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("zero-limit requests must not reach the network")

    async def scenario():
        async with client(handler) as http:
            return await MusicBrainzProvider(
                "Moodwave/1.0", client=http, min_interval=0
            ).verify_artist_tracks("Bjork", limit=0)

    assert run(scenario()) == []


def test_cover_art_uses_release_then_release_group_and_rejects_unusable_images():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/release-1"):
            return httpx.Response(404, json={})
        return httpx.Response(
            200,
            json={"images": [{"front": False, "image": "http://insecure.example/art.jpg"}, {"front": True, "image": "https://img.example/front.jpg"}]},
        )

    async def scenario():
        async with client(handler) as http:
            return await CoverArtProvider(client=http).find_cover("release-1", "group-1")

    assert run(scenario()) == "https://img.example/front.jpg"
    assert paths == ["/release/release-1", "/release-group/group-1"]


def test_requester_retries_transient_failures_at_most_twice_and_sets_timeout():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"secret": "must not leak"})

    async def scenario():
        async with client(handler) as http:
            requester = JsonRequester(http, timeout=0.25, sleep=lambda _: asyncio.sleep(0))
            with pytest.raises(ProviderError, match="unavailable") as error:
                await requester.get("https://provider.example/data", params={"api_key": "private"})
            return str(error.value)

    message = run(scenario())

    assert attempts == 3
    assert "private" not in message
    assert "must not leak" not in message


def test_requester_converts_timeout_without_leaking_request_details():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out with api_key=private", request=request)

    async def scenario():
        async with client(handler) as http:
            with pytest.raises(ProviderError, match="timed out") as error:
                await JsonRequester(http, retries=0).get(
                    "https://provider.example/data", params={"api_key": "private"}
                )
            return str(error.value)

    assert "private" not in run(scenario())


def test_discovery_service_uses_normalized_cache_key_and_bounds_output():
    class StubLastFm:
        calls = 0

        async def discover(self, tags, limit):
            self.calls += 1
            return [CandidateArtist(name=f"Artist {index}", source="stub") for index in range(100)]

    async def scenario():
        provider = StubLastFm()
        service = DiscoveryService(provider, max_results=3)
        first = await service.discover([" Calm ", "CALM"], limit=99)
        second = await service.discover(["calm"], limit=99)
        return provider.calls, first, second

    calls, first, second = run(scenario())

    assert calls == 1
    assert len(first) == len(second) == 3


def test_discovery_service_expands_similar_artists_with_normalized_cache_key():
    class StubLastFm:
        calls = 0

        async def similar(self, artists, limit):
            self.calls += 1
            assert artists == ["beach house"]
            return [CandidateArtist(name="M83", source="stub")]

    async def scenario():
        provider = StubLastFm()
        service = DiscoveryService(provider)
        first = await service.expand([" Beach House "])
        second = await service.expand(["beach house"])
        return provider.calls, first, second

    calls, first, second = run(scenario())

    assert calls == 1
    assert first == second == [CandidateArtist(name="M83", source="stub")]


def test_verification_keeps_other_artists_when_one_fails_and_cover_failure_is_none():
    class StubMusicBrainz:
        async def verify_artist_tracks(self, artist, limit):
            if artist == "Broken":
                raise ProviderError("provider unavailable")
            from moodwave_mcp.models import VerifiedTrack

            return [VerifiedTrack(recording_id="ok-1", title="Song", artist=artist)]

    class StubCovers:
        async def find_cover(self, release_id, release_group_id=None):
            raise ProviderError("cover unavailable")

    candidates = [
        CandidateArtist(name="Broken", source="lastfm", tags=["calm"]),
        CandidateArtist(name="Working", source="lastfm", tags=["calm"], popularity=7),
    ]

    tracks = run(VerificationService(StubMusicBrainz(), StubCovers()).verify(candidates, tracks_per_artist=2))

    assert len(tracks) == 1
    assert tracks[0].recording_id == "ok-1"
    assert tracks[0].cover_url is None
    assert tracks[0].tags == ["calm"]
    assert tracks[0].popularity == 7
