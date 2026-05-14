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
    "https://d8j0ntlcm91z4.cloudfront.net/user_33dxZ6VrJEWONHus0sRNp74z8Vt/hf_20260510_050434_c59ecd08-ff7a-4332-8b84-585c2c069746.png"
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


def remove_background(image_path: str) -> str:
    """rembg で背景を透過化。透過版のパスを返す（キャッシュあり）"""
    if not image_path or not os.path.exists(image_path):
        return ""
    base, ext = os.path.splitext(image_path)
    cutout_path = base + "_cutout.png"
    if os.path.exists(cutout_path):
        return cutout_path
    try:
        from rembg import remove
        from PIL import Image
        print(f"[背景透過] {os.path.basename(image_path)} 処理中...")
        with open(image_path, "rb") as f:
            input_data = f.read()
        output_data = remove(input_data)
        with open(cutout_path, "wb") as f:
            f.write(output_data)
        print(f"[背景透過] {os.path.basename(cutout_path)} 完了")
        return cutout_path
    except Exception as e:
        print(f"[警告] 背景透過失敗 {image_path}: {e}")
        return image_path  # 失敗時は元画像を返す


def crop_character_transparent(image_path: str, target_w: int, target_h: int,
                                 zoom: float = 1.0, vertical_offset: float = 0.33):
    """透過キャラ画像をリサイズして返す（RGBA）"""
    from PIL import Image
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path).convert("RGBA")
        iw, ih = img.size
        base_scale = max(target_w / iw, target_h / ih)
        scale = base_scale * zoom
        new_w, new_h = int(iw * scale), int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top  = max(0, int((new_h - target_h) * vertical_offset))
        return img.crop((left, top, left + target_w, top + target_h))
    except Exception as e:
        print(f"[警告] 透過クロップ失敗: {e}")
        return None


