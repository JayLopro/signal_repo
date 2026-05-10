"""시그널 산정 엔진 — legacy `signal_engine_v3.py` 6 함수 이식 (streamlit 제거).

decisions.md §4, legacy_migration.md §2 기반.

핵심 6 함수 (TODO §C2):
- get_change_value(monthly, crym, mode)
- get_momentum_ab(monthly, crym, window)
- calc_current_deviation(monthly, crym, window)
- build_change_distribution(monthly, crym, mode, window)
- classify_signal_rank(current_change, distribution)        # v3 3단계 호환
- classify_signal_bidirectional(current_change, distribution, polarity)  # v4 5단계 메인

통합 entry point: calc_signal_v3(monthly, crym, mode, polarity, window).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .signal_constants import (
    DISABLED_MODE_WINDOW,
    MOMENTUM_WINDOW,
    PERCENTILE_WINDOW_MONTHS,
    SIGNAL_INSUFFICIENT,
    SIGNAL_NO_CHANGE,
    SIGNAL_STRONG_CHANGE,
    SIGNAL_STRONG_NEGATIVE,
    SIGNAL_STRONG_POSITIVE,
    SIGNAL_STRONG_THRESHOLD,
    SIGNAL_V4_TO_V3,
    SIGNAL_WEAK_CHANGE,
    SIGNAL_WEAK_NEGATIVE,
    SIGNAL_WEAK_POSITIVE,
    SIGNAL_WEAK_THRESHOLD,
    SYSTEM_3SIGMA,
    SYSTEM_CUTOFF,
    SYSTEM_PERCENTILE,
    SYSTEM_RANKED5,
    SYSTEM_ZSCORE,
)


# ── 월 유틸 ─────────────────────────────────────────
def _prev_month(crym: str) -> str:
    year, month = int(crym[:4]), int(crym[4:])
    if month == 1:
        return f"{year - 1}12"
    return f"{year}{month - 1:02d}"


def _get_past_months(crym: str, n: int) -> list[str]:
    out: list[str] = []
    cur = crym
    for _ in range(n):
        out.append(cur)
        cur = _prev_month(cur)
    return out


def _yoy_month(crym: str) -> str:
    year = int(crym[:4])
    month = crym[4:]
    return f"{year - 1}{month}"


# ── 변화율 ─────────────────────────────────────────
def calc_mom_change(monthly: dict, crym: str) -> Optional[float]:
    prev = _prev_month(crym)
    cur, prv = monthly.get(crym), monthly.get(prev)
    if cur is None or prv is None or prv == 0:
        return None
    return round((cur - prv) / abs(prv) * 100, 2)


def calc_yoy_change(monthly: dict, crym: str) -> Optional[float]:
    yoy = _yoy_month(crym)
    cur, ref = monthly.get(crym), monthly.get(yoy)
    if cur is None or ref is None or ref == 0:
        return None
    return round((cur - ref) / abs(ref) * 100, 2)


def calc_momentum_change(monthly: dict, crym: str, window: int = 3) -> Optional[float]:
    """모멘텀 변화율: 최근 N개월 평균 vs 이전 N개월 평균."""
    recent = _get_past_months(crym, window)
    older_start = _prev_month(recent[-1])
    older = _get_past_months(older_start, window)

    rv = [monthly[m] for m in recent if m in monthly and monthly[m] is not None]
    ov = [monthly[m] for m in older if m in monthly and monthly[m] is not None]

    min_required = max(2, window // 2)
    if len(rv) < min_required or len(ov) < min_required:
        return None

    B = sum(rv) / len(rv)
    A = sum(ov) / len(ov)
    if A == 0:
        return None
    return round((B - A) / abs(A) * 100, 2)


def get_change_value(monthly: dict, crym: str, mode: str) -> Optional[float]:
    if mode == "mom":
        return calc_mom_change(monthly, crym)
    if mode == "yoy":
        return calc_yoy_change(monthly, crym)
    if mode.startswith("momentum"):
        w = MOMENTUM_WINDOW.get(mode, 3)
        return calc_momentum_change(monthly, crym, window=w)
    if mode == "momentum":  # legacy alias
        return calc_momentum_change(monthly, crym, window=3)
    return None


def get_momentum_ab(
    monthly: dict, crym: str, window: int = 3
) -> tuple[Optional[float], Optional[float]]:
    """A(이전 기간 평균), B(최근 기간 평균)."""
    recent = _get_past_months(crym, window)
    older_start = _prev_month(recent[-1])
    older = _get_past_months(older_start, window)

    rv = [monthly[m] for m in recent if m in monthly and monthly[m] is not None]
    ov = [monthly[m] for m in older if m in monthly and monthly[m] is not None]

    min_required = max(2, window // 2)
    if len(rv) < min_required or len(ov) < min_required:
        return None, None
    return round(sum(ov) / len(ov), 2), round(sum(rv) / len(rv), 2)


def calc_current_deviation(
    monthly: dict, crym: str, window: int = 3
) -> Optional[float]:
    """현재값 vs 최근 평균(B) 추세 대비 차이 (%)."""
    cur = monthly.get(crym)
    _, B = get_momentum_ab(monthly, crym, window)
    if cur is None or B is None or B == 0:
        return None
    return round((cur - B) / abs(B) * 100, 2)


# ── 분포 ───────────────────────────────────────────
def build_change_distribution(
    monthly: dict,
    crym: str,
    mode: str,
    window: int = PERCENTILE_WINDOW_MONTHS,
) -> list[float]:
    """과거 N개월 변화율 분포 (당월 제외).

    window=0 이면 보유 전체. 그 외엔 prev_month부터 N개월.
    """
    if window == 0:
        # 보유 전체 — monthly에서 crym 미만 모든 월의 변화율
        all_yms = sorted([m for m in monthly if m < crym])
        past_months = all_yms
    else:
        past_months = _get_past_months(_prev_month(crym), window)
    out: list[float] = []
    for m in past_months:
        v = get_change_value(monthly, m, mode)
        if v is not None:
            out.append(v)
    return out


def is_window_disabled(mode: str, window: int) -> bool:
    """장기 모드 + 12 윈도우 = 비활성화 (decisions.md §4)."""
    return (mode, window) in DISABLED_MODE_WINDOW


# ── 분류기 (v3·v4 5단계 양방향) ─────────────────────
def classify_signal_rank(current_change: float, distribution: list[float]) -> str:
    """v3 3단계 — 절대값 기준 상대 순위. legacy 하위호환."""
    if len(distribution) < 3:
        return SIGNAL_INSUFFICIENT
    abs_dist = np.array([abs(v) for v in distribution])
    p_strong = float(np.percentile(abs_dist, SIGNAL_STRONG_THRESHOLD * 100))
    p_weak = float(np.percentile(abs_dist, SIGNAL_WEAK_THRESHOLD * 100))
    abs_cur = abs(current_change)
    if abs_cur >= p_strong:
        return SIGNAL_STRONG_CHANGE
    if abs_cur >= p_weak:
        return SIGNAL_WEAK_CHANGE
    return SIGNAL_NO_CHANGE


def classify_signal_bidirectional(
    current_change: float,
    distribution: list[float],
    polarity: str = "positive",
) -> str:
    """v4 5단계 양방향 — 메인 신호 분류 (decisions.md §4 신호체계 1번 = 상대순위 5단계).

    polarity:
      positive  → 증가가 긍정 (예: 매출액)
      negative  → 감소가 긍정 (예: 폐업기업수)
    """
    if len(distribution) < 3:
        return SIGNAL_INSUFFICIENT
    if current_change == 0:
        return SIGNAL_NO_CHANGE

    if polarity == "negative":
        is_positive_dir = current_change < 0
    else:
        is_positive_dir = current_change > 0

    if is_positive_dir:
        same_dir = [v for v in distribution if v < 0] if polarity == "negative" else [v for v in distribution if v > 0]
    else:
        same_dir = [v for v in distribution if v > 0] if polarity == "negative" else [v for v in distribution if v < 0]

    abs_cur = abs(current_change)
    if len(same_dir) < 3:
        # 같은 방향 분포 부족 → 전체 절대값 분포로 폴백
        abs_dist = np.array([abs(v) for v in distribution])
        p_strong = float(np.percentile(abs_dist, SIGNAL_STRONG_THRESHOLD * 100))
        p_weak = float(np.percentile(abs_dist, SIGNAL_WEAK_THRESHOLD * 100))
    else:
        abs_same = np.array([abs(v) for v in same_dir])
        p_strong = float(np.percentile(abs_same, SIGNAL_STRONG_THRESHOLD * 100))
        p_weak = float(np.percentile(abs_same, SIGNAL_WEAK_THRESHOLD * 100))

    if abs_cur >= p_strong:
        return SIGNAL_STRONG_POSITIVE if is_positive_dir else SIGNAL_STRONG_NEGATIVE
    if abs_cur >= p_weak:
        return SIGNAL_WEAK_POSITIVE if is_positive_dir else SIGNAL_WEAK_NEGATIVE
    return SIGNAL_NO_CHANGE


def _determine_direction(change: Optional[float], polarity: str) -> Optional[str]:
    if change is None or change == 0:
        return "중립"
    if polarity == "negative":
        return "긍정" if change < 0 else "부정"
    return "긍정" if change > 0 else "부정"


# ── 비교 신호체계 4종 (decisions.md §4) ────────────
def _polarity_apply(value: float, polarity: str) -> float:
    """negative polarity면 부호 뒤집어 '+값=긍정' 통일."""
    return -value if polarity == "negative" else value


def classify_3sigma(
    current_change: float, distribution: list[float], polarity: str = "positive"
) -> str:
    """평균 ±3σ 관리한계 — |z|≥3 strong, |z|≥2 weak, else no_change."""
    if len(distribution) < 3:
        return SIGNAL_INSUFFICIENT
    arr = np.array(distribution, dtype=float)
    mean, std = float(arr.mean()), float(arr.std(ddof=1))
    if std == 0:
        return SIGNAL_NO_CHANGE
    z = (current_change - mean) / std
    z = _polarity_apply(z, polarity)
    abs_z = abs(z)
    if abs_z >= 3.0:
        return SIGNAL_STRONG_POSITIVE if z > 0 else SIGNAL_STRONG_NEGATIVE
    if abs_z >= 2.0:
        return SIGNAL_WEAK_POSITIVE if z > 0 else SIGNAL_WEAK_NEGATIVE
    return SIGNAL_NO_CHANGE


def classify_zscore(
    current_change: float, distribution: list[float], polarity: str = "positive"
) -> str:
    """z-score — |z|≥1.0 strong, |z|≥0.5 weak, else no_change."""
    if len(distribution) < 3:
        return SIGNAL_INSUFFICIENT
    arr = np.array(distribution, dtype=float)
    mean, std = float(arr.mean()), float(arr.std(ddof=1))
    if std == 0:
        return SIGNAL_NO_CHANGE
    z = (current_change - mean) / std
    z = _polarity_apply(z, polarity)
    abs_z = abs(z)
    if abs_z >= 1.0:
        return SIGNAL_STRONG_POSITIVE if z > 0 else SIGNAL_STRONG_NEGATIVE
    if abs_z >= 0.5:
        return SIGNAL_WEAK_POSITIVE if z > 0 else SIGNAL_WEAK_NEGATIVE
    return SIGNAL_NO_CHANGE


def classify_percentile(
    current_change: float, distribution: list[float], polarity: str = "positive"
) -> str:
    """분위수 P10/P30/P70/P90 — 양 끝 분위가 strong, 중간 분위가 weak."""
    if len(distribution) < 3:
        return SIGNAL_INSUFFICIENT
    arr = np.array(distribution, dtype=float)
    p10, p30, p70, p90 = (float(np.percentile(arr, p)) for p in (10, 30, 70, 90))
    c = current_change
    if c >= p90:
        is_high, strong = True, True
    elif c >= p70:
        is_high, strong = True, False
    elif c > p30:
        return SIGNAL_NO_CHANGE
    elif c >= p10:
        is_high, strong = False, False
    else:
        is_high, strong = False, True

    is_positive_dir = (not is_high) if polarity == "negative" else is_high
    if strong:
        return SIGNAL_STRONG_POSITIVE if is_positive_dir else SIGNAL_STRONG_NEGATIVE
    return SIGNAL_WEAK_POSITIVE if is_positive_dir else SIGNAL_WEAK_NEGATIVE


def classify_cutoff(
    current_change: float,
    distribution: list[float],  # noqa: ARG001 (분포 무관, 인터페이스 통일)
    polarity: str = "positive",
    cutoff_strong: float = 10.0,
    cutoff_weak: float = 5.0,
) -> str:
    """직접 컷오프 — 절대 변화율 기준 (사용자 지정). 분포 무관."""
    abs_chg = abs(current_change)
    if abs_chg < cutoff_weak:
        return SIGNAL_NO_CHANGE
    strong = abs_chg >= cutoff_strong
    if polarity == "negative":
        is_positive_dir = current_change < 0
    else:
        is_positive_dir = current_change > 0
    if strong:
        return SIGNAL_STRONG_POSITIVE if is_positive_dir else SIGNAL_STRONG_NEGATIVE
    return SIGNAL_WEAK_POSITIVE if is_positive_dir else SIGNAL_WEAK_NEGATIVE


_CLASSIFIER_BY_SYSTEM = {
    SYSTEM_RANKED5:    classify_signal_bidirectional,
    SYSTEM_3SIGMA:     classify_3sigma,
    SYSTEM_ZSCORE:     classify_zscore,
    SYSTEM_PERCENTILE: classify_percentile,
    # SYSTEM_CUTOFF는 cutoff_strong/cutoff_weak 인자 추가라 별도 처리
}


# ── 통합 entry point (5종 신호체계) ────────────────
def calc_signal(
    monthly: dict,
    crym: str,
    mode: str = "mom",
    polarity: str = "positive",
    window: int = PERCENTILE_WINDOW_MONTHS,
    system: str = SYSTEM_RANKED5,
    cutoff_strong: float = 10.0,
    cutoff_weak: float = 5.0,
) -> dict:
    """5종 신호체계 통합 entry (decisions.md §4).

    system: ranked5 | 3sigma | zscore | percentile | cutoff
    """
    out: dict = {
        "signal": SIGNAL_INSUFFICIENT,
        "signal_v4": SIGNAL_INSUFFICIENT,
        "direction": None,
        "change_pct": None,
        "mode": mode,
        "polarity": polarity,
        "window": window,
        "system": system,
        "percentile": None,
        "p_strong": None, "p_weak": None,
        "A": None, "B": None,
        "current_value": monthly.get(crym),
        "deviation": None,
        "n_distribution": 0,
    }

    if is_window_disabled(mode, window):
        return out

    change = get_change_value(monthly, crym, mode)
    if change is None:
        return out
    out["change_pct"] = change

    if mode.startswith("momentum"):
        w = MOMENTUM_WINDOW.get(mode, 3)
        A, B = get_momentum_ab(monthly, crym, window=w)
        out["A"], out["B"] = A, B
        out["deviation"] = calc_current_deviation(monthly, crym, window=w)

    distribution = build_change_distribution(monthly, crym, mode, window=window)
    out["n_distribution"] = len(distribution)

    # 분류
    if system == SYSTEM_CUTOFF:
        out["signal_v4"] = classify_cutoff(
            change, distribution, polarity, cutoff_strong, cutoff_weak
        )
    elif system in _CLASSIFIER_BY_SYSTEM:
        # ranked5 분포 부족 폴백 (legacy 호환): |change| >= 5% → weak
        if system == SYSTEM_RANKED5 and len(distribution) < 3:
            if abs(change) >= 5.0:
                if polarity == "negative":
                    out["signal_v4"] = SIGNAL_WEAK_POSITIVE if change < 0 else SIGNAL_WEAK_NEGATIVE
                else:
                    out["signal_v4"] = SIGNAL_WEAK_POSITIVE if change > 0 else SIGNAL_WEAK_NEGATIVE
            else:
                out["signal_v4"] = SIGNAL_NO_CHANGE
        else:
            out["signal_v4"] = _CLASSIFIER_BY_SYSTEM[system](change, distribution, polarity)
    else:
        out["signal_v4"] = SIGNAL_INSUFFICIENT

    out["signal"] = SIGNAL_V4_TO_V3.get(out["signal_v4"], SIGNAL_INSUFFICIENT)
    out["direction"] = _determine_direction(change, polarity)

    # ranked5 추가 정보 (legacy 호환)
    if system == SYSTEM_RANKED5 and len(distribution) >= 3:
        abs_dist = np.array([abs(v) for v in distribution])
        out["p_strong"] = round(float(np.percentile(abs_dist, SIGNAL_STRONG_THRESHOLD * 100)), 2)
        out["p_weak"] = round(float(np.percentile(abs_dist, SIGNAL_WEAK_THRESHOLD * 100)), 2)
        rank_pct = float((abs_dist <= abs(change)).sum() / len(abs_dist) * 100)
        out["percentile"] = round(rank_pct, 1)
    return out


def calc_signal_v3(
    monthly: dict,
    crym: str,
    mode: str = "mom",
    polarity: str = "positive",
    window: int = PERCENTILE_WINDOW_MONTHS,
) -> dict:
    """legacy alias — system='ranked5' (decisions.md §4 default)."""
    return calc_signal(monthly, crym, mode, polarity, window, system=SYSTEM_RANKED5)
