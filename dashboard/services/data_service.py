"""데이터마트 리더 — `fact_monthly_kpi` (long-format) → monthly series dict.

decisions.md §7 (DB 분리, 읽기전용), legacy_migration.md §1 (categories) 기반.

읽기 전용. 쓰기 작업은 `dashboard.management.commands.importcsv`.
"""
from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

from django.conf import settings

from .categories import (
    get_breakdown,
    get_headline_metric,
    list_categories,
)


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{settings.MART_DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


# ── monthly series ─────────────────────────────────
def get_monthly_series(
    category: str,
    admdong_cd: str | None = None,
    metric: str | None = None,
) -> dict[str, float]:
    """헤드라인 monthly series (ym str → value).

    - category: 카테고리명 (categories.CATEGORIES key)
    - admdong_cd: None=시군 합계 (fact admdong_cd=''), 또는 8자리 코드
    - metric: None=카테고리 헤드라인 metric, 또는 명시
    - 헤드라인 행만 필터 (dim_kind='' AND age_gb='' AND sex_gb='')
    """
    if metric is None:
        metric = get_headline_metric(category)
    admdong = "" if admdong_cd is None else admdong_cd

    with _connect() as con:
        rows = con.execute(
            """
            SELECT etl_ym, value FROM fact_monthly_kpi
            WHERE category = ? AND metric = ?
              AND admdong_cd = ?
              AND dim_kind = '' AND age_gb = '' AND sex_gb = ''
            ORDER BY etl_ym
            """,
            (category, metric, admdong),
        ).fetchall()
    return {str(r["etl_ym"]): float(r["value"]) for r in rows}


def get_yoy_pairs(
    category: str, admdong_cd: str | None = None
) -> list[dict]:
    """YoY 페어 — (전년동월값 x, 올해동월값 y) 모든 가능 페어.

    38개월 데이터 → 202401~202602 26쌍 (TODO §C3.5).
    """
    series = get_monthly_series(category, admdong_cd=admdong_cd)
    months = sorted(series.keys())
    pairs = []
    for m in months:
        yoy_m = f"{int(m[:4]) - 1}{m[4:]}"
        if yoy_m in series:
            pairs.append({
                "ym":     m,
                "yoy_ym": yoy_m,
                "x":      series[yoy_m],
                "y":      series[m],
            })
    return pairs


def get_breakdown_series(
    category: str, admdong_cd: str | None = None
) -> dict[str, dict[str, float]]:
    """1차 차원분해 series — {dim_label: {ym: value}}.

    카테고리 정의(`breakdown.type`)에 따라:
    - "metric"   : fact의 dim_kind='' 헤드라인 metric별로 분리 (모든 admdong 조회 가능)
    - "dim_kind" : fact의 dim_kind/dim_value로 조회 (시군 합계만, admdong_cd 무시)
    """
    bd = get_breakdown(category)
    admdong = "" if admdong_cd is None else admdong_cd
    out: dict[str, dict[str, float]] = {}

    if bd["type"] == "metric":
        with _connect() as con:
            for label, metric in bd["mapping"]:
                rows = con.execute(
                    """
                    SELECT etl_ym, value FROM fact_monthly_kpi
                    WHERE category = ? AND metric = ?
                      AND admdong_cd = ?
                      AND dim_kind = '' AND age_gb = '' AND sex_gb = ''
                    ORDER BY etl_ym
                    """,
                    (category, metric, admdong),
                ).fetchall()
                out[label] = {str(r["etl_ym"]): float(r["value"]) for r in rows}
        return out

    if bd["type"] == "dim_kind":
        kind = bd["kind"]
        metric = bd["metric"]
        with _connect() as con:
            for v in bd["values"]:
                rows = con.execute(
                    """
                    SELECT etl_ym, value FROM fact_monthly_kpi
                    WHERE category = ? AND metric = ?
                      AND dim_kind = ? AND dim_value = ?
                      AND admdong_cd = '' AND age_gb = '' AND sex_gb = ''
                    ORDER BY etl_ym
                    """,
                    (category, metric, kind, v),
                ).fetchall()
                out[v] = {str(r["etl_ym"]): float(r["value"]) for r in rows}
        return out

    raise ValueError(f"unknown breakdown type: {bd['type']}")


def get_monthly_series_all_admdong(
    category: str,
    metric: str | None = None,
) -> dict[str, dict[str, float]]:
    """admdong_cd → monthly dict (Top N·Choropleth용 일괄)."""
    if metric is None:
        metric = get_headline_metric(category)
    with _connect() as con:
        rows = con.execute(
            """
            SELECT admdong_cd, etl_ym, value FROM fact_monthly_kpi
            WHERE category = ? AND metric = ?
              AND admdong_cd <> ''
              AND dim_kind = '' AND age_gb = '' AND sex_gb = ''
            ORDER BY admdong_cd, etl_ym
            """,
            (category, metric),
        ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["admdong_cd"], {})[str(r["etl_ym"])] = float(r["value"])
    return out


# ── 차원 ───────────────────────────────────────────
@lru_cache(maxsize=1)
def get_admdong_list() -> list[dict]:
    """[{cd, nm}] 정렬 (cd asc)."""
    with _connect() as con:
        rows = con.execute(
            "SELECT admdong_cd, admdong_nm FROM dim_admdong ORDER BY admdong_cd"
        ).fetchall()
    return [{"cd": r["admdong_cd"], "nm": r["admdong_nm"]} for r in rows]


@lru_cache(maxsize=1)
def get_admdong_name_map() -> dict[str, str]:
    return {a["cd"]: a["nm"] for a in get_admdong_list()}


@lru_cache(maxsize=1)
def get_available_months() -> list[str]:
    """etl_ym 정렬 (오래된 것부터)."""
    with _connect() as con:
        rows = con.execute(
            "SELECT etl_ym FROM dim_time ORDER BY etl_ym"
        ).fetchall()
    return [str(r["etl_ym"]) for r in rows]


def get_latest_month() -> str:
    return get_available_months()[-1]


def get_data_range_label() -> str:
    """푸터용: '2023.01 ~ 2026.02'."""
    months = get_available_months()
    if not months:
        return ""
    fst, lst = months[0], months[-1]
    return f"{fst[:4]}.{fst[4:]} ~ {lst[:4]}.{lst[4:]}"


def fmt_ym_label(ym: str) -> str:
    return f"{ym[:4]}.{ym[4:]}"


# ── TopoJSON (지도) ───────────────────────────────
@lru_cache(maxsize=1)
def get_admdong_topojson() -> dict:
    """`수원시_background.json` 원본 TopoJSON. 행정동코드는 10자리 — 클라이언트에서 8자리로 정규화."""
    with open(settings.ADMDONG_TOPOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def categories_for_dashboard() -> list[str]:
    """1차 PoC 6 카테고리 순서 (decisions.md §3)."""
    return list_categories()
