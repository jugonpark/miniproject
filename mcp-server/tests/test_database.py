from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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
                position=1,
                recording_id="recording-2",
                title="Second track",
                artist="Artist B",
                youtube_music_url="https://music.youtube.com/watch?v=second",
                familiar=False,
            ),
            RecommendedTrack(
                position=2,
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


def test_initialize_migrates_legacy_zero_based_positions_once(tmp_path):
    database = Database(tmp_path / "moodwave.db")
    database.initialize()
    with sqlite3.connect(database.path) as connection:
        playlist_id = connection.execute(
            """
            INSERT INTO playlists (title, description, request_json, created_at, idempotency_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Legacy", "", '{"conditions":["calm"]}', "2026-01-01T00:00:00+00:00", None),
        ).lastrowid
        connection.executemany(
            """
            INSERT INTO playlist_tracks (
                playlist_id, position, recording_id, title, artist, youtube_music_url, familiar
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (playlist_id, 0, "legacy-1", "First", "Artist A", "https://music.youtube.com/first", 0),
                (playlist_id, 1, "legacy-2", "Second", "Artist B", "https://music.youtube.com/second", 1),
            ],
        )

    database.initialize()
    migrated = database.get_playlist(playlist_id)
    database.initialize()
    repeated = database.get_playlist(playlist_id)

    assert [track.position for track in migrated.tracks] == [1, 2]
    assert repeated == migrated


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
    assert [track.position for track in saved.tracks] == [1, 2]

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


def test_concurrent_idempotency_keys_return_the_same_playlist(tmp_path):
    barrier = Barrier(2)

    class RacingDatabase(Database):
        def _insert_playlist(self, connection, draft, idempotency_key):
            barrier.wait()
            return super()._insert_playlist(connection, draft, idempotency_key)

    database = RacingDatabase(tmp_path / "moodwave.db")
    database.initialize()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: database.save_playlist(make_draft("Focus"), "save-focus"),
                range(2),
            )
        )

    assert results[0] == results[1]


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
