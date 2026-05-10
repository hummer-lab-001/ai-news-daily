"""
generate_audio.py
dialogue.json を読み込み、2人の声で交互に音声生成 → ffmpegで連結 → 1.5倍速MP3を出力
BGMが指定されている場合は背景に重ねる
環境変数:
  FISH_AUDIO_API_KEY : Fish Audio APIキー
  FISH_VOICE_ID_A    : キャスターA の声ID
  FISH_VOICE_ID_B    : キャスターB の声ID
  AUDIO_SPEED        : 再生速度倍率（デフォルト 1.2）
  BGM_URL            : BGM音源のURL（省略可・未設定ならBGMなし）
  BGM_VOLUME         : BGMの音量倍率（デフォルト 0.12 = ナレーションの12%）
入力:  output/dialogue.json
出力:  output/news.mp3, output/timing.json
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import urllib.request


def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def download_bgm(url: str) -> str:
    """BGMファイルをダウンロードしてキャッシュパスを返す"""
    if not url:
        return ""
    cache_path = "output/assets/bgm.mp3"
    if os.path.exists(cache_path):
        return cache_path
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        print(f"[BGM] ダウンロード: {url[:60]}...")
        urllib.request.urlretrieve(url, cache_path)
        return cache_path
    except Exception as e:
        print(f"[警告] BGMダウンロード失敗: {e}")
        return ""


def main() -> None:
    api_key = os.environ.get("FISH_AUDIO_API_KEY", "")
    voice_a = os.environ.get("FISH_VOICE_ID_A") or "f1d92c18f84e47c6b5bc0cebb80ddaf5"
    voice_b = os.environ.get("FISH_VOICE_ID_B") or "4be4823b28884678b6c5bd1785516652"
    speed   = float(os.environ.get("AUDIO_SPEED", "1.2"))
    bgm_url = os.environ.get("BGM_URL", "").strip()
    bgm_volume = float(os.environ.get("BGM_VOLUME", "0.12"))

    dialogue_path = os.environ.get("DIALOGUE_JSON_PATH", "output/dialogue.json")
    out_path      = os.environ.get("NEWS_AUDIO_PATH",   "output/news.mp3")
    timing_path   = os.environ.get("TIMING_JSON_PATH",  "output/timing.json")

    if not api_key:
        print("[エラー] FISH_AUDIO_API_KEY 未設定")
        sys.exit(1)

    if not os.path.exists(dialogue_path):
        print(f"[エラー] {dialogue_path} が見つかりません")
        sys.exit(1)

    with open(dialogue_path, encoding="utf-8") as f:
        dialogue = json.load(f)

    try:
        from fish_audio_sdk import Session, TTSRequest
    except ImportError:
        print("[エラー] fish-audio-sdk 未インストール")
        sys.exit(1)

    session = Session(api_key)

    flat_lines = []
    timing = {"opening_lines": 0, "topics": [], "closing_lines": 0, "line_speakers": []}

    for line in dialogue.get("opening", []):
        flat_lines.append(line)
        timing["opening_lines"] += 1
        timing["line_speakers"].append(line.get("speaker", "A"))

    for topic in dialogue.get("topics", []):
        timing["topics"].append({
            "title": topic.get("title", ""),
            "n_lines": len(topic.get("lines", []))
        })
        for line in topic.get("lines", []):
            flat_lines.append(line)
            timing["line_speakers"].append(line.get("speaker", "A"))

    for line in dialogue.get("closing", []):
        flat_lines.append(line)
        timing["closing_lines"] += 1
        timing["line_speakers"].append(line.get("speaker", "A"))

    if not flat_lines:
        print("[エラー] セリフが0件")
        sys.exit(1)

    print(f"[音声生成] {len(flat_lines)}セリフ・{speed}倍速")

    tmpdir = tempfile.mkdtemp()
    audio_files = []
    durations = []

    try:
        for i, line in enumerate(flat_lines, 1):
            speaker = line.get("speaker", "A")
            text    = (line.get("text", "") or "").strip()
            if not text:
                durations.append(0.0)
                continue

            voice_id = voice_a if speaker == "A" else voice_b
            chunk_path = os.path.join(tmpdir, f"chunk_{i:04d}.mp3")

            preview = text[:40].replace("\n", " ")
            print(f"  [{i:>3}/{len(flat_lines)}] {speaker}: {preview}...", end="", flush=True)
            try:
                with open(chunk_path, "wb") as f:
                    for chunk in session.tts(TTSRequest(reference_id=voice_id, text=text)):
                        f.write(chunk)
            except Exception as e:
                print(f"\n[エラー] Fish Audio API失敗: {e}")
                sys.exit(1)

            audio_files.append(chunk_path)
            dur = get_audio_duration(chunk_path) / speed
            durations.append(dur)
            print(f" {dur:.1f}秒")

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for af in audio_files:
                f.write(f"file '{af}'\n")

        tmp_concat = os.path.join(tmpdir, "concat.mp3")
        print(f"\n[連結中]...")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_file, "-c", "copy", tmp_concat],
            check=True, capture_output=True
        )

        # 速度変更
        tmp_speed = os.path.join(tmpdir, "speed.mp3")
        print(f"[速度変更] {speed}倍速")
        atempo_chain = build_atempo_chain(speed)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_concat,
             "-filter:a", atempo_chain,
             "-b:a", "192k", tmp_speed],
            check=True, capture_output=True
        )

        # BGM ミックス（指定されていれば）
        bgm_path = download_bgm(bgm_url)
        if bgm_path and os.path.exists(bgm_path):
            print(f"[BGM] ナレーションとミックス（音量{bgm_volume}）")
            # ナレーションの長さを取得
            narration_dur = get_audio_duration(tmp_speed)
            # BGMをループ + フェードイン/アウト + 音量調整 + ミックス
            mix_filter = (
                f"[1:a]aloop=loop=-1:size=2e+09,"
                f"volume={bgm_volume},"
                f"afade=t=in:st=0:d=2,"
                f"afade=t=out:st={max(0, narration_dur - 2):.2f}:d=2[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[out]"
            )
            r = subprocess.run([
                "ffmpeg", "-y",
                "-i", tmp_speed,
                "-i", bgm_path,
                "-filter_complex", mix_filter,
                "-map", "[out]",
                "-b:a", "192k",
                "-t", f"{narration_dur:.2f}",
                out_path
            ], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[警告] BGMミックス失敗、ナレーションのみ使用:\n{r.stderr[-300:]}")
                shutil.copy(tmp_speed, out_path)
            else:
                print(f"[BGM] ミックス完了")
        else:
            shutil.copy(tmp_speed, out_path)

        size_kb = os.path.getsize(out_path) // 1024
        total = sum(durations)
        print(f"[音声完成] {out_path} ({size_kb}KB / {total:.1f}秒)")

        timing["durations"] = durations
        timing["total_duration"] = total
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing, f, ensure_ascii=False, indent=2)
        print(f"[タイミング保存] {timing_path}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_atempo_chain(speed: float) -> str:
    if speed <= 0:
        return "atempo=1.0"
    chain = []
    s = speed
    while s > 2.0:
        chain.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        chain.append("atempo=0.5")
        s /= 0.5
    chain.append(f"atempo={s:.4f}")
    return ",".join(chain)


if __name__ == "__main__":
    main()
