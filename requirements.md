# AI News Daily — 仕様書 (Claude Code 用)

**プロジェクトオーナー:** HUMMER
**GitHubユーザー名:** hummer-lab-001
**公開予定URL:** https://hummer-lab-001.github.io/ai-news-daily/

---

## 1. プロジェクト目的

日本のAIコンサル実務向けに、毎朝 **6:00 JST** までに更新される「その日の必読AIニュース」を、携帯ブラウザで閲覧できるPWA型ダッシュボードを構築する。

### 優先順位(重要)
- **8割:コンサル実務寄り** — 企業活用事例、ツール・サービスのローンチ、日本市場動向、ビジネス応用
- **2割:バランス** — 技術・研究(主要論文、新モデル、大手ラボ発表)、業界資金調達動向

---

## 2. 技術スタック

| レイヤ | 選定 | 理由 |
|---|---|---|
| 実行基盤 | GitHub Actions (cron) | 無料・安定・保守ゼロ |
| 言語 | Python 3.11+ | RSS/API処理が豊富 |
| AI要約 | Claude Sonnet 4.5 API | 日本語品質・コスト最適 |
| フロント | 静的HTML + Tailwind CSS (CDN) | ビルド不要・軽量 |
| ホスティング | GitHub Pages | 無料・HTTPS・高速 |
| 携帯閲覧 | PWA (manifest.json) | ホーム画面追加でアプリ化 |

**月額コスト想定:$1〜3(Claude API のみ)**

---

## 3. ディレクトリ構成

```
ai-news-daily/
├── .github/
│   └── workflows/
│       └── daily.yml          # cron 21:00 UTC = 6:00 JST
├── config/
│   └── sources.yml            # ソース定義・重み付け
├── src/
│   ├── __init__.py
│   ├── fetch.py               # 全ソース並列取得
│   ├── summarize.py           # Claude API要約
│   ├── rank.py                # 重要度スコアリング
│   └── build.py               # HTML生成
├── templates/
│   ├── index.html.j2          # メインテンプレ
│   └── manifest.json          # PWA設定
├── docs/                      # GitHub Pages出力先
│   ├── index.html
│   ├── archive/YYYY-MM-DD.html # 過去ログ(30日分保持)
│   └── manifest.json
├── tests/
│   └── test_fetch.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. ソース定義 (`config/sources.yml`)

### 重み付けポリシー
- `weight: 3` = 最優先(コンサル実務直結)
- `weight: 2` = 中優先(日本語一般読者向け、ビジネス)
- `weight: 1` = 補助(技術・研究、バランス用)

### 具体ソース

```yaml
sources:
  # ===== コンサル実務 (weight 3) — 日本語メディア =====
  - name: ITmedia AI+
    type: rss
    url: https://rss.itmedia.co.jp/rss/2.0/aiplus.xml
    weight: 3
    lang: ja

  - name: Ledge.ai
    type: rss
    url: https://ledge.ai/feed
    weight: 3
    lang: ja

  - name: ZDNet Japan AI
    type: rss
    url: https://japan.zdnet.com/rss/ai/index.rdf
    weight: 3
    lang: ja

  - name: ASCII.jp AI
    type: rss
    url: https://ascii.jp/rss.xml
    filter_keywords: [AI, 生成AI, LLM, ChatGPT, Claude, Gemini]
    weight: 3
    lang: ja

  - name: 日経クロステック AI
    type: rss
    url: https://xtech.nikkei.com/rss/index.rdf
    filter_keywords: [AI, 生成AI, LLM]
    weight: 3
    lang: ja

  # ===== コンサル実務 (weight 3) — ツール・製品 =====
  - name: OpenAI Blog
    type: rss
    url: https://openai.com/blog/rss.xml
    weight: 3
    lang: en

  - name: Anthropic News
    type: rss
    url: https://www.anthropic.com/news/rss.xml
    weight: 3
    lang: en

  - name: Google AI Blog
    type: rss
    url: https://blog.google/technology/ai/rss/
    weight: 3
    lang: en

  - name: Product Hunt AI
    type: api
    url: https://api.producthunt.com/v2/api/graphql
    category: artificial-intelligence
    weight: 3
    lang: en

  # ===== ビジネス・業界 (weight 2) =====
  - name: TechCrunch AI
    type: rss
    url: https://techcrunch.com/category/artificial-intelligence/feed/
    weight: 2
    lang: en

  - name: VentureBeat AI
    type: rss
    url: https://venturebeat.com/category/ai/feed/
    weight: 2
    lang: en

  - name: The Verge AI
    type: rss
    url: https://www.theverge.com/ai-artificial-intelligence/rss/index.xml
    weight: 2
    lang: en

  # ===== 技術・研究 (weight 1) — バランス2割 =====
  - name: arXiv cs.AI
    type: arxiv
    categories: [cs.AI, cs.LG, cs.CL]
    max_items: 5
    weight: 1
    lang: en

  - name: Hugging Face Daily Papers
    type: api
    url: https://huggingface.co/api/daily_papers
    max_items: 3
    weight: 1
    lang: en

  - name: Google DeepMind
    type: rss
    url: https://deepmind.google/blog/rss.xml
    weight: 1
    lang: en

  - name: Meta AI Blog
    type: rss
    url: https://ai.meta.com/blog/rss/
    weight: 1
    lang: en

  - name: Hacker News (AI)
    type: api
    url: https://hn.algolia.com/api/v1/search
    query: (AI OR LLM OR GPT OR Claude OR Gemini)
    min_points: 100
    weight: 1
    lang: en

