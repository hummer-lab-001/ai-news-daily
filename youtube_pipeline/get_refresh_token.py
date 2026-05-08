"""
get_refresh_token.py
YouTube OAuth2 リフレッシュトークンを取得する（初回のみ・ローカル実行専用）。
実行前: pip install google-auth-oauthlib
"""

from google_auth_oauthlib.flow import InstalledAppFlow

print("="*60)
print("YouTube OAuth2 リフレッシュトークン取得ツール")
print("="*60)
print()
print("Google Cloud Console から取得した値を入力してください。")
print()

CLIENT_ID     = input("クライアントID          : ").strip()
CLIENT_SECRET = input("クライアントシークレット    : ").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("[エラー] クライアントIDとシークレットは必須です")
    raise SystemExit(1)

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

print()
print("ブラウザが開きます。動画をアップロードしたいチャンネルの")
print("Googleアカウントでログインしてください。")
print()

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)

print()
print("="*60)
print("✅ 以下の3つを GitHub Secrets に登録してください")
print("="*60)
print()
print(f"Secret名: YOUTUBE_CLIENT_ID")
print(f"値      : {CLIENT_ID}")
print()
print(f"Secret名: YOUTUBE_CLIENT_SECRET")
print(f"値      : {CLIENT_SECRET}")
print()
print(f"Secret名: YOUTUBE_REFRESH_TOKEN")
print(f"値      : {creds.refresh_token}")
print()
print("="*60)
print("登録先: GitHubリポジトリ → Settings → Secrets and variables → Actions")
print("="*60)
