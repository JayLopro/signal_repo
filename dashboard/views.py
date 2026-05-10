"""메인 대시보드 뷰 — decisions.md §5-2 6 KPI / 6축 레이더 / TopN / Choropleth."""
from __future__ import annotations

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render

from .services.categories import (
    CATEGORIES,
    get_breakdown,
    get_category_by_slug,
    get_headline_metric,
    get_slug,
)
from .services.data_service import (
    categories_for_dashboard,
    fmt_ym_label,
    get_admdong_list,
    get_admdong_name_map,
    get_admdong_topojson,
    get_available_months,
    get_breakdown_series,
    get_data_range_label,
    get_latest_month,
    get_monthly_series,
    get_monthly_series_all_admdong,
    get_yoy_pairs,
)
from .services.metrics_meta import METRIC_META
from .services.llm_service import (
    MODEL_GEMINI,
    MODEL_GPT4O,
    read_insight_from_mart,
)

_LLM_TOGGLE_TO_MODEL = {"gemini": MODEL_GEMINI, "gpt4o": MODEL_GPT4O}
from .services.metrics_meta import get_polarity, get_unit
from .services.signal_constants import (
    ALL_SIGNAL_SYSTEMS,
    COMPARE_MODES,
    SIGNAL_INSUFFICIENT,
    SIGNAL_RADAR_VALUE,
    WINDOW_OPTIONS,
)
from .services.signal_service import calc_signal, is_window_disabled

ANALYSIS_MODES = (
    ("mom",            "전월대비(MoM)"),
    ("yoy",            "전년동월대비(YoY)"),
    ("momentum_short", "단기추세(3M)"),
    ("momentum_long",  "장기추세(12M)"),
)
SIGNAL_SYSTEMS = (
    ("ranked5",    "상대순위 5단계"),
    ("3sigma",     "±3σ 관리한계"),
    ("zscore",     "z-score"),
    ("percentile", "분위수 P10/30/70/90"),
    ("cutoff",     "직접 컷오프"),
)
WINDOW_LABELS = {12: "12개월", 24: "24개월", 0: "전체"}
LLM_MODELS = (
    ("gemini", "Gemini 2.5 Flash"),
    ("gpt4o",  "GPT-4o"),
)
MODE_KEYS = [k for k, _ in ANALYSIS_MODES]
SYSTEM_KEYS = [k for k, _ in SIGNAL_SYSTEMS]


def _parse_controls(request) -> dict:
    months = get_available_months()
    crym = request.GET.get("crym") or get_latest_month()
    if crym not in months:
        crym = get_latest_month()

    mode = request.GET.get("mode") or "mom"
    if mode not in MODE_KEYS:
        mode = "mom"

    system = request.GET.get("system") or "ranked5"
    if system not in ALL_SIGNAL_SYSTEMS:
        system = "ranked5"

    try:
        window = int(request.GET.get("window", 24))
    except (TypeError, ValueError):
        window = 24
    if window not in WINDOW_OPTIONS:
        window = 24

    llm_model = request.GET.get("llm_model") or "gemini"
    if llm_model not in {k for k, _ in LLM_MODELS}:
        llm_model = "gemini"

    return {
        "crym": crym, "mode": mode, "system": system,
        "window": window, "llm_model": llm_model,
    }


def _build_kpi_card(category: str, ctrl: dict) -> dict:
    metric = get_headline_metric(category)
    polarity = get_polarity(metric)
    series = get_monthly_series(category)

    main_sig = calc_signal(
        series, ctrl["crym"], mode=ctrl["mode"],
        polarity=polarity, window=ctrl["window"], system=ctrl["system"],
    )

    modes: dict[str, dict] = {}
    for mkey, _ in ANALYSIS_MODES:
        sig = calc_signal(
            series, ctrl["crym"], mode=mkey,
            polarity=polarity, window=ctrl["window"], system=ctrl["system"],
        )
        modes[mkey] = {
            "change_pct": sig["change_pct"],
            "signal_v4":  sig["signal_v4"],
            "disabled":   is_window_disabled(mkey, ctrl["window"]),
        }

    return {
        "category":        category,
        "slug":            get_slug(category),
        "headline_metric": metric,
        "unit":            get_unit(metric),
        "polarity":        polarity,
        "current_value":   series.get(ctrl["crym"]),
        "modes":           modes,
        "main_signal":     main_sig["signal_v4"],
        "main_change_pct": main_sig["change_pct"],
        "main_percentile": main_sig.get("percentile"),
        "n_distribution": main_sig.get("n_distribution", 0),
    }


