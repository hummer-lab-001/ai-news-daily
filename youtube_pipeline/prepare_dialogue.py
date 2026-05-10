"""
prepare_dialogue.py
news.txt を読み込み、記号や英単語を整えた上で Claude API で「2人の掛け合い形式」に変換する。
出力: output/dialogue.json
"""

import os
import re
import json
import sys


def clean_text(text: str) -> str:
    """markdown記号・URL・HTMLタグなど読み上げに不適切な文字を除去"""
    # markdown
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"_{2,}", "", text)
    text = re.sub(r"~~", "", text)
    text = re.sub(r">\s*", "", text)
    text = re.sub(r"-{3,}", "", text)
    # markdownリンク [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # HTMLタグ
    text = re.sub(r"<[^>]+>", "", text)
    # URL
    text = re.sub(r"https?://\S+", "", text)
    # 連続する空白・改行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def convert_to_dialogue(text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[エラー] ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("[エラー] anthropic がインストールされていません: pip install anthropic")
        sys.exit(1)

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""あなたはAIニュース番組の構成作家です。
以下のニュース原稿を、テンポの良い「2人キャスターの掛け合い形式」に書き直してください。

【話者設定】
- キャスターA = Aoi：メインキャスター・29歳・落ち着いた知的な大人女性・ニュースの主軸を正確に伝える・専門用語にも詳しい
- キャスターB = Hina：サブキャスター・24歳の新卒ビジネス女子・明るく素直・視聴者の代弁者として「それって何ですか？」と素直に質問する役

【番組コンセプト】
通勤中の20〜30代IT男性が、毎朝3分でAIニュースを聴きながら**1日1つAI用語を覚えられる**学習型ニュース番組。

【厳守ルール】
1. 全体を「トピック」に分ける（1ニュース = 1トピック）
2. 各トピックに 15文字以内の短いタイトルを付ける
3. アップテンポで歯切れよく、1セリフは80文字以内
4. 英単語・略語は読み方をカタカナで併記
   例: OpenAI → オープンAI / ChatGPT → チャットGPT / GPT-5 → ジーピーティーファイブ
5. 記号（: * # 〜 など）は一切使わず、自然な口語のみ
6. 数字は読み上げやすく（例: 2026年 → 二〇二六年）
7. 冒頭に明るいオープニング、最後にチャンネル登録呼びかけのクロージングを入れる
8. オープニングとクロージングは合わせて 4〜6セリフ程度

【★最重要：AI用語学習コーナー】
全トピックの中から、**最も重要なAI関連用語を1つだけ**ピックアップしてください。
そのトピック内で、以下のような「自然な掛け合い」を必ず入れてください：

  Aoi: 「（ニュース文脈で用語を使う）例えば、〇〇とAPIで連携できるようになって…」
  Hina: 「ちょっと待ってください、APIって何ですか？私もよく聞くんですけど…」
  Aoi: 「いい質問ですね。APIっていうのは、〇〇のことなんです。例えば…」
  Hina: 「なるほど！〇〇ってことですね。よく分かりました！」
  Aoi: 「そうなんです。これを覚えておくと、今後のニュースもグッと理解しやすくなりますよ」

ポイント：
- Hina の質問は自然な驚き・素直さを表現（「えーっと」「なんとなくわかるんですけど」など）
- Aoi の解説は20〜30代男性向けに、専門的すぎず、でも本質を突く
- 解説後は「これは覚えておくと得です」のような視聴者へのメッセージで締める
- 用語選定基準：その日のニュースで複数回出てくる or 今後も使う重要語

【出力形式】
以下のJSONのみを出力。説明文・前置き・コードブロックは一切不要。

{{
  "opening": [
    {{"speaker": "A", "text": "..."}},
    {{"speaker": "B", "text": "..."}}
  ],
  "topics": [
    {{
      "title": "短いタイトル",
      "lines": [
        {{"speaker": "A", "text": "..."}},
        {{"speaker": "B", "text": "..."}}
      ]
    }}
  ],
  "closing": [
    {{"speaker": "A", "text": "..."}},
    {{"speaker": "B", "text": "..."}}
  ]
}}

【元のニュース原稿】
{text}
"""

    print(f"[Claude] {model} でダイアログ変換中...")
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # コードブロックを削除
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # 最初の { から最後の } までを取り出し
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        print(f"[エラー] Claude応答からJSONが取れません:\n{raw[:500]}")
        sys.exit(1)
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"[エラー] JSONパース失敗: {e}\n応答先頭: {raw[:500]}")
        sys.exit(1)


def main() -> None:
    text_path = os.environ.get("NEWS_TEXT_PATH", "output/news.txt")
    out_path  = os.environ.get("DIALOGUE_JSON_PATH", "output/dialogue.json")

    if not os.path.exists(text_path):
        print(f"[エラー] {text_path} が見つかりません")
        sys.exit(1)

    with open(text_path, encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_text(raw)
    print(f"[クリーニング] {len(raw)}文字 → {len(cleaned)}文字")

    dialogue = convert_to_dialogue(cleaned)

    n_topics = len(dialogue.get("topics", []))
    n_lines  = len(dialogue.get("opening", [])) + len(dialogue.get("closing", []))
    n_lines += sum(len(t.get("lines", [])) for t in dialogue.get("topics", []))
    print(f"[ダイアログ生成完了] {n_topics}トピック / {n_lines}セリフ")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dialogue, f, ensure_ascii=False, indent=2)
    print(f"[保存] {out_path}")


if __name__ == "__main__":
    main()
