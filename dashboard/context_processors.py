"""템플릿 컨텍스트 — 사이드바 카테고리 목록 등 공통 변수."""
from .services.categories import CATEGORIES, list_categories

_ICONS = {
    "유동·생활인구": "🚶",
    "생활이동":      "🔁",
    "카드 가맹":     "🏪",
    "카드 소비자":   "🛒",
    "기업신용":      "🏢",
    "개인신용":      "👤",
}


def sidebar(request):
    return {
        "sidebar_categories": [
            {"name": n, "slug": CATEGORIES[n]["slug"], "icon": _ICONS.get(n, "•")}
            for n in list_categories()
        ],
    }
