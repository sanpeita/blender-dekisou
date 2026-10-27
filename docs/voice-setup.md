# Voice setup — Fish Speech 1.5 zero-shot (reproducible)

Paths below use `<repo>` for a local checkout (the reference machine was `D:/ToolProjects/blender-dekisou` on Windows 11). The reference wav itself is not redistributed — use ~30 s of clean speech of your own.

---

# うのっち 声クローン（Fish Speech 1.5 zero-shot）

参照音声 `assets/voice_ref/ref_30s.wav`（実体は 192kHz/24bit/モノラル 30.0s）から
日本語の zero-shot 音声クローンをローカル（RTX 3060 Laptop 6GB）で実行した記録。

## 結論

- エンジン: **Fish Speech 1.5**（`fishaudio/fish-speech` tag `v1.5.0` / commit `7902e40`, 重み `fishaudio/fish-speech-1.5`）
- 0.5B Dual-AR, fp16, **VRAMピーク 2.11GB**（6GBで余裕）
- 日本語は破綻せず、声質も本人に近い（WavLM x-vector コサイン 0.944–0.966 / 参照なし生成の基準値 0.600）
- 生成速度は約 2.5–3 token/s ≒ 実時間の 7–10倍遅い（8秒の音声に 60–90秒）

## 環境構築（再現手順）

```bash
cd <repo>/voice
uv venv --python 3.11 .venv

# torch は cu124 ホイールを明示（PyPI既定はCPU版）
uv pip install --python .venv/Scripts/python.exe "torch==2.5.1" "torchaudio==2.5.1" \
  --index-url https://download.pytorch.org/whl/cu124

# fish-speech の依存のうち推論に必要な最小集合（funasr/kui/gradio/pyaudio は不要）
uv pip install --python .venv/Scripts/python.exe \
  "numpy==1.26.4" "transformers==4.46.3" "tokenizers==0.20.3" \
  hydra-core omegaconf loguru tqdm click soundfile pydub "pydantic==2.9.2" \
  cachetools ormsgpack zstandard tiktoken "vector_quantize_pytorch==1.14.24" \
  "einx==0.2.2" resampy natsort rich pyrootutils lightning protobuf loralib

# 検証用ツール
uv pip install --python .venv/Scripts/python.exe faster-whisper pykakasi librosa lazy_loader soxr audioread

git clone --depth 1 --branch v1.5.0 https://github.com/fishaudio/fish-speech.git

# 重み（model.pth 1.28GB + firefly VQGAN 188MB + tokenizer）
hf download fishaudio/fish-speech-1.5 \
  --local-dir <repo>/voice/ckpt/fish-speech-1.5
```

### 必須の環境変数（この2つを忘れると失敗する）

```bash
export HF_HOME=<repo>/voice/hf_cache   # 既定の ~/.cache はサンドボックスで書けない
export PATH="<repo>/voice/.venv/Lib/site-packages/torch/lib:$PATH"
```

## 実行

```bash
# 参照音声を24kに変換（元は192kHz）
ffmpeg -y -i ../assets/voice_ref/ref_30s.wav -ac 1 -ar 24000 -c:a pcm_s16le ref/ref24k_full.wav

# 参照音声の書き起こし（プロンプトテキストに使用。ref/ref.txt に保存済み）
.venv/Scripts/python.exe transcribe_ref.py ref/ref24k_full.wav large-v3-turbo

# 3文を生成（1文あたり3候補 = best-of-3）
.venv/Scripts/python.exe run_fish_tts.py \
  --ref ref/ref24k_full.wav --ref-text ref/ref.txt --texts texts_v2.txt \
  --out-dir ../out --prefix cand --half --num-samples 3 --seed 100

# 候補をASR復唱・話者類似度・F0・ポーズで採点して最良を voice_test_N.wav にコピー
.venv/Scripts/python.exe select_best.py

# 物理検証
.venv/Scripts/python.exe verify_wav.py ../out/voice_test_1.wav ../out/voice_test_2.wav ../out/voice_test_3.wav
.venv/Scripts/python.exe prosody_check.py ../out/voice_test_*.wav
.venv/Scripts/python.exe gap_check.py ../out/voice_test_*.wav
```

## 結果（最終成果物）

| file | 長さ | SR | peak | RMS | 話者類似度 | ASR復唱CER | F0中央値 / 抑揚(IQR) |
|---|---|---|---|---|---|---|---|
| `out/voice_test_1.wav` | 6.97s | 44.1kHz mono | -2.8 dBFS | -23.5 dBFS | 0.966 | 0.0% | 118.6Hz / 2.8st |
| `out/voice_test_2.wav` | 6.18s | 44.1kHz mono | -3.5 dBFS | -23.7 dBFS | 0.958 | 6.2% | 121.4Hz / 5.1st |
| `out/voice_test_3.wav` | 5.06s | 44.1kHz mono | -2.2 dBFS | -22.6 dBFS | 0.944 | 0.0% | 127.1Hz / 5.5st |
| 参照 (30s) | 30.0s | 24kHz mono | — | — | 1.000 | — | 132.4Hz / 5.8st |

