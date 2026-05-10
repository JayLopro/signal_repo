"""카테고리 트리 — legacy `categories.py` 트리밍 (streamlit·UI 렌더링 모두 제거).

1차 PoC 6 카테고리. 각 카테고리는 헤드라인 KPI + 1차 차원분해 + 노출 지표 화이트리스트.
SSOT: docs/data_whitelist.md, decisions.md §3.
UI 렌더링은 Phase 3 (Django 템플릿)에서.
"""
from .metrics_meta import metrics_by_category

# decisions.md §3 표 그대로
# breakdown.type:
#   - "metric"   : dim_value → metric 이름 매핑 (fact의 1차 차원이 metric별로 분리됨)
#   - "dim_kind" : fact_monthly_kpi.dim_kind / dim_value로 조회 (시군 합계만, 행정동 분해 X)
CATEGORIES: dict[str, dict] = {
    "기업신용": {
        "slug": "gieop",
        "headline": "신설기업수 − 폐업기업수 (순증)",
        "headline_metric": "신설기업수",
        "dimension": {"kind": "SCALE_DIV", "values": ["대기업", "중견기업", "중기업", "기타"]},
        "metrics": metrics_by_category("기업신용"),
        "breakdown": {
            "type": "metric",
            "label": "신설·폐업·전체",
            "mapping": [
                ("신설기업수",  "신설기업수"),
                ("폐업기업수",  "폐업기업수"),
                ("전체기업수",  "전체기업수"),
            ],
        },
    },
    "개인신용": {
        "slug": "sinyong",
        "headline": "월소득평균",
        "headline_metric": "월소득평균",
        "dimension": {"kind": "FINAN_GB", "values": ["월소득", "대출잔액"]},
        "metrics": metrics_by_category("개인신용"),
        "breakdown": {
            "type": "metric",
            "label": "월소득 / 대출잔액",
            "mapping": [
                ("월소득",   "월소득평균"),
                ("대출잔액", "평균대출잔액"),
            ],
        },
    },
    "유동·생활인구": {
        "slug": "flow",
        "headline": "일평균유동인구",
        "headline_metric": "일평균유동인구",
        "dimension": {
            "kind": "POP_GB",
            "values": ["유동인구", "거주인구", "직장인구", "방문인구"],
            "raw_uncalibrated": ["거주인구", "직장인구", "방문인구"],  # UI에서 "1차 미보정" 배지
        },
        "metrics": metrics_by_category("유동·생활인구"),
        "breakdown": {
            "type": "metric",
            "label": "POP_GB (유동/거주/직장/방문)",
            "mapping": [
                ("유동인구", "일평균유동인구"),
                ("거주인구", "거주인구"),
                ("직장인구", "직장인구"),
                ("방문인구", "방문인구"),
            ],
        },
    },
    "생활이동": {
        "slug": "move",
        "headline": "순유입(유입−유출)",
        "headline_metric": "일평균유입인구",
        "dimension": {"kind": "IN_OUT_GB", "values": ["유입", "유출"]},
        "metrics": metrics_by_category("생활이동"),
        "secondary_dimensions": [
            {"kind": "PURPOSE", "values": ["관광", "귀가", "기타", "등교", "병원", "쇼핑", "출근"]},
            {"kind": "TRANS",   "values": ["고속버스", "기차", "기타", "노선버스", "도보", "지하철", "차량", "항공"]},
        ],
        "breakdown": {
            "type": "metric",
            "label": "IN_OUT_GB (유입/유출)",
            "mapping": [
                ("유입", "일평균유입인구"),
                ("유출", "일평균유출인구"),
            ],
        },
    },
    "카드 가맹": {
        "slug": "card-m",
        "headline": "가맹점매출액",
        "headline_metric": "가맹점매출액",
        "dimension": {
            "kind": "CARD_TPBUZ_NM_1",
            "values": [
                "음식", "소매/유통", "생활서비스", "학문/교육",
                "의료/건강", "여가/오락", "미디어/통신", "공연/전시", "공공/기업/단체",
            ],
        },
        "metrics": metrics_by_category("카드 가맹"),
        "breakdown": {
            "type": "dim_kind",
            "label": "CARD_TPBUZ (업종 9)",
            "kind": "CARD_TPBUZ",
            "metric": "가맹점매출액",
            "values": [
                "음식", "소매/유통", "생활서비스", "학문/교육",
                "의료/건강", "여가/오락", "미디어/통신", "공연/전시", "공공/기업/단체",
            ],
        },
    },
    "카드 소비자": {
        "slug": "card-c",
        "headline": "일평균이용금액",
        "headline_metric": "일평균이용금액",
        "dimension": {"kind": "INFLOW_GB", "values": ["수원시", "경기도", "경기도외"]},
        "metrics": metrics_by_category("카드 소비자"),
        "breakdown": {
            "type": "metric",
            "label": "INFLOW_GB (수원시/경기도/경기도외)",
            "mapping": [
                ("수원시",   "관내이용금액"),
                ("경기도",   "도내이용금액"),
                ("경기도외", "도외이용금액"),
            ],
        },
    },
}

_SLUG_TO_CATEGORY = {meta["slug"]: name for name, meta in CATEGORIES.items()}

CATEGORY_ORDER = (
    "유동·생활인구",
    "생활이동",
    "카드 가맹",
    "카드 소비자",
    "기업신용",
    "개인신용",
)


def get_category(name: str) -> dict:
    return CATEGORIES[name]


def list_categories() -> list[str]:
    return list(CATEGORY_ORDER)


def get_headline_metric(category: str) -> str:
    return CATEGORIES[category]["headline_metric"]


def get_slug(category: str) -> str:
    return CATEGORIES[category]["slug"]


def get_category_by_slug(slug: str) -> str | None:
    return _SLUG_TO_CATEGORY.get(slug)


def get_breakdown(category: str) -> dict:
    return CATEGORIES[category]["breakdown"]
