from typing import Final, assert_never
from pathlib import Path

from src.source_result import CollectionStatus, CoverageEntry

_SOURCE_LABELS: Final[dict[str, str]] = {
    "bizinfo_support": "기업마당 지원사업",
    "bizinfo_event": "기업마당 행사",
    "fanfandaero": "판판대로",
    "sbiz24": "소상공인24 소진공 공고",
    "sbiz24_combine": "소상공인24 통합조회",
}


def _status_label(status: CollectionStatus) -> str:
    match status:
        case CollectionStatus.SUCCESS:
            return "성공"
        case CollectionStatus.PARTIAL:
            return "부분"
        case CollectionStatus.FAILED:
            return "실패"
        case CollectionStatus.DISABLED:
            return "미사용"
        case unreachable:
            assert_never(unreachable)


def _count_label(entry: CoverageEntry) -> str:
    if entry.reported_count is None:
        return f"{entry.normalized_count}건"
    if entry.unique_count == entry.fetched_count:
        return f"{entry.normalized_count}/{entry.reported_count}"
    return (
        f"{entry.fetched_count}/{entry.reported_count}행, "
        f"고유 {entry.normalized_count}건"
    )


def format_coverage_manifest(entries: tuple[CoverageEntry, ...]) -> str:
    lines = ["📊 coverage_manifest"]
    for entry in entries:
        label = _SOURCE_LABELS.get(entry.source, entry.source)
        line = f"- {label}: {_status_label(entry.status)} ({_count_label(entry)})"
        if entry.note:
            line += f" — {entry.note}"
        lines.append(line)
    return "\n".join(lines)


def has_degraded_sources(entries: tuple[CoverageEntry, ...]) -> bool:
    return any(
        entry.status in (CollectionStatus.PARTIAL, CollectionStatus.FAILED)
        for entry in entries
    )


def write_github_step_summary(coverage_manifest: str, path: str) -> None:
    summary_path = Path(path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("## 지원사업 수집 현황\n\n")
        summary.write(coverage_manifest + "\n")
