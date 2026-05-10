"""LLM·운영 가드 — decisions.md §6/§7, RUNBOOK.md §7~9 정책의 코드화.

5종 가드:
- assert_llm_allowed: PA 환경 + ENABLE_LLM_ON_PA=false 시 차단
- validate_llm_response_schema: 강제 JSON 스키마 검증
- detect_unknown_numbers: 응답 내 입력 외 수치 토큰 검출 (환각 가드)
- daily_cap_exceeded: 모델별 일일 호출 cap (1차 PoC는 카운터 미구현, 인터페이스만)
- compute_insight_cache_key: 캐시 키 (decisions.md §7)
"""
from __future__ import annotations

import os
import re
from typing import Iterable

REQUIRED_KEYS_CATEGORY = ("summary", "drivers", "risks", "policy_hint", "confidence")
REQUIRED_KEYS_OVERALL = ("summary", "drivers", "risks", "policy_hint", "confidence")


class LLMBlockedOnPAError(RuntimeError):
    """PA 환경 + LLM 호출 시도."""


class LLMResponseSchemaError(ValueError):
    """응답 JSON 스키마 위반."""


# ── 1. 운영 분기 가드 ─────────────────────────────────
def assert_llm_allowed() -> None:
    """LLM 호출 허용 여부 검사.

    PA 환경(`PYTHONANYWHERE_DOMAIN` 환경변수 존재) + `ENABLE_LLM_ON_PA=false` 이면 차단.
    decisions.md §7 / RUNBOOK §3.
    """
    is_pa = bool(os.getenv("PYTHONANYWHERE_DOMAIN"))
    enabled = os.getenv("ENABLE_LLM_ON_PA", "false").lower() == "true"
    if is_pa and not enabled:
        raise LLMBlockedOnPAError(
            "PA 환경에서 LLM 호출이 차단되었습니다. 사전 생성된 인사이트만 조회 가능합니다."
        )


# ── 2. 응답 스키마 강제 ────────────────────────────────
def validate_llm_response_schema(
    response: dict,
    schema_keys: Iterable[str] = REQUIRED_KEYS_CATEGORY,
) -> None:
    """필수 키 + 타입 검증.

    summary(str), drivers(list[str]), risks(list[str]), policy_hint(str), confidence(float 0~1).
    """
    if not isinstance(response, dict):
        raise LLMResponseSchemaError(f"response must be dict, got {type(response).__name__}")

    for key in schema_keys:
        if key not in response:
            raise LLMResponseSchemaError(f"missing required key: {key}")

    if not isinstance(response["summary"], str) or not response["summary"].strip():
        raise LLMResponseSchemaError("summary must be non-empty string")
    if not isinstance(response["policy_hint"], str):
        raise LLMResponseSchemaError("policy_hint must be string")
    if not isinstance(response["drivers"], list) or not all(isinstance(x, str) for x in response["drivers"]):
        raise LLMResponseSchemaError("drivers must be list[str]")
    if not isinstance(response["risks"], list) or not all(isinstance(x, str) for x in response["risks"]):
        raise LLMResponseSchemaError("risks must be list[str]")
    if not isinstance(response["confidence"], (int, float)):
        raise LLMResponseSchemaError("confidence must be number")
    c = float(response["confidence"])
    if not 0.0 <= c <= 1.0:
        raise LLMResponseSchemaError(f"confidence out of [0,1]: {c}")


# ── 3. 환각 가드 (입력 외 수치 토큰) ──────────────────
# 천 단위 콤마(`5,983,333`) 포함 큰 숫자를 한 토큰으로 매치. 콤마 없는 일반 숫자는 fallback.
_NUMBER_TOKEN_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


def _normalize_number(s: str) -> str:
    """`1,234.56` / `1234.56` 등을 비교용 정규 형태로 — 천단위 콤마 제거."""
    return s.replace(",", "")


def detect_unknown_numbers(
    response_text: str,
    allowed_numbers: Iterable[float],
    *,
    abs_tol: float = 0.5,
) -> list[str]:
    """응답에서 입력 외 수치 토큰 추출.

    응답에 등장한 모든 숫자 토큰 → `allowed_numbers` 중 어떤 값과도
    `abs(token - allowed) <= abs_tol`로 매칭되지 않으면 미허가로 분류.

    abs_tol은 1차 PoC default 0.5. 큰 단위(억원/명)는 호출 사이트에서 조정.
    """
    allowed = [float(x) for x in allowed_numbers]
    unknown: list[str] = []
    for m in _NUMBER_TOKEN_RE.finditer(response_text or ""):
        tok = m.group(0)
        try:
            v = float(_normalize_number(tok))
        except ValueError:
            continue
        if not any(abs(v - a) <= abs_tol for a in allowed):
            unknown.append(tok)
    return unknown


# ── 4. 일일 cap (1차 PoC는 카운터 미구현) ──────────────
def daily_cap_exceeded(model: str, today: str, limit: int = 1000) -> bool:  # noqa: ARG001
    """일일 호출 cap. 1차 PoC는 항상 False (인터페이스만, 카운터 구현은 후속).

    구현 시점: 사전 생성 파이프라인(`generate_insights`) 도입 후 카운터 + 영속 저장.
    """
    return False


# ── 5. 캐시 키 ─────────────────────────────────────────
def compute_insight_cache_key(
    *,
    sigun: str,
    base_ym: str,
    category: str | None,
    model: str,
    prompt_version: str,
) -> str:
    """LLM 인사이트 캐시 키 (decisions.md §7).

    - 카테고리 인사이트: (시군, 기준월, 카테고리, 모델, 프롬프트 버전)
    - 종합 보고서: category=None → 캐시 키에서 category 부분이 '__overall__'.
    """
    cat = category if category else "__overall__"
    return f"sigun={sigun}|base_ym={base_ym}|category={cat}|model={model}|prompt_ver={prompt_version}"
