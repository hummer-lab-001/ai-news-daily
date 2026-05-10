"""
generate_video.py
ニューススタジオ風スライド（Aoi + Hina 2人キャスター + 高層ビル背景）を音声に合わせて切り替える動画を生成。
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

# キャラクター画像URL（Higgsfield CloudFront）
AOI_URL = os.environ.get(
    "AOI_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_011904_d37adc90-702d-42b1-901d-8f9335ede8f2.png"
)
HINA_URL = os.environ.get(
    "HINA_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_011127_8249e8cc-ee28-4428-9c46-909d7270fc57.png"
)
STUDIO_URL = os.environ.get(
    "STUDIO_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_005605_388ec50e-62f4-4f3b-9b2a-2867d6548b57.png"
)
AOI_LOCAL_PATH    = "output/assets/aoi.png"
HINA_LOCAL_PATH   = "output/assets/hina.png"
STUDIO_LOCAL_PATH = "output/assets/studio.png"


def find_font(size: int):
    from PIL import ImageFont
    for p in [FONT_JA, FONT_FB]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def download_image(url: str, local: str) -> str:
    if os.path.exists(local):
        return local
    os.makedirs(os.path.dirname(local), exist_ok=True)
    print(f"[キャラ画像] DL: {os.path.basename(local)}")
    try:
        urllib.request.urlretrieve(url, local)
        return local
    except Exception as e:
        print(f"[警告] DL失敗 {local}: {e}")
        return ""


def crop_character(image_path: str, target_w: int, target_h: int):
    """キャラ画像を指定サイズにクロップして返す"""
    from PIL import Image
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path).convert("RGB")
        iw, ih = img.size
        scale = max(target_w / iw, target_h / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # 中央クロップ
        left = (new_w - target_w) // 2
        top  = max(0, (new_h - target_h) // 3)  # 顔が見えるよう上寄り
        return img.crop((left, top, left + target_w, top + target_h))
    except Exception as e:
        print(f"[警告] クロップ失敗: {e}")
        return None


def make_studio_slide(title: str, subtitle: str, date_disp: str, out_path: str,
                       mode: str = "topic", active_speaker: str = "A"):
    """
    ニューススタジオ風スライド：
    - 左：Aoi（メインキャスター）
    - 右：Hina（サブキャスター）
    - 中央：ニュース見出し
    - active_speaker = "A" or "B" でハイライト
    """
    from PIL import Image, ImageDraw, ImageEnhance

    # ベース：スタジオ背景をフルキャンバスに
    studio_path = download_image(STUDIO_URL, STUDIO_LOCAL_PATH)
    if studio_path and os.path.exists(studio_path):
        try:
            studio = Image.open(studio_path).convert("RGB")
            sw, sh = studio.size
            scale = max(WIDTH / sw, HEIGHT / sh)
            studio = studio.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
            cw, ch = studio.size
            studio = studio.crop(((cw - WIDTH) // 2, (ch - HEIGHT) // 2,
                                  (cw - WIDTH) // 2 + WIDTH, (ch - HEIGHT) // 2 + HEIGHT))
            img = studio.copy()
        except Exception as e:
            print(f"[警告] スタジオ画像配置失敗: {e}")
            img = Image.new("RGB", (WIDTH, HEIGHT), DARKBG)
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), DARKBG)

    # 左にAoi、右にHinaを配置
    aoi_path  = download_image(AOI_URL,  AOI_LOCAL_PATH)
    hina_path = download_image(HINA_URL, HINA_LOCAL_PATH)

    char_w = 360
    char_h = 720
    aoi_img  = crop_character(aoi_path,  char_w, char_h)
    hina_img = crop_character(hina_path, char_w, char_h)

    # スピーカーに応じて明度調整
    if active_speaker == "A":
        if hina_img: hina_img = ImageEnhance.Brightness(hina_img).enhance(0.55)
    else:
        if aoi_img:  aoi_img  = ImageEnhance.Brightness(aoi_img).enhance(0.55)

    if aoi_img:
        img.paste(aoi_img, (0, 0))
    if hina_img:
        img.paste(hina_img, (WIDTH - char_w, 0))

    # 中央のセンターパネル（半透明ダーク）
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    panel_left  = char_w - 20
    panel_right = WIDTH - char_w + 20
    od.rectangle([(panel_left, 90), (panel_right, HEIGHT - 70)], fill=(5, 15, 35, 230))
    # 縦アクセントライン
    od.rectangle([(panel_left, 90),  (panel_left + 4,  HEIGHT - 70)], fill=(*ACCENT, 255))
    od.rectangle([(panel_right - 4, 90), (panel_right, HEIGHT - 70)], fill=(*ACCENT, 255))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 上部ヘッダー帯
    for y in range(80):
        draw.line([(0, y), (WIDTH, y)], fill=(0, 50, 100))
    draw.rectangle([(0, 80), (WIDTH, 85)], fill=ACCENT)

    # 下部ティッカー帯
    draw.rectangle([(0, HEIGHT - 60), (WIDTH, HEIGHT)], fill=(0, 30, 70))
    draw.rectangle([(0, HEIGHT - 65), (WIDTH, HEIGHT - 60)], fill=ACCENT)

    f_header = find_font(32)
    f_date   = find_font(32)
    f_label  = find_font(22)
    f_name   = find_font(24)
    f_title  = find_font(46 if mode == "opening" else 40)
    f_sub    = find_font(26)
    f_footer = find_font(22)

    # ヘッダー
    if   mode == "opening": program_label = "📺 OPENING"
    elif mode == "closing": program_label = "🙏 ENDING"
    else:                   program_label = "🤖 毎日AIニュース"
    draw.text((30, 25), program_label, font=f_header, fill=WHITE)
    draw.text((WIDTH - 270, 28), date_disp, font=f_date, fill=ACCENT)

    # キャスターネームプレート
    name_y = HEIGHT - 130
    # Aoi (左)
    draw.rectangle([(20, name_y), (260, name_y + 50)],
                   fill=(*ACCENT, 255) if active_speaker == "A" else (60, 60, 80))
    draw.text((30, name_y + 8), "🎙 Aoi  メインMC", font=f_name, fill=WHITE)
    # Hina (右)
    draw.rectangle([(WIDTH - 260, name_y), (WIDTH - 20, name_y + 50)],
                   fill=(*ACCENT, 255) if active_speaker == "B" else (60, 60, 80))
    draw.text((WIDTH - 250, name_y + 8), "🎙 Hina  サブMC", font=f_name, fill=WHITE)

    # 中央パネル：LIVE バッジ
    cx_left = panel_left + 30
    live_y = 110
    draw.rectangle([(cx_left, live_y), (cx_left + 70, live_y + 32)], fill=(220, 0, 50))
    draw.text((cx_left + 12, live_y + 4), "LIVE", font=f_label, fill=WHITE)
    draw.text((cx_left + 90, live_y + 5), "Marunouchi", font=f_label, fill=SUBCOLOR)

    # 中央パネル：メインタイトル
    text_left  = panel_left + 30
    text_right = panel_right - 30
    text_w = text_right - text_left

    # 折り返し計算
    char_per_line = max(8, int(text_w / (f_title.size * 0.6)))
    lines = textwrap.wrap(title, width=char_per_line) if title else [""]
    line_h = f_title.size + 12
    block_h = len(lines) * line_h
    y = (HEIGHT - block_h) // 2 - 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f_title)
        tw = bbox[2] - bbox[0]
        x = text_left + (text_w - tw) // 2
        draw.text((x, y), line, font=f_title, fill=WHITE)
        y += line_h

    # サブタイトル
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
        tw = bbox[2] - bbox[0]
        x = text_left + (text_w - tw) // 2
        draw.text((x, y + 16), subtitle, font=f_sub, fill=ACCENT)

    # フッター
    if   mode == "closing": footer = "🔔 チャンネル登録・高評価よろしくお願いします！"
    elif mode == "opening": footer = "📡 毎朝6時 LIVE  |  Morning AI News"
    else:                   footer = "📡 毎日AIニュース  |  Powered by AI"
    draw.text((30, HEIGHT - 42), footer, font=f_footer, fill=ACCENT)

    img.save(out_path, "PNG")


def topic_majority_speaker(topic_lines):
    """トピック内で多く喋ってる話者を返す"""
    a = sum(1 for l in topic_lines if l.get("speaker") == "A")
    b = sum(1 for l in topic_lines if l.get("speaker") == "B")
    return "A" if a >= b else "B"


def make_video(slide_paths, slide_durations, audio_path, out_path):
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
    with open(dlg_path, encoding="utf-8") as f:
        dialogue = json.load(f)
    durations = timing["durations"]

    os.makedirs(slides_dir, exist_ok=True)

    # 事前ダウンロード（共有キャッシュ）
    download_image(AOI_URL,    AOI_LOCAL_PATH)
    download_image(HINA_URL,   HINA_LOCAL_PATH)
    download_image(STUDIO_URL, STUDIO_LOCAL_PATH)

    slide_paths = []
    slide_durs  = []
    cursor = 0

    # オープニング
    n = timing.get("opening_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "00_opening.png")
        # オープニングはAoiが主導
        make_studio_slide("今日のAIニュース", date_disp, date_disp, s,
                          mode="opening", active_speaker="A")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n]))
        cursor += n

    # トピックごと
    for i, (timing_topic, dlg_topic) in enumerate(zip(timing.get("topics", []),
                                                        dialogue.get("topics", []))):
        s = os.path.join(slides_dir, f"{i+1:02d}_topic.png")
        title = timing_topic.get("title", f"トピック{i+1}") or f"トピック{i+1}"
        active = topic_majority_speaker(dlg_topic.get("lines", []))
        make_studio_slide(title, f"トピック {i+1}", date_disp, s,
                          mode="topic", active_speaker=active)
        slide_paths.append(s)
        n_lines = timing_topic.get("n_lines", 0)
        slide_durs.append(sum(durations[cursor:cursor + n_lines]))
        cursor += n_lines

    # クロージング
    n = timing.get("closing_lines", 0)
    if n > 0:
        s = os.path.join(slides_dir, "99_closing.png")
        # クロージングはHinaが視聴者へ呼びかけ寄り
        make_studio_slide("ご視聴ありがとうございました", "明日もお楽しみに！", date_disp, s,
                          mode="closing", active_speaker="B")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n]))
        cursor += n

    if not slide_paths:
        print("[エラー] スライドが0個")
        sys.exit(1)

    print(f"[動画生成] スライド数: {len(slide_paths)} / 合計: {sum(slide_durs):.1f}秒")
    for i, (p, d) in enumerate(zip(slide_paths, slide_durs)):
        print(f"  [{i:>2}] {os.path.basename(p)} : {d:.1f}秒")

    shutil.copy(slide_paths[0], thumb_path)
    print(f"[サムネイル] {thumb_path}")

    make_video(slide_paths, slide_durs, audio_path, video_path)

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[動画完成] {video_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