ASR 復唱（whisper large-v3-turbo, ja）:

- 1: 「こんにちはウノッチーです。今日はブレンダーでここだけ触ってみましょう。」→ 一致
- 2: 「難しそうに見えますがまずは1個だけ覚えれば大丈夫です。」→ 一致（表記ゆれのみ）
- 3: 「できそうって思えたら、それはもう半分できています。」→ 一致

## 品質の正直な評価

**総合: 良（実用水準）。ただし「完璧な本人」ではない。**

良い点
- 3文とも日本語として崩れておらず、内容は一字レベルで復唱一致（促音・長音含む）
- 声質は本人に近い（類似度 0.94–0.97、参照なし生成 0.60 との差が明確）
- ノイズ・クリップ・欠落なし（clip 0.00%）

不自然な点
1. **抑揚がやや平板**。文1の IQR は 2.8 半音で参照 5.8 半音の半分。文2・3は 5.1–5.5 と自然。
2. **英語表記の混在に弱い**。「Blender」をそのまま渡すと「レッツ、ゲンダー」と誤読した（v1 で実測）。
   → カタカナ「ブレンダー」に正規化して解決。**英単語は必ずカナ化すること。**
3. **サンプリング揺らぎが大きい**。同じ文でもシード次第で
   - 文1: 語頭の一文が丸ごと落ちる / 「うのうち」になる / 完璧
   - 文3: 促音「っ」が落ちる / 完璧
   - 文2: F0 p90 が 526Hz（甲高い squeak）になる候補があった
   → 単発生成は危険。**best-of-3 + 自動ゲート（CER・F0・ポーズ）が必須。**
4. 参照を 30s → 14s に短縮すると品質が明確に悪化（文1が「ではアウトネタで…」と崩壊）。
   → 参照は長め（30s）が安定。ただしリファレンスが雑音/ポーズ多めだと平板化する。

聴感での最終確認は未実施（このエージェントは音を再生できない）。上記はすべて
ASR復唱・話者埋め込み・F0・ポーズ長・音量の客観指標にもとづく評価。

## 詰まった点と回避策

| 症状 | 原因 | 回避策 |
|---|---|---|
| `PermissionError: [WinError 5] ...\.cache\huggingface` | ホームのキャッシュに書けない | `HF_HOME` をワークスペース内に |
| `OSError: [Errno 22] Invalid argument` → `RuntimeError: Invalid string length in model.bin` | HF xet バックエンドの書き込み不具合（壊れた部分DL） | `HF_HUB_DISABLE_XET=1`、壊れたキャッシュを削除して再DL |
| `Library cublas64_12.dll is not found`（ctranslate2/faster-whisper） | torch 同梱の CUDA DLL に PATH が通っていない | `PATH=.venv/Lib/site-packages/torch/lib:$PATH` |
| `ModuleNotFoundError: loralib` | 推論でも LoRA モジュールを import する | `uv pip install loralib` |
| `json.load` が `UnicodeDecodeError`（config.json 読込） | `BaseTransformer.from_pretrained` は **ディレクトリ** を受ける（model.pth ではない） | `--ckpt ckpt/fish-speech-1.5`（ディレクトリ）を渡す |
| `speechbrain` 導入で torch が CPU版 2.14 に置換され `device=cpu` に落ちた | speechbrain の依存解決が torch を上書き | 話者類似度は transformers の `microsoft/wavlm-base-plus-sv` を使用（追加依存なし）。追加パッケージ導入後は必ず `torch==2.5.1+cu124` を再固定 |
| 参照なし生成が `max_new_tokens` まで走り続ける | 参照プロンプト無しだと `<|im_end>` が出ない | 参照は必ず与える（ベースライン用途のみ許容） |

## ファイル

- `run_fish_tts.py` — 推論ドライバ（参照エンコード→生成→VQGANデコード、best-of-N対応）
- `select_best.py` — 候補の自動採点・選抜（CER / 話者類似度 / F0 / ポーズ）
- `verify_wav.py` — ffprobe + 波形統計（長さ・peak・RMS・無音率・クリップ）
- `prosody_check.py` — F0（pyin）と音量の統計
- `gap_check.py` — 内部ポーズ検出（脱落・不自然な間）
- `speaker_sim_wavlm.py` — WavLM x-vector による話者類似度
- `asr_check2.py` / `select_best.py` — ASR復唱とCER（かな正規化）
- `ref/ref24k_full.wav`, `ref/ref.txt` — 参照音声とその書き起こし（プロンプト用）
- `out/voice_test_{1,2,3}.wav` — 最終成果物
- `out/cand_{1,2,3}_s{0,1,2}.wav`, `out/candidates_scores.json` — 全候補と採点ログ
