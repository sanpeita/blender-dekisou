"""録画 + timeline.json から、シリーズの型（9:16・上部テロップ・下部Blender画面）に組む。

    python harness/compose.py out/<slug>

入力:  out/<slug>/record.mp4, timeline.json, ../assets/scripts/<slug>.json
出力:  out/<slug>/final.mp4（音声があれば合成）
      out/<slug>/telop.ass
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
SCREEN_TOP = 980           # Blender画面は下 940px（視認性優先で1/3→1/2に拡大）
SCREEN_H = H - SCREEN_TOP
FONT = "Yu Gothic UI"
ACCENT = "&H00D7F5C8"      # ASS は BGR。ここではシアン系（BBGGRR）


def ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(script: dict, timeline: dict, out: Path) -> Path:
    steps = {s.get("id"): s for s in script.get("steps", [])}
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Alignment 8=上中央 / 5=中央 / 2=下中央。\pos を使うと自動折り返しが
        # 効かなくなりテロップが画面端で切れるので、位置は Style 側で決める。
        f"Style: Title,{FONT},52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,1,0,1,6,3,8,90,90,300,1",
        f"Style: Telop,{FONT},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,1,0,1,6,3,8,90,90,620,1",
        f"Style: Sub,{FONT},44,&H00E8E8E8,&H00FFFFFF,&H00000000,&H80000000,"
        f"0,0,0,0,100,100,0,0,1,4,2,2,90,90,120,1",
        # フック用: BorderStyle=3 で文字の後ろに箱を敷く（型の「無理そう…→できそう!」）
        # BorderStyle=3: OutlineColour が箱の色、BackColour が影。Primary が文字色。
        f"Style: Pain,{FONT},64,&H00FFFFFF,&H00FFFFFF,&H002020C8,&H90000000,"
        f"-1,0,0,0,100,100,1,0,3,18,0,8,120,120,200,1",
        f"Style: Move,{FONT},64,&H00FFFFFF,&H00FFFFFF,&H0020A020,&H90000000,"
        f"-1,0,0,0,100,100,1,0,3,18,0,8,120,120,200,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    # タイトル（フック）を冒頭に
    hook = (script.get("hook") or {})
    title = script.get("title") or ""
    pain = hook.get("pain") or "無理そう…"
    move = hook.get("one_move") or "できそう!"
    # 型の核: 赤い箱「無理そう…」→ 緑の箱「できそう!」を上部の黒帯に出す
    lines.append(f"Dialogue: 0,{ass_time(0.2)},{ass_time(3.0)},Pain,,0,0,0,,"
                 f"{{\\fad(180,180)}}無理そう…")
    lines.append(f"Dialogue: 0,{ass_time(3.0)},{ass_time(6.0)},Move,,0,0,0,,"
                 f"{{\\fad(180,180)}}できそう!")
    if title:
        lines.append(f"Dialogue: 0,{ass_time(6.0)},{ass_time(9.0)},Title,,0,0,0,,"
                     f"{escape(title)}")

    for st in timeline.get("steps", []):
        sid = st.get("id")
        cap = (steps.get(sid) or {}).get("caption")
        if not cap:
            continue
        start, end = st.get("t_start", 0) + 0.25, st.get("t_end", 0)
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(max(end, start + 1.2))},"
                     f"Telop,,0,0,0,,{escape(cap)}")

    closing = script.get("closing") or {}
    if closing.get("caption"):
        last = timeline.get("steps")[-1]["t_end"] if timeline.get("steps") else 10
        lines.append(f"Dialogue: 0,{ass_time(last)},{ass_time(last + 3)},Sub,,0,0,0,,"
                     f"{escape(closing['caption'])}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def escape(s: str) -> str:
    return s.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", " ")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python harness/compose.py out/<slug>")
        return
    work = Path(sys.argv[1])
    tl = json.loads((work / "timeline.json").read_text(encoding="utf-8"))
    slug = work.name
    # 音声合成済みの台本があればそちらを優先（caption は同じ、hold と audio が入っている）
    voiced = work / "script_voiced.json"
    script_path = (voiced if voiced.exists() else
                   ROOT / "assets" / "scripts" / f"{slug}.json")
    script = json.loads(script_path.read_text(encoding="utf-8")) if script_path.exists() else {}

    ass = build_ass(script, tl, work / "telop.ass")
    rec = work / "record.mp4"
    if not rec.exists():
        print("!! record.mp4 がありません")
        return

    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(rec)], capture_output=True, text=True)
    try:
        recorded = float(dur.stdout.strip())
    except ValueError:
        print("!! 尺が読めません")
        return

    # 音声トラックを組む（各工程の開始に合わせて配置）
    steps = {s.get("id"): s for s in script.get("steps", [])}
    audios: list[tuple[Path, float]] = []
    for st in tl.get("steps", []):
        meta = steps.get(st.get("id")) or {}
        a = meta.get("audio")
        if a and Path(a).exists():
            audios.append((Path(a), max(0.0, st.get("t_start", 0) + 0.25)))
    closing = script.get("closing") or {}
    if closing.get("audio") and Path(closing["audio"]).exists() and tl.get("steps"):
        audios.append((Path(closing["audio"]), tl["steps"][-1].get("t_end", 0) + 0.3))

    voiced_end = max([t + 0.5 for _, t in audios], default=0.0)
    last_step_end = tl.get("steps")[-1].get("t_end", 0) if tl.get("steps") else 0
    total = max(recorded, last_step_end + 1.5, voiced_end + 1.0)
    print(f"尺: 録画{recorded:.2f}s → 出力{total:.2f}s / 音声{len(audios)}本")

    # 下1/3に画面、上は暗い背景。テロップは ASS で焼く。映像は音声の尺まで最終フレームで伸ばす。
    fc = (
        f"color=c=0x0E1014:s={W}x{H}:d={total:.2f}[bg];"
        f"[0:v]scale=-2:{SCREEN_H}:flags=lanczos,crop={W}:{SCREEN_H}:(iw-{W})/2:0,"
        f"tpad=stop_mode=clone:stop_duration={max(0.0, total - recorded) + 1:.2f}[s];"
        f"[bg][s]overlay=0:{SCREEN_TOP}:shortest=1[v0];"
        f"[v0]ass={ass.as_posix()}[v]"
    )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(rec)]
    for path, _ in audios:
        cmd += ["-i", str(path)]

    if audios:
        chains = []
        labels = []
        for i, (_, at) in enumerate(audios, start=1):
            ms = int(round(at * 1000))
            chains.append(f"[{i}:a]adelay={ms}:all=1,aresample=48000[a{i}]")
            labels.append(f"[a{i}]")
        mix = "".join(labels) + f"amix=inputs={len(audios)}:normalize=0:dropout_transition=0," \
                                 "loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
        fc = fc + ";" + ";".join(chains) + ";" + mix
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-filter_complex", fc, "-map", "[v]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", str(work / "final.mp4")]
    out = work / "final.mp4"
    print("合成中…")
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        print("!! 合成失敗:", p.stderr.decode("utf-8", "replace")[:600])
        return
    print("出力:", out, out.stat().st_size)


if __name__ == "__main__":
    main()
