"""script.json の narration を Fish Speech で一括合成し、音声の尺に合わせて hold_sec を更新する。

    python harness/tts_all.py assets/scripts/角を丸くする.json

出力:
    out/<slug>/narr/narr_01.wav …（step数ぶん）
    out/<slug>/script_voiced.json（hold_sec を音声長+余白に更新した台本）
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE = ROOT / "voice"
PY = VOICE / ".venv" / "Scripts" / "python.exe"
PAD = 0.45  # 音声の後に置く余白（秒）


def clean(text: str) -> str:
    """Fish Speech は英単語を誤読しやすいので、既知の技術名をカタカナに寄せる。"""
    repl = {
        "Blender": "ブレンダー",
        "blender": "ブレンダー",
        "ベベル": "ベベル",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text).strip()


def duration(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python harness/tts_all.py assets/scripts/<name>.json")
        return
    src = Path(sys.argv[1])
    script = json.loads(src.read_text(encoding="utf-8"))
    slug = src.stem
    work = ROOT / "out" / slug
    narr_dir = work / "narr"
    narr_dir.mkdir(parents=True, exist_ok=True)

    steps = script.get("steps", [])
    lines = [clean(s.get("narration") or s.get("caption") or "") for s in steps]
    if script.get("closing", {}).get("narration"):
        lines.append(clean(script["closing"]["narration"]))

    texts = work / "narr_texts.txt"
    texts.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)}文を合成します（{PY.name} / Fish Speech 1.5）")

    env = dict(os.environ)
    env["HF_HOME"] = str(VOICE / "hf_cache")
    env["HF_HUB_DISABLE_XET"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [str(PY), "run_fish_tts.py",
           "--ref", "ref/ref24k_full.wav", "--ref-text", "ref/ref.txt",
           "--texts", str(texts), "--out-dir", str(narr_dir),
           "--prefix", "narr", "--half"]
    p = subprocess.run(cmd, cwd=str(VOICE), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (p.stdout or "")[-1500:]
    print(tail)
    if p.returncode != 0:
        print("!! 失敗:", (p.stderr or "")[-1200:])
        return

    # 生成されたファイルを step 順に突き合わせる
    files = sorted(narr_dir.glob("narr_*.wav"))
    if not files:
        print("!! wav がありません")
        return

    updated = 0
    for i, st in enumerate(steps):
        if i >= len(files):
            break
        d = duration(files[i])
        if d > 0:
            st["audio"] = str(files[i])
            st["audio_sec"] = round(d, 2)
            st["hold_sec"] = round(d + PAD, 2)
            updated += 1
            print(f"  step{st.get('id')}: 音声 {d:.2f}s → hold {st['hold_sec']}s")
    if len(files) > len(steps):
        script.setdefault("closing", {})["audio"] = str(files[len(steps)])
        script["closing"]["audio_sec"] = round(duration(files[len(steps)]), 2)
        print(f"  closing: {script['closing']['audio_sec']}s")

    script["_voice"] = {"engine": "fish-speech-1.5", "ref_sec": 30.0,
                        "pad_sec": PAD, "updated_steps": updated}
    out = work / "script_voiced.json"
    out.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print("保存:", out)


if __name__ == "__main__":
    main()
