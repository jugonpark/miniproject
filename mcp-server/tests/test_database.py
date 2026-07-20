from __future__ import annotations

import sqlite3

import pytest

from moodwave_mcp.database import Database
from moodwave_mcp.models import (
    MusicRequest,
    PlaylistDraft,
    RecommendedTrack,
)


def make_draft(title: str, tracks: list[RecommendedTrack] | None = None) -> PlaylistDraft:
    return PlaylistDraft(
        title=title,
        description=f"{title} description",
        request=MusicRequest(conditions=["calm"]),
        tracks=tracks
        or [
            RecommendedTrack(
                recording_id="recording-2",
                title="Second track",
                artist="Artist B",
                youtube_music_url="https://music.youtube.com/watch?v=second",
                familiar=False,
            ),
            RecommendedTrack(
                recording_id="recording-1",
                title="First track",
                artist="Artist A",
                youtube_music_url="https://music.youtube.com/watch?v=first",
                familiar=True,
            ),
        ],
    )


def test_initialize_is_idempotent(tmp_path):
    database = Database(tmp_path / "moodwave.db")

    database.initialize()
    database.initialize()

    with sqlite3.connect(tmp_path / "moodwave.db") as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"playlists", "playlist_tracks"} <= tables


def test_save_playlist_is_idempotent_and_returns_tracks_in_position_order(tmp_path):
    database = Database(tmp_path / "moodwave.db")
    database.initialize()

    saved = database.save_playlist(make_draft("Focus"), "save-focus")
    repeated = database.save_playlist(make_draft("Changed title"), "save-focus")

    assert repeated == saved
    assert [track.recording_id for track in saved.tracks] == [
        "recording-2",
        "recording-1",
    ]

    fetched = database.get_playlist(saved.id)
    assert fetched == saved


def test_list_playlists_is_newest_first_and_supports_paging(tmp_path):
    database = Database(tmp_path / "moodwave.db")
    database.initialize()
    first = database.save_playlist(make_draft("First"), "first")
    second = database.save_playlist(make_draft("Second"), "second")

    assert [playlist.id for playlist in database.list_playlists(limit=10, offset=0)] == [
        second.id,
        first.id,
    ]
    assert database.list_playlists(limit=1, offset=1) == [first]


def test_delete_playlist_cascades_tracks_and_missing_ids_raise_lookup_error(tmp_path):
    database = Database(tmp_path / "moodwave.db")
    database.initialize()
    saved = database.save_playlist(make_draft("Delete me"), "delete-me")

    database.delete_playlist(saved.id)

    with sqlite3.connect(tmp_path / "moodwave.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0] == 0
    with pytest.raises(LookupError):
        database.get_playlist(saved.id)
    with pytest.raises(LookupError):
        database.delete_playlist(saved.id)
