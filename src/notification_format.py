from datetime import datetime

from src.llm_filter import Assessment
from src.program_state import ChangeKind


def source_label(program: dict) -> str:
    labels = {
        "bizinfo": "기업마당",
        "fanfandaero": "판판대로",
        "sbiz24": "소상공인24",
        "sbiz24_combine": "소상공인24 통합",
    }
    return labels.get(program.get("source"), program.get("source") or "출처미상")


def change_marker(program: dict) -> str:
    kind = program.get("_change_kind")
    if kind == ChangeKind.NEW:
        return "[신규] "
    if kind != ChangeKind.CHANGED:
        return ""

    labels = {
        "title": "제목",
        "status": "상태",
        "apply_start_at": "접수 시작",
        "apply_end_at": "마감",
        "agency": "기관",
        "summary_raw": "내용",
    }
    changed = [labels.get(field, field) for field in program.get("_changed_fields", [])]
    return f"[변경: {', '.join(changed) or '내용'}] "


def format_graded_message(
    grade_a: list[tuple[dict, Assessment]],
    grade_b: list[tuple[dict, Assessment]],
    total_checked: int,
    stage1_passed: int,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not grade_a and not grade_b:
        return f"✅ [{today}] 신규 해당 공고 없음 ({total_checked}건 검토, {stage1_passed}건 상세 판단)"

    parts = [f"📢 [{today}] 지원사업 알림\n"]

    if grade_a:
        parts.append(f"🔴 반드시 검토 ({len(grade_a)}건)\n")
        for index, (program, assessment) in enumerate(grade_a, 1):
            title = (program.get("title") or "제목 없음").strip()
            parts.append(f"{index}. {change_marker(program)}[{source_label(program)}] {title}")
            parts.append(f"   → [{assessment.verdict.value}] {assessment.reason}")
            parts.append(f"   🔗 {program.get('url', '#')}\n")

    if grade_b:
        heading = "참고 사항" if not grade_a else "참고"
        parts.append(f"🟡 {heading} ({len(grade_b)}건)\n")
        for index, (program, assessment) in enumerate(grade_b, 1):
            title = (program.get("title") or "제목 없음").strip()
            parts.append(f"{index}. {change_marker(program)}[{source_label(program)}] {title}")
            parts.append(f"   → [{assessment.verdict.value}] {assessment.reason}")
            parts.append(f"   🔗 {program.get('url', '#')}\n")

    return "\n".join(parts)


def format_fallback_message(recommendations: list[dict]) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"⚠️ [{today}] LLM 판단 불가, 키워드 기반 결과 ({len(recommendations)}건)\n"]
    for recommendation in recommendations:
        item = recommendation["item"]
        title = (item.get("title") or "제목 없음").strip()
        reasons = ", ".join(recommendation["reasons"])
        parts.append(
            f"[{recommendation['score']}] {change_marker(item)}[{source_label(item)}] {title}"
        )
        parts.append(f"💡 {reasons}")
        parts.append(f"🔗 {item.get('url', '#')}\n")

    return "\n".join(parts)


def _split_message(body: str, max_length: int) -> list[str]:
    chunks: list[str] = []
    remaining = body.strip()
    while len(remaining) > max_length:
        window = remaining[: max_length + 1]
        split_at = max(window.rfind("\n\n"), window.rfind("\n"))
        if split_at <= 0:
            split_at = max_length
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def messages_with_coverage(
    body: str,
    coverage_manifest: str,
    max_length: int = 4000,
) -> tuple[str, ...]:
    chunks = _split_message(body, max_length)
    suffix = "\n\n" + coverage_manifest
    if chunks and len(chunks[-1]) + len(suffix) <= max_length:
        chunks[-1] += suffix
    else:
        chunks.extend(_split_message(coverage_manifest, max_length))
    return tuple(chunks)


def with_coverage(body: str, coverage_manifest: str) -> str:
    separator = "\n\n"
    max_body_length = max(0, 4000 - len(separator) - len(coverage_manifest))
    if len(body) > max_body_length:
        body = body[: max(0, max_body_length - 18)] + "\n...(공고 일부 생략)..."
    return body + separator + coverage_manifest
