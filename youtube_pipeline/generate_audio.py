"""
generate_audio.py
Fish Audio API を使って AIニュース本文 → MP3 を生成する。
GitHub Actions (ubuntu-latest) で動作。
環境変数:
  FISH_AUDIO_API_KEY : Fish Audio の APIキー (GitHub Secrets)
  FISH_VOICE_ID      : 使用する声のID (GitHub Secrets または デフォルト値)
入力:  output/news.txt  (既存ワークフローが生成したニュース本文)
出力:  output/news.mp3
"""

import os
import sys


def main() -> None:
    api_key  = os.environ.get("FISH_AUDIO_API_KEY", "")
    voice_id = os.environ.get("FISH_VOICE_ID", "f1d92c18f84e47c6b5bc0cebb80ddaf5")
    text_path = os.environ.get("NEWS_TEXT_PATH", "output/news.txt")
    audio_path = os.environ.get("NEWS_AUDIO_PATH", "output/news.mp3")

    if not api_key:
        print("[エラー] FISH_AUDIO_API_KEY が設定されていません")
        sys.exit(1)

    if not os.path.exists(text_path):
        print(f"[エラー] ニューステキストが見つかりません: {text_path}")
        sys.exit(1)

    with open(text_path, encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("[エラー] ニューステキストが空です")
        sys.exit(1)

    print(f"[音声生成] テキスト長: {len(text)} 文字")
    print(f"[音声生成] 声ID: {voice_id}")

    try:
        from fish_audio_sdk import Session, TTSRequest
    except ImportError:
        print("[エラー] fish-audio-sdk がインストールされていません: pip install fish-audio-sdk")
        sys.exit(1)

    os.makedirs(os.path.dirname(audio_path), exist_ok=True)

    try:
        session = Session(api_key)
        with open(audio_path, "wb") as f:
            for chunk in session.tts(TTSRequest(reference_id=voice_id, text=text)):
                f.write(chunk)
        size_kb = os.path.getsize(audio_path) // 1024
        print(f"[音声生成完了] {audio_path} ({size_kb} KB)")
    except Exception as e:
        print(f"[エラー] Fish Audio API 呼び出し失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
