"""
generate_video.py
ニューススタジオ風スライド（Aoiキャラ + 高層ビル背景）を音声に合わせて切り替える動画を生成。
入力:  output/dialogue.json, output/timing.json, output/news.mp3
出力:  output/news.mp4, output/thumbnail.png, output/slides/*.png
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import textwrap
import urllib.request
from datetime import datetime


WIDTH, HEIGHT = 1280, 720
BG       = (10, 20, 50)
ACCENT   = (0, 200, 255)
WHITE    = (255, 255, 255)
SUBCOLOR = (180, 220, 255)
DARKBG   = (5, 15, 35)
FONT_JA  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_FB  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Aoi キャラクター画像のURL（Higgsfield CloudFront）
AOI_URL = os.environ.get(
    "AOI_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260509_163956_150d9827-80e9-4102-adc9-c236672044df.png"
)
AOI_LOCAL_PATH = "output/assets/aoi.png"


def find_font(size: int):
    from PIL import ImageFont
    for p in [FONT_JA, FONT_FB]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def download_aoi() -> str:
    """Aoi画像をダウンロードしてキャッシュ"""
    if os.path.exists(AOI_LOCAL_PATH):
        return AOI_LOCAL_PATH
    os.makedirs(os.path.dirname(AOI_LOCAL_PATH), exist_ok=True)
    print(f"[Aoi画像] ダウンロード中: {AOI_URL}")
    try:
        urllib.request.urlretrieve(AOI_URL, AOI_LOCAL_PATH)
        print(f"[Aoi画像] 保存: {AOI_LOCAL_PATH}")
        return AOI_LOCAL_PATH
    except Exception as e:
        print(f"[警告] Aoi画像ダウンロード失敗: {e}")
        return ""


def make_studio_slide(title: str, subtitle: str, date_disp: str, out_path: str, mode: str = "topic"):
    """
    ニューススタジオ風スライド：
    - 左側にAoiキャラ（写真）
    - 右側にニュース見出し
    - 上部にチャンネル名と日付
    - 下部にティッカー風フッター
    """
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (WIDTH, HEIGHT), DARKBG)
    draw = ImageDraw.Draw(img)

    # Aoi画像を左半分に配置（背景の高層ビルごと使う）
    aoi_path = download_aoi()
    if aoi_path and os.path.exists(aoi_path):
        try:
            aoi = Image.open(aoi_path).convert("RGB")
            # 16:9で左半分（640x720）にトリミング
            aw, ah = aoi.size
            target_w, target_h = 640, 720
            # アスペクト比を維持して target_h に合わせて拡大
            scale = target_h / ah
            new_w = int(aw * scale)
            new_h = target_h
            aoi_resized = aoi.resize((new_w, new_h), Image.LANCZOS)
            # 中央クロップ
            if new_w > target_w:
                left = (new_w - target_w) // 2
                aoi_resized = aoi_resized.crop((left, 0, left + target_w, target_h))
            img.paste(aoi_resized, (0, 0))
        except Exception as e:
            print(f"[警告] Aoi画像配置失敗: {e}")

    # 右側のニュース表示エリア（半透明オーバーレイ）
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    # 右半分を半透明ダーク
    overlay_draw.rectangle([(640, 0), (WIDTH, HEIGHT)], fill=(5, 15, 35, 235))
    # 左右の境界に縦のアクセントライン
    overlay_draw.rectangle([(636, 0), (640, HEIGHT)], fill=(*ACCENT, 255))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 上部ヘッダー帯（番組ロゴエリア）
    for y in range(80):
        alpha_val = int(220 * (1 - y / 80))
        draw.line([(0, y), (WIDTH, y)], fill=(0, 50, 100))
    draw.rectangle([(0, 80), (WIDTH, 85)], fill=ACCENT)

    # 下部ティッカー帯
    draw.rectangle([(0, HEIGHT - 60), (WIDTH, HEIGHT)], fill=(0, 30, 70))
    draw.rectangle([(0, HEIGHT - 65), (WIDTH, HEIGHT - 60)], fill=ACCENT)

    f_header = find_font(34)
    f_date   = find_font(34)
    f_label  = find_font(26)
    f_title  = find_font(48 if mode == "opening" else 44)
    f_sub    = find_font(28)
    f_footer = find_font(24)

    # ヘッダー：番組ロゴ
    if   mode == "opening": program_label = "📺 OPENING"
    elif mode == "closing": program_label = "🙏 ENDING"
    else:                   program_label = "🤖 毎日AIニュース"
    draw.text((30, 25), program_label, font=f_header, fill=WHITE)
    draw.text((WIDTH - 280, 28), date_disp, font=f_date, fill=ACCENT)

    # 右側：「LIVE」ラベル
    live_x, live_y = 670, 110
    draw.rectangle([(live_x, live_y), (live_x + 80, live_y + 36)], fill=(220, 0, 50))
    draw.text((live_x + 14, live_y + 4), "LIVE", font=f_label, fill=WHITE)
    draw.text((live_x + 95, live_y + 4), "From Marunouchi", font=f_label, fill=SUBCOLOR)

    # 右側：メインタイトル
    text_area_left = 670
    text_area_right = WIDTH - 30
    text_area_width = text_area_right - text_area_left

    lines = textwrap.wrap(title, width=14) if title else [""]
    line_h = f_title.size + 14
    block_h = len(lines) * line_h
    y = (HEIGHT - block_h) // 2 - 30
    for line in lines:
        draw.text((text_area_left, y), line, font=f_title, fill=WHITE)
        y += line_h

    # 右側：サブタイトル
    if subtitle:
        draw.text((text_area_left, y + 20), subtitle, font=f_sub, fill=ACCENT)

    # 右側：装飾アクセント
    draw.rectangle([(text_area_left, 200), (text_area_left + 60, 204)], fill=ACCENT)

    # フッター
    if   mode == "closing": footer = "🔔 チャンネル登録・高評価よろしくお願いします！"
    elif mode == "opening": footer = "📡 毎朝6時 LIVE配信中  |  Morning AI News"
    else:                   footer = "📡 毎日AIニュース  |  Powered by AI"
    draw.text((30, HEIGHT - 42), footer, font=f_footer, fill=ACCENT)

    img.save(out_path, "PNG")


def make_video(slide_paths, slide_durations, audio_path, out_path):
    """各スライドをdurationだけ表示する動画を ffmpeg で作る"""
    tmpdir = tempfile.mkdtemp()
    try:
        seg_paths = []
        for i, (slide, dur) in enumerate(zip(slide_paths, slide_durations)):
            if dur <= 0.05:
                continue
            seg = os.path.join(tmpdir, f"seg_{i:03d}.mp4")
            r = subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", slide,
                "-c:v", "libx264", "-tune", "stillimage",
                "-t", f"{dur:.3f}",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={WIDTH}:{HEIGHT}",
                "-r", "30",
                seg
            ], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[エラー] セグメント生成失敗: {r.stderr[-500:]}")
                sys.exit(1)
            seg_paths.append(seg)

        if not seg_paths:
            print("[エラー] セグメントが0個です")
            sys.exit(1)

        # 連結
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for s in seg_paths:
                f.write(f"file '{s}'\n")

        video_only = os.path.join(tmpdir, "video.mp4")
        r = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", video_only
        ], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[エラー] 連結失敗: {r.stderr[-500:]}")
            sys.exit(1)

        # 音声と合成
        r = subprocess.run([
            "ffmpeg", "-y", "-i", video_only, "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", out_path
        ], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[エラー] 音声合成失敗: {r.stderr[-500:]}")
            sys.exit(1)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    date_str   = os.environ.get("NEWS_DATE", datetime.now().strftime("%Y-%m-%d"))
    dlg_path   = os.environ.get("DIALOGUE_JSON_PATH", "output/dialogue.json")
    timing_path= os.environ.get("TIMING_JSON_PATH",   "output/timing.json")
    audio_path = os.environ.get("NEWS_AUDIO_PATH",    "output/news.mp3")
    video_path = os.environ.get("NEWS_VIDEO_PATH",    "output/news.mp4")
    thumb_path = os.environ.get("NEWS_THUMB_PATH",    "output/thumbnail.png")
    slides_dir = os.environ.get("SLIDES_DIR",         "output/slides")

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_disp = dt.strftime("%Y年%m月%d日")
    except ValueError:
        date_disp = date_str

    for p, name in [(audio_path, "音声"), (timing_path, "timing.json"), (dlg_path, "dialogue.json")]:
        if not os.path.exists(p):
            print(f"[エラー] {name} が見つかりません: {p}")
            sys.exit(1)

    with open(timing_path, encoding="utf-8") as f:
        timing = json.load(f)
    durations = timing["durations"]

    os.makedirs(slides_dir, exist_ok=True)

    # Aoi画像を事前にダウンロード（一度だけ）
    download_aoi()

    slide_paths = []
    slide_durs  = []
    cursor = 0

    # オープニング
    n = timing.get("opening_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "00_opening.png")
        make_studio_slide("今日のAIニュース", date_disp, date_disp, s, mode="opening")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n]))
        cursor += n

    # トピックごと
    for i, topic in enumerate(timing.get("topics", [])):
        s = os.path.join(slides_dir, f"{i+1:02d}_topic.png")
        title = topic.get("title", f"トピック{i+1}") or f"トピック{i+1}"
        make_studio_slide(title, f"トピック {i+1}", date_disp, s, mode="topic")
        slide_paths.append(s)
        n_lines = topic.get("n_lines", 0)
        slide_durs.append(sum(durations[cursor:cursor + n_lines]))
        cursor += n_lines

    # クロージング
    n = timing.get("closing_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "99_closing.png")
        make_studio_slide("ご視聴ありがとうございました", "明日もお楽しみに！", date_disp, s, mode="closing")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n]))
        cursor += n

    if not slide_paths:
        print("[エラー] スライドが0個")
        sys.exit(1)

    print(f"[動画生成] スライド数: {len(slide_paths)} / 合計: {sum(slide_durs):.1f}秒")
    for i, (p, d) in enumerate(zip(slide_paths, slide_durs)):
        print(f"  [{i:>2}] {os.path.basename(p)} : {d:.1f}秒")

    # サムネイル: オープニングまたは最初のスライド
    shutil.copy(slide_paths[0], thumb_path)
    print(f"[サムネイル] {thumb_path}")

    make_video(slide_paths, slide_durs, audio_path, video_path)

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[動画完成] {video_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
