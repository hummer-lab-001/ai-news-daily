"""全ソースからAI記事を並列取得し、正規化・重複排除してJSONに保存するモジュール。"""

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
import feedparser
import yaml
from dateutil import parser as dateutil_parser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yml"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

JST = timezone(timedelta(hours=9))


@dataclass
class Article:
    source_name: str
    source_weight: int
    title: str
    url: str
    published_at: str  # ISO8601文字列
    summary_raw: str
    lang: str


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_url(url: str) -> str:
    """クエリ・フラグメントを除いてURLを正規化する。"""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


def is_within_lookback(published_at: str, lookback_hours: int) -> bool:
    try:
        dt = dateutil_parser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        threshold = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        return dt >= threshold
    except Exception:
        return True  # パース失敗時は対象として残す


def contains_exclude_keywords(text: str, exclude_keywords: list[str]) -> bool:
    return any(kw in text for kw in exclude_keywords)


def passes_filter_keywords(text: str, filter_keywords: list[str] | None) -> bool:
    if not filter_keywords:
        return True
    return any(kw in text for kw in filter_keywords)


def title_similarity(a: str, b: str) -> float:
    """単語集合のJaccard係数で簡易的にタイトルの類似度を計算する。"""
    set_a = set(re.findall(r"\w+", a.lower()))
    set_b = set(re.findall(r"\w+", b.lower()))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def deduplicate(articles: list[Article]) -> list[Article]:
    """URL重複と高類似タイトル(Jaccard≥0.8)を除去する。"""
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    result: list[Article] = []
    for art in articles:
        norm_url = normalize_url(art.url)
        if norm_url in seen_urls:
            continue
        if any(title_similarity(art.title, t) >= 0.8 for t in seen_titles):
            continue
        seen_urls.add(norm_url)
        seen_titles.append(art.title)
        result.append(art)
    return result


# ---------------------------------------------------------------------------
# 各ソースタイプの取得関数
# ---------------------------------------------------------------------------

async def fetch_rss(client: httpx.AsyncClient, source: dict, lookback_hours: int, exclude_keywords: list[str]) -> tuple[list[Article], str | None]:
    """RSSフィードを取得してArticleリストに変換する。"""
    url = source["url"]
    name = source["name"]
    weight = source.get("weight", 1)
    lang = source.get("lang", "en")
    filter_kw = source.get("filter_keywords")

    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries:
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            summary_text = re.sub(r"<[^>]+>", "", summary)[:200]

            published_raw = (
                getattr(entry, "published", None)
                or getattr(entry, "updated", None)
                or datetime.now(timezone.utc).isoformat()
            )
            try:
                published_at = dateutil_parser.parse(str(published_raw)).isoformat()
            except Exception:
                published_at = datetime.now(timezone.utc).isoformat()

            combined_text = title + " " + summary_text
            if not passes_filter_keywords(combined_text, filter_kw):
                continue
            if contains_exclude_keywords(combined_text, exclude_keywords):
                continue
            if not is_within_lookback(published_at, lookback_hours):
                continue

            articles.append(Article(
                source_name=name,
                source_weight=weight,
                title=title,
                url=link,
                published_at=published_at,
                summary_raw=summary_text,
                lang=lang,
            ))
        logger.info(f"[RSS] {name}: {len(articles)} 件取得")
        return articles, None
    except Exception as e:
        err = f"{name}: {e}"
        logger.warning(f"[RSS] 取得失敗 — {err}")
        return [], err


async def fetch_arxiv(source: dict, lookback_hours: int) -> tuple[list[Article], str | None]:
    """arXiv APIから最新論文を取得する。"""
    import arxiv
    name = source["name"]
    weight = source.get("weight", 1)
    categories = source.get("categories", ["cs.AI"])
    max_items = source.get("max_items", 5)

    try:
        query = " OR ".join(f"cat:{c}" for c in categories)
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_items * 3,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        articles = []
        threshold = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        for result in client.results(search):
            if result.published.replace(tzinfo=timezone.utc) < threshold:
                continue
            articles.append(Article(
                source_name=name,
                source_weight=weight,
                title=result.title,
                url=result.entry_id,
                published_at=result.published.isoformat(),
                summary_raw=result.summary[:200],
                lang="en",
            ))
            if len(articles) >= max_items:
                break
        logger.info(f"[arXiv] {name}: {len(articles)} 件取得")
        return articles, None
    except Exception as e:
        err = f"{name}: {e}"
        logger.warning(f"[arXiv] 取得失敗 — {err}")
        return [], err


