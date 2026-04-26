"""Claude APIを使い、取得済み記事を要約・ランク付けしてJSONに保存するモジュール。"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"

JST = timezone(timedelta(hours=9))

SYSTEM_PROMPT = """\
あなたは日本のAIコンサルタント向けニュースキュレーターです。
以下の記事群から、日本企業のAI活用実務に最も役立つ情報を抽出してください。

重要度の判断基準(優先順):
1. 日本企業がすぐ使える具体的な活用事例・ツール・サービス
2. 主要AIツール(ChatGPT/Claude/Gemini/Copilot等)の新機能・価格・仕様変更
3. 日本のAI市場動向・規制・大手SIer/コンサル動向
4. 大手ラボ(OpenAI/Anthropic/Google/Meta)の製品発表
5. 資金調達・M&A等の業界動向
6. 技術・研究ブレイクスルー(実用性の高いもの)

出力形式(必ずJSONのみ、前後に文章を付けない。HTMLタグは一切含めないこと):
{
  "must_read": [
    {
      "rank": 1,
      "title_ja": "日本語タイトル",
      "summary_ja": "3行要約(100字前後×3)",
      "consultant_insight": "コンサル実務視点の一言(80字以内)",
      "importance": 5,
      "category": "実務|ツール|業界|研究",
      "source_name": "元ソース名",
      "url": "元URL"
    }
  ],
  "digest": [
    {
      "title_ja": "タイトル",
      "one_liner": "1行要約(50字以内)",
      "category": "実務|ツール|業界|研究",
      "url": "元URL"
    }
  ]
}

- must_read は source_weight が高いものを優先しつつ、ニュース価値も加味して上位10件を選ぶ
- digest はその他注目15件まで
- 英語記事は日本語に翻訳
- consultant_insight は「この情報を顧客にどう活かせるか」を一言で
- 重複する話題はまとめて1エントリにする
"""


def load_raw_articles(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y%m%d")
    path = DATA_DIR / f"raw_{date_str}.json"
    if not path.exists():
        raise FileNotFoundError(f"生データが見つかりません: {path}\n先に src/fetch.py を実行してください。")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_user_message(articles: list[dict]) -> str:
    lines = [f"記事数: {len(articles)}\n"]
    for i, art in enumerate(articles, 1):
        lines.append(
            f"[{i}] source_weight={art['source_weight']} lang={art['lang']}\n"
            f"  ソース: {art['source_name']}\n"
            f"  タイトル: {art['title']}\n"
            f"  URL: {art['url']}\n"
            f"  冒頭: {art['summary_raw'][:150]}\n"
        )
    return "\n".join(lines)


def call_claude(user_message: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY が設定されていません。\n"
            ".env.example を参考に .env ファイルを作成するか、環境変数を設定してください。"
        )

    client = anthropic.Anthropic(api_key=api_key)
    logger.info("Claude API にリクエスト送信中...")

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = message.content[0].text.strip()
    logger.info(f"Claude API 応答受信 (入力: {message.usage.input_tokens} tokens, 出力: {message.usage.output_tokens} tokens)")

    # JSONブロックが ```json ... ``` で囲まれている場合に対応
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    return json.loads(raw_text)


def save_summary(summary: dict, failed_sources: list[str]) -> Path:
    today = datetime.now(JST).strftime("%Y%m%d")
    summary["date"] = today
    summary["failed_sources"] = failed_sources
    output_path = DATA_DIR / f"summary_{today}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"要約を保存しました: {output_path}")
    return output_path


def main():
    data = load_raw_articles()
    articles = data["articles"]
    failed_sources = data.get("failed_sources", [])

    if not articles:
        logger.warning("記事が0件です。fetch.py が正常に実行されているか確認してください。")
        # 空の要約を保存して後続ステップが失敗しないようにする
        save_summary({"must_read": [], "digest": []}, failed_sources)
        return

    user_message = build_user_message(articles)
    summary = call_claude(user_message)
    save_summary(summary, failed_sources)
    logger.info(f"must_read: {len(summary.get('must_read', []))} 件, digest: {len(summary.get('digest', []))} 件")


if __name__ == "__main__":
    main()
