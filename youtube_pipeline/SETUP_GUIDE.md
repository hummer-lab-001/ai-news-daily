# YouTube 自動アップロード セットアップガイド

## 概要

```
GitHub Actions（毎朝6時JST）
  ↓ [既存] Claude API でAIニューステキスト生成
  ↓ [追加] Fish Audio で日本語音声生成（MP3）
  ↓ [追加] Pillow でサムネイル画像生成（PNG）
  ↓ [追加] ffmpeg で音声＋画像を合成（MP4）
  ↓ [追加] YouTube Data API v3 で自動アップロード
```

---

## STEP 1: Fish Audio APIキー取得

1. https://fish.audio にアクセス
2. 右上「Sign Up」でアカウント作成（Googleログイン可）
3. ログイン後、右上メニュー → 「API」または「Settings」
4. 「Create API Key」をクリック → APIキーをコピー
5. 声IDは https://fish.audio/ja/ で試聴して選択
   - 声のページURL末尾の英数字が Voice ID
   - デフォルト設定: `f1d92c18f84e47c6b5bc0cebb80ddaf5`（変更可）

---

## STEP 2: Google Cloud プロジェクト & YouTube OAuth設定

### 2-1. プロジェクト作成
1. https://console.cloud.google.com にアクセス
2. 「プロジェクトを作成」→ 名前例: `ai-news-youtube`
3. 作成したプロジェクトを選択

### 2-2. YouTube Data API v3 を有効化
1. 左メニュー「APIとサービス」→「ライブラリ」
2. 「YouTube Data API v3」を検索 → 「有効にする」

### 2-3. OAuth 同意画面の設定
1. 「APIとサービス」→「OAuth 同意画面」
2. User Type: 「外部」→「作成」
3. アプリ名: `AI News Auto Upload`（任意）
4. サポートメール: 自分のGmailアドレス
5. 「保存して次へ」を3回クリック
6. 「テストユーザー」タブ → 「＋ADD USERS」→ 自分のGmailを追加
7. 「保存して次へ」

### 2-4. OAuth 2.0 クライアントIDの作成
1. 「APIとサービス」→「認証情報」
2. 「＋認証情報を作成」→「OAuth クライアントID」
3. アプリケーションの種類: 「デスクトップ アプリ」
4. 名前: `ai-news-cli`（任意）→「作成」
5. **クライアントID** と **クライアントシークレット** をメモ

---

## STEP 3: リフレッシュトークン取得（Windows・初回のみ）

Windowsのコマンドプロンプトまたは PowerShell で以下を実行します。

### 3-1. 必要パッケージをインストール
```cmd
pip install google-auth-oauthlib
```

### 3-2. トークン取得スクリプトを実行
```cmd
python youtube_pipeline/get_refresh_token.py
```

> ※ `get_refresh_token.py` は次ファイルの内容です。  
> 以下のコードを `youtube_pipeline/get_refresh_token.py` として保存してください:

```python
"""
YouTube OAuth2 リフレッシュトークン取得スクリプト（初回のみ実行）
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID     = input("クライアントID     : ").strip()
CLIENT_SECRET = input("クライアントシークレット: ").strip()

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "="*60)
print("✅ 以下の値を GitHub Secrets に登録してください")
print("="*60)
print(f"YOUTUBE_CLIENT_ID     : {CLIENT_ID}")
print(f"YOUTUBE_CLIENT_SECRET : {CLIENT_SECRET}")
print(f"YOUTUBE_REFRESH_TOKEN : {creds.refresh_token}")
print("="*60)
```

### 3-3. ブラウザでYouTubeチャンネルのGoogleアカウントにログイン
- スクリプト実行後、ブラウザが自動で開きます
- 動画をアップロードしたいチャンネルのGoogleアカウントでログイン
- 「このアプリはGoogleで確認されていません」→ 「詳細」→「続行」

