# src/llm_filter.py
import os
import json
import logging
from dataclasses import dataclass
from enum import StrEnum

from google.genai import errors as genai_errors

from src.company_profile import build_stage1_prompt, build_stage2_prompt

logger = logging.getLogger(__name__)

BATCH_SIZE = 10


class EligibilityVerdict(StrEnum):
    CONFIRMED = "확인됨"
    CONDITIONAL = "조건부"
    NEEDS_CONFIRMATION = "확인 필요"
    INELIGIBLE = "신청 불가"
    PIVOT_CANDIDATE = "사업전환 후보"


class GeminiConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Assessment:
    grade: str       # "A", "B", "C"
    reason: str      # One-line rationale
    eligibility: str  # "충족", "미확인", "미충족"
    verdict: EligibilityVerdict = EligibilityVerdict.NEEDS_CONFIRMATION


def parse_stage1_response(raw, total_count: int) -> dict[int, str]:
    """Parse Stage 1 JSON response. Missing/invalid entries default to PASS."""
    result = {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    items = raw.get("results", []) if isinstance(raw, dict) else []
    if not isinstance(items, list):
        items = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        decision = item.get("decision", "PASS")
        result[item["id"]] = decision if decision in ("PASS", "REJECT") else "PASS"

    # Fill missing IDs with PASS
    for i in range(1, total_count + 1):
        if i not in result:
            result[i] = "PASS"

    return result


def parse_stage2_response(raw) -> Assessment:
    """Parse Stage 2 JSON response. Invalid values get safe defaults."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    grade = raw.get("grade", "B")
    if grade not in ("A", "B", "C"):
        grade = "B"
    reason = raw.get("reason", "LLM 판단 불가")
    reason = reason if isinstance(reason, str) else "LLM 판단 불가"
    eligibility = raw.get("eligibility", "미확인")
    if eligibility not in ("충족", "미확인", "미충족"):
        eligibility = "미확인"
    try:
        verdict = EligibilityVerdict(raw.get("verdict"))
    except (TypeError, ValueError):
        if eligibility == "미충족" or grade == "C":
            verdict = EligibilityVerdict.INELIGIBLE
        else:
            verdict = EligibilityVerdict.NEEDS_CONFIRMATION
    return Assessment(
        grade=grade,
        reason=reason,
        eligibility=eligibility,
        verdict=verdict,
    )


def _get_gemini_client():
    """Lazy-init Gemini client. Returns None if key not set."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    from google import genai
    return genai.Client(api_key=api_key)


def stage1_quick_filter(programs: list[dict]) -> list[dict]:
    """Batch-filter programs by title+summary. Returns PASS-ed programs."""
    client = _get_gemini_client()
    if client is None:
        raise GeminiConfigurationError("GEMINI_API_KEY not configured")

    passed = []
    for batch_start in range(0, len(programs), BATCH_SIZE):
        batch = programs[batch_start : batch_start + BATCH_SIZE]
        prompt = build_stage1_prompt(batch)

        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "decision": {"type": "string", "enum": ["PASS", "REJECT"]},
                                    },
                                    "required": ["id", "decision"],
                                },
                            }
                        },
                    },
                },
            )
            decisions = parse_stage1_response(json.loads(response.text), len(batch))
        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            json.JSONDecodeError,
            genai_errors.APIError,
        ) as error:
            logger.error("Stage 1 Gemini call failed: %s", error)
            decisions = {i: "PASS" for i in range(1, len(batch) + 1)}

        for i, program in enumerate(batch, 1):
            if decisions.get(i) == "PASS":
                passed.append(program)

    return passed


def stage2_assess(program: dict, detail_text: str) -> Assessment:
    """Assess single program with detail page text."""
    if not detail_text:
        return Assessment(
            grade="B",
            reason="상세페이지 접근 불가",
            eligibility="미확인",
            verdict=EligibilityVerdict.NEEDS_CONFIRMATION,
        )

    client = _get_gemini_client()
    if client is None:
        raise GeminiConfigurationError("GEMINI_API_KEY not configured")

    prompt = build_stage2_prompt(program, detail_text)

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "grade": {"type": "string", "enum": ["A", "B", "C"]},
                        "reason": {"type": "string"},
                        "eligibility": {"type": "string", "enum": ["충족", "미확인", "미충족"]},
                        "verdict": {
                            "type": "string",
                            "enum": ["확인됨", "조건부", "확인 필요", "신청 불가", "사업전환 후보"],
                        },
                    },
                    "required": ["grade", "reason", "eligibility", "verdict"],
                },
            },
        )
        return parse_stage2_response(json.loads(response.text))
    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        genai_errors.APIError,
    ) as error:
        logger.error("Stage 2 Gemini call failed: %s", error)
        return Assessment(
            grade="B",
            reason="LLM 판단 불가",
            eligibility="미확인",
            verdict=EligibilityVerdict.NEEDS_CONFIRMATION,
        )
