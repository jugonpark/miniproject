from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    nvidia_api_key: str | None
    lastfm_api_key: str | None
    musicbrainz_user_agent: str | None
    musicbrainz_contact: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", "moodwave.db")),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY") or None,
            lastfm_api_key=os.getenv("LASTFM_API_KEY") or None,
            musicbrainz_user_agent=os.getenv("MUSICBRAINZ_USER_AGENT") or None,
            musicbrainz_contact=os.getenv("MUSICBRAINZ_CONTACT") or None,
        )