# 取得範囲
lookback_hours: 24

# 除外キーワード(ノイズカット)
exclude_keywords:
  - クリプト
  - 仮想通貨
  - NFT
  - 占い
```

**注意:** RSS URLはサイト側で変更される場合があるため、初回実装時に一度全URL疎通確認を行う。到達不可のものはコメントアウトし、代替を探す。

---

## 5. Fetch モジュール (`src/fetch.py`)

### 機能
- `sources.yml` を読み、並列(asyncio)で全ソース取得
- 各記事を正規化形式に統一:

```python
@dataclass
class Article:
    source_name: str
    source_weight: int  # 1-3
    title: str
    url: str
    published_at: datetime
    summary_raw: str    # 元記事の冒頭200字
    lang: str           # 'ja' or 'en'
```

- 重複排除:URL正規化 + タイトル類似度(80%以上は同一扱い)
- `lookback_hours` より古い記事は除外
- `exclude_keywords` を含む記事は除外
- 結果を `data/raw_YYYYMMDD.json` に保存

### エラーハンドリング
- 個別ソース失敗で全体停止しない(try/except でログ記録し継続)
- 失敗ソースは最終HTMLのフッタに「取得失敗」として小さく表示

---

## 6. Summarize モジュール (`src/summarize.py`)

### Claude API 呼び出し仕様
- model: `claude-sonnet-4-5`
- 1日分の全記事を**バッチで1リクエスト**(コスト最適)
- max_tokens: 8000
- 入力:全記事のタイトル + 冒頭200字 + source_weight
- 出力:JSON

### プロンプト(システム)

```
あなたは日本のAIコンサルタント向けニュースキュレーターです。
以下の記事群から、日本企業のAI活用実務に最も役立つ情報を抽出してください。

重要度の判断基準(優先順):
1. 日本企業がすぐ使える具体的な活用事例・ツール・サービス
2. 主要AIツール(ChatGPT/Claude/Gemini/Copilot等)の新機能・価格・仕様変更
3. 日本のAI市場動向・規制・大手SIer/コンサル動向
4. 大手ラボ(OpenAI/Anthropic/Google/Meta)の製品発表
5. 資金調達・M&A等の業界動向
6. 技術・研究ブレイクスルー(実用性の高いもの)

出力形式(必ずJSONのみ、前後に文章を付けない):
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
    // 上位10件
  ],
  "digest": [
    {
      "title_ja": "タイトル",
      "one_liner": "1行要約(50字以内)",
      "category": "...",
      "url": "..."
    }
    // その他注目15件まで
  ]
}

