"""script.json の工程表を Blender MCP で実行し、画面を録画して timeline.json を残す。

    python harness/execute.py assets/scripts/角を丸くする.json

前提:
  - Blender が起動していて MCP サーバが立っている（.env の BLENDER_MCP_URL / TOKEN）
  - 実行前に **新規ファイル** を開いておく（既存の作業を壊さないため）
出力:
  out/<slug>/record.mp4      画面録画（Blenderウィンドウのクロップ）
  out/<slug>/timeline.json   各工程の開始/終了時刻
  out/<slug>/steps/step_XX.png  各工程直後のフレーム
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import BlenderMCP, resolve_token  # noqa: E402
from bpy_snippets import (CLEAR_MARK, CLEAR_SCENE, FRAME_SELECTED, MARK,  # noqa: E402
                          TO_VIEW3D, VIEW_ALL)
from models import load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
PS = ROOT / "harness" / "blender_focus.ps1"


def focus_and_rect() -> tuple[int, int, int, int] | None:
    """Blender を最前面にし、(x, y, w, h) を返す。"""
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", str(PS)], capture_output=True, timeout=60)
        out = p.stdout.decode("utf-8", "replace")
        m = re.search(r"RECT (-?\d+) (-?\d+) (\d+) (\d+)", out)
        if not m:
            print("!! ウィンドウ矩形が取れません:", out.strip()[:120])
            return None
        x, y, w, h = (int(v) for v in m.groups())
        # 画面外・負座標をクランプ（gdigrab の crop は 0 以上）
        x, y = max(0, x), max(0, y)
        w -= w % 2
        h -= h % 2
        return x, y, w, h
    except Exception as e:
        print("!! focus 失敗:", e)
        return None


def start_recording(path: Path, rect: tuple[int, int, int, int], fps: int = 30) -> subprocess.Popen:
    x, y, w, h = rect
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "gdigrab", "-framerate", str(fps), "-i", "desktop",
           "-vf", f"crop={w}:{h}:{x}:{y}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", str(path)]
    print("録画開始:", " ".join(cmd[-1:]))
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)


def stop_recording(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def grab_frame(video: Path, at: float, dest: Path) -> bool:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{max(0.0, at):.2f}", "-i", str(video), "-frames:v", "1", str(dest)]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and dest.exists()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python harness/execute.py assets/scripts/<name>.json")
        return
    load_env()
    script_path = Path(sys.argv[1])
    script = json.loads(script_path.read_text(encoding="utf-8"))
    # out/<slug>/script_voiced.json を渡された場合は <slug> を出力先にする
    slug = (script_path.parent.name if script_path.stem == "script_voiced"
            else script_path.stem)
    work = OUT / slug
    (work / "steps").mkdir(parents=True, exist_ok=True)

    url = os.environ.get("BLENDER_MCP_URL", "http://127.0.0.1:9880/mcp")
    token = resolve_token()
    b = BlenderMCP(url, token=token)
    b.initialize()
    print("MCP接続:", url, "tools:", len(b.tool_names()))

    # コンソールのままだと録画に3Dビューが写らないので、3Dビューに戻しておく
    try:
        b.call("execute_code", {"code": TO_VIEW3D})
    except Exception as e:
        print("!! 3Dビュー切替失敗:", e)

    # 前回の残骸を消してから始める（このプロジェクト専用の未保存シーン前提）
    try:
        b.call("execute_code", {"code": CLEAR_SCENE})
    except Exception as e:
        print("!! クリア失敗:", e)

    info = b.call("get_scene_info", {})
    print("実行前シーン:", info.get("object_count"), "objects /", info.get("engine"))
    if info.get("object_count", 0) > 3:
        print("!! 既存オブジェクトが多い。新規ファイルで実行するのが望ましい（続行）")

    rect = focus_and_rect()
    if not rect:
        print("!! 録画できないため中止")
        return
    print("矩形:", rect)
    time.sleep(1.0)

    rec_path = work / "record.mp4"
    time.sleep(1.2)  # クリア後の再描画が反映されるのを待つ
    rec = start_recording(rec_path, rect)
    t0 = time.time()
    timeline = {"script": script_path.name, "rect": rect, "fps": 30, "steps": []}
    time.sleep(0.6)

    ok = True
    for step in script.get("steps", []):
        sid = step.get("id")
        code = (step.get("action") or {}).get("code") or ""
        hold = float(step.get("hold_sec") or 3.0)
        t_start = time.time() - t0
        try:
            res = b.call("execute_code", {"code": code})
            out = res.get("output", "") if isinstance(res, dict) else str(res)
        except Exception as e:
            print(f"  step{sid} !! {e}")
            ok = False
            timeline["steps"].append({"id": sid, "error": str(e), "t_start": t_start})
            break
        # 変化が見えるように、工程ごとに選択対象へ寄せてハイライト枠を出す
        try:
            b.call("execute_code", {"code": MARK})
            b.call("execute_code",
                   {"code": VIEW_ALL if step.get("view") == "all" else FRAME_SELECTED})
        except Exception:
            pass
        time.sleep(max(0.8, hold))
        t_end = time.time() - t0
        print(f"  step{sid} ok ({hold}s) out={str(out)[:40]!r}")
        timeline["steps"].append({"id": sid, "t_start": round(t_start, 2),
                                  "t_end": round(t_end, 2), "hold": hold,
                                  "output": str(out)[:300], "frame": None})

    stop_recording(rec)
    time.sleep(0.5)
    # 録画ファイルが確定してから各工程のフレームを抜く
    for item in timeline["steps"]:
        if "t_end" not in item:
            continue
        snap = work / "steps" / f"step_{item['id']:02d}.png"
        if grab_frame(rec_path, item["t_end"] - 0.3, snap):
            item["frame"] = str(snap)
    try:
        b.call("execute_code", {"code": CLEAR_MARK})
    except Exception:
        pass
    final = b.call("get_scene_info", {})
    timeline["result_scene"] = {k: final.get(k) for k in
                                ("object_count", "active_object", "engine", "frame_current")}
    timeline["ok"] = ok
    (work / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print("\n実行後シーン:", timeline["result_scene"])
    print("録画:", rec_path, rec_path.stat().st_size if rec_path.exists() else "無し")
    print("timeline:", work / "timeline.json")


if __name__ == "__main__":
    main()
