from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: str
    nvidia_api_key: str | None
    lastfm_api_key: str | None
    musicbrainz_user_agent: str | None
    musicbrainz_contact: str | None
    itunes_search_enabled: bool
    itunes_search_base_url: str
    itunes_search_country: str
    itunes_search_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ENV_FILE, override=False)
        return cls(
            database_path=os.getenv("DATABASE_URL") or os.getenv("DATABASE_PATH", "moodwave.db"),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY") or None,
            lastfm_api_key=os.getenv("LASTFM_API_KEY") or None,
            musicbrainz_user_agent=os.getenv("MUSICBRAINZ_USER_AGENT") or None,
            musicbrainz_contact=os.getenv("MUSICBRAINZ_CONTACT") or None,
            itunes_search_enabled=os.getenv("ITUNES_SEARCH_ENABLED", "true").lower() == "true",
            itunes_search_base_url=os.getenv("ITUNES_SEARCH_BASE_URL", "https://itunes.apple.com/search"),
            itunes_search_country=os.getenv("ITUNES_SEARCH_COUNTRY", "KR"),
            itunes_search_timeout=int(os.getenv("ITUNES_SEARCH_TIMEOUT_MS", "5000")) / 1000,
        )