def _build_radar(kpi_cards: list[dict]) -> dict:
    labels  = [c["category"] for c in kpi_cards]
    values  = [SIGNAL_RADAR_VALUE.get(c["main_signal"], 0) for c in kpi_cards]
    insuff  = [c["main_signal"] == SIGNAL_INSUFFICIENT for c in kpi_cards]
    return {"labels": labels, "values": values, "insufficient": insuff}


def _build_top_n_sigun(ctrl: dict, max_n: int = 10) -> list[dict]:
    """시군 합계 17 metric (헤드라인 6 + 부차 11) 정렬 상위 N — 행정동 차원 X.

    행정동별 metric은 규모·이슈 편차가 커서 (예: 신설기업수 ±100%) 일반 사용자
    가독성 떨어짐. 시군 단위 헤드라인+부차 17 metric에서 |change_pct| 상위만 노출.
    """
    rows: list[dict] = []
    for cat in categories_for_dashboard():
        headline = get_headline_metric(cat)
        for metric in CATEGORIES[cat]["metrics"]:
            polarity = get_polarity(metric)
            series = get_monthly_series(cat, metric=metric)
            sig = calc_signal(
                series, ctrl["crym"], mode=ctrl["mode"],
                polarity=polarity, window=ctrl["window"], system=ctrl["system"],
            )
            if sig["change_pct"] is None or sig["signal_v4"] == SIGNAL_INSUFFICIENT:
                continue
            rows.append({
                "category":    cat,
                "metric":      metric,
                "unit":        get_unit(metric),
                "is_headline": (metric == headline),
                "change_pct":  sig["change_pct"],
                "current":     series.get(ctrl["crym"]),
                "signal_v4":   sig["signal_v4"],
            })

    rows.sort(key=lambda r: abs(r["change_pct"]), reverse=True)
    top = rows[:max_n]
    for i, r in enumerate(top, 1):
        r["rank"] = i
    return top


def _build_choropleth(ctrl: dict) -> dict:
    """행정동별 6 카테고리 헤드라인 신호 강도 평균 (메인 지도용)."""
    name_map = get_admdong_name_map()
    admdong_scores: dict[str, list[int]] = {}

    for cat in categories_for_dashboard():
        metric = get_headline_metric(cat)
        polarity = get_polarity(metric)
        all_series = get_monthly_series_all_admdong(cat)
        for cd, series in all_series.items():
            sig = calc_signal(
                series, ctrl["crym"], mode=ctrl["mode"],
                polarity=polarity, window=ctrl["window"], system=ctrl["system"],
            )
            if sig["signal_v4"] != SIGNAL_INSUFFICIENT:
                admdong_scores.setdefault(cd, []).append(
                    SIGNAL_RADAR_VALUE.get(sig["signal_v4"], 0)
                )

    choropleth: dict[str, dict] = {}
    for cd in name_map:
        vals = admdong_scores.get(cd, [])
        if vals:
            choropleth[cd] = {"score": round(sum(vals) / len(vals), 3),
                              "n": len(vals), "nm": name_map[cd]}
        else:
            choropleth[cd] = {"score": None, "n": 0, "nm": name_map[cd]}
    return choropleth


def main_dashboard(request):
    ctrl = _parse_controls(request)
    categories = categories_for_dashboard()
    kpi_cards = [_build_kpi_card(c, ctrl) for c in categories]
    radar     = _build_radar(kpi_cards)
    top_n      = _build_top_n_sigun(ctrl, max_n=10)
    choropleth = _build_choropleth(ctrl)

    report_label = "생성" if settings.APP_MODE == "staging" else "보기"
    window_disabled = is_window_disabled(ctrl["mode"], ctrl["window"])

    context = {
        "page_title":   "메인 대시보드",
        "active_menu": "dashboard",
        "controls": {
            "current":  ctrl,
            "options": {
                "crym":      [{"value": m, "label": fmt_ym_label(m)} for m in reversed(get_available_months())],
                "mode":      list(ANALYSIS_MODES),
                "system":    list(SIGNAL_SYSTEMS),
                "window":    [{"value": w, "label": WINDOW_LABELS[w], "disabled": is_window_disabled(ctrl["mode"], w)} for w in WINDOW_OPTIONS],
                "llm_model": list(LLM_MODELS),
            },
            "window_disabled": window_disabled,
        },
        "kpi_cards":         kpi_cards,
        "radar":             radar,
        "top_n":             top_n,
        "choropleth":        choropleth,
        "data_range_label":  get_data_range_label(),
        "report_label":      report_label,
        "app_mode":          settings.APP_MODE,
    }
    return render(request, "dashboard/main.html", context)


