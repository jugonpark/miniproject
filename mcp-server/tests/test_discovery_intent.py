import asyncio

import httpx

from moodwave_mcp.providers.lastfm import LastFmProvider
from moodwave_mcp.services.constraints import discovery_tags_by_category


def test_intent_maps_to_separate_lastfm_categories():
    intent = {
        "hardConstraints": {"requiredScenes": ["KOREAN_INDIE"]},
        "preferences": {"moods": ["답답함"], "activities": ["STUDY"], "vocalAmount": "low"},
    }
    groups = discovery_tags_by_category("domestic", ["답답함", "공부"], intent)
    assert groups["scene"][:2] == ["korean indie", "k-indie"]
    assert "moody" in groups["mood"]
    assert "focus" in groups["activity"]
    assert "instrumental" in groups["vocal"]


def test_lastfm_accumulates_artist_evidence_across_all_tags():
    requested = []

    def handler(request: httpx.Request):
        tag = request.url.params["tag"]
        requested.append(tag)
        artists = [{"name": "Shared", "listeners": "10"}]
        if tag == "focus":
            artists.append({"name": "Focus Only", "listeners": "5"})
        return httpx.Response(200, json={"topartists": {"artist": artists}})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LastFmProvider("secret", client=client).discover_grouped(
                {"scene": ["korean indie"], "mood": ["moody"], "activity": ["focus"]},
                {"scene": 12, "mood": 8, "activity": 6},
                limit=20,
            )

    artists = asyncio.run(scenario())
    shared = next(artist for artist in artists if artist.name == "Shared")
    assert requested == ["korean indie", "moody", "focus"]
    assert shared.matched_tags == ["korean indie", "moody", "focus"]
    assert shared.matched_categories == ["scene", "mood", "activity"]
    assert shared.appearance_count == 3


def test_same_ui_with_different_chat_intent_changes_search_tags():
    base = ["답답함", "공부"]
    study = {"hardConstraints": {"requiredScenes": ["KOREAN_INDIE"]}, "preferences": {"moods": ["차분함"], "activities": ["STUDY"], "vocalAmount": "low", "genres": ["indie"]}}
    workout = {"hardConstraints": {"requiredScenes": ["KOREAN_INDIE"]}, "preferences": {"moods": ["신나는"], "activities": ["WORKOUT"], "vocalAmount": "prominent", "genres": ["rock"]}}
    assert discovery_tags_by_category("domestic", base, study) != discovery_tags_by_category("domestic", base, workout)


def test_domestic_without_explicit_genre_has_no_scene_or_indie_tags():
    intent = {
        "hardConstraints": {"region": "domestic", "allowedCountries": ["KR"], "requiredScenes": []},
        "preferences": {"moods": ["energetic", "upbeat"], "activities": ["REVIVAL"], "genres": [], "energy": .85},
    }
    groups = discovery_tags_by_category("domestic", ["에너지가 넘쳐요", "확실하게 기분 전환"], intent)
    assert "scene" not in groups
    assert "genre" not in groups
    assert {"energetic", "upbeat", "exciting", "danceable"} <= set(groups["mood"])
    assert not {"korean indie", "k-indie"} & {tag for values in groups.values() for tag in values}


def test_explicit_domestic_indie_and_hiphop_use_different_tags():
    indie = {"hardConstraints": {"requiredScenes": ["KOREAN_INDIE"]}, "preferences": {"moods": ["energetic"], "genres": ["indie"]}}
    hiphop = {"hardConstraints": {"requiredScenes": []}, "preferences": {"moods": ["energetic"], "genres": ["hip-hop"]}}
    indie_groups = discovery_tags_by_category("domestic", [], indie)
    hiphop_groups = discovery_tags_by_category("domestic", [], hiphop)
    assert indie_groups["scene"][:2] == ["korean indie", "k-indie"]
    assert hiphop_groups.get("scene", []) == []
    assert hiphop_groups["genre"] == ["hip-hop"]


def test_country_seed_discovery_is_not_treated_as_origin_verification():
    def handler(request: httpx.Request):
        assert request.url.params["method"] == "geo.gettopartists"
        assert request.url.params["country"] == "Korea, Republic of"
        return httpx.Response(200, json={"topartists": {"artist": [{"name": "Popular in Korea", "listeners": "20"}]}})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LastFmProvider("secret", client=client).discover_country("Korea, Republic of", 10)

    artists = asyncio.run(scenario())
    assert artists[0].matched_categories == ["country_seed"]
    assert artists[0].origin_status == "UNKNOWN"
