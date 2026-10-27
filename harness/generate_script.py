"""theme + style.json → script.json（台本＋工程表）を Ultra で生成し、検証する。

使い方:
    python harness/generate_script.py "角を丸くする"
出力:
    assets/scripts/<slug>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import Nebius, MODEL_PLANNER, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STYLE = ROOT / "assets" / "style.json"
OUTDIR = ROOT / "assets" / "scripts"

BANNED = ["quit_blender", "save_mainfile", "wm.read_homefile", "os.remove",
          "shutil.rmtree", "read_factory_settings"]

SYSTEM = """あなたはVTuber「うのっち」の動画ディレクターです。
シリーズ「Blenderできそう」の台本と操作工程表をJSONだけで書きます。

このシリーズの思想（絶対に守る）:
- Blenderの機能を全部教えるコンテンツではない。
- 初心者が「無理そう」と感じる一点を、今日はここだけ見えればいい、まで近づける。
- 1本につき操作は「1つのこと」だけ。欲張らない。
- 断定しすぎない。「まずは」「ここだけ」「戻れる」という言い方をする。
- 失敗しても戻れることを必ずどこかで伝える。

出力はJSONのみ。前後に説明文を書かない。"""

USER = """テーマ: {theme}

参考にする「型」（実測）:
{style}

次のスキーマでJSONを出力してください。

{{
 "theme": "{theme}",
 "title": "Blenderって無理そう？{{つまずき}}は{{解決の1手}}",
 "duration_target_sec": 35-50の数値,
 "promise": "この1手だけ見えればOKという一言",
 "hook": {{"pain": "初心者がつまずく一点", "one_move": "解決の1手"}},
 "steps": [
   {{
     "id": 1,
     "caption": "18文字以内のテロップ",
     "narration": "読み上げ原稿（40文字以内、話し言葉）",
     "action": {{"kind": "python", "code": "bpyで実行するPython1行〜数行"}},
     "camera": {{"kind": "viewport", "zoom": 1.0}},
     "hold_sec": 3.0,
     "reveal": "この工程で見せるもの1つ"
   }}
 ],
 "closing": {{"caption": "できそう？", "narration": "締めの一言"}}
}}

厳守:
- steps は 4〜7個。8個以上は「全部教える」になるので禁止。
- 各 caption は18文字以内。
- 各 action.code は bpy で実行可能な Python。1ステップ1操作。printは書かない。
- bpy.ops.wm.quit_blender / save_mainfile / ファイル削除 / read_factory_settings は禁止。
- 最後の工程は必ず「元に戻せる」ことを示す（Ctrl+Z 相当、または変更前の状態に戻す手順をnarrationに入れる）。
- Blender 5.2 のAPIで動くコードにする（bpy.ops.mesh.primitive_cube_add など標準APIのみ）。"""


def validate(s: dict) -> list[str]:
    errs = []
    steps = s.get("steps") or []
    if not (4 <= len(steps) <= 7):
        errs.append(f"steps={len(steps)}（4〜7であること）")
    d = s.get("duration_target_sec")
    if not isinstance(d, (int, float)) or not (30 <= d <= 60):
        errs.append(f"duration_target_sec={d}（30〜60）")
    for st in steps:
        cap = st.get("caption") or ""
        if len(cap) > 18:
            errs.append(f"step{st.get('id')} caption {len(cap)}字（18字以内）")
        code = (st.get("action") or {}).get("code") or ""
        if not code.strip():
            errs.append(f"step{st.get('id')} action.code が空")
        for b in BANNED:
            if b in code:
                errs.append(f"step{st.get('id')} 禁止API: {b}")
    if not s.get("closing"):
        errs.append("closing が無い")
    return errs


def slug(text: str) -> str:
    s = re.sub(r"[^\w一-龥ぁ-んァ-ヶー]+", "_", text).strip("_")
    return s[:40] or "script"


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python harness/generate_script.py "テーマ"')
        return
    theme = sys.argv[1]
    load_env()
    style = json.loads(STYLE.read_text(encoding="utf-8"))
    # 大きいキーは落としてトークンを節約
    style_brief = {k: style[k] for k in
                   ("duration_sec", "hook", "pacing", "telop",
                    "operation_visibility", "layout", "tone_notes") if k in style}

    n = Nebius()
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER.format(
                theme=theme,
                style=json.dumps(style_brief, ensure_ascii=False, indent=1))}]
    r = n.chat(MODEL_PLANNER, msgs, temperature=0.7, max_tokens=3000,
               reasoning_effort="none")
    txt = n.text(r)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        print("!! JSONが取れません:\n", txt[:600])
        return
    script = json.loads(m.group(0))

    errs = validate(script)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"{slug(theme)}.json"
    script["_meta"] = {"model": MODEL_PLANNER, "theme": theme,
                       "validation_errors": errs}
    path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"タイトル: {script.get('title')}")
    print(f"尺: {script.get('duration_target_sec')}秒 / steps {len(script.get('steps', []))}")
    for st in script.get("steps", []):
        print(f"  {st.get('id')}. [{len(st.get('caption',''))}字] {st.get('caption')}")
        print(f"      code: {(st.get('action') or {}).get('code','')[:90]}")
    print(f"\n検証: {'OK' if not errs else errs}")
    print(f"保存: {path}")


if __name__ == "__main__":
    main()