def _build_headline_timeseries(category: str, ctrl: dict) -> dict:
    """헤드라인 metric 38개월 시계열 + 12M 이동평균 ± 1σ 밴드."""
    series = get_monthly_series(category)
    months = get_available_months()
    values = [series.get(m) for m in months]

    rolling, band_up, band_lo = [], [], []
    window = 12
    for i in range(len(values)):
        if i < window - 1:
            rolling.append(None); band_up.append(None); band_lo.append(None)
            continue
        win_vals = [v for v in values[i - window + 1 : i + 1] if v is not None]
        if len(win_vals) < 3:
            rolling.append(None); band_up.append(None); band_lo.append(None)
            continue
        m = sum(win_vals) / len(win_vals)
        var = sum((v - m) ** 2 for v in win_vals) / (len(win_vals) - 1)
        sd = var ** 0.5
        rolling.append(round(m, 2))
        band_up.append(round(m + sd, 2))
        band_lo.append(round(m - sd, 2))

    return {
        "labels":       [fmt_ym_label(m) for m in months],
        "months":       months,
        "values":       values,
        "rolling_mean": rolling,
        "band_upper":   band_up,
        "band_lower":   band_lo,
        "current_ym":   ctrl["crym"],
        "unit":         get_unit(get_headline_metric(category)),
    }


def _build_trend_series(category: str, ctrl: dict, admdong_cd: str | None = None) -> dict:
    """시군(default) 또는 단일 행정동의 단기·장기 모멘텀 변화율 시계열.

    x=38개월, y=변화율%, 두 라인(단기 3M / 장기 12M). 일반 사용자 가독성 ↑
    (기존 행정동 44 산점도 대체).
    legend 클릭으로 라인 토글, default 표시는 두 라인 모두 (사용자가 한쪽만 보고 싶을 때
    legend 클릭하여 hide).
    """
    metric = get_headline_metric(category)
    polarity = get_polarity(metric)
    series = get_monthly_series(category, admdong_cd=admdong_cd)
    months = get_available_months()

    short_vals: list = []
    long_vals: list = []
    long_disabled = is_window_disabled("momentum_long", ctrl["window"])

    for m in months:
        s_short = calc_signal(series, m, mode="momentum_short",
                              polarity=polarity, window=ctrl["window"], system=ctrl["system"])
        short_vals.append(s_short["change_pct"])
        if long_disabled:
            long_vals.append(None)
        else:
            s_long = calc_signal(series, m, mode="momentum_long",
                                 polarity=polarity, window=ctrl["window"], system=ctrl["system"])
            long_vals.append(s_long["change_pct"])

    return {
        "labels":        [fmt_ym_label(m) for m in months],
        "months":        months,
        "short":         short_vals,
        "long":          long_vals,
        "current_ym":    ctrl["crym"],
        "long_disabled": long_disabled,
        "admdong_cd":    admdong_cd or "",
        "scope_label":   "시군 합계 (4111)" if not admdong_cd else (get_admdong_name_map().get(admdong_cd, admdong_cd)),
    }


def _build_breakdown(category: str, ctrl: dict) -> dict:
    """1차 차원분해 — categories.breakdown 정의 사용."""
    bd = get_breakdown(category)
    headline_metric = get_headline_metric(category)
    series_map = get_breakdown_series(category)
    months = get_available_months()

    items = []
    for label, series in series_map.items():
        if not series:
            continue
        if bd["type"] == "metric":
            metric = dict(bd["mapping"]).get(label, label)
        else:
            metric = bd.get("metric", headline_metric)
        meta = METRIC_META.get(metric, {})
        polarity = meta.get("polarity", "positive")
        sig = calc_signal(series, ctrl["crym"], mode=ctrl["mode"],
                          polarity=polarity, window=ctrl["window"], system=ctrl["system"])
        items.append({
            "name":          label,
            "metric":        metric,
            "unit":          meta.get("unit", ""),
            "latest_value":  series.get(ctrl["crym"]),
            "change_pct":    sig["change_pct"],
            "signal_v4":     sig["signal_v4"],
            "series":        [series.get(m) for m in months],
            "raw_badge":     label in CATEGORIES[category].get("dimension", {}).get("raw_uncalibrated", []),
        })
    return {
        "type":         bd["type"],
        "label":        bd["label"],
        "labels_ym":    [fmt_ym_label(m) for m in months],
        "items":        items,
    }


