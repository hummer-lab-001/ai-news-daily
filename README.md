# AI News Daily 📰

> 日本のAIコンサル実務向け「毎朝6:00 JST 更新」AIニュースダッシュボード

**公開URL:** https://hummer-lab-001.github.io/ai-news-daily/

---

## プロジェクト概要

毎朝 GitHub Actions が自動で以下を実行します：

1. 国内外のAIニュースをRSS・APIから取得（ITmedia、日経クロステック、OpenAI Blog、TechCrunch ほか）
2. Claude AIが記事を要約・ランク付け（コンサル実務視点で重要度を評価）
3. モバイル対応のHTML（PWA）を生成して GitHub Pages に公開

月額コストは **Claude API 代のみ $1〜3** です。

---

## セットアップ手順

### ステップ1: GitHubリポジトリを作成する

1. https://github.com/new を開く
2. Repository name: `ai-news-daily`
3. **Public** を選択
4. 「Create repository」をクリック

---

### ステップ2: GitHub Secretsに APIキーを登録する

> ここで登録したAPIキーは暗号化されて保存されます。外部に漏れることはありません。

1. GitHubの `ai-news-daily` リポジトリを開く
2. 上部タブの「**Settings**」をクリック
3. 左メニューの「**Secrets and variables**」→「**Actions**」を開く
4. 「**New repository secret**」ボタンをクリック
5. 以下のように入力して「Add secret」

   | 項目 | 値 |
   |---|---|
   | Name | `ANTHROPIC_API_KEY` |
   | Secret | `sk-ant-api03-xxxxxxxx`（Wordに保存してあるキー） |

---

### ステップ3: GitHub Pages を有効化する

1. リポジトリの「**Settings**」を開く
2. 左メニューの「**Pages**」をクリック
3. **Source** を `Deploy from a branch` に設定
4. **Branch** を `gh-pages` に設定（後述のコードpush後に選択肢が現れます）
5. 「Save」をクリック

---

### ステップ4: コードを GitHub に送る

ターミナル（コマンドプロンプト）で、`ai-news-daily` フォルダに移動してから以下を実行：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/hummer-lab-001/ai-news-daily.git
git push -u origin main
```

---

### ステップ5: 初回の手動実行

1. GitHubの `ai-news-daily` リポジトリを開く
2. 上部タブの「**Actions**」をクリック
3. 左メニューの「**Daily AI News Update**」を選択
4. 「**Run workflow**」ボタンをクリック → 「Run workflow」
5. 数分後にページが公開されます

---

### ステップ6（任意）: スマホのホーム画面に追加

1. スマホのブラウザで https://hummer-lab-001.github.io/ai-news-daily/ を開く
2. iPhoneの場合：下部の「共有」→「ホーム画面に追加」
3. Androidの場合：右上メニュー→「アプリをインストール」

---

## ローカル実行方法

> 自分のPCでテスト実行したいときの手順です。

### 前提
- Python 3.11 以上がインストール済み
- Anthropic APIキーが手元にある

### 環境構築

```bash
# リポジトリのフォルダに移動
cd ai-news-daily

# パッケージをインストール
pip install -r requirements.txt

# .env ファイルを作成してAPIキーを設定
copy .env.example .env
# .env ファイルをメモ帳で開き、APIキーを入力して保存
```

### 実行

```bash
# 1. 記事を取得（data/raw_YYYYMMDD.json が生成される）
python -m src.fetch

# 2. Claude で要約（data/summary_YYYYMMDD.json が生成される）
python -m src.summarize

# 3. HTML を生成（docs/index.html が生成される）
python -m src.build
```

生成された `docs/index.html` をブラウザで開くと確認できます。

### テスト実行

```bash
python -m pytest tests/test_fetch.py -v
```

---

## ディレクトリ構成

```
ai-news-daily/
├── .github/workflows/daily.yml   # GitHub Actions（毎朝自動実行）
├── config/sources.yml            # ニュースソースの定義・設定
├── src/
│   ├── fetch.py                  # RSSフィード・API取得
│   ├── summarize.py              # Claude AIによる要約
│   ├── rank.py                   # 重要度スコア・バッジ生成
│   └── build.py                  # HTML出力
├── templates/
│   ├── index.html.j2             # HTMLテンプレート
│   └── manifest.json             # PWA設定
├── docs/                         # GitHub Pagesの公開フォルダ
│   └── archive/                  # 過去30日分のバックナンバー
├── data/                         # 取得した記事・要約データ（Git管理外）
├── tests/test_fetch.py           # 自動テスト
├── requirements.txt              # Pythonパッケージ一覧
└── .env.example                  # 環境変数のサンプル
```

---

## ニュースソース一覧

| ソース | 種別 | 優先度 |
|---|---|---|
| ITmedia AI+ | RSS (日本語) | ★★★ |
| ASCII.jp AI | RSS (日本語) | ★★★ |
| 日経クロステック AI | RSS (日本語) | ★★★ |
| AI-Scholar | RSS (日本語) | ★★ |
| OpenAI Blog | RSS | ★★★ |
| Google AI Blog | RSS | ★★★ |
| Product Hunt AI | API | ★★★ |
| TechCrunch AI | RSS | ★★ |
| VentureBeat AI | RSS | ★★ |
| The Verge AI | RSS | ★★ |
| arXiv cs.AI/LG/CL | API | ★ |
| Hugging Face Daily Papers | API | ★ |
| Google DeepMind Blog | RSS | ★ |
| Meta AI Blog | RSS | ★ |
| Hacker News (AI) | API | ★ |

---

## トラブルシューティング

### Q: GitHub Actionsが失敗する

**確認ポイント:**
1. `ANTHROPIC_API_KEY` がSecretsに正しく登録されているか確認
2. Actionsタブでエラーログを確認（赤い×印のジョブをクリック）
3. APIキーの残高が残っているか https://console.anthropic.com/ で確認

---

### Q: ページが表示されない（404エラー）

**確認ポイント:**
1. Settings → Pages で `gh-pages` ブランチが選択されているか確認
2. Actions が最低1回成功しているか確認（`gh-pages` ブランチが作られるまで Pages は有効化できません）

---

### Q: 記事が0件になる

RSS配信サイド（各メディア）のURLが変更された可能性があります。

```bash
# ローカルで疎通確認スクリプトを実行
python -c "
import httpx, yaml, asyncio
with open('config/sources.yml') as f:
    cfg = yaml.safe_load(f)
async def check():
    async with httpx.AsyncClient(follow_redirects=True) as c:
        for s in [x for x in cfg['sources'] if x.get('type')=='rss']:
            try:
                r = await c.get(s['url'], timeout=10)
                print(s['name'], r.status_code)
            except Exception as e:
                print(s['name'], 'ERROR:', e)
asyncio.run(check())
"
```

404が出たソースについては `config/sources.yml` の該当行をコメントアウト(`#`)してください。

---

### Q: ローカルで `ANTHROPIC_API_KEY が設定されていません` と出る

`.env` ファイルにAPIキーを記入したうえで、以下で読み込んでください：

```bash
# Windows (コマンドプロンプト)
set ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx
python -m src.summarize
```

または `.env` ファイルを使う場合：

```bash
pip install python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv()"
python -m src.summarize
```

---

### Q: Pythonのバージョンが古い

このプロジェクトは Python 3.11 以上が必要です。
https://www.python.org/downloads/ から最新版をインストールしてください。

---

## ライセンス

MIT License — 個人・業務利用ともに自由にご使用ください。
