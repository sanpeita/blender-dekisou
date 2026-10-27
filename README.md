# blender-dekisou — turn one theme into a Blender short, automatically

An agent pipeline that takes a single theme line and produces a **vertical 9:16 Blender
short** in the established style of the *"Blenderって無理そう？"* series: a hook, 4–7 single-action
steps performed live in Blender, Japanese narration in the author's own voice, burned-in
captions, and a "you can always undo" close.

Built for **Nebius × NVIDIA Global AI Hackathon 2026 — Best Apps and Agents**
(NVIDIA Nemotron models served by Nebius Token Factory).

**Live demo: <https://unotchi.com/blender-dekisou/>** — plays the two runs below and walks the
recorded timeline step by step (no API key is exposed; the demo is a replay of real runs).

**Demo video: <https://youtu.be/q2eqxVOVD98>** — 37 s, public on the author's channel (1080×1920).
The narration is an AI voice built from 30 s of the author's own recordings, and the description says so.

The design rule: **the LLM never touches the video.** Models plan, write, watch and verify;
ffmpeg and `bpy` do the deterministic work. If a model returns garbage, the tool still
finishes and says so instead of producing a broken file silently.

---

## Measured results (2026-10-27, single RTX 3060 Laptop 6GB)

Both videos below were produced end-to-end by this pipeline — theme in, MP4 out.

| Output | Length | Format | Steps |
|---|---|---|---|
| `角を丸くする` (round the corners: bevel) | **36.0 s** | 1080×1920 / 30 fps / with audio | 6 |
| `物が増えて迷うとき名前をつける` (name things so you stop getting lost) | **33.2 s** | 1080×1920 / 30 fps / with audio | 5 |

Voice cloning (Fish Speech 1.5, zero-shot, 30 s reference):

| Metric | Value |
|---|---|
| Speaker similarity (WavLM x-vector) | **0.944 – 0.966** (no-reference baseline 0.60) |
| ASR round-trip CER (Whisper large-v3-turbo) | **0.0 % / 6.2 % / 0.0 %** (the 6.2 % is notation only) |
| VRAM peak | **2.11 GB** |

Style extraction: duration statistics measured over **10 reference Shorts** (median 41 s,
range 27.8–65.0 s), visual grammar extracted from 3 representative videos.

> Videos and generated artifacts are intentionally **not** committed (`out/`, `*.mp4`).
> The reference Shorts belong to the author's channel and are not redistributed.

---

## Pipeline

```
theme
  │
  ├─ [Super VL]  frames of past episodes → per-video observations
  │              → [Ultra] merge → assets/style.json   (length, layout, caption rules)
  │
  ├─ [Ultra]     style + theme → assets/scripts/<theme>.json
  │              (title, hook, 4–7 steps, caption ≤18 chars, bpy per step)
  │              → validator: step count, caption length, banned APIs
  │
  ├─ [Fish Speech 1.5]  narration → wav per step
  │              → each step's hold_sec is recomputed from the measured audio length
  │
  ├─ [Lightning] writes/fixes the bpy code, executed one step at a time over
  │              the Blender MCP server (localhost) → timeline.json
  │
  ├─ [ffmpeg]    gdigrab of the Blender window rect (real UI, not a render)
  │              → ASS captions + hook cards + audio placed at step starts
  │              → final.mp4 (1080×1920)
  │
  └─ [Super VL]  scores sampled frames; failing steps only are sent back to Ultra
                 (implemented as a schema/prompt path; see "Status")
```

### Model roles are not interchangeable

| Role | Model (actual ID) | Why this one |
|---|---|---|
| Planner / writer | `nvidia/Nemotron-3-Ultra-550b-a55b` | 550B-class reasoning: decides *which single* beginner pain to address and how to frame it |
| Watcher / verifier | `nvidia/Nemotron-3.5-Super-VL` | Sees images and video. Turns past episodes into numbers and checks generated frames for breakage |
| Executor loop | `nvidia/Nemotron-3_5-Lightning` | 30B/A3B speed. Tool-calling loop that runs dozens of times per video |

---

## Quickstart (Windows)

Requirements

- Blender **5.2** + the **MCP for Blender Pro** add-on (HTTP MCP server)
- `ffmpeg` / `ffprobe` on `PATH`
- Python 3.11+ (the harness itself is standard-library only)
- A Nebius Token Factory API key
- For narration only: a local Fish Speech 1.5 checkout in `voice/` (not vendored; setup notes in
  `docs/voice-setup.md`)

```bash
cp .env.example .env          # put NEBIUS_API_KEY in it
python harness/models.py      # 1) verify the three models answer
```

Start the Blender side once per Blender session (Shift+F4 opens the Python console):

```python
exec(open(r"<path-to-repo>/harness/restart_mcp.py").read())
# → RESTART ok= True port 9880 token_required True
```

The script writes the MCP token to `~/.blender_mcp_token` (override with
`BLENDER_MCP_TOKEN_FILE`), so the token never has to be pasted into a chat or a config file.

```bash
python harness/mcp_client.py                       # 2) MCP reachable, list tools
python harness/extract_style.py                    # 3) reference frames → style.json (needs assets/refs)
python harness/generate_script.py "角を丸くする"      # 4) theme → script.json (+ validator)
python harness/tts_all.py "assets/scripts/角を丸くする.json"   # 5) narration + hold_sec sync
python harness/execute.py "out/角を丸くする/script_voiced.json"  # 6) run in Blender + record
python harness/compose.py "out/角を丸くする"          # 7) captions + audio → final.mp4
```

