import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

ProgramRecord = dict[str, JsonValue]
_COMPARE_FIELDS: Final = (
    "title",
    "status",
    "apply_start_at",
    "apply_end_at",
    "agency",
    "summary_raw",
)


class ChangeKind(StrEnum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class ProgramSnapshot:
    source: str
    title: str
    status: str
    apply_start_at: str
    apply_end_at: str
    agency: str
    summary_raw: str


@dataclass(frozen=True, slots=True)
class ProgramChange:
    kind: ChangeKind
    changed_fields: tuple[str, ...]
    program: ProgramRecord


class _SnapshotModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    title: str
    status: str
    apply_start_at: str
    apply_end_at: str
    agency: str
    summary_raw: str


class _StateModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int
    updated_at: str
    programs: dict[str, _SnapshotModel]


def _text(value: JsonValue | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _snapshot(program: ProgramRecord) -> ProgramSnapshot:
    return ProgramSnapshot(
        source=_text(program.get("source")),
        title=_text(program.get("title")),
        status=_text(program.get("status")),
        apply_start_at=_text(program.get("apply_start_at")),
        apply_end_at=_text(program.get("apply_end_at")),
        agency=_text(program.get("agency")),
        summary_raw=_text(program.get("summary_raw")),
    )


def snapshot_programs(programs: list[ProgramRecord]) -> dict[str, ProgramSnapshot]:
    return {
        _text(program.get("program_key")): _snapshot(program)
        for program in programs
        if program.get("program_key")
    }


def merge_snapshots(
    current: dict[str, ProgramSnapshot],
    previous: dict[str, ProgramSnapshot],
    preserved_sources: set[str],
) -> dict[str, ProgramSnapshot]:
    merged = dict(current)
    for key, snapshot in previous.items():
        if snapshot.source in preserved_sources and key not in merged:
            merged[key] = snapshot
    return merged


def classify_programs(
    programs: list[ProgramRecord],
    previous: dict[str, ProgramSnapshot],
    legacy_notified: set[str] | None = None,
) -> tuple[ProgramChange, ...]:
    track_handled = legacy_notified is not None
    legacy_keys = legacy_notified or set()
    changes: list[ProgramChange] = []
    for program in programs:
        key = _text(program.get("program_key"))
        current = _snapshot(program)
        old = previous.get(key)
        if old is None:
            kind = ChangeKind.UNCHANGED if key in legacy_keys else ChangeKind.NEW
            changes.append(ProgramChange(kind, (), program))
            continue

        changed_fields = tuple(
            field
            for field in _COMPARE_FIELDS
            if getattr(old, field) != getattr(current, field)
        )
        if changed_fields:
            kind = ChangeKind.CHANGED
        elif track_handled and key not in legacy_keys:
            kind = ChangeKind.NEW
        else:
            kind = ChangeKind.UNCHANGED
        changes.append(ProgramChange(kind, changed_fields, program))
    return tuple(changes)


def load_program_state(path: str) -> dict[str, ProgramSnapshot]:
    state_path = Path(path)
    if not state_path.exists():
        return {}
    try:
        payload = _StateModel.model_validate_json(state_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return {}
    return {
        key: ProgramSnapshot(**snapshot.model_dump())
        for key, snapshot in payload.programs.items()
    }


def save_snapshot_state(snapshots: dict[str, ProgramSnapshot], path: str) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "programs": {key: asdict(snapshot) for key, snapshot in snapshots.items()},
    }
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(state_path)


def save_program_state(programs: list[ProgramRecord], path: str) -> None:
    save_snapshot_state(snapshot_programs(programs), path)
