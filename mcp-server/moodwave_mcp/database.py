from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import MusicRequest, PlaylistDraft, RecommendedTrack, SavedPlaylist


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY,
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    recording_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    artist_id TEXT,
                    release_id TEXT,
                    release_title TEXT,
                    cover_url TEXT,
                    youtube_music_url TEXT NOT NULL,
                    familiar INTEGER NOT NULL,
                    UNIQUE (playlist_id, position)
                );
                """
            )

    def save_playlist(
        self, draft: PlaylistDraft, idempotency_key: str | None
    ) -> SavedPlaylist:
        with self._connect() as connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    "SELECT id FROM playlists WHERE idempotency_key = ?", (idempotency_key,)
                ).fetchone()
                if existing is not None:
                    playlist_id = existing["id"]
                else:
                    playlist_id = self._insert_playlist(connection, draft, idempotency_key)
                    if playlist_id is None:
                        playlist_id = connection.execute(
                            "SELECT id FROM playlists WHERE idempotency_key = ?",
                            (idempotency_key,),
                        ).fetchone()["id"]
            else:
                playlist_id = self._insert_playlist(connection, draft, None)
                assert playlist_id is not None
        return self.get_playlist(playlist_id)

    def _insert_playlist(
        self, connection: sqlite3.Connection, draft: PlaylistDraft, idempotency_key: str | None
    ) -> int | None:
        created_at = datetime.now(UTC).isoformat()
        cursor = connection.execute(
            """
            INSERT INTO playlists (
                title, description, request_json, created_at, idempotency_key
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (
                draft.title,
                draft.description,
                json.dumps(draft.request.model_dump(mode="json")),
                created_at,
                idempotency_key,
            ),
        )
        if cursor.rowcount == 0:
            return None
        playlist_id = cursor.lastrowid
        assert playlist_id is not None
        connection.executemany(
            """
            INSERT INTO playlist_tracks (
                playlist_id, position, recording_id, title, artist, artist_id,
                release_id, release_title, cover_url, youtube_music_url, familiar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    playlist_id,
                    track.position,
                    track.recording_id,
                    track.title,
                    track.artist,
                    track.artist_id,
                    track.release_id,
                    track.release_title,
                    str(track.cover_url) if track.cover_url is not None else None,
                    str(track.youtube_music_url),
                    int(track.familiar),
                )
                for track in draft.tracks
            ],
        )
        return playlist_id

    def list_playlists(self, limit: int, offset: int) -> list[SavedPlaylist]:
        if limit < 1 or offset < 0:
            raise ValueError("limit must be positive and offset cannot be negative")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM playlists ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._playlist_from_row(connection, row) for row in rows]

    def get_playlist(self, playlist_id: int) -> SavedPlaylist:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
            if row is None:
                raise LookupError(f"playlist {playlist_id} was not found")
            return self._playlist_from_row(connection, row)

    def delete_playlist(self, playlist_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            if cursor.rowcount == 0:
                raise LookupError(f"playlist {playlist_id} was not found")

    def _playlist_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> SavedPlaylist:
        track_rows = connection.execute(
            "SELECT * FROM playlist_tracks WHERE playlist_id = ? ORDER BY position", (row["id"],)
        ).fetchall()
        return SavedPlaylist(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            request=MusicRequest.model_validate_json(row["request_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            tracks=[
                RecommendedTrack(
                    position=track["position"],
                    recording_id=track["recording_id"],
                    title=track["title"],
                    artist=track["artist"],
                    artist_id=track["artist_id"],
                    release_id=track["release_id"],
                    release_title=track["release_title"],
                    cover_url=track["cover_url"],
                    youtube_music_url=track["youtube_music_url"],
                    familiar=bool(track["familiar"]),
                )
                for track in track_rows
            ],
        )