def crop_to_person_normalized(image_path: str, target_w: int, target_h: int,
                                upper_ratio: float = 0.55):
    """透過画像から人物の上半身（顔＋胸元）を検出してアップで揃える。
    upper_ratio: 人物の上から何割を使うか（0.5=半身、0.4=顔寄り）
    """
    from PIL import Image
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        img = Image.open(image_path).convert("RGBA")
        bbox = img.getbbox()
        if not bbox:
            return None
        left, top, right, bottom = bbox
        # 上半身だけにクロップ
        upper_bottom = top + int((bottom - top) * upper_ratio)
        person = img.crop((left, top, right, upper_bottom))
        pw, ph = person.size

        # キャンバスを埋めるようスケール（顔がデカく見える）
        scale_h = target_h / ph
        scale_w = target_w / pw
        scale = max(scale_h, scale_w)  # キャンバスを完全に埋める
        new_pw = int(pw * scale)
        new_ph = int(ph * scale)
        person = person.resize((new_pw, new_ph), Image.LANCZOS)

        # 中央クロップ
        canvas_crop_left = max(0, (new_pw - target_w) // 2)
        canvas_crop_top = 0  # 上寄せ（顔を上部に）
        person = person.crop((canvas_crop_left, canvas_crop_top,
                              canvas_crop_left + target_w, canvas_crop_top + target_h))

        # 透過キャンバスに配置
        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        canvas.paste(person, (0, 0), person)
        return canvas
    except Exception as e:
        print(f"[警告] 人物正規化失敗: {e}")
        return None


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

    # キャラサイズ（先に決めておく）
    char_w = 280
    char_h = 420
    char_y = HEIGHT - char_h - 70

    # ───── 順序：背景 → パネル → テキスト → キャラ（前面） ─────
    # ① モニター位置にテキストパネル（先に描画）
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    panel_left, panel_right = 240, WIDTH - 240
    panel_top,  panel_bot   = 100, 510
    od.rectangle([(panel_left, panel_top), (panel_right, panel_bot)], fill=(3, 8, 18, 250))
    # ベゼル風枠
    od.rectangle([(panel_left, panel_top), (panel_left + 5, panel_bot)], fill=(*ACCENT, 255))
    od.rectangle([(panel_right - 5, panel_top), (panel_right, panel_bot)], fill=(*ACCENT, 255))
    od.rectangle([(panel_left, panel_top), (panel_right, panel_top + 5)], fill=(*ACCENT, 255))
    od.rectangle([(panel_left, panel_bot - 5), (panel_right, panel_bot)], fill=(*ACCENT, 255))
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
    f_title  = find_font(72 if mode == "opening" else 64)  # 大幅サイズUP
    f_sub    = find_font(32)
    f_footer = find_font(22)
    f_label  = find_font(28)

    # ヘッダー
    if   mode == "opening": program_label = "OPENING"
    elif mode == "closing": program_label = "ENDING"
    else:                   program_label = "毎日AIニュース"
    draw.text((30, 25), program_label, font=f_header, fill=WHITE)

    # LIVEバッジ（パネル左上）
    draw.rectangle([(panel_left + 25, panel_top + 25),
                    (panel_left + 130, panel_top + 70)], fill=HOT)
    draw.text((panel_left + 40, panel_top + 30), "LIVE", font=f_label, fill=WHITE)

    # テキスト領域＝キャラに被らない中央ゾーンに限定
    # キャラは x=20-300（Aoi）と x=980-1260（Hina）を占有
    # → テキストは x=320-960（中央 640px）に収める
    text_left  = 320
    text_right = WIDTH - 320
    text_w = text_right - text_left

    # タイトル（超デカ・極太縁取り）
    char_per_line = max(5, int(text_w / (f_title.size * 0.65)))
    lines = textwrap.wrap(title, width=char_per_line) if title else [""]
    line_h = f_title.size + 18
    block_h = len(lines) * line_h
    y = panel_top + 100 + max(0, ((panel_bot - panel_top - 100) - block_h) // 2 - 30)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f_title)
        lw = bbox[2] - bbox[0]
        x = text_left + (text_w - lw) // 2
        # 黒の極太縁取り（8方向にずらして描画 = 太字感UP）
        for dx, dy in [(-3,-3),(-3,0),(-3,3),(0,-3),(0,3),(3,-3),(3,0),(3,3),
                       (-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((x + dx, y + dy), line, font=f_title, fill=(0, 0, 0))
        # 白本体
        draw.text((x, y), line, font=f_title, fill=WHITE)
        y += line_h

    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
        sw = bbox[2] - bbox[0]
        sx = text_left + (text_w - sw) // 2
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((sx + dx, y + 16 + dy), subtitle, font=f_sub, fill=(0, 0, 0))
        draw.text((sx, y + 16), subtitle, font=f_sub, fill=ACCENT)

    # ② キャラを最後に貼る（テキストより前面に出る）
    aoi_cutout  = remove_background(aoi_path)
    hina_cutout = remove_background(hina_path)
    aoi_img  = crop_to_person_normalized(aoi_cutout,  char_w, char_h, upper_ratio=0.42)
    hina_img = crop_to_person_normalized(hina_cutout, char_w, char_h, upper_ratio=0.55)
    img = img.convert("RGBA")
    if aoi_img:  img.paste(aoi_img,  (20, char_y), aoi_img)
    if hina_img: img.paste(hina_img, (WIDTH - char_w - 20, char_y), hina_img)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    # フッター（キャラの後に描画して足元情報を残す）
    if   mode == "closing": footer = "チャンネル登録・高評価よろしくお願いします！"
    elif mode == "opening": footer = "毎朝6時 配信中"
    else:                   footer = "毎日AIニュース"
    draw.text((30, HEIGHT - 42), footer, font=f_footer, fill=ACCENT)

    img.save(out_path, "PNG")


def compose_thumbnail_from_template(template_path: str, headline: str, out_path: str):
    """テンプレートサムネの赤い帯エリアに今日のトピックを自動描画する"""
    from PIL import Image, ImageDraw

    template = Image.open(template_path).convert("RGB")
    tw, th = template.size
    # YouTubeサムネ標準 1280x720 にリサイズ（テンプレが違うサイズの場合）
    if (tw, th) != (1280, 720):
        scale = max(1280 / tw, 720 / th)
        new_w, new_h = int(tw * scale), int(th * scale)
        template = template.resize((new_w, new_h), Image.LANCZOS)
        cw, ch = template.size
        template = template.crop(((cw - 1280) // 2, (ch - 720) // 2,
                                   (cw - 1280) // 2 + 1280, (ch - 720) // 2 + 720))

    draw = ImageDraw.Draw(template)

    # 赤い帯のテキスト描画エリア（テンプレの構図に合わせる）
    banner_left, banner_right = 200, 1180
    banner_top,  banner_bot   = 30,  420
    text_w = banner_right - banner_left
    text_h = banner_bot - banner_top

    # フォントサイズを自動調整：1行で収まらなければ縮小・改行
    YELLOW = (255, 230, 30)
    OUTLINE = (0, 0, 0)

    # 改行を試行：適切なフォントサイズを探す
    import textwrap
    best_lines = None
    best_font_size = 100
    for fs in [110, 100, 92, 84, 76, 68, 60]:
        f = find_font(fs)
        # 1行あたりの文字数を推定
        chars_per_line = max(4, int(text_w / (fs * 0.85)))
        for char_n in range(chars_per_line, 3, -1):
            test_lines = textwrap.wrap(headline, width=char_n)
            if not test_lines:
                continue
            line_h = fs + 8
            block_h = len(test_lines) * line_h
            # 1行の最大幅をチェック
            max_lw = 0
            for line in test_lines:
                bbox = draw.textbbox((0, 0), line, font=f)
                max_lw = max(max_lw, bbox[2] - bbox[0])
            if max_lw <= text_w and block_h <= text_h:
                best_lines = test_lines
                best_font_size = fs
                break
        if best_lines:
            break
    if not best_lines:
        best_lines = [headline[:10] + "..."]
        best_font_size = 60

    f_title = find_font(best_font_size)
    line_h = best_font_size + 8
    block_h = len(best_lines) * line_h
    y = banner_top + (text_h - block_h) // 2

    for line in best_lines:
        bbox = draw.textbbox((0, 0), line, font=f_title)
        lw = bbox[2] - bbox[0]
        x = banner_left + (text_w - lw) // 2
        # 極太縁取り（黒・8方向×複数距離）
        for d in [4, 3]:
            for dx, dy in [(-d,-d),(-d,0),(-d,d),(0,-d),(0,d),(d,-d),(d,0),(d,d)]:
                draw.text((x + dx, y + dy), line, font=f_title, fill=OUTLINE)
        # 本体（黄色）
        draw.text((x, y), line, font=f_title, fill=YELLOW)
        y += line_h

    template.save(out_path, "PNG")


def make_thumbnail(headline: str, out_path: str):
    """サムネ：上70%にホットトピック帯、下30%にキャラ＋ブランド"""
    from PIL import Image, ImageDraw

    # キャンバス
    img = Image.new("RGB", (WIDTH, HEIGHT), DARKBG)

    # ───── 上70%（504px）：HOT TOPIC バナー ─────
    banner_h = int(HEIGHT * 0.7)  # 504
    # 赤グラデーション風（上が濃く、下がやや明るく）
    for y in range(banner_h):
        ratio = y / banner_h
        r = int(200 - 30 * ratio)
        g = int(20 + 10 * ratio)
        b = int(30 + 20 * ratio)
        for x in range(WIDTH):
            img.putpixel((x, y), (r, g, b))
    # でも遅いので、上書きでベタ塗り
    overlay = Image.new("RGB", (WIDTH, banner_h), (200, 30, 40))
    img.paste(overlay, (0, 0))
    # 縞模様の動きで派手に
    draw_banner = ImageDraw.Draw(img)
    for i in range(0, WIDTH, 80):
        draw_banner.polygon([(i, 0), (i + 30, 0), (i + 60, banner_h), (i + 30, banner_h)],
                           fill=(220, 40, 50))

    # 「TODAY 注目」ラベル（左上）
    f_today = find_font(36)
    draw_banner.rectangle([(30, 30), (260, 80)], fill=(255, 220, 50))
    draw_banner.text((50, 36), "TODAY 注目", font=f_today, fill=(40, 0, 0))

    # 「🔥」記号代わりに「!」を装飾
    draw_banner.rectangle([(WIDTH - 130, 30), (WIDTH - 30, 130)], fill=(255, 220, 50))
    f_fire = find_font(64)
    draw_banner.text((WIDTH - 110, 35), "!!", font=f_fire, fill=(200, 0, 0))

    # メインヘッドライン（超大きく、影付き）
    f_head = find_font(82)
    head_lines = textwrap.wrap(headline, width=10) if headline else [""]
    if len(head_lines) > 3:
        head_lines = head_lines[:3]
    line_h = f_head.size + 18
    block_h = len(head_lines) * line_h
    y = 130 + max(0, (banner_h - 130 - 30 - block_h) // 2)
    for line in head_lines:
        bbox = draw_banner.textbbox((0, 0), line, font=f_head)
        lw = bbox[2] - bbox[0]
        x = (WIDTH - lw) // 2
        # 黒い太い縁取り（複数回ずらして描画）
        for dx, dy in [(-3,-3),(-3,3),(3,-3),(3,3),(-3,0),(3,0),(0,-3),(0,3)]:
            draw_banner.text((x + dx, y + dy), line, font=f_head, fill=(0, 0, 0))
        # 白本体
        draw_banner.text((x, y), line, font=f_head, fill=WHITE)
        y += line_h

    # ───── 下30%（216px）：キャラ＋ブランド ─────
    char_area_top = banner_h  # 504

    # スタジオ背景の下部を背景に
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
            studio_bottom = studio.crop((0, char_area_top, WIDTH, HEIGHT))
            img.paste(studio_bottom, (0, char_area_top))
        except Exception:
            pass

    # キャラを下に配置
    char_h = HEIGHT - char_area_top  # 216
    char_w = 200
    aoi_path  = download_image(AOI_URL,  AOI_LOCAL_PATH)
    hina_path = download_image(HINA_URL, HINA_LOCAL_PATH)
    aoi_img  = crop_character(aoi_path,  char_w, char_h)
    hina_img = crop_character(hina_path, char_w, char_h)
    if aoi_img:  img.paste(aoi_img,  (30, char_area_top))
    if hina_img: img.paste(hina_img, (WIDTH - char_w - 30, char_area_top))

    # 中央：チャンネルブランド
    draw = ImageDraw.Draw(img)
    brand_left  = char_w + 60
    brand_right = WIDTH - char_w - 60
    brand_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bo = ImageDraw.Draw(brand_overlay)
    bo.rectangle([(brand_left, char_area_top + 30),
                  (brand_right, HEIGHT - 30)], fill=(5, 15, 35, 230))
    img = Image.alpha_composite(img.convert("RGBA"), brand_overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    f_brand = find_font(48)
    f_sub_brand = find_font(22)
    brand_text = "毎日AIニュース"
    bbox = draw.textbbox((0, 0), brand_text, font=f_brand)
    bw = bbox[2] - bbox[0]
    bx = (WIDTH - bw) // 2
    by = char_area_top + 50
    draw.text((bx, by), brand_text, font=f_brand, fill=WHITE)

    sub = "毎朝6時 / 1日5分のAIインテリジェンス"
    bbox = draw.textbbox((0, 0), sub, font=f_sub_brand)
    sw_ = bbox[2] - bbox[0]
    sx = (WIDTH - sw_) // 2
    draw.text((sx, by + 60), sub, font=f_sub_brand, fill=ACCENT)

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

    aoi_local  = download_image(AOI_URL,    AOI_LOCAL_PATH)
    hina_local = download_image(HINA_URL,   HINA_LOCAL_PATH)
    download_image(STUDIO_URL, STUDIO_LOCAL_PATH)

    # キャラの背景を事前に透過化（rembgは初回モデルDLで時間かかるため1回だけ）
    print("[前処理] キャラ画像の背景を透過化中...")
    remove_background(aoi_local)
    remove_background(hina_local)
    print("[前処理] 完了")

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

    # ───── サムネイル：テンプレ + 毎日のトピック自動合成 ─────
    main_headline = "今日のAIニュース"
    topics = dialogue.get("topics", [])
    if topics:
        main_headline = topics[0].get("title", main_headline) or main_headline

    template_thumb = "youtube_pipeline/thumbnail_template.png"
    static_thumb   = "youtube_pipeline/thumbnail.png"

    if os.path.exists(template_thumb):
        # テンプレに今日のトピックを描画
        compose_thumbnail_from_template(template_thumb, main_headline, thumb_path)
        print(f"[サムネイル] テンプレ＋トピック合成: {main_headline}")
    elif os.path.exists(static_thumb):
        # 固定サムネ（旧運用）
        shutil.copy(static_thumb, thumb_path)
        print(f"[サムネイル] 固定サムネを使用: {static_thumb}")
    else:
        # フォールバック自動生成
        make_thumbnail(main_headline, thumb_path)
        print(f"[サムネイル] フォールバック自動生成: {main_headline}")

    make_video(slide_paths, slide_durs, audio_path, video_path)

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[動画完成] {video_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
