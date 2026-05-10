"""LLM 인사이트 서비스 — 프롬프트 빌드 + 모델 호출 + 응답 검증 + 캐시 I/O.

decisions.md §6 (인사이트 사양), §7 (캐시 키), RUNBOOK §9 (가드).

1차 PoC 모델 토글: Gemini 2.5 Flash + GPT-4o (둘 다 결과 저장).
실 호출은 `APP_MODE=staging` + 키 셋업 + `assert_llm_allowed()` 통과 시만.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
from pathlib import Path
from string import Template
from typing import Any

from django.conf import settings

from .categories import (
    CATEGORIES,
    get_breakdown,
    get_headline_metric,
)
from .data_service import (
    fmt_ym_label,
    get_breakdown_series,
    get_monthly_series,
)
from .guards import (
    LLMBlockedOnPAError,
    REQUIRED_KEYS_CATEGORY,
    REQUIRED_KEYS_OVERALL,
    LLMResponseSchemaError,
    assert_llm_allowed,
    compute_insight_cache_key,
    daily_cap_exceeded,
    detect_unknown_numbers,
    validate_llm_response_schema,
)
from .metrics_meta import get_polarity, get_unit
from .signal_constants import PERCENTILE_WINDOW_MONTHS, SYSTEM_RANKED5
from .signal_service import calc_signal

PROMPT_VERSION = "v1"
PROMPTS_DIR = Path(settings.BASE_DIR) / "prompts" / PROMPT_VERSION
SIGUN = "4111"   # 1차 PoC 단일 시군

MODEL_GEMINI = "gemini-2.5-flash"
MODEL_GPT4O  = "gpt-4o"
ALL_MODELS = (MODEL_GEMINI, MODEL_GPT4O)


# ── 프롬프트 빌드 ───────────────────────────────────
def _load_template(name: str) -> Template:
    with open(PROMPTS_DIR / name, encoding="utf-8") as f:
        return Template(f.read())


def _build_category_payload(category: str, base_ym: str) -> dict:
    """프롬프트 컨텍스트 + 환각 가드용 allowed_numbers 수집."""
    metric = get_headline_metric(category)
    polarity = get_polarity(metric)
    unit = get_unit(metric)
    series = get_monthly_series(category)
    cur = series.get(base_ym)

    sig_mom   = calc_signal(series, base_ym, mode="mom",            polarity=polarity, window=PERCENTILE_WINDOW_MONTHS, system=SYSTEM_RANKED5)
    sig_yoy   = calc_signal(series, base_ym, mode="yoy",            polarity=polarity, window=PERCENTILE_WINDOW_MONTHS, system=SYSTEM_RANKED5)
    sig_short = calc_signal(series, base_ym, mode="momentum_short", polarity=polarity, window=PERCENTILE_WINDOW_MONTHS, system=SYSTEM_RANKED5)
    sig_long  = calc_signal(series, base_ym, mode="momentum_long",  polarity=polarity, window=PERCENTILE_WINDOW_MONTHS, system=SYSTEM_RANKED5)

    breakdown = get_breakdown(category)
    bd_series = get_breakdown_series(category)
    breakdown_lines = []
    bd_values: list[float] = []
    for name, srs in bd_series.items():
        v = srs.get(base_ym)
        if v is not None:
            breakdown_lines.append(f"  - {name}: {v:,.2f}")
            bd_values.append(float(v))
        else:
            breakdown_lines.append(f"  - {name}: 데이터 없음")

    allowed_numbers: list[float] = []
    for v in (cur, sig_mom["change_pct"], sig_yoy["change_pct"],
              sig_short["change_pct"], sig_long["change_pct"]):
        if v is not None:
            allowed_numbers.append(float(v))
    allowed_numbers.extend(bd_values)
    allowed_numbers.append(float(sig_mom.get("n_distribution") or 0))

    return {
        "sigun":            SIGUN,
        "base_ym":          fmt_ym_label(base_ym),
        "category":         category,
        "headline_metric":  metric,
        "unit":             unit,
        "polarity":         polarity,
        "current_value":    "데이터 없음" if cur is None else f"{cur:,.2f}",
        "mom_change":   "—" if sig_mom["change_pct"]   is None else f"{sig_mom['change_pct']:+.2f}",
        "mom_signal":   sig_mom["signal_v4"],
        "yoy_change":   "—" if sig_yoy["change_pct"]   is None else f"{sig_yoy['change_pct']:+.2f}",
        "yoy_signal":   sig_yoy["signal_v4"],
        "short_change": "—" if sig_short["change_pct"] is None else f"{sig_short['change_pct']:+.2f}",
        "short_signal": sig_short["signal_v4"],
        "long_change":  "—" if sig_long["change_pct"]  is None else f"{sig_long['change_pct']:+.2f}",
        "long_signal":  sig_long["signal_v4"],
        "n_distribution": sig_mom.get("n_distribution", 0),
        "breakdown_label": breakdown["label"],
        "breakdown_lines": "\n".join(breakdown_lines) if breakdown_lines else "  (없음)",
        "_allowed_numbers": allowed_numbers,
    }


def build_category_prompt(category: str, base_ym: str) -> tuple[str, dict]:
    """카테고리 인사이트용 프롬프트 본문 + 환각 가드 컨텍스트.

    Returns:
        (prompt_text, payload) — payload는 `_allowed_numbers` 포함.
    """
    payload = _build_category_payload(category, base_ym)
    tmpl = _load_template("category.j2")
    text = tmpl.safe_substitute({k: v for k, v in payload.items() if not k.startswith("_")})
    return text, payload


def build_overall_prompt(base_ym: str) -> tuple[str, dict]:
    """종합 보고서 프롬프트."""
    lines = []
    allowed: list[float] = []
    for cat in CATEGORIES:
        p = _build_category_payload(cat, base_ym)
        lines.append(
            f"- [{cat}] 헤드라인 {p['headline_metric']} = {p['current_value']} {p['unit']} | "
            f"MoM {p['mom_change']}% {p['mom_signal']} / YoY {p['yoy_change']}% {p['yoy_signal']} / "
            f"단기 {p['short_change']}% {p['short_signal']} / 장기 {p['long_change']}% {p['long_signal']}"
        )
        allowed.extend(p["_allowed_numbers"])
    tmpl = _load_template("overall.j2")
    text = tmpl.safe_substitute({
        "sigun":          SIGUN,
        "base_ym":        fmt_ym_label(base_ym),
        "category_lines": "\n".join(lines),
    })
    return text, {"_allowed_numbers": allowed}


# ── 캐시 I/O (mart_insight) ─────────────────────────
def _connect_mart() -> sqlite3.Connection:
    con = sqlite3.connect(str(settings.MART_DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def read_insight_from_mart(
    *, base_ym: str, category: str | None, model: str
) -> dict | None:
    """캐시 적중 시 응답 JSON dict 반환. miss면 None."""
    cat = category if category else ""
    with _connect_mart() as con:
        row = con.execute(
            """
            SELECT response_json, has_unknown_numbers, created_at FROM mart_insight
            WHERE sigun=? AND base_ym=? AND category=? AND model=? AND prompt_version=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (SIGUN, int(base_ym), cat, model, PROMPT_VERSION),
        ).fetchone()
    if row is None:
        return None
    return {
        "response":             json.loads(row["response_json"]),
        "has_unknown_numbers":  bool(row["has_unknown_numbers"]),
        "created_at":           row["created_at"],
    }


