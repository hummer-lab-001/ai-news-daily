"""
generate_video.py
ニューススタジオ風スライド（Aoi + Hina + 高層ビル背景）
- A6: セリフ単位でスピーカーを大きく切り替え
- A7: クリック率最適化サムネを別途生成
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import textwrap
import urllib.request


WIDTH, HEIGHT = 1280, 720
BG       = (10, 20, 50)
ACCENT   = (0, 200, 255)
WHITE    = (255, 255, 255)
SUBCOLOR = (180, 220, 255)
DARKBG   = (5, 15, 35)
HOT      = (255, 60, 50)
FONT_JA  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_FB  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

AOI_URL = os.environ.get(
    "AOI_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_033603_5dae32bb-0432-47b3-99cb-ff78daf251bb.png"
)
HINA_URL = os.environ.get(
    "HINA_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_011127_8249e8cc-ee28-4428-9c46-909d7270fc57.png"
)
STUDIO_URL = os.environ.get(
    "STUDIO_IMAGE_URL",
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_042918_e91d930e-133c-43f3-a3d7-e5e3596f8115.png"
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
    print(f"[画像DL] {os.path.basename(local)}")
    try:
        urllib.request.urlretrieve(url, local)
        return local
    except Exception as e:
        print(f"[警告] DL失敗 {local}: {e}")
        return ""


def crop_character(image_path: str, target_w: int, target_h: int):
    from PIL import Image
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path).convert("RGB")
        iw, ih = img.size
        scale = max(target_w / iw, target_h / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top  = max(0, (new_h - target_h) // 3)
        return img.crop((left, top, left + target_w, top + target_h))
    except Exception as e:
        print(f"[警告] クロップ失敗: {e}")
        return None


def make_studio_base():
    """スタジオ背景（共通ベース）"""
    from PIL import Image
    studio_path = download_image(STUDIO_URL, STUDIO_LOCAL_PATH)
    if studio_path and os.path.exists(studio_path):
        try:
            studio = Image.open(studio_path).convert("RGB")
            sw, sh = studio.size
            scale = max(WIDTH / sw, HEIGHT / sh)
            studio = studio.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
            cw, ch = studio.size
            return studio.crop(((cw - WIDTH) // 2, (ch - HEIGHT) // 2,
                               (cw - WIDTH) // 2 + WIDTH, (ch - HEIGHT) // 2 + HEIGHT))
        except Exception as e:
            print(f"[警告] スタジオ画像配置失敗: {e}")
    return Image.new("RGB", (WIDTH, HEIGHT), DARKBG)


def make_line_slide(title: str, subtitle: str, out_path: str,
                     mode: str = "topic", active_speaker: str = "A"):
    """静止スライド：両キャラ固定位置、テキスト中央固定（A6撤廃版）"""
    from PIL import Image, ImageDraw

    img = make_studio_base()

    aoi_path  = download_image(AOI_URL,  AOI_LOCAL_PATH)
    hina_path = download_image(HINA_URL, HINA_LOCAL_PATH)

    # 両キャラ固定サイズ（小さめ）でスタジオを広く見せる
    char_w = 280
    char_h = 540
    char_y = HEIGHT - char_h - 80   # 下寄せ・フッター上に配置

    aoi_img  = crop_character(aoi_path,  char_w, char_h)
    hina_img = crop_character(hina_path, char_w, char_h)

    if aoi_img:  img.paste(aoi_img,  (10, char_y))
    if hina_img: img.paste(hina_img, (WIDTH - char_w - 10, char_y))

    # 中央テキストパネル（固定位置・ずれなし）
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    panel_left, panel_right = 320, WIDTH - 320
    panel_top,  panel_bot   = 130, char_y + 40
    od.rectangle([(panel_left, panel_top), (panel_right, panel_bot)], fill=(5, 15, 35, 215))
    od.rectangle([(panel_left, panel_top), (panel_left + 4, panel_bot)], fill=(*ACCENT, 255))
    od.rectangle([(panel_right - 4, panel_top), (panel_right, panel_bot)], fill=(*ACCENT, 255))
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
    f_title  = find_font(38 if mode == "opening" else 34)
    f_sub    = find_font(24)
    f_footer = find_font(22)
    f_label  = find_font(22)

    # ヘッダー
    if   mode == "opening": program_label = "OPENING"
    elif mode == "closing": program_label = "ENDING"
    else:                   program_label = "毎日AIニュース"
    draw.text((30, 25), program_label, font=f_header, fill=WHITE)

    # LIVEバッジ
    draw.rectangle([(panel_left + 20, panel_top + 20),
                    (panel_left + 90, panel_top + 52)], fill=HOT)
    draw.text((panel_left + 30, panel_top + 24), "LIVE", font=f_label, fill=WHITE)

    # タイトル
    text_left  = panel_left + 20
    text_right = panel_right - 20
    text_w = text_right - text_left
    char_per_line = max(8, int(text_w / (f_title.size * 0.6)))
    lines = textwrap.wrap(title, width=char_per_line) if title else [""]
    line_h = f_title.size + 10
    block_h = len(lines) * line_h
    y = panel_top + 80 + max(0, ((panel_bot - panel_top - 80) - block_h) // 2 - 30)
    for line in lines:
        draw.text((text_left, y), line, font=f_title, fill=WHITE)
        y += line_h

    if subtitle:
        draw.text((text_left, y + 16), subtitle, font=f_sub, fill=ACCENT)

    # フッター
    if   mode == "closing": footer = "チャンネル登録・高評価よろしくお願いします！"
    elif mode == "opening": footer = "毎朝6時 配信中"
    else:                   footer = "毎日AIニュース"
    draw.text((30, HEIGHT - 42), footer, font=f_footer, fill=ACCENT)

    img.save(out_path, "PNG")


def make_thumbnail(headline: str, out_path: str):
    """A7: YouTubeサムネ専用（クリック率最適化版）"""
    from PIL import Image, ImageDraw, ImageFilter

    img = make_studio_base()

    aoi_path  = download_image(AOI_URL,  AOI_LOCAL_PATH)
    hina_path = download_image(HINA_URL, HINA_LOCAL_PATH)

    aoi_img  = crop_character(aoi_path,  340, 720)
    hina_img = crop_character(hina_path, 340, 720)

    if aoi_img:  img.paste(aoi_img,  (0, 0))
    if hina_img: img.paste(hina_img, (WIDTH - 340, 0))

    # 中央パネル（強コントラスト）
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([(310, 100), (WIDTH - 310, HEIGHT - 100)], fill=(5, 15, 35, 235))
    # 太いアクセント枠
    od.rectangle([(305, 95), (WIDTH - 305, HEIGHT - 95)], outline=(*ACCENT, 255), width=6)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 上部「今日のAIニュース」の帯
    draw.rectangle([(305, 95), (WIDTH - 305, 165)], fill=ACCENT)
    f_label = find_font(40)
    label = "毎日AIニュース"
    bbox = draw.textbbox((0, 0), label, font=f_label)
    lw = bbox[2] - bbox[0]
    draw.text(((WIDTH - lw) // 2, 110), label, font=f_label, fill=DARKBG)

    # メインヘッドライン（超大きく）
    f_head = find_font(72)
    head_lines = textwrap.wrap(headline, width=11) if headline else [""]
    if len(head_lines) > 3:
        head_lines = head_lines[:3]
    line_h = f_head.size + 12
    block_h = len(head_lines) * line_h
    y = 200 + max(0, (HEIGHT - 300 - block_h) // 2)
    for line in head_lines:
        bbox = draw.textbbox((0, 0), line, font=f_head)
        lw = bbox[2] - bbox[0]
        x = (WIDTH - lw) // 2
        # 影
        draw.text((x + 4, y + 4), line, font=f_head, fill=(0, 0, 0))
        draw.text((x, y), line, font=f_head, fill=WHITE)
        y += line_h

    # 下部ホットリボン
    draw.rectangle([(305, HEIGHT - 165), (WIDTH - 305, HEIGHT - 95)], fill=HOT)
    f_hot = find_font(36)
    hot_text = "今日も最新AI"
    bbox = draw.textbbox((0, 0), hot_text, font=f_hot)
    hw = bbox[2] - bbox[0]
    draw.text(((WIDTH - hw) // 2, HEIGHT - 152), hot_text, font=f_hot, fill=WHITE)

    img.save(out_path, "PNG")


def make_video(slide_paths, slide_durations, audio_path, out_path):
    tmpdir = tempfile.mkdtemp()
    try:
        seg_paths = []
        for i, (slide, dur) in enumerate(zip(slide_paths, slide_durations)):
            if dur <= 0.05:
                continue
            seg = os.path.join(tmpdir, f"seg_{i:04d}.mp4")
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
    dlg_path   = os.environ.get("DIALOGUE_JSON_PATH", "output/dialogue.json")
    timing_path= os.environ.get("TIMING_JSON_PATH",   "output/timing.json")
    audio_path = os.environ.get("NEWS_AUDIO_PATH",    "output/news.mp3")
    video_path = os.environ.get("NEWS_VIDEO_PATH",    "output/news.mp4")
    thumb_path = os.environ.get("NEWS_THUMB_PATH",    "output/thumbnail.png")
    slides_dir = os.environ.get("SLIDES_DIR",         "output/slides")

    for p, name in [(audio_path, "音声"), (timing_path, "timing.json"), (dlg_path, "dialogue.json")]:
        if not os.path.exists(p):
            print(f"[エラー] {name} が見つかりません: {p}")
            sys.exit(1)

    with open(timing_path, encoding="utf-8") as f:
        timing = json.load(f)
    with open(dlg_path, encoding="utf-8") as f:
        dialogue = json.load(f)

    durations = timing["durations"]
    line_speakers = timing.get("line_speakers", [])

    os.makedirs(slides_dir, exist_ok=True)

    download_image(AOI_URL,    AOI_LOCAL_PATH)
    download_image(HINA_URL,   HINA_LOCAL_PATH)
    download_image(STUDIO_URL, STUDIO_LOCAL_PATH)

    # 静止スライド（トピックごとに1枚・効率化）
    slide_paths = []
    slide_durs  = []
    cursor = 0

    # オープニング
    n_open = timing.get("opening_lines", 0)
    if n_open > 0:
        s = os.path.join(slides_dir, "00_opening.png")
        make_line_slide("今日のAIニュース", "", s, mode="opening")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n_open]))
        cursor += n_open

    # トピックごと
    for ti, timing_topic in enumerate(timing.get("topics", [])):
        title = timing_topic.get("title", f"トピック{ti+1}") or f"トピック{ti+1}"
        n_lines = timing_topic.get("n_lines", 0)
        s = os.path.join(slides_dir, f"{ti+1:02d}_topic.png")
        make_line_slide(title, f"トピック {ti+1}", s, mode="topic")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n_lines]))
        cursor += n_lines

    # クロージング
    n_close = timing.get("closing_lines", 0)
    if n_close > 0:
        s = os.path.join(slides_dir, "99_closing.png")
        make_line_slide("ご視聴ありがとうございました", "明日もお楽しみに！", s, mode="closing")
        slide_paths.append(s)
        slide_durs.append(sum(durations[cursor:cursor + n_close]))
        cursor += n_close

    if not slide_paths:
        print("[エラー] スライドが0個")
        sys.exit(1)

    print(f"[動画生成] スライド数: {len(slide_paths)} / 合計: {sum(slide_durs):.1f}秒")

    # ───── A7: サムネ生成（メイントピックを使用） ─────
    main_headline = "今日のAIニュース"
    topics = dialogue.get("topics", [])
    if topics:
        main_headline = topics[0].get("title", main_headline) or main_headline
    make_thumbnail(main_headline, thumb_path)
    print(f"[サムネイル] {thumb_path} (見出し: {main_headline})")

    make_video(slide_paths, slide_durs, audio_path, video_path)

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[動画完成] {video_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
