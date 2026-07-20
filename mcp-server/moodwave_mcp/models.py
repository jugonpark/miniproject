from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class MusicRequest(BaseModel):
    conditions: list[str] = Field(min_length=1)
    region: Literal["domestic", "global", "mixed"] = "mixed"
    free_text: str | None = None
    familiar_artists: list[str] = Field(default_factory=list)
    count: Literal[5, 10, 15] = 10


class CandidateArtist(BaseModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    popularity: int = Field(default=0, ge=0)
    region: str | None = None


class VerifiedTrack(BaseModel):
    recording_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    artist_id: str | None = None
    release_id: str | None = None
    release_title: str | None = None
    cover_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list)
    popularity: int = Field(default=0, ge=0)
    region: str | None = None


class RecommendedTrack(BaseModel):
    position: int = Field(ge=1)
    recording_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    artist_id: str | None = None
    release_id: str | None = None
    release_title: str | None = None
    cover_url: HttpUrl | None = None
    youtube_music_url: HttpUrl
    familiar: bool


class PlaylistDraft(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    request: MusicRequest
    tracks: list[RecommendedTrack] = Field(min_length=1)


class SavedPlaylist(PlaylistDraft):
    id: int = Field(gt=0)
    created_at: datetime
