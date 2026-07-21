from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata
from typing import TypeVar


T = TypeVar("T")


def normalize_music_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.split(r"\b(?:feat\.?|ft\.?|featuring)\b", value, maxsplit=1)[0]
    return " ".join(re.sub(r"[^\w]+", " ", value).split())


def music_version(value: str) -> frozenset[str]:
    normalized = normalize_music_name(value)
    markers = {"live", "remix", "instrumental", "acoustic", "ost"}
    found = {marker for marker in markers if re.search(rf"\b{marker}\b", normalized)}
    if re.search(r"\bremaster(?:ed)?\b", normalized):
        found.add("remaster")
    if "radio edit" in normalized:
        found.add("radio edit")
    return frozenset(found)


def normalize_tags(values: Iterable[str]) -> list[str]:
    return dedupe_candidates(value.strip().casefold() for value in values if value.strip())


def dedupe_candidates(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    return [value for value in values if not (value in seen or seen.add(value))]
