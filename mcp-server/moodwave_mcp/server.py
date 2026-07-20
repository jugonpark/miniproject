from __future__ import annotations

from fastmcp import FastMCP

from .config import Settings
from .database import Database
from .models import CandidateArtist, MusicRequest, PlaylistDraft, VerifiedTrack
from .providers.cover_art import CoverArtProvider
from .providers.lastfm import LastFmProvider
from .providers.musicbrainz import MusicBrainzProvider
from .postgres_database import PostgresDatabase
from .services.discovery import DiscoveryService
from .services.recommendation import compose_playlist as compose
from .services.verification import VerificationService

settings = Settings.from_env()
database = PostgresDatabase(settings.database_path) if settings.database_path.startswith(("postgres://", "postgresql://")) else Database(settings.database_path)
database.initialize()
mcp = FastMCP("MOODWAVE")


def _discovery() -> DiscoveryService | None:
    return DiscoveryService(LastFmProvider(settings.lastfm_api_key)) if settings.lastfm_api_key else None


def _verification() -> VerificationService | None:
    if not settings.musicbrainz_user_agent:
        return None
    return VerificationService(MusicBrainzProvider(settings.musicbrainz_user_agent), CoverArtProvider())


@mcp.tool
async def discover_music_candidates(
    moods: list[str], activities: list[str], vocal_preference: str | None = None,
    region: str = "mixed", limit: int = 20,
) -> list[CandidateArtist]:
    """Find artists related to the requested mood and activity."""
    service = _discovery()
    if service is None:
        raise RuntimeError("LASTFM_API_KEY is required")
    return await service.discover([*moods, *activities, *([vocal_preference] if vocal_preference else [])], limit)


@mcp.tool
async def expand_similar_artists(
    seed_artists: list[str], tags: list[str], limit: int = 10,
) -> list[CandidateArtist]:
    """Expand artist candidates when discovery variety is insufficient."""
    service = _discovery()
    if service is None:
        raise RuntimeError("LASTFM_API_KEY is required")
    return await service.expand(seed_artists, limit)


@mcp.tool
async def verify_music_tracks(
    artist_candidates: list[str], region: str = "mixed", limit_per_artist: int = 5,
) -> list[VerifiedTrack]:
    """Verify real recordings with MusicBrainz and attach cover art when available."""
    service = _verification()
    if service is None:
        raise RuntimeError("MUSICBRAINZ_USER_AGENT is required")
    candidates = [CandidateArtist(name=name, source="agent") for name in artist_candidates]
    return await service.verify(candidates, limit_per_artist)


@mcp.tool
def compose_playlist(
    verified_tracks: list[VerifiedTrack], conditions: list[str], region: str = "mixed",
    track_count: int = 10, original_request: str = "", familiar_artists: list[str] | None = None,
) -> PlaylistDraft:
    """Compose the final playlist exclusively from verified track input."""
    request = MusicRequest(
        conditions=conditions, region=region, free_text=original_request or None,
        familiar_artists=familiar_artists or [], count=track_count,
    )
    return compose(verified_tracks, request)


@mcp.tool
def save_playlist(draft: PlaylistDraft, idempotency_key: str) -> dict:
    """Persist a playlist only after an explicit user save action."""
    return database.save_playlist(draft, idempotency_key).model_dump(mode="json")


@mcp.tool
def list_playlists(limit: int = 20, offset: int = 0) -> list[dict]:
    """List saved playlists newest first."""
    return [item.model_dump(mode="json") for item in database.list_playlists(limit, offset)]


@mcp.tool
def get_playlist(playlist_id: int) -> dict:
    """Get one saved playlist and its ordered tracks."""
    return database.get_playlist(playlist_id).model_dump(mode="json")


@mcp.tool
def delete_playlist(playlist_id: int) -> dict:
    """Delete a playlist and its tracks."""
    database.delete_playlist(playlist_id)
    return {"deleted": True, "playlist_id": playlist_id}


def main() -> None:
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
