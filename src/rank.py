"""記事の重要度スコアを計算する補助モジュール。build.pyから利用される。"""

from typing import Any


IMPORTANCE_COLORS = {
    5: "border-red-500 bg-red-50",
    4: "border-orange-400 bg-orange-50",
    3: "border-yellow-400 bg-yellow-50",
    2: "border-blue-300 bg-blue-50",
    1: "border-gray-300 bg-gray-50",
}


def get_card_border(importance: int) -> str:
    return IMPORTANCE_COLORS.get(importance, "border-gray-300 bg-gray-50")


def enrich_must_read(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """must_readエントリにUI用の属性を付与する。"""
    for item in items:
        item["card_border"] = get_card_border(item.get("importance", 3))
    return items


def enrich_digest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return items
