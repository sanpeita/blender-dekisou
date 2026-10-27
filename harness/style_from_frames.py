"""SuperVL に過去回のフレームを見せて「型」をJSONで抽出させ、Ultraで統合する。

SuperVL は1プロンプト最大8枚の制約があるので、動画ごとに1回呼ぶ。
（動画が増えてもスケールする設計）

使い方:
    python harness/style_from_frames.py [--videos ZqXTGcICMFA,g7Y-mSuVeQU,...]
出力:
    assets/style.json
    assets/style_parts/<video_id>.json
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import Nebius, MODEL_VL, MODEL_PLANNER  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "assets" / "frames"
PARTS = ROOT / "assets" / "style_parts"
OUT = ROOT / "assets" / "style.json"

DEFAULT_VIDEOS = {
    "ZqXTGcICMFA": (40.3, "背景ボケは主役を決めればOK"),
    "g7Y-mSuVeQU": (46.1, "レンダーは見たいところだけ試せる"),
    "KsgvL4SW4u4": (30.5, "色を見るならマテリアルプレビュー"),
}

PER_VIDEO_SYSTEM = """あなたは映像ディレクターです。渡された連続フレーム（1本の縦型ショート動画から
時系列で抜いたもの）を観察し、その動画の作りをJSONだけで報告します。
推測で埋めず、フレームから実際に確認できることだけ書いてください。不明は null。"""

PER_VIDEO_USER = """動画ID: {vid} / 尺: {dur}秒 / テーマ: {title} / 縦型 360x640 30fps
以下の{count}枚は時系列です。

{{"vid":"{vid}","first_caption_within_sec":number|null,
 "telop":{{"cards":number|null,"chars_per_card_max":number|null,"position":string,"has_outline_or_shadow":bool}},
 "operation_visibility":{{"cursor_or_highlight_visible":bool,"ui_panels_visible":bool,"zoom_ins":number|null}},
 "visual_style":{{"background":string,"avatar_present":bool,"color_accent":string}},
 "pacing":{{"state_changes":number|null,"text_changes_fast":bool}},
 "hook_observed":string,"notes":string}}"""

MERGE_SYSTEM = """あなたは映像ディレクターです。複数の動画から個別に抽出した観察結果を統合し、
シリーズ共通の「型」をJSONで出力します。数値は中央値や最頻値を使ってください。
観察結果に無い情報を足さないこと。"""

MERGE_USER = """シリーズ「Blenderできそう」の{count}本分の観察結果です。

{parts}

これらを統合し、次のスキーマでJSONだけを出力してください。

{{"series":"blender-dekisou","sample_count":{count},
 "duration_sec":{{"median":{median},"min":{dmin},"max":{dmax}}},
 "hook":{{"template":string,"first_caption_within_sec":number|null,"pain_is_stated_as_question":bool|null}},
 "pacing":{{"state_changes":number|null,"text_changes_fast":bool|null}},
 "telop":{{"cards":number|null,"chars_per_card_max":number|null,"position":string,"has_outline_or_shadow":bool|null}},
 "operation_visibility":{{"cursor_or_highlight_visible":bool|null,"ui_panels_visible":bool|null,"zoom_ins":number|null}},
 "visual_style":{{"background":string,"avatar_present":bool|null,"color_accent":string}},
 "tone_notes":string}}"""


def analyze_video(n: Nebius, vid: str, dur: float, title: str) -> dict | None:
    files = sorted((FRAMES / vid).glob("*.jpg"))[:8]  # 8枚上限
    if not files:
        print(f"[skip] {vid}: フレーム無し")
        return None
    content: list[dict] = [{"type": "text", "text": PER_VIDEO_USER.format(
        vid=vid, dur=dur, title=title, count=len(files))}]
    for f in files:
        b64 = base64.b64encode(f.read_bytes()).decode("ascii")
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    msgs = [{"role": "system", "content": PER_VIDEO_SYSTEM},
            {"role": "user", "content": content}]
    r = n.chat(MODEL_VL, msgs, temperature=0.2, max_tokens=2048,
               reasoning_effort="none")
    txt = n.text(r)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        print(f"[{vid}] JSON無し: {txt[:200]}")
        return None
    try:
        part = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"[{vid}] パース失敗: {e}")
        return None
    PARTS.mkdir(parents=True, exist_ok=True)
    (PARTS / f"{vid}.json").write_text(
        json.dumps(part, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{vid}] ok: cards={part.get('telop', {}).get('cards')} "
          f"cursor={part.get('operation_visibility', {}).get('cursor_or_highlight_visible')}")
    return part


def merge(n: Nebius, parts: list[dict], durations: list[float]) -> dict:
    durations = sorted(durations)
    med = durations[len(durations) // 2]
    body = MERGE_USER.format(
        count=len(parts), median=med, dmin=durations[0], dmax=durations[-1],
        parts=json.dumps(parts, ensure_ascii=False, indent=1))
    msgs = [{"role": "system", "content": MERGE_SYSTEM},
            {"role": "user", "content": body}]
    r = n.chat(MODEL_PLANNER, msgs, temperature=0.2, max_tokens=2000,
               reasoning_effort="none")
    txt = n.text(r)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise RuntimeError(f"統合JSONが取れません: {txt[:300]}")
    return json.loads(m.group(0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", help="カンマ区切りの動画ID（既定は3本）")
    args = ap.parse_args()

    if args.videos:
        ids = [v.strip() for v in args.videos.split(",") if v.strip()]
        videos = {i: DEFAULT_VIDEOS.get(i, (0.0, "")) for i in ids}
    else:
        videos = DEFAULT_VIDEOS

    n = Nebius()
    parts, durations = [], []
    for vid, (dur, title) in videos.items():
        p = analyze_video(n, vid, dur, title)
        if p:
            parts.append(p)
            durations.append(dur)
    if not parts:
        print("!! 1本も解析できませんでした")
        return

    style = merge(n, parts, durations)
    style["_source"] = {
        "vl_model": MODEL_VL,
        "merge_model": MODEL_PLANNER,
        "videos": list(videos.keys()),
        "measured": {"duration_median_sec": 41.0, "min": 27.8, "max": 65.0,
                     "aspect": "360x640", "fps": 30, "sample": 10},
    }
    OUT.write_text(json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {OUT}")
    print(json.dumps(style, ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
