import asyncio
import logging

import httpx

from moodwave_mcp.models import CandidateArtist, TrackCandidate, VerifiedTrack
from moodwave_mcp.providers.itunes import ITunesProvider
from moodwave_mcp.services.verification import VerificationService


def run(awaitable):
    return asyncio.run(awaitable)


def test_itunes_maps_valid_songs_and_ignores_invalid_results():
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["country"] == "KR"
        assert request.url.params["entity"] == "song"
        return httpx.Response(200, json={"resultCount": 2, "results": [
            {"wrapperType": "track", "kind": "song", "trackId": 123, "artistName": "아이유", "trackName": "좋은 날", "collectionName": "REAL", "artworkUrl100": "https://img.example/100.jpg", "releaseDate": "2010-12-09T00:00:00Z", "primaryGenreName": "K-Pop"},
            {"wrapperType": "collection", "collectionId": 456},
        ]})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = ITunesProvider(client=client)
            return await provider.search_artist_tracks("아이유", 5), await provider.search_artist_tracks(" 아이유 ", 5)

    tracks, cached = run(scenario())
    assert [(track.recording_id, track.track_title, track.artist_name, track.source) for track in tracks] == [("itunes:123", "좋은 날", "아이유", "itunes")]
    assert str(tracks[0].cover_image_url) == "https://img.example/100.jpg"
    assert cached == tracks
    assert calls == 1


def test_verification_uses_itunes_only_for_musicbrainz_shortfall():
    class MusicBrainz:
        async def verify_artist_tracks(self, artist, limit):
            return []

    class ITunes:
        calls = 0
        async def search_artist_tracks(self, artist, limit):
            self.calls += 1
            return [VerifiedTrack(recording_id="itunes:1", title="좋은 날", artist=artist, source="itunes")]

    class Covers:
        async def find_cover(self, release_id, release_group_id=None):
            return None

    async def scenario():
        itunes = ITunes()
        tracks = await VerificationService(MusicBrainz(), Covers(), itunes=itunes).verify([CandidateArtist(name="아이유", source="lastfm")], tracks_per_artist=2)
        return itunes.calls, tracks

    calls, tracks = run(scenario())
    assert calls == 1
    assert [track.recording_id for track in tracks] == ["itunes:1"]


def test_verification_prefers_musicbrainz_when_itunes_returns_same_song():
    class MusicBrainz:
        async def verify_artist_tracks(self, artist, limit):
            return [VerifiedTrack(recording_id="mb:1", title="좋은 날", artist=artist)]

    class ITunes:
        async def search_artist_tracks(self, artist, limit):
            return [VerifiedTrack(recording_id="itunes:1", title="좋은 날", artist=artist, source="itunes")]

    class Covers:
        async def find_cover(self, release_id, release_group_id=None):
            return None

    tracks = run(VerificationService(MusicBrainz(), Covers(), itunes=ITunes()).verify([CandidateArtist(name="아이유", source="lastfm")], tracks_per_artist=2))
    assert [track.recording_id for track in tracks] == ["mb:1"]


def test_verification_collects_real_track_candidates_before_catalog_verification(caplog):
    caplog.set_level(logging.INFO, logger="moodwave.verification")
    class LastFm:
        async def top_tracks(self, artist, limit):
            return [TrackCandidate(artist=artist, title="좋은 날", source="lastfm:toptracks")]

    class MusicBrainz:
        async def verify_track(self, candidate):
            assert (candidate.artist, candidate.title) == ("아이유", "좋은 날")
            return VerifiedTrack(recording_id="mb:good-day", title=candidate.title, artist=candidate.artist)

    class Covers:
        async def find_cover(self, release_id, release_group_id=None):
            return None

    tracks = run(VerificationService(MusicBrainz(), Covers(), track_provider=LastFm()).verify([CandidateArtist(name="아이유", source="lastfm")], tracks_per_artist=2))
    assert [track.recording_id for track in tracks] == ["mb:good-day"]
    assert '"topTracks": 1' in caplog.text
    assert '"musicBrainzMatches": 1' in caplog.text
    assert '"finalVerifiedCandidates": 1' in caplog.text


def test_itunes_accepts_a_musicbrainz_artist_alias():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results":[{"wrapperType":"track","kind":"song","trackId":1,"artistName":"아이유","trackName":"Good Day"}]})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ITunesProvider(client=client).search_track("IU", "Good Day", aliases=["아이유"])

    assert run(scenario()).recording_id == "itunes:1"


def test_itunes_prefers_matching_original_version_over_live_first_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [
            {"wrapperType": "track", "kind": "song", "trackId": 1, "artistName": "Artist", "trackName": "Dream (Live)"},
            {"wrapperType": "track", "kind": "song", "trackId": 2, "artistName": "Artist", "trackName": "Dream"},
        ]})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ITunesProvider(client=client).search_track("Artist", "Dream")
    assert run(scenario()).recording_id == "itunes:2"


def test_itunes_fallback_survives_musicbrainz_request_failure():
    class LastFm:
        async def top_tracks(self, artist, limit):
            return [TrackCandidate(artist=artist, title="Real Song", source="lastfm:toptracks")]
    class MusicBrainz:
        async def verify_track(self, candidate):
            raise RuntimeError("catalog unavailable")
        async def artist_aliases(self, artist):
            return []
    class ITunes:
        async def search_track(self, artist, title, aliases=None):
            return VerifiedTrack(recording_id="itunes:strong", title=title, artist=artist, source="itunes")
    class Covers:
        async def find_cover(self, release_id, release_group_id=None):
            return None

    tracks = run(VerificationService(MusicBrainz(), Covers(), itunes=ITunes(), track_provider=LastFm()).verify([CandidateArtist(name="Artist", source="lastfm")]))
    assert [track.recording_id for track in tracks] == ["itunes:strong"]
