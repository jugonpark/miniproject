from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar


T = TypeVar("T")


def normalize_tags(values: Iterable[str]) -> list[str]:
    return dedupe_candidates(value.strip().casefold() for value in values if value.strip())


def dedupe_candidates(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    return [value for value in values if not (value in seen or seen.add(value))]