### 3-4. 表示された3つの値をメモ
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`  
- `YOUTUBE_REFRESH_TOKEN`

---

## STEP 4: GitHub Secrets に登録

1. GitHubリポジトリ（`hummer-lab-001/[リポジトリ名]`）を開く
2. 「Settings」→「Secrets and variables」→「Actions」
3. 「New repository secret」で以下を1つずつ追加：

| Secret名 | 値 |
|---|---|
| `FISH_AUDIO_API_KEY` | STEP1で取得したAPIキー |
| `FISH_VOICE_ID` | 使用する声のID（省略可） |
| `YOUTUBE_CLIENT_ID` | STEP3で取得 |
| `YOUTUBE_CLIENT_SECRET` | STEP3で取得 |
| `YOUTUBE_REFRESH_TOKEN` | STEP3で取得 |
| `YOUTUBE_PLAYLIST_ID` | プレイリストID（省略可） |

---

## STEP 5: ワークフローファイルに追記

### 5-1. 既存ワークフローの確認
`.github/workflows/` 内のYAMLファイルを開く

### 5-2. ニュース本文の artifact 出力を確認・追加
既存の「ニュース生成ジョブ」に以下を追加してください：

```yaml
      - name: ニュース本文を artifact として保存
        uses: actions/upload-artifact@v4
        with:
          name: ai-news-text
          path: output/news.txt    # ← ニュース本文が保存されるパス
          retention-days: 1
```

> ※ 既存ジョブがどこにテキストを出力しているか確認して `path` を合わせてください。

### 5-3. `workflow_addition.yml` の内容を追記
`workflow_addition.yml` のコードを既存 YAML の末尾に追加する。

```yaml
  # （既存 jobs: の中に追記）
  youtube-upload:
    needs: generate-news    # ← 既存のジョブ名に変更
    ...（workflow_addition.yml の内容をそのまま貼り付け）
```

### 5-4. スクリプトをリポジトリに追加
```
リポジトリ直下/
  youtube_pipeline/
    generate_audio.py     ✅
    generate_video.py     ✅
    upload_youtube.py     ✅
    requirements.txt      ✅
    get_refresh_token.py  ✅（ローカル実行専用・コミット可）
```

```cmd
git add youtube_pipeline/
git commit -m "feat: YouTube自動アップロードパイプライン追加"
git push
```

---

## STEP 6: 動作確認

1. GitHub Actions の「Actions」タブを開く
2. 「Run workflow」で手動実行
3. `youtube-upload` ジョブのログを確認
4. GitHubサマリーに動画URLが表示されれば成功 🎉

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|---|---|---|
| `FISH_AUDIO_API_KEY が設定されていません` | Secrets未登録 | STEP4を確認 |
| `ffmpeg: command not found` | ワークフローのaptインストール失敗 | ワークフローのaptステップを確認 |
| `Invalid client` | クライアントIDが間違い | STEP2-4をやり直し |
| `Token has been expired` | リフレッシュトークン無効 | STEP3をやり直し |
| `quotaExceeded` | YouTube API 日次上限 | 翌日に再試行（上限:10,000ユニット/日） |
| `uploadLimitExceeded` | 未認証チャンネルの上限 | チャンネル認証（電話番号確認）を実施 |

---

## YouTube API クォータについて

- デフォルトのクォータ: **10,000 ユニット/日**
- 動画アップロード: **1,600 ユニット**
- 毎日1本アップロード: 問題なし（余裕あり）

---

## ファイル構成

```
リポジトリ/
├── .github/
│   └── workflows/
│       └── ai-news.yml          # 既存 + youtube-upload ジョブを追記
├── youtube_pipeline/
│   ├── generate_audio.py        # Fish Audio TTS
│   ├── generate_video.py        # サムネイル生成 + ffmpeg
│   ├── upload_youtube.py        # YouTube アップロード
│   ├── get_refresh_token.py     # 初回セットアップ用（ローカルのみ実行）
│   └── requirements.txt
└── output/                      # GitHub Actions が生成（.gitignore推奨）
    ├── news.txt
    ├── news.mp3
    ├── thumbnail.png
    ├── news.mp4
    └── youtube_video_id.txt
```
