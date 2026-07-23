import os

from src.filters import get_days_left, is_obviously_irrelevant, is_recommended
from src.program_state import (
    ChangeKind,
    ProgramChange,
    ProgramRecord,
    ProgramSnapshot,
    merge_snapshots,
    save_snapshot_state,
    snapshot_programs,
)
from src.source_result import CollectionStatus, CoverageEntry


def run_keyword_fallback(items: list[dict], profile: dict) -> list[dict]:
    recommendations = []
    for item in items:
        hard_rejected, _ = is_obviously_irrelevant(item)
        if hard_rejected:
            continue
        ok, score, reasons = is_recommended(item, profile)
        if ok:
            recommendations.append({"item": item, "score": score, "reasons": reasons})
    recommendations.sort(key=lambda recommendation: recommendation["score"], reverse=True)
    return recommendations


def programs_to_process(changes: tuple[ProgramChange, ...]) -> list[ProgramRecord]:
    programs: list[ProgramRecord] = []
    for change in changes:
        if change.kind is ChangeKind.UNCHANGED:
            continue
        if change.kind is ChangeKind.NEW:
            status = str(change.program.get("status") or "")
            days_left = get_days_left(change.program)
            if status == "마감" or (days_left is not None and days_left < 0):
                continue

        program = dict(change.program)
        program["_change_kind"] = change.kind.value
        program["_changed_fields"] = list(change.changed_fields)
        programs.append(program)
    return programs


def prioritize_programs(items: list[ProgramRecord], limit: int) -> list[ProgramRecord]:
    def priority(program: ProgramRecord) -> tuple[int, str]:
        days_left = get_days_left(program)
        deadline_rank = days_left if days_left is not None else 1_000_000
        return deadline_rank, str(program.get("title") or "")

    changed = [item for item in items if item.get("_change_kind") == ChangeKind.CHANGED]
    new = [item for item in items if item.get("_change_kind") != ChangeKind.CHANGED]
    remaining_slots = max(0, limit - len(changed))
    return sorted(changed, key=priority) + sorted(new, key=priority)[:remaining_slots]


def _preserved_program_sources(coverage: tuple[CoverageEntry, ...]) -> set[str]:
    source_map = {
        "bizinfo_support": "bizinfo",
        "bizinfo_event": "bizinfo",
        "fanfandaero": "fanfandaero",
        "sbiz24": "sbiz24",
        "sbiz24_combine": "sbiz24_combine",
    }
    return {
        source_map[entry.source]
        for entry in coverage
        if entry.status in (CollectionStatus.PARTIAL, CollectionStatus.FAILED)
        and entry.source in source_map
    }


def persist_program_state(
    items: list[ProgramRecord],
    previous: dict[str, ProgramSnapshot],
    coverage: tuple[CoverageEntry, ...],
) -> None:
    current = snapshot_programs(items)
    merged = merge_snapshots(current, previous, _preserved_program_sources(coverage))
    path = os.getenv("PROGRAM_STATE_PATH", "data/program_state.json")
    save_snapshot_state(merged, path)


def apply_hard_filter(items: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    candidates = []
    rejected = []
    for item in items:
        is_rejected, reason = is_obviously_irrelevant(item)
        if is_rejected:
            rejected.append((item, reason))
        else:
            candidates.append(item)
    return candidates, rejected
