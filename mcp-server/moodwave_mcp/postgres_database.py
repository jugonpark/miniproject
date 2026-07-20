from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from .models import MusicRequest, PlaylistDraft, RecommendedTrack, SavedPlaylist


class PostgresDatabase:
    def __init__(self, url: str) -> None:
        self.url = url

    def _connect(self):
        return psycopg.connect(self.url, row_factory=dict_row)

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
                    request_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL,
                    idempotency_key TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id BIGSERIAL PRIMARY KEY,
                    playlist_id BIGINT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, recording_id TEXT NOT NULL, title TEXT NOT NULL,
                    artist TEXT NOT NULL, artist_id TEXT, release_id TEXT, release_title TEXT,
                    release_year INTEGER, cover_url TEXT, tags_json JSONB NOT NULL DEFAULT '[]',
                    discovery_type TEXT NOT NULL DEFAULT 'discovery', recommendation_reason TEXT NOT NULL DEFAULT '',
                    youtube_music_url TEXT NOT NULL, familiar BOOLEAN NOT NULL,
                    UNIQUE (playlist_id, position)
                );
                ALTER TABLE playlist_tracks ADD COLUMN IF NOT EXISTS release_year INTEGER;
                ALTER TABLE playlist_tracks ADD COLUMN IF NOT EXISTS tags_json JSONB NOT NULL DEFAULT '[]';
                ALTER TABLE playlist_tracks ADD COLUMN IF NOT EXISTS discovery_type TEXT NOT NULL DEFAULT 'discovery';
                ALTER TABLE playlist_tracks ADD COLUMN IF NOT EXISTS recommendation_reason TEXT NOT NULL DEFAULT '';
            """)

    def save_playlist(self, draft: PlaylistDraft, idempotency_key: str | None) -> SavedPlaylist:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO playlists(title,description,request_json,created_at,idempotency_key)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT(idempotency_key) DO NOTHING RETURNING id""",
                (draft.title, draft.description, json.dumps(draft.request.model_dump(mode="json")), datetime.now(UTC), idempotency_key),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT id FROM playlists WHERE idempotency_key=%s", (idempotency_key,))
                row = cursor.fetchone()
            playlist_id = row["id"]
            cursor.executemany(
                """INSERT INTO playlist_tracks(playlist_id,position,recording_id,title,artist,artist_id,release_id,release_title,release_year,cover_url,tags_json,discovery_type,recommendation_reason,youtube_music_url,familiar)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(playlist_id,position) DO NOTHING""",
                [(playlist_id,t.position,t.recording_id,t.title,t.artist,t.artist_id,t.release_id,t.release_title,t.release_year,str(t.cover_url) if t.cover_url else None,json.dumps(t.tags),t.discovery_type,t.recommendation_reason,str(t.youtube_music_url),t.familiar) for t in draft.tracks],
            )
        return self.get_playlist(playlist_id)

    def list_playlists(self, limit: int, offset: int) -> list[SavedPlaylist]:
        if limit < 1 or offset < 0: raise ValueError("invalid pagination")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM playlists ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s", (limit, offset))
            rows = cursor.fetchall()
            return [self._from_row(cursor, row) for row in rows]

    def get_playlist(self, playlist_id: int) -> SavedPlaylist:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM playlists WHERE id=%s", (playlist_id,))
            row = cursor.fetchone()
            if row is None: raise LookupError(f"playlist {playlist_id} was not found")
            return self._from_row(cursor, row)

    def delete_playlist(self, playlist_id: int) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM playlists WHERE id=%s", (playlist_id,))
            if cursor.rowcount == 0: raise LookupError(f"playlist {playlist_id} was not found")

    def _from_row(self, cursor, row) -> SavedPlaylist:
        cursor.execute("SELECT * FROM playlist_tracks WHERE playlist_id=%s ORDER BY position", (row["id"],))
        tracks = cursor.fetchall()
        request_data = row["request_json"] if isinstance(row["request_json"], dict) else json.loads(row["request_json"])
        return SavedPlaylist(
            id=row["id"], title=row["title"], description=row["description"],
            request=MusicRequest.model_validate(request_data), created_at=row["created_at"],
            tracks=[RecommendedTrack(position=t["position"],recording_id=t["recording_id"],title=t["title"],artist=t["artist"],artist_id=t["artist_id"],release_id=t["release_id"],release_title=t["release_title"],release_year=t["release_year"],cover_url=t["cover_url"],tags=t["tags_json"] if isinstance(t["tags_json"],list) else json.loads(t["tags_json"]),discovery_type=t["discovery_type"],recommendation_reason=t["recommendation_reason"],youtube_music_url=t["youtube_music_url"],familiar=t["familiar"]) for t in tracks],
        )
