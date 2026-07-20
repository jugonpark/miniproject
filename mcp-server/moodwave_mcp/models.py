from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class MusicRequest(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    region: Literal["domestic", "global", "mixed"] = "mixed"
    free_text: str | None = None
    familiar_artists: list[str] = Field(default_factory=list)
    count: Literal[5, 10, 15] = 10
    artist_origin_country: Literal["KR"] | None = None
    scene: Literal["KOREAN_INDIE"] | None = None
    strict_country_filter: bool = False
    allow_foreign_artists: bool = True
    recommendation_intent: dict | None = None

    @model_validator(mode="after")
    def require_condition_or_free_text(self) -> "MusicRequest":
        if not any(value.strip() for value in self.conditions) and not (
            self.free_text or ""
        ).strip():
            raise ValueError("conditions or free_text is required")
        return self


class CandidateArtist(BaseModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    popularity: int = Field(default=0, ge=0)
    region: str | None = None
    origin_status: Literal["VERIFIED_KR", "VERIFIED_FOREIGN", "UNKNOWN"] = "UNKNOWN"
    artist_country: str | None = None
    scene_match: Literal["KOREAN_INDIE"] | None = None
    matched_tags: list[str] = Field(default_factory=list)
    matched_categories: list[str] = Field(default_factory=list)
    appearance_count: int = Field(default=1, ge=1)


class TrackCandidate(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)


class VerifiedTrack(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recording_id: str = Field(min_length=1)
    track_title: str = Field(
        min_length=1,
        validation_alias=AliasChoices("track_title", "title"),
    )
    artist_name: str = Field(
        min_length=1,
        validation_alias=AliasChoices("artist_name", "artist"),
    )
    artist_mbid: str | None = Field(
        default=None,
        validation_alias=AliasChoices("artist_mbid", "artist_id"),
    )
    album_title: str | None = Field(
        default=None,
        validation_alias=AliasChoices("album_title", "release_title"),
    )
    release_year: int | None = None
    release_id: str | None = None
    release_group_id: str | None = None
    cover_image_url: HttpUrl | None = Field(
        default=None,
        validation_alias=AliasChoices("cover_image_url", "cover_url"),
    )
    tags: list[str] = Field(default_factory=list)
    popularity_score: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("popularity_score", "popularity"),
    )
    source: str = Field(default="musicbrainz", min_length=1)
    candidate_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    artist_country: str | None = Field(default=None, exclude_if=lambda value: value is None)
    origin_status: Literal["VERIFIED_KR", "VERIFIED_FOREIGN", "UNKNOWN"] | None = Field(default=None, exclude_if=lambda value: value is None)
    scene_match: Literal["KOREAN_INDIE"] | None = Field(default=None, exclude_if=lambda value: value is None)

    # Compatibility properties keep Task 2 callers working while serialized data uses the approved contract.
    @property
    def title(self) -> str:
        return self.track_title

    @property
    def artist(self) -> str:
        return self.artist_name

    @property
    def artist_id(self) -> str | None:
        return self.artist_mbid

    @property
    def release_title(self) -> str | None:
        return self.album_title

    @property
    def cover_url(self) -> HttpUrl | None:
        return self.cover_image_url

    @property
    def popularity(self) -> int:
        return self.popularity_score


class RecommendedTrack(BaseModel):
    position: int = Field(ge=1)
    recording_id: str = Field(min_length=1)
    candidate_id: str | None = None
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    artist_id: str | None = None
    release_id: str | None = None
    release_title: str | None = None
    release_year: int | None = None
    cover_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list)
    discovery_type: Literal["familiar", "discovery"] = "discovery"
    recommendation_reason: str = ""
    youtube_music_url: HttpUrl
    familiar: bool
    role: Literal["EMPATHY", "GROUNDING", "TRANSITION", "TARGET", "CLOSURE"] | None = None


class PlaylistDraft(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    request: MusicRequest
    tracks: list[RecommendedTrack] = Field(min_length=1)
    recommendation_status: Literal["SUCCESS", "PARTIAL", "INSUFFICIENT_MATCHING_TRACKS"] = "SUCCESS"


class SavedPlaylist(PlaylistDraft):
    id: int = Field(gt=0)
    created_at: datetime
