"""지표 메타 — legacy `metrics_meta_v3.py` 트리밍 (data_units.md SSOT).

1차 PoC 노출 17개 metric만 등록 (data_whitelist.md §1).
polarity / unit / category는 데이터마트 dim_metric과 일치.
정의 문구는 legacy METRIC_DEF에서 발췌.
"""

# (metric, category, unit, polarity, definition)
METRIC_META: dict[str, dict] = {
    # 기업신용
    "전체기업수": {
        "category": "기업신용", "unit": "개", "polarity": "positive",
        "definition": "관내에 등록된 전체 기업 수 (TIMESERIES_GIEOP.TOTAL_COMP_CNT 합).",
    },
    "신설기업수": {
        "category": "기업신용", "unit": "개", "polarity": "positive",
        "definition": "기준월 신설된 기업 수.",
    },
    "폐업기업수": {
        "category": "기업신용", "unit": "개", "polarity": "negative",
        "definition": "기준월 휴폐업 기업 수. 증가 = 부정.",
    },
    # 개인신용
    "월소득평균": {
        "category": "개인신용", "unit": "백만원", "polarity": "positive",
        "definition": "TIMESERIES_SINYONG VALUE의 평균 ÷ 1000 (천원 → 백만원).",
    },
    "평균대출잔액": {
        "category": "개인신용", "unit": "백만원", "polarity": "negative",
        "definition": "TIMESERIES_SINYONG VALUE 평균 ÷ 1000. 증가 = 부정.",
    },
    # 유동·생활인구
    "일평균유동인구": {
        "category": "유동·생활인구", "unit": "명", "polarity": "positive",
        "definition": "TIMESERIES_FLOW_LIVE_POP POP_GB=유동인구 월합 ÷ 일수.",
    },
    "거주인구": {
        "category": "유동·생활인구", "unit": "명·24h누적", "polarity": "neutral",
        "definition": "POP_GB=거주인구 시간대(24h) 누적 월합. 1차 미보정 raw — UI 배지로 명시.",
    },
    "직장인구": {
        "category": "유동·생활인구", "unit": "명·24h누적", "polarity": "neutral",
        "definition": "POP_GB=직장인구 시간대(24h) 누적 월합. 1차 미보정 raw.",
    },
    "방문인구": {
        "category": "유동·생활인구", "unit": "명·24h누적", "polarity": "positive",
        "definition": "POP_GB=방문인구 시간대(24h) 누적 월합. 1차 미보정 raw.",
    },
    # 생활이동
    "일평균유입인구": {
        "category": "생활이동", "unit": "명", "polarity": "positive",
        "definition": "TIMESERIES_PURPOSE_POP IN_OUT_GB=유입 IN_OUT_CNT 합 ÷ 일수.",
    },
    "일평균유출인구": {
        "category": "생활이동", "unit": "명", "polarity": "negative",
        "definition": "TIMESERIES_PURPOSE_POP IN_OUT_GB=유출 IN_OUT_CNT 합 ÷ 일수.",
    },
    # 카드 가맹
    "가맹점매출액": {
        "category": "카드 가맹", "unit": "억원", "polarity": "positive",
        "definition": "TIMESERIES_CARD_M VALUE_GB=매출액 합 ÷ 10⁸.",
    },
    "가맹점매출건수": {
        "category": "카드 가맹", "unit": "건", "polarity": "positive",
        "definition": "TIMESERIES_CARD_M VALUE_GB=매출건수 합.",
    },
    # 카드 소비자
    "일평균이용금액": {
        "category": "카드 소비자", "unit": "억원", "polarity": "positive",
        "definition": "TIMESERIES_CARD_C AMT 합 ÷ 일수 ÷ 10⁸.",
    },
    "관내이용금액": {
        "category": "카드 소비자", "unit": "억원", "polarity": "positive",
        "definition": "INFLOW_GB=수원시 AMT 합 ÷ 10⁸.",
    },
    "도내이용금액": {
        "category": "카드 소비자", "unit": "억원", "polarity": "positive",
        "definition": "INFLOW_GB=경기도 AMT 합 ÷ 10⁸.",
    },
    "도외이용금액": {
        "category": "카드 소비자", "unit": "억원", "polarity": "positive",
        "definition": "INFLOW_GB=경기도외 AMT 합 ÷ 10⁸.",
    },
}


def get_meta(metric: str) -> dict:
    return METRIC_META.get(metric, {"category": "unknown", "unit": "", "polarity": "neutral", "definition": metric})


def get_polarity(metric: str) -> str:
    return get_meta(metric)["polarity"]


def get_unit(metric: str) -> str:
    return get_meta(metric)["unit"]


def get_definition(metric: str) -> str:
    return get_meta(metric)["definition"]


def metrics_by_category(category: str) -> list[str]:
    return [m for m, meta in METRIC_META.items() if meta["category"] == category]