def _build_yoy_scatter(category: str, ctrl: dict) -> dict:
    """YoY 산점도 — 전년동월값(x) vs 올해동월값(y) 모든 가능 페어 + 45°선용 범위."""
    pairs = get_yoy_pairs(category)
    unit = get_unit(get_headline_metric(category))
    points = []
    for p in pairs:
        points.append({
            "x":       p["x"],
            "y":       p["y"],
            "ym":      p["ym"],
            "yoy_ym":  p["yoy_ym"],
            "current": (p["ym"] == ctrl["crym"]),
        })
    all_vals = [p["x"] for p in points] + [p["y"] for p in points]
    if all_vals:
        lo, hi = min(all_vals), max(all_vals)
        pad = (hi - lo) * 0.05 if hi > lo else max(abs(hi), 1) * 0.05
        axis_min = lo - pad
        axis_max = hi + pad
    else:
        axis_min, axis_max = 0, 1
    return {
        "points":   points,
        "unit":     unit,
        "axis_min": axis_min,
        "axis_max": axis_max,
        "current_ym": ctrl["crym"],
    }


def _build_metric_tree(category: str) -> list[dict]:
    """카테고리 지표 트리 — categories.metrics + metrics_meta."""
    out = []
    for m in CATEGORIES[category]["metrics"]:
        meta = METRIC_META.get(m, {})
        out.append({
            "metric":     m,
            "unit":       meta.get("unit", ""),
            "polarity":   meta.get("polarity", "neutral"),
            "definition": meta.get("definition", ""),
        })
    return out


def category_detail(request, slug: str):
    category = get_category_by_slug(slug)
    if category is None:
        raise Http404(f"unknown category slug: {slug}")

    ctrl = _parse_controls(request)
    # 행정동 셀렉터: default = 시군 합계(빈 문자열). 유효 코드만 허용.
    admdong_cd = request.GET.get("admdong", "") or ""
    valid_cds = {a["cd"] for a in get_admdong_list()}
    if admdong_cd and admdong_cd not in valid_cds:
        admdong_cd = ""

    kpi = _build_kpi_card(category, ctrl)
    timeseries = _build_headline_timeseries(category, ctrl)
    trend_series = _build_trend_series(category, ctrl, admdong_cd=admdong_cd or None)
    yoy_scatter = _build_yoy_scatter(category, ctrl)
    breakdown  = _build_breakdown(category, ctrl)
    metric_tree = _build_metric_tree(category)

    report_label = "생성" if settings.APP_MODE == "staging" else "보기"
    window_disabled = is_window_disabled(ctrl["mode"], ctrl["window"])

    # LLM 인사이트 조회 (mart_insight 캐시) — 적중 시 박스에 표시, 미적중 시 placeholder 유지
    llm_model_id = _LLM_TOGGLE_TO_MODEL.get(ctrl["llm_model"], MODEL_GEMINI)
    llm_insight = read_insight_from_mart(
        base_ym=ctrl["crym"], category=category, model=llm_model_id,
    )

    context = {
        "page_title":   f"{category} · 카테고리 상세",
        "active_menu":  slug,
        "category":     category,
        "category_slug": slug,
        "controls": {
            "current":  ctrl,
            "options": {
                "crym":      [{"value": m, "label": fmt_ym_label(m)} for m in reversed(get_available_months())],
                "mode":      list(ANALYSIS_MODES),
                "system":    list(SIGNAL_SYSTEMS),
                "window":    [{"value": w, "label": WINDOW_LABELS[w], "disabled": is_window_disabled(ctrl["mode"], w)} for w in WINDOW_OPTIONS],
                "llm_model": list(LLM_MODELS),
            },
            "window_disabled": window_disabled,
        },
        "kpi":              kpi,
        "timeseries":       timeseries,
        "trend_series":     trend_series,
        "yoy_scatter":      yoy_scatter,
        "breakdown":        breakdown,
        "metric_tree":      metric_tree,
        "admdong_options":  [{"cd": "", "nm": "시군 합계 (4111)"}] + get_admdong_list(),
        "admdong_selected": admdong_cd,
        "data_range_label": get_data_range_label(),
        "report_label":     report_label,
        "app_mode":         settings.APP_MODE,
        "llm_placeholder": (
            f"{llm_model_id} 모델 사전 생성 인사이트가 없습니다 "
            f"(기준: 상대순위 5단계 · 24개월 · MoM·YoY·단기·장기 · 기준월 {fmt_ym_label(ctrl['crym'])}). "
            f"`python manage.py generate_insights --category {slug} --crym {ctrl['crym']} --model {ctrl['llm_model']}` 으로 생성."
        ),
        "llm_insight":  llm_insight,
        "llm_model_id": llm_model_id,
    }
    return render(request, "dashboard/category_detail.html", context)


