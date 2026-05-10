"""시그널 산정 상수 — legacy `config_v3.py` 시그널 부분만 이식.

decisions.md §4, legacy_migration.md §3 기반.
streamlit·LLM·DATA_ROOT·SGG_CODES 등은 의도적으로 제외 (Django settings·data_whitelist.md SSOT).
"""

# ── 분포 윈도우 ─────────────────────────────────────
PERCENTILE_WINDOW_MONTHS = 24  # default
WINDOW_OPTIONS = (12, 24, 0)   # 0 = 전체 (보유 전체)

# ── 분석 모드 ───────────────────────────────────────
POINT_MODES = {
    "전월대비(%)":     "mom",
    "전년동월대비(%)": "yoy",
}
TREND_MODES = {
    "단기추세(%)": "momentum_short",
    "장기추세(%)": "momentum_long",
}
COMPARE_MODES = {**POINT_MODES, **TREND_MODES}

MOMENTUM_WINDOW = {
    "momentum_short": 3,
    "momentum_long":  12,
}

# 장기 모드 + 12 윈도우 조합은 비활성화 (decisions.md §4)
DISABLED_MODE_WINDOW = {("momentum_long", 12)}

# ── 상대순위 5단계 (v4 양방향) — legacy 기본값 ─────
SIGNAL_STRONG_THRESHOLD = 0.80   # 상위 20% → 강한
SIGNAL_WEAK_THRESHOLD   = 0.60   # 상위 40% → 약한

# ── 신호 라벨 (5단계 양방향 + 데이터부족) ──────────
SIGNAL_STRONG_POSITIVE = "strong_positive"
SIGNAL_WEAK_POSITIVE   = "weak_positive"
SIGNAL_NO_CHANGE       = "no_change"
SIGNAL_WEAK_NEGATIVE   = "weak_negative"
SIGNAL_STRONG_NEGATIVE = "strong_negative"
SIGNAL_INSUFFICIENT    = "insufficient"

# v3 하위호환 (legacy 호출처용)
SIGNAL_STRONG_CHANGE = "strong_change"
SIGNAL_WEAK_CHANGE   = "weak_change"

# 5단계 → 레이더 매핑 (decisions.md §4)
SIGNAL_RADAR_VALUE = {
    SIGNAL_STRONG_POSITIVE: 2,
    SIGNAL_WEAK_POSITIVE:   1,
    SIGNAL_NO_CHANGE:       0,
    SIGNAL_WEAK_NEGATIVE:   -1,
    SIGNAL_STRONG_NEGATIVE: -2,
    SIGNAL_INSUFFICIENT:    0,  # + 회색 점선 + tooltip 별도 처리
}

# v4 6단계 → v3 3단계 매핑 (하위호환)
SIGNAL_V4_TO_V3 = {
    SIGNAL_STRONG_POSITIVE: SIGNAL_STRONG_CHANGE,
    SIGNAL_WEAK_POSITIVE:   SIGNAL_WEAK_CHANGE,
    SIGNAL_NO_CHANGE:       SIGNAL_NO_CHANGE,
    SIGNAL_WEAK_NEGATIVE:   SIGNAL_WEAK_CHANGE,
    SIGNAL_STRONG_NEGATIVE: SIGNAL_STRONG_CHANGE,
    SIGNAL_INSUFFICIENT:    SIGNAL_INSUFFICIENT,
}

# ── 신호체계 식별자 (decisions.md §4 — 5종) ────────
SYSTEM_RANKED5    = "ranked5"     # 상대순위 5단계 (legacy default)
SYSTEM_3SIGMA     = "3sigma"      # 평균 ±3σ (β 구현)
SYSTEM_ZSCORE     = "zscore"      # z-score ±0.5σ/±1.0σ (β 구현)
SYSTEM_PERCENTILE = "percentile"  # 분위수 P10/P30/P70/P90 (β 구현)
SYSTEM_CUTOFF     = "cutoff"      # 직접 컷오프 % (β 구현)

ALL_SIGNAL_SYSTEMS = (
    SYSTEM_RANKED5,
    SYSTEM_3SIGMA,
    SYSTEM_ZSCORE,
    SYSTEM_PERCENTILE,
    SYSTEM_CUTOFF,
)