def write_insight_to_mart(
    *, base_ym: str, category: str | None, model: str,
    response: dict, has_unknown: bool,
) -> None:
    """카테고리 또는 종합 결과를 mart_insight에 INSERT."""
    cat = category if category else ""
    with _connect_mart() as con:
        con.execute(
            """
            INSERT INTO mart_insight
                (sigun, base_ym, category, model, prompt_version,
                 response_json, has_unknown_numbers, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                SIGUN, int(base_ym), cat, model, PROMPT_VERSION,
                json.dumps(response, ensure_ascii=False),
                1 if has_unknown else 0,
                _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ),
        )
        con.commit()


# ── 모델 호출 (provider 추상) ────────────────────────
class LLMCallError(RuntimeError):
    """LLM 호출 실패 (키 부재, API 에러, 응답 파싱 실패 등)."""


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        t = t.rstrip("`").rstrip()
        if t.endswith("```"):
            t = t[:-3].rstrip()
    return t


def call_llm(model: str, prompt: str, *, timeout: float = 30.0) -> dict:
    """모델별 호출 → JSON 응답 dict.

    실 호출은 키 환경변수 존재 시만 (`GOOGLE_API_KEY`, `OPENAI_API_KEY`).
    `assert_llm_allowed()`로 운영 가드 1차 차단.
    """
    assert_llm_allowed()
    if daily_cap_exceeded(model, _dt.date.today().isoformat()):
        raise LLMCallError(f"daily cap exceeded for {model}")

    if model == MODEL_GEMINI:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise LLMCallError("GOOGLE_API_KEY 미설정 — .env.staging 확인")
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(MODEL_GEMINI)
        resp = gm.generate_content(prompt, request_options={"timeout": timeout})
        text = _strip_code_fences(resp.text or "")
    elif model == MODEL_GPT4O:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMCallError("OPENAI_API_KEY 미설정 — .env.staging 확인")
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=timeout)
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = _strip_code_fences(completion.choices[0].message.content or "")
    else:
        raise LLMCallError(f"unknown model: {model}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMCallError(f"JSON 파싱 실패: {e} | text[:200]={text[:200]!r}") from e


# ── 통합 entry ──────────────────────────────────────
def generate_category_insight(
    *, base_ym: str, category: str, model: str,
    force: bool = False, dry_run: bool = False,
) -> dict:
    """캐시 조회 → 미적중 시 호출 → 검증 → 저장 → 결과 dict.

    Returns:
        {response, has_unknown_numbers, cache_hit: bool, dry_run: bool, cache_key: str}
    """
    cache_key = compute_insight_cache_key(
        sigun=SIGUN, base_ym=base_ym, category=category,
        model=model, prompt_version=PROMPT_VERSION,
    )
    if not force:
        hit = read_insight_from_mart(base_ym=base_ym, category=category, model=model)
        if hit:
            return {**hit, "cache_hit": True, "dry_run": False, "cache_key": cache_key}

    prompt, payload = build_category_prompt(category, base_ym)
    if dry_run:
        return {"prompt": prompt, "cache_hit": False, "dry_run": True, "cache_key": cache_key}

    response = call_llm(model, prompt)
    validate_llm_response_schema(response, REQUIRED_KEYS_CATEGORY)
    unknown = detect_unknown_numbers(json.dumps(response, ensure_ascii=False),
                                     payload["_allowed_numbers"])
    has_unknown = len(unknown) > 0
    write_insight_to_mart(base_ym=base_ym, category=category, model=model,
                          response=response, has_unknown=has_unknown)
    return {
        "response": response, "has_unknown_numbers": has_unknown,
        "cache_hit": False, "dry_run": False, "cache_key": cache_key,
        "unknown_tokens": unknown,
    }


def generate_overall_report(
    *, base_ym: str, model: str, force: bool = False, dry_run: bool = False,
) -> dict:
    cache_key = compute_insight_cache_key(
        sigun=SIGUN, base_ym=base_ym, category=None,
        model=model, prompt_version=PROMPT_VERSION,
    )
    if not force:
        hit = read_insight_from_mart(base_ym=base_ym, category=None, model=model)
        if hit:
            return {**hit, "cache_hit": True, "dry_run": False, "cache_key": cache_key}

    prompt, payload = build_overall_prompt(base_ym)
    if dry_run:
        return {"prompt": prompt, "cache_hit": False, "dry_run": True, "cache_key": cache_key}

    response = call_llm(model, prompt)
    validate_llm_response_schema(response, REQUIRED_KEYS_OVERALL)
    unknown = detect_unknown_numbers(json.dumps(response, ensure_ascii=False),
                                     payload["_allowed_numbers"])
    has_unknown = len(unknown) > 0
    write_insight_to_mart(base_ym=base_ym, category=None, model=model,
                          response=response, has_unknown=has_unknown)
    return {
        "response": response, "has_unknown_numbers": has_unknown,
        "cache_hit": False, "dry_run": False, "cache_key": cache_key,
        "unknown_tokens": unknown,
    }
