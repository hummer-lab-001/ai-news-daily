"""記事の重要度スコアを計算する補助モジュール。build.pyから利用される。"""

from typing import Any


CATEGORY_COLORS = {
    "実務": "bg-blue-100 text-blue-800",
    "ツール": "bg-green-100 text-green-800",
    "業界": "bg-purple-100 text-purple-800",
    "研究": "bg-gray-100 text-gray-800",
}

IMPORTANCE_COLORS = {
    5: "border-red-500 bg-red-50",
    4: "border-orange-400 bg-orange-50",
    3: "border-yellow-400 bg-yellow-50",
    2: "border-blue-300 bg-blue-50",
    1: "border-gray-300 bg-gray-50",
}

IMPORTANCE_STAR_COLORS = {
    5: "text-red-500",
    4: "text-orange-400",
    3: "text-yellow-500",
    2: "text-blue-400",
    1: "text-gray-400",
}


def get_category_badge(category: str) -> str:
    css = CATEGORY_COLORS.get(category, "bg-gray-100 text-gray-700")
    return f'<span class="inline-block px-2 py-0.5 rounded text-xs font-medium {css}">{category}</span>'


def get_importance_stars(importance: int) -> str:
    color = IMPORTANCE_STAR_COLORS.get(importance, "text-gray-400")
    filled = "★" * importance
    empty = "☆" * (5 - importance)
    return f'<span class="{color} font-bold">{filled}</span><span class="text-gray-300">{empty}</span>'


def get_card_border(importance: int) -> str:
    return IMPORTANCE_COLORS.get(importance, "border-gray-300 bg-gray-50")


def enrich_must_read(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """must_readエントリにUI用の属性を付与する。"""
    for item in items:
        importance = item.get("importance", 3)
        category = item.get("category", "業界")
        item["category_badge"] = get_category_badge(category)
        item["importance_stars"] = get_importance_stars(importance)
        item["card_border"] = get_card_border(importance)
    return items


def enrich_digest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """digestエントリにUI用の属性を付与する。"""
    for item in items:
        category = item.get("category", "業界")
        item["category_badge"] = get_category_badge(category)
    return items
