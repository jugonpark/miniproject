import asyncio

from moodwave_mcp.models import CandidateArtist, MusicRequest, VerifiedTrack
from moodwave_mcp.services.constraints import discovery_tags, enforce_track_constraints
from moodwave_mcp.services.recommendation import compose_playlist
from moodwave_mcp.services.verification import VerificationService


class Covers:
    async def find_cover(self, *_): return None


def test_domestic_emotion_values_become_lastfm_music_tags():
    tags = discovery_tags(
        "domestic",
        ["무언가 꽉 막힌 느낌", "차분함", "답답함", "공부"],
    )
    assert tags[:4] == [
        "korean indie",
        "k-indie",
        "korean singer-songwriter",
        "korean indie rock",
    ]
    assert {"introspective", "moody", "atmospheric", "calm", "mellow", "soft", "focus", "instrumental", "ambient"} <= set(tags)
    assert not set(tags) & {"domestic", "무언가 꽉 막힌 느낌", "차분함", "답답함", "공부"}


def test_strict_domestic_filter_keeps_only_verified_korean_artist():
    tracks = [
        VerifiedTrack(recording_id="kr", title="K", artist="Korean", artist_country="KR", origin_status="VERIFIED_KR", scene_match="KOREAN_INDIE"),
        VerifiedTrack(recording_id="jp", title="J", artist="Japanese", artist_country="JP", origin_status="VERIFIED_FOREIGN", scene_match="KOREAN_INDIE"),
        VerifiedTrack(recording_id="unknown", title="U", artist="Unknown"),
    ]
    request = MusicRequest(conditions=["국내 인디"], region="domestic", artist_origin_country="KR", scene="KOREAN_INDIE", strict_country_filter=True, allow_foreign_artists=False)
    assert [track.recording_id for track in enforce_track_constraints(tracks, request)] == ["kr"]
    assert [track.recording_id for track in compose_playlist(tracks, request).tracks] == ["kr"]


def test_release_country_never_substitutes_for_artist_origin():
    class MusicBrainz:
        async def artist_origin(self, artist): return "UNKNOWN", None
        async def verify_artist_tracks(self, artist, limit):
            return [VerifiedTrack(recording_id="release-kr", title="Song", artist=artist, release_id="KR-release")]
    result = asyncio.run(VerificationService(MusicBrainz(), Covers()).verify([CandidateArtist(name="Foreign", source="lastfm")], strict_country_filter=True, korean_indie=True))
    assert result == []


def test_verified_foreign_lastfm_candidate_is_rejected_even_with_korean_indie_tag():
    class MusicBrainz:
        async def artist_origin(self, artist): return "VERIFIED_FOREIGN", "JP"
        async def verify_artist_tracks(self, artist, limit): raise AssertionError("foreign artist must be filtered first")
    result = asyncio.run(VerificationService(MusicBrainz(), Covers()).verify([CandidateArtist(name="Japanese", source="lastfm", tags=["korean indie"])], strict_country_filter=True, korean_indie=True))
    assert result == []
