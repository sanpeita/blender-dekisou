"""SuperVL に過去回のフレームを見せて「型」をJSONで抽出させる。

使い方:
    python harness/extract_style.py
出力:
    assets/style.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import Nebius, MODEL_VL, frames_messages  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "assets" / "frames"
OUT = ROOT / "assets" / "style.json"

VIDEOS = [
    ("ZqXTGcICMFA", 40.3, "背景ボケは主役を決めればOK"),
    ("g7Y-mSuVeQU", 46.1, "レンダーは見たいところだけ試せる"),
    ("KsgvL4SW4u4", 30.5, "色を見るならマテリアルプレビュー"),
]

SYSTEM = """あなたは映像ディレクターです。与えられた連続フレームから、
ショート動画シリーズの「型」を観察してJSONだけで答えます。
推測で埋めず、フレームから実際に確認できることだけを書いてください。
数値は秒・文字数・枚数の実数で。"""

USER_TMPL = """以下は同じシリーズ「Blenderできそう」の3本の動画から、時系列で等間隔に抜いたフレームです。
1本あたり4〜6枚。縦型ショート（360x640, 30fps）。

{video_sections}

この3本に共通する「型」を、次のJSONスキーマで出力してください。
値は必ずフレームから観察できる範囲で。不明な項目は null。

{{
  "hook": {{"first_caption_within_sec": number|null, "pain_is_stated_as_question": bool, "template": string|null}},
  "telop": {{"cards_per_video": number|null, "chars_per_card_max": number|null, "position": string, "has_outline_or_shadow": bool}},
  "operation_visibility": {{"cursor_or_highlight_visible": bool, "ui_panels_visible": bool, "zoom_ins": number|null, "screen_is_mostly_ui": bool}},
  "visual_style": {{"background": string, "avatar_present": bool, "color_accent": string}},
  "pacing": {{"cuts_or_state_changes": number|null, "text_changes_fast": bool}},
  "tone_notes": string
}}"""


def section(vid: str, dur: float, title: str, files: list[Path]) -> str:
    head = (f"### 動画 {vid}（{dur}秒）テーマ: {title} — "
            f"時系列で{len(files)}枚\n")
    return head


def main() -> None:
    n = Nebius()
    content: list[dict] = []
    sections: list[str] = []
    for vid, dur, title in VIDEOS:
        files = sorted((FRAMES / vid).glob("*.jpg"))
        if not files:
            print(f"[skip] {vid}: フレームなし")
            continue
        sections.append(section(vid, dur, title, files))
    text = USER_TMPL.format(video_sections="\n".join(sections))
    content.append({"type": "text", "text": text})

    # 画像はセクション見出しの直後に並べる（モデルが対応づけやすい）
    for vid, dur, title in VIDEOS:
        files = sorted((FRAMES / vid).glob("*.jpg"))
        if not files:
            continue
        content.append({"type": "text", "text": f"[{vid} のフレーム {len(files)}枚]"})
        for f in files:
            import base64
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": content}]
    print(f"送信: 画像 {len(content) - 1 - len(VIDEOS)} 枚相当, 要素 {len(content)}")
    r = n.chat(MODEL_VL, msgs, temperature=0.2, max_tokens=2048,
               reasoning_effort="low")
    txt = n.text(r)
    print("---- raw ----")
    print(txt[:2500])
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        print("!! JSONが見つかりません")
        return
    try:
        style = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print("!! JSONパース失敗:", e)
        return
    style["_source"] = {"model": MODEL_VL, "videos": [v[0] for v in VIDEOS],
                        "measured": {"duration_median_sec": 41.0, "min": 27.8,
                                     "max": 65.0, "aspect": "360x640", "fps": 30}}
    OUT.write_text(json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {OUT}")


if __name__ == "__main__":
    main()