- must_read は source_weight が高いものを優先しつつ、ニュース価値も加味して並び替える
- 英語記事は日本語に翻訳
- consultant_insight は「この情報を顧客にどう活かせるか」を一言で
- 重複する話題はまとめて1エントリにする
```

---

## 7. Build モジュール (`src/build.py`)

### HTML生成(Jinja2)

**必須要件:**
- モバイルファースト(375px基準)
- Tailwind CSS(CDN版でOK)
- ダークモード対応
- 重要度 ★1〜★5 を色帯で視覚化(★5=赤、★3=オレンジ、★1=グレー)
- カテゴリバッジ(実務/ツール/業界/研究)で色分け
- 元記事リンクは新規タブで開く
- ヘッダに最終更新時刻(JST)表示
- PWA manifest.json をリンク

**レイアウト:**
1. ヘッダ:「今日のAIニュース」+ 日付(JST) + 「最終更新:06:00 JST」
2. セクション1:「必読 TOP10」(カード形式、大)
3. セクション2:「その他注目」(リスト形式、コンパクト)
4. フッタ:「バックナンバー(30日)」へのリンク、取得失敗ソース

### 過去ログ
- 実行ごとに `docs/archive/YYYY-MM-DD.html` にコピー保存
- 30日より古いものは削除

---

## 8. GitHub Actions (`.github/workflows/daily.yml`)

```yaml
name: Daily AI News Update

on:
  schedule:
    - cron: '0 21 * * *'  # 21:00 UTC = 06:00 JST
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - run: pip install -r requirements.txt

      - name: Fetch & Summarize & Build
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python -m src.fetch
          python -m src.summarize
          python -m src.build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs

      - name: Commit archive
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add docs/archive/
          git commit -m "Archive $(date -u +%Y-%m-%d)" || echo "No changes"
          git push
```

---

## 9. セットアップ状況

### ✅ 完了済み
- GitHubアカウント作成(`hummer-lab-001`)
- Anthropic APIキー取得(Wordファイルに保存済み)
- Gitインストール(v2.53.0)
- Claude Codeデスクトップ版 起動確認

### 👉 これから行う手順
1. **GitHubリポジトリ作成**:`ai-news-daily`(Public推奨)
2. **GitHub Secrets に APIキー登録**:`ANTHROPIC_API_KEY`
3. **GitHub Pages 有効化**:Settings → Pages → gh-pages branch
4. **ローカルにコード実装**(Claude Code が作業)
5. **git push で GitHub に公開**
6. **Actions で初回手動実行 → 動作確認**
7. **携帯でURLを開き、ホーム画面に追加**

---

## 10. requirements.txt

```
anthropic>=0.40.0
feedparser>=6.0.11
httpx>=0.27.0
pyyaml>=6.0
jinja2>=3.1
python-dateutil>=2.9
arxiv>=2.1.0
beautifulsoup4>=4.12
lxml>=5.0
```

---

## 11. 拡張余地(フェーズ2以降)

- Discord Webhook通知
- 過去30日検索機能
- ブックマーク機能
- 英語→日本語の本文全訳
- クライアント別カスタマイズ版

---

## 12. Claude Code への最初の指示文(コピペ用)

Claude Code のチャット欄に、以下をそのまま貼り付けてください:

---

```
このフォルダに requirements.md があります。その仕様に従って ai-news-daily プロジェクトを一から実装してください。

ステップ順:
1. まず requirements.md を読み込んで全体像を把握する
2. ディレクトリ構造とファイル雛形を作る
3. config/sources.yml の全RSS URLについて、httpx で疎通確認を行う。到達不可のものはコメントアウトし、代替候補があれば提案する
4. src/fetch.py → src/summarize.py → src/build.py を順に実装し、各段階でローカルテストしてからコミット
5. .github/workflows/daily.yml を設定
6. README.md に日本語で以下を記載:
   - プロジェクト概要
   - セットアップ手順(GitHub Secrets登録、Pages有効化)
   - ローカル実行方法
   - トラブルシューティング
7. 最後に、GitHub に push するための git コマンド一式を提示する

進行中、以下に留意:
- 私(ユーザー)はプログラミング初心者です。エラーが出たら原因と対処を平易な日本語で説明してください
- 各ファイル作成後、短い説明文でその役割を教えてください
- 不明点があれば先に聞いてください。勝手に判断しないでください
- GitHubユーザー名は hummer-lab-001、公開URLは https://hummer-lab-001.github.io/ai-news-daily/ を想定しています
```

---

以上。
