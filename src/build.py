"""要約JSONからHTML(index.html + アーカイブ)を生成するモジュール。"""

import json
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.rank import enrich_digest, enrich_must_read

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
DOCS_DIR = ROOT / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"
DOCS_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)

JST = timezone(timedelta(hours=9))
ARCHIVE_KEEP_DAYS = 30


def load_summary(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y%m%d")
    path = DATA_DIR / f"summary_{date_str}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"要約データが見つかりません: {path}\n先に src/summarize.py を実行してください。"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_archive_links() -> list[dict]:
    """過去30日のアーカイブリンクリストを生成する。"""
    links = []
    today = datetime.now(JST)
    for i in range(1, ARCHIVE_KEEP_DAYS + 1):
        dt = today - timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        file_name = f"{date_str}.html"
        archive_path = ARCHIVE_DIR / file_name
        if archive_path.exists():
            links.append({"date": date_str, "url": f"archive/{file_name}"})
    return links


def cleanup_old_archives():
    """30日より古いアーカイブを削除する。"""
    threshold = datetime.now(JST) - timedelta(days=ARCHIVE_KEEP_DAYS)
    for f in ARCHIVE_DIR.glob("*.html"):
        try:
            file_date = datetime.strptime(f.stem, "%Y-%m-%d").replace(tzinfo=JST)
            if file_date < threshold:
                f.unlink()
                logger.info(f"古いアーカイブを削除: {f.name}")
        except ValueError:
            pass


def render_html(summary: dict, now_jst: datetime) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("index.html.j2")

    must_read = enrich_must_read(summary.get("must_read", []))
    digest = enrich_digest(summary.get("digest", []))
    failed_sources = summary.get("failed_sources", [])
    archive_links = build_archive_links()

    return template.render(
        date_display=now_jst.strftime("%Y年%m月%d日"),
        updated_at=now_jst.strftime("%H:%M JST"),
        must_read=must_read,
        digest=digest,
        failed_sources=failed_sources,
        archive_links=archive_links,
    )


def main():
    now_jst = datetime.now(JST)
    today_str = now_jst.strftime("%Y%m%d")
    today_dash = now_jst.strftime("%Y-%m-%d")

    summary = load_summary(today_str)
    html = render_html(summary, now_jst)

    # メインページを出力
    index_path = DOCS_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    logger.info(f"生成完了: {index_path}")

    # アーカイブにコピー
    archive_path = ARCHIVE_DIR / f"{today_dash}.html"
    shutil.copy2(index_path, archive_path)
    logger.info(f"アーカイブ保存: {archive_path}")

    # 古いアーカイブを削除
    cleanup_old_archives()

    # manifest.json をdocsにコピー
    manifest_src = TEMPLATES_DIR / "manifest.json"
    manifest_dst = DOCS_DIR / "manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, manifest_dst)

    logger.info("ビルド完了")


if __name__ == "__main__":
    main()