async def fetch_hf_daily_papers(client: httpx.AsyncClient, source: dict) -> tuple[list[Article], str | None]:
    """Hugging Face Daily Papers APIから取得する。"""
    name = source["name"]
    weight = source.get("weight", 1)
    max_items = source.get("max_items", 3)
    url = source["url"]

    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        papers = resp.json()
        articles = []
        for paper in papers[:max_items]:
            p = paper.get("paper", paper)
            title = p.get("title", "")
            abstract = (p.get("abstract", "") or "")[:200]
            arxiv_id = p.get("id", "")
            link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else url
            published_at = p.get("publishedAt", datetime.now(timezone.utc).isoformat())
            articles.append(Article(
                source_name=name,
                source_weight=weight,
                title=title,
                url=link,
                published_at=published_at,
                summary_raw=abstract,
                lang="en",
            ))
        logger.info(f"[HF] {name}: {len(articles)} 件取得")
        return articles, None
    except Exception as e:
        err = f"{name}: {e}"
        logger.warning(f"[HF] 取得失敗 — {err}")
        return [], err


async def fetch_hn_ai(client: httpx.AsyncClient, source: dict) -> tuple[list[Article], str | None]:
    """Hacker News Algolia APIからAI関連トップ記事を取得する。"""
    name = source["name"]
    weight = source.get("weight", 1)
    min_points = source.get("min_points", 100)
    query = source.get("query", "AI")
    url = source["url"]

    try:
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"points>={min_points}",
            "hitsPerPage": 10,
        }
        resp = await client.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            created_at = hit.get("created_at", datetime.now(timezone.utc).isoformat())
            articles.append(Article(
                source_name=name,
                source_weight=weight,
                title=title,
                url=link,
                published_at=created_at,
                summary_raw="",
                lang="en",
            ))
        logger.info(f"[HN] {name}: {len(articles)} 件取得")
        return articles, None
    except Exception as e:
        err = f"{name}: {e}"
        logger.warning(f"[HN] 取得失敗 — {err}")
        return [], err


async def fetch_product_hunt(client: httpx.AsyncClient, source: dict) -> tuple[list[Article], str | None]:
    """Product Hunt GraphQL APIからAIカテゴリ製品を取得する(APIキー不要の公開エンドポイント)。"""
    name = source["name"]
    weight = source.get("weight", 1)

    # Product Hunt公開APIはキー必須のため、RSSで代替
    rss_url = "https://www.producthunt.com/feed?category=artificial-intelligence"
    try:
        resp = await client.get(rss_url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:10]:
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "") or "")[:200]
            published_raw = getattr(entry, "published", datetime.now(timezone.utc).isoformat())
            try:
                published_at = dateutil_parser.parse(str(published_raw)).isoformat()
            except Exception:
                published_at = datetime.now(timezone.utc).isoformat()
            articles.append(Article(
                source_name=name,
                source_weight=weight,
                title=title,
                url=link,
                published_at=published_at,
                summary_raw=summary,
                lang="en",
            ))
        logger.info(f"[PH] {name}: {len(articles)} 件取得")
        return articles, None
    except Exception as e:
        err = f"{name}: {e}"
        logger.warning(f"[PH] 取得失敗 — {err}")
        return [], err


# ---------------------------------------------------------------------------
# メイン実行
# ---------------------------------------------------------------------------

async def fetch_all() -> tuple[list[Article], list[str]]:
    config = load_config()
    sources = config["sources"]
    lookback_hours = config.get("lookback_hours", 24)
    exclude_keywords = config.get("exclude_keywords", [])

    all_articles: list[Article] = []
    failed_sources: list[str] = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "ai-news-daily/1.0 (github.com/hummer-lab-001/ai-news-daily)"},
    ) as client:
        tasks = []
        source_types = []

        for src in sources:
            stype = src.get("type", "rss")
            if stype == "rss":
                tasks.append(fetch_rss(client, src, lookback_hours, exclude_keywords))
                source_types.append("rss")
            elif stype == "arxiv":
                tasks.append(fetch_arxiv(src, lookback_hours))
                source_types.append("arxiv")
            elif stype == "api":
                sname = src.get("name", "")
                if "Hugging Face" in sname:
                    tasks.append(fetch_hf_daily_papers(client, src))
                    source_types.append("api")
                elif "Hacker News" in sname:
                    tasks.append(fetch_hn_ai(client, src))
                    source_types.append("api")
                elif "Product Hunt" in sname:
                    tasks.append(fetch_product_hunt(client, src))
                    source_types.append("api")
                else:
                    logger.warning(f"未対応のAPIソース: {sname}")
                    continue

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failed_sources.append(str(result))
                continue
            articles, err = result
            all_articles.extend(articles)
            if err:
                failed_sources.append(err)

    all_articles = deduplicate(all_articles)
    logger.info(f"合計 {len(all_articles)} 件（重複排除後）")
    return all_articles, failed_sources


def save_articles(articles: list[Article], failed_sources: list[str]) -> Path:
    today = datetime.now(JST).strftime("%Y%m%d")
    output_path = DATA_DIR / f"raw_{today}.json"
    payload = {
        "date": today,
        "articles": [asdict(a) for a in articles],
        "failed_sources": failed_sources,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"保存完了: {output_path}")
    return output_path


def main():
    articles, failed = asyncio.run(fetch_all())
    save_articles(articles, failed)


if __name__ == "__main__":
    main()
