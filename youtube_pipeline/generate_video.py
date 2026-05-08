"""
generate_video.py
サムネイル画像(Pillow) + 音声(MP3) → 動画(MP4) を ffmpeg で生成する。
GitHub Actions (ubuntu-latest) で動作。
環境変数:
  NEWS_DATE      : 放送日 (例: 2026-05-08)
  NEWS_TITLE     : 動画タイトル (省略時は自動生成)
  NEWS_TEXT_PATH : ニューステキストのパス (デフォルト: output/news.txt)
  NEWS_AUDIO_PATH: 音声ファイルのパス   (デフォルト: output/news.mp3)
  NEWS_VIDEO_PATH: 出力動画のパス       (デフォルト: output/news.mp4)
入力:  output/news.mp3, output/news.txt
出力:  output/news.mp4, output/thumbnail.png
"""

import os
import sys
import subprocess
import textwrap
from datetime import datetime


# ── 定数 ─────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
BG_COLOR      = (10, 20, 50)       # ダークネイビー
ACCENT_COLOR  = (0, 200, 255)      # シアン
TEXT_COLOR    = (255, 255, 255)    # 白
DATE_COLOR    = (0, 200, 255)
FONT_PATH_JA  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_PATH_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def find_font(size: int):
    """利用可能な日本語フォントを返す"""
    from PIL import ImageFont
    for path in [FONT_PATH_JA, FONT_PATH_FALLBACK]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_thumbnail(title: str, date_str: str, out_path: str) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[エラー] Pillow がインストールされていません: pip install Pillow")
        sys.exit(1)

    img  = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # グラデーション風の上部バー
    for y in range(80):
        alpha = int(255 * (1 - y / 80))
        draw.line([(0, y), (WIDTH, y)], fill=(0, 100, 200))

    # アクセントライン
    draw.rectangle([(0, 80), (WIDTH, 85)], fill=ACCENT_COLOR)

    # ヘッダーラベル
    font_small = find_font(32)
    draw.text((50, 25), "🤖  AI ニュース", font=font_small, fill=TEXT_COLOR)

    # 日付
    font_date = find_font(36)
    draw.text((WIDTH - 280, 30), date_str, font=font_date, fill=DATE_COLOR)

    # タイトル（折り返し）
    font_title = find_font(64)
    lines = textwrap.wrap(title, width=20)
    y_pos = HEIGHT // 2 - (len(lines) * 80) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x_pos = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x_pos, y_pos), line, font=font_title, fill=TEXT_COLOR)
        y_pos += 80

    # フッター
    font_footer = find_font(28)
    draw.rectangle([(0, HEIGHT - 60), (WIDTH, HEIGHT)], fill=(0, 50, 100))
    draw.text((50, HEIGHT - 42), "毎朝6時更新 | AI News Channel", font=font_footer, fill=ACCENT_COLOR)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    print(f"[サムネイル生成完了] {out_path}")


def generate_video(image_path: str, audio_path: str, video_path: str) -> None:
    """ffmpeg で静止画 + 音声 → MP4"""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        video_path
    ]
    print(f"[動画生成] ffmpeg 実行中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[エラー] ffmpeg 失敗:\n{result.stderr}")
        sys.exit(1)
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[動画生成完了] {video_path} ({size_mb:.1f} MB)")


def main() -> None:
    date_str   = os.environ.get("NEWS_DATE", datetime.now().strftime("%Y-%m-%d"))
    text_path  = os.environ.get("NEWS_TEXT_PATH",  "output/news.txt")
    audio_path = os.environ.get("NEWS_AUDIO_PATH", "output/news.mp3")
    video_path = os.environ.get("NEWS_VIDEO_PATH", "output/news.mp4")
    thumb_path = os.environ.get("NEWS_THUMB_PATH", "output/thumbnail.png")

    # 日付フォーマット変換: 2026-05-08 → 2026年05月08日
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = dt.strftime("%Y年%m月%d日")
        title = f"今日のAIニュース {date_display}"
    except ValueError:
        date_display = date_str
        title = f"今日のAIニュース {date_display}"

    custom_title = os.environ.get("NEWS_TITLE", "")
    if custom_title:
        title = custom_title

    if not os.path.exists(audio_path):
        print(f"[エラー] 音声ファイルが見つかりません: {audio_path}")
        print("  先に generate_audio.py を実行してください")
        sys.exit(1)

    print(f"[動画生成] タイトル: {title}")
    print(f"[動画生成] 日付: {date_display}")

    make_thumbnail(title, date_display, thumb_path)
    generate_video(thumb_path, audio_path, video_path)


if __name__ == "__main__":
    main()