def overall_report(request):
    """종합 보고서 — mart_insight(category=NULL/'')에서 조회.

    decisions.md §1·§6: PA는 사전 결과 보기, 로컬 staging은 LLM 호출 생성.
    """
    ctrl = _parse_controls(request)
    llm_model_id = _LLM_TOGGLE_TO_MODEL.get(ctrl["llm_model"], MODEL_GEMINI)
    insight = read_insight_from_mart(base_ym=ctrl["crym"], category=None, model=llm_model_id)

    context = {
        "page_title":  "종합 보고서",
        "active_menu": "overall",
        "controls": {
            "current": ctrl,
            "options": {
                "crym":      [{"value": m, "label": fmt_ym_label(m)} for m in reversed(get_available_months())],
                "mode":      list(ANALYSIS_MODES),
                "system":    list(SIGNAL_SYSTEMS),
                "window":    [{"value": w, "label": WINDOW_LABELS[w], "disabled": is_window_disabled(ctrl["mode"], w)} for w in WINDOW_OPTIONS],
                "llm_model": list(LLM_MODELS),
            },
            "window_disabled": is_window_disabled(ctrl["mode"], ctrl["window"]),
        },
        "llm_insight":      insight,
        "llm_model_id":     llm_model_id,
        "report_label":     "생성" if settings.APP_MODE == "staging" else "보기",
        "app_mode":         settings.APP_MODE,
        "data_range_label": get_data_range_label(),
        "generate_command": f"python manage.py generate_insights --overall --crym {ctrl['crym']} --model {ctrl['llm_model']}",
    }
    return render(request, "dashboard/overall_report.html", context)


def signal_compare(request):
    """6 카테고리 헤드라인 × 5 신호체계 일괄 비교 표 (decisions.md §5-4)."""
    ctrl = _parse_controls(request)
    rows = []
    for cat in categories_for_dashboard():
        metric = get_headline_metric(cat)
        polarity = get_polarity(metric)
        series = get_monthly_series(cat)
        system_cells = []
        for system_key, system_label in SIGNAL_SYSTEMS:
            sig = calc_signal(
                series, ctrl["crym"], mode=ctrl["mode"],
                polarity=polarity, window=ctrl["window"], system=system_key,
            )
            system_cells.append({
                "system":     system_key,
                "label":      system_label,
                "signal_v4":  sig["signal_v4"],
                "change_pct": sig["change_pct"],
            })
        rows.append({
            "category":        cat,
            "slug":            get_slug(cat),
            "headline_metric": metric,
            "polarity":        polarity,
            "cells":           system_cells,
        })

    captions = {
        "ranked5":    "상대순위: 과거 분포 대비 절대값 상위 20%/40% 컷",
        "3sigma":     "±3σ: 평균 ±3σ를 강한, ±2σ를 약한 신호로 분류",
        "zscore":     "z-score: |z|≥1.0 강한, ≥0.5 약한 신호 (분포 정규성 가정)",
        "percentile": "분위수: P10/30/70/90 컷오프로 5단계",
        "cutoff":     "직접 컷오프: 절대 변화율 |chg|≥10% 강한, ≥5% 약한 (기본 컷)",
    }

    context = {
        "page_title":  "신호체계 비교",
        "active_menu": "compare",
        "controls": {
            "current":  ctrl,
            "options": {
                "crym":      [{"value": m, "label": fmt_ym_label(m)} for m in reversed(get_available_months())],
                "mode":      list(ANALYSIS_MODES),
                "system":    list(SIGNAL_SYSTEMS),
                "window":    [{"value": w, "label": WINDOW_LABELS[w], "disabled": is_window_disabled(ctrl["mode"], w)} for w in WINDOW_OPTIONS],
                "llm_model": list(LLM_MODELS),
            },
            "window_disabled": is_window_disabled(ctrl["mode"], ctrl["window"]),
        },
        "rows":              rows,
        "system_columns":    list(SIGNAL_SYSTEMS),
        "captions":          captions,
        "data_range_label":  get_data_range_label(),
        "app_mode":          settings.APP_MODE,
    }
    return render(request, "dashboard/signal_compare.html", context)


def admdong_topojson(request):
    """수원시_background.json 원본 TopoJSON 그대로 응답 (클라이언트에서 GeoJSON 변환)."""
    response = JsonResponse(get_admdong_topojson(), json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "public, max-age=3600"
    return response
