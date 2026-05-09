"""
generate_video.py
オープニング → トピック別スライド → クロージング を音声に合わせて切り替える動画を生成。
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
from datetime import datetime


WIDTH, HEIGHT = 1280, 720
BG       = (10, 20, 50)
ACCENT   = (0, 200, 255)
WHITE    = (255, 255, 255)
SUBCOLOR = (180, 220, 255)
FONT_JA  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_FB  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def find_font(size: int):
    from PIL import ImageFont
    for p in [FONT_JA, FONT_FB]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_frame(draw):
    """共通のヘッダー帯・フッター帯"""
    for y in range(80):
        draw.line([(0, y), (WIDTH, y)], fill=(0, 100, 200))
    draw.rectangle([(0, 80), (WIDTH, 85)], fill=ACCENT)
    draw.rectangle([(0, HEIGHT - 60), (WIDTH, HEIGHT)], fill=(0, 50, 100))


def make_slide(title: str, subtitle: str, date_disp: str, out_path: str, mode: str = "topic"):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    draw_frame(draw)

    f_header = find_font(32)
    f_date   = find_font(36)
    f_title  = find_font(80 if mode == "opening" else 64)
    f_sub    = find_font(36)
    f_footer = find_font(28)

    # ヘッダーラベル
    if   mode == "opening": label = "📺 OPENING"
    elif mode == "closing": label = "🙏 ENDING"
    else:                   label = "🤖 AIニュース"
    draw.text((50, 25), label, font=f_header, fill=WHITE)
    draw.text((WIDTH - 280, 30), date_disp, font=f_date, fill=ACCENT)

    # メインタイトル（折り返し）
    lines = textwrap.wrap(title, width=18) if title else [""]
    line_h = f_title.size + 12
    block_h = len(lines) * line_h
    y = (HEIGHT - block_h) // 2 - 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f_title)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=f_title, fill=WHITE)
        y += line_h

    # サブタイトル
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y + 20), subtitle, font=f_sub, fill=SUBCOLOR)

    # フッター
    if   mode == "closing": footer = "🔔 チャンネル登録・高評価よろしくお願いします！"
    elif mode == "opening": footer = "毎朝6時 配信中"
    else:                   footer = "毎日AIニュース"
    draw.text((50, HEIGHT - 42), footer, font=f_footer, fill=ACCENT)

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

    slide_paths = []
    slide_durs  = []
    cursor = 0

    # オープニング
    n = timing.get("opening_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "00_opening.png")
        make_slide("今日のAIニュース", date_disp, date_disp, s, mode="opening")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n]))
        cursor += n

    # トピックごと
    for i, topic in enumerate(timing.get("topics", [])):
        s = os.path.join(slides_dir, f"{i+1:02d}_topic.png")
        title = topic.get("title", f"トピック{i+1}") or f"トピック{i+1}"
        make_slide(title, f"トピック {i+1}", date_disp, s, mode="topic")
        slide_paths.append(s)
        n_lines = topic.get("n_lines", 0)
        slide_durs.append(sum(durations[cursor:cursor + n_lines]))
        cursor += n_lines

    # クロージング
    n = timing.get("closing_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "99_closing.png")
        make_slide("ご視聴ありがとうございました", "明日もお楽しみに！", date_disp, s, mode="closing")
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
