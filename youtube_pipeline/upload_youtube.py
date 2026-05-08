"""
upload_youtube.py
YouTube Data API v3 で動画を自動アップロードする。
GitHub Actions (ubuntu-latest) で動作。
環境変数:
  YOUTUBE_CLIENT_ID     : OAuth2 クライアントID     (GitHub Secrets)
  YOUTUBE_CLIENT_SECRET : OAuth2 クライアントシークレット (GitHub Secrets)
  YOUTUBE_REFRESH_TOKEN : リフレッシュトークン      (GitHub Secrets)
  NEWS_DATE             : 放送日 (例: 2026-05-08)
  NEWS_TEXT_PATH        : ニューステキストのパス (説明文に使用)
  NEWS_VIDEO_PATH       : アップロードする動画のパス
  NEWS_THUMB_PATH       : サムネイル画像のパス
  YOUTUBE_PLAYLIST_ID   : 追加するプレイリストID (省略可)
出力:  output/youtube_video_id.txt (アップロード後の動画ID)
"""

import os
import sys
import json
from datetime import datetime


def get_credentials():
    """環境変数から OAuth2 認証情報を構築する"""
    client_id     = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    missing = []
    if not client_id:     missing.append("YOUTUBE_CLIENT_ID")
    if not client_secret: missing.append("YOUTUBE_CLIENT_SECRET")
    if not refresh_token: missing.append("YOUTUBE_REFRESH_TOKEN")

    if missing:
        print(f"[エラー] 以下の環境変数が設定されていません: {', '.join(missing)}")
        print("  GitHub Secrets に追加してください")
        sys.exit(1)

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print("[エラー] google-auth がインストールされていません")
        print("  pip install google-auth google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"]
    )
    creds.refresh(Request())
    return creds


def upload_video(creds, video_path: str, title: str, description: str, thumb_path: str) -> str:
    """動画をアップロードして動画IDを返す"""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("[エラー] google-api-python-client がインストールされていません")
        sys.exit(1)

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["AIニュース", "人工知能", "テクノロジー", "毎日更新"],
            "categoryId": "28",   # 科学・技術
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024   # 10MB チャンク
    )

    print(f"[YouTube] アップロード開始: {title}")
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    video_id = None
    while True:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  アップロード中... {pct}%")
        if response:
            video_id = response["id"]
            break

    print(f"[YouTube] アップロード完了: https://youtube.com/watch?v={video_id}")

    # サムネイル設定
    if os.path.exists(thumb_path):
        try:
            from googleapiclient.http import MediaFileUpload as MFU
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MFU(thumb_path, mimetype="image/png")
            ).execute()
            print(f"[YouTube] サムネイル設定完了")
        except Exception as e:
            print(f"[警告] サムネイル設定失敗 (動画は公開済み): {e}")

    return video_id


def add_to_playlist(creds, video_id: str, playlist_id: str) -> None:
    """動画をプレイリストに追加する"""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return

    youtube = build("youtube", "v3", credentials=creds)
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        ).execute()
        print(f"[YouTube] プレイリスト追加完了: {playlist_id}")
    except Exception as e:
        print(f"[警告] プレイリスト追加失敗: {e}")


def main() -> None:
    date_str   = os.environ.get("NEWS_DATE", datetime.now().strftime("%Y-%m-%d"))
    text_path  = os.environ.get("NEWS_TEXT_PATH",  "output/news.txt")
    video_path = os.environ.get("NEWS_VIDEO_PATH", "output/news.mp4")
    thumb_path = os.environ.get("NEWS_THUMB_PATH", "output/thumbnail.png")
    playlist_id = os.environ.get("YOUTUBE_PLAYLIST_ID", "")

    if not os.path.exists(video_path):
        print(f"[エラー] 動画ファイルが見つかりません: {video_path}")
        print("  先に generate_video.py を実行してください")
        sys.exit(1)

    # タイトル・説明文を組み立てる
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = dt.strftime("%Y年%m月%d日")
    except ValueError:
        date_display = date_str

    title = f"今日のAIニュース {date_display}"

    description_parts = [
        f"📰 {date_display} のAIニュースをお届けします。",
        "",
        "このチャンネルでは毎朝6時(JST)にAI関連の最新ニュースを自動配信しています。",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🔔 チャンネル登録・高評価よろしくお願いします！",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if os.path.exists(text_path):
        with open(text_path, encoding="utf-8") as f:
            news_body = f.read().strip()
        description_parts.append("■ 本日のニュース内容")
        description_parts.append("")
        # YouTube 説明文は5000文字制限
        description_parts.append(news_body[:3000])

    description = "\n".join(description_parts)

    # 認証 → アップロード
    print(f"[YouTube] 認証中...")
    creds = get_credentials()

    video_id = upload_video(creds, video_path, title, description, thumb_path)

    if playlist_id:
        add_to_playlist(creds, video_id, playlist_id)

    # 動画IDをファイルに保存（後続ステップで参照可能）
    id_path = "output/youtube_video_id.txt"
    os.makedirs("output", exist_ok=True)
    with open(id_path, "w") as f:
        f.write(video_id)
    print(f"[完了] 動画ID保存: {id_path}")
    print(f"[完了] 公開URL: https://youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    main()
