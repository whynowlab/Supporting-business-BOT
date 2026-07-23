from dataclasses import dataclass
from enum import StrEnum

from pydantic import JsonValue

RawItem = dict[str, JsonValue]


class CollectionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SourceBatch:
    source: str
    items: tuple[RawItem, ...]
    status: CollectionStatus
    reported_count: int | None
    fetched_count: int
    note: str | None = None
    @property
    def unique_count(self) -> int:
        return len(self.items)

    def to_coverage(self, normalized_count: int) -> "CoverageEntry":
        return CoverageEntry(
            source=self.source,
            status=self.status,
            reported_count=self.reported_count,
            fetched_count=self.fetched_count,
            unique_count=self.unique_count,
            normalized_count=normalized_count,
            note=self.note,
        )


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    source: str
    status: CollectionStatus
    reported_count: int | None
    fetched_count: int
    unique_count: int
    normalized_count: int
    note: str | None = None
