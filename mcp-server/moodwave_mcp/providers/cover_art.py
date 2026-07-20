from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .base import JsonRequester


class CoverArtProvider:
    base_url = "https://coverartarchive.org"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.requester = JsonRequester(client or httpx.AsyncClient(), timeout=timeout)

    async def find_cover(
        self,
        release_id: str | None,
        release_group_id: str | None = None,
    ) -> str | None:
        for kind, identifier in (("release", release_id), ("release-group", release_group_id)):
            if not identifier:
                continue
            payload = await self.requester.get(
                f"{self.base_url}/{kind}/{identifier}",
                allow_not_found=True,
            )
            cover = _cover_url(payload)
            if cover:
                return cover
        return None


def _cover_url(payload: dict | None) -> str | None:
    images = payload.get("images", []) if payload else []
    if not isinstance(images, list):
        return None
    ordered = sorted(
        (item for item in images if isinstance(item, dict)),
        key=lambda item: not bool(item.get("front")),
    )
    for image in ordered:
        url = str(image.get("image", "")).strip()
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc:
            return url
    return None