Use a **new, unsaved Blender file** for step 6: the harness clears the scene, and it is
designed to never touch a file you care about.

---

## Engineering notes — what actually broke

Every item below was found by running the thing, not by reading docs. They are the reason
the pipeline is structured the way it is.

| # | Trap | Fix |
|---|---|---|
| 1 | `reasoning_effort` unset → **empty `content`** (thinking tokens consume `max_tokens`) | pass `reasoning_effort="none"` explicitly |
| 2 | Super VL's catalog name is not its model ID | query `GET /v1/models`; the ID is `nvidia/Nemotron-3.5-Super-VL` |
| 3 | One prompt accepts at most **8 images** | summarise per video, then merge with a text model |
| 4 | `bpy.context.active_operator.segments = 8` raises instead of changing the bevel | pass `segments=` to the operator call |
| 5 | `viewport_screenshot` returns a **camera render** — no UI, no viewport | `ffmpeg -f gdigrab` cropped to the window rect from `GetWindowRect` |
| 6 | Recording captured the **Python console** because Shift+F4 leaves the area in CONSOLE | switch every area back to `VIEW_3D` before recording |
| 7 | Scene clear did not repaint before capture → previous frame recorded | `tag_redraw()` + settle delay (still the source of the open issue below) |
| 8 | MCP add-on: `stop()` then immediate `start()` leaves **two LISTEN sockets on the same port** (`SO_REUSEADDR`), so connections hang | force `_server=None` / `_thread=None`, then bind a different port (9880) |
| 9 | ASS `BorderStyle=3`: the box colour is **OutlineColour**, not BackColour | set the outline colour for hook cards (otherwise a white empty box) |
| 10 | `\pos` in ASS kills auto-wrap; long captions get clipped at the frame edge | position via Style (alignment + margins) |
| 11 | Fish Speech mispronounces English tokens ("Blender" → "レッツ、ゲンダー") | katakana normalisation before synthesis |
| 12 | Sampling variance is large (dropped mora, wrong F0, ~526 Hz spikes) | best-of-3 per sentence + automatic gates (CER / F0 / pauses) |
| 13 | Captions and narration drifted apart | derive `hold_sec` from the measured wav length, not from the estimate |

---

## Status (honest)

Working, measured on real runs:

- style extraction, script generation + validator, voice cloning + gates, step execution over
  MCP including a **real failure the pipeline had to detect and fix** (trap 4), window
  recording, caption/audio composition to 1080×1920
- two finished videos, produced by the same pipeline with different themes

Open / not done:

- **Avatar zone**: the series' upper area holds the VTuber avatar. Cropping it out of existing
  videos was unusable (captions and UI overlap), so the upper zone currently carries the
  red→green hook cards instead. Needs a clean VRM / transparent bust-up asset.
- **Second video's reveal**: the "three cubes on screen" beat is visible in a direct screenshot
  but not reliably in the recording — a redraw/record timing issue (trap 7). The second video
  still demonstrates end-to-end generality; this one beat is unresolved.
- **Verifier loop** exists as schema + prompt path; the automatic "score frames → retry only
  failing steps" round-trip has not been exercised on a full run.
- The demo video is public for judging. Whether the series continues to publish AI-generated
  cuts as regular episodes is a separate editorial decision for the channel owner.
- Windows-only capture path (`gdigrab`); Japanese captions only (Yu Gothic UI).

---

## Repository layout

```
harness/
  models.py             Nebius client (stdlib only, reads .env)
  mcp_client.py         minimal MCP JSON-RPC client (streamable HTTP, SSE)
  extract_style.py      reference frames → style.json (Super VL → Ultra)
  style_from_frames.py  per-video observation helper
  generate_script.py    theme → script.json + validator
  tts_all.py            narration (Fish Speech) + hold_sec sync
  execute.py            run steps over MCP + record the window
  compose.py            ASS captions + audio → final.mp4
  bpy_snippets.py       deterministic scene helpers (clear, frame selected, highlight)
  restart_mcp.py        one-liner to (re)start the MCP server inside Blender
  plan_schema.md        style.json / script.json schema and constraints
assets/
  style.json            the extracted "type" (committed)
  scripts/*.json        generated scripts for the two demo videos (committed)
docs/
  voice-setup.md        reproducible Fish Speech 1.5 setup and measurement loop
web/                    hosted demo (static, no build step) — published via gh-pages
```

## License

MIT — see `LICENSE`. Third-party pieces are **not** vendored: the Blender add-on, Fish Speech
and the Nemotron models are installed or accessed separately under their own terms.

---

## 日本語メモ

- テーマ1行 → 「Blenderできそう」型の縦型ショート（36.0秒 / 33.2秒の2本を実生成）。
- 3モデルの役割は固定：Ultra＝企画・台本、Super VL＝型の抽出と検証、Lightning＝工程の実行ループ。
- 録画・編集・音声は決定論的処理（ffmpeg / bpy）。LLMに映像を作らせない。
- 音声は Fish Speech 1.5 の zero-shot（参照30秒、話者類似度 0.94–0.97、VRAM 2.1GB）。
- 未解決：上部のアバターゾーン（素材待ち）、2本目の「3つ並べる」見せ場、検証ループの実運用。
