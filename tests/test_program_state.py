from src.program_state import (
    ChangeKind,
    ProgramRecord,
    classify_programs,
    merge_snapshots,
    snapshot_programs,
)


def _program(end_at: str) -> ProgramRecord:
    return {
        "program_key": "support:PBLN_1",
        "source": "bizinfo",
        "title": "수출 바우처",
        "agency": "중소벤처기업부",
        "status": "접수중",
        "apply_start_at": "2026-07-01",
        "apply_end_at": end_at,
        "summary_raw": "수출 준비 지원",
    }


def test_program_state_detects_deadline_change():
    previous = snapshot_programs([_program("2026-07-31")])

    changes = classify_programs([_program("2026-08-15")], previous)

    assert changes[0].kind is ChangeKind.CHANGED
    assert changes[0].changed_fields == ("apply_end_at",)


def test_program_state_marks_first_seen_and_unchanged():
    program = _program("2026-07-31")

    first = classify_programs([program], {})
    unchanged = classify_programs([program], snapshot_programs([program]))

    assert first[0].kind is ChangeKind.NEW
    assert unchanged[0].kind is ChangeKind.UNCHANGED


def test_program_state_requeues_seen_but_unhandled_program():
    program = _program("2026-07-31")
    previous = snapshot_programs([program])

    queued = classify_programs([program], previous, set())
    handled = classify_programs([program], previous, {"support:PBLN_1"})

    assert queued[0].kind is ChangeKind.NEW
    assert handled[0].kind is ChangeKind.UNCHANGED


def test_program_state_preserves_failed_source_snapshot():
    bizinfo = _program("2026-07-31")
    sbiz = {**_program("2026-08-01"), "program_key": "sbiz24:1", "source": "sbiz24"}
    previous = snapshot_programs([bizinfo, sbiz])
    current = snapshot_programs([sbiz])

    merged = merge_snapshots(current, previous, {"bizinfo"})

    assert "support:PBLN_1" in merged
    assert "sbiz24:1" in merged
