"""Nebius Token Factory の3モデルを役割分担で呼ぶ薄いラッパ。

  MODEL_PLANNER = nvidia/Nemotron-3-Ultra-550b-a55b     企画・台本・工程表
  MODEL_VL      = nvidia/nemotron-3.5-super-vl-120b-a12b 動画/画像の理解・検証
  MODEL_FAST    = nvidia/Nemotron-3_5-Lightning          高速ループ（ツール呼び出し）

依存ゼロ（stdlib のみ）。.env を自前で読む。
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://api.tokenfactory.nebius.com/v1/"

MODEL_PLANNER = os.environ.get("MODEL_PLANNER", "nvidia/Nemotron-3-Ultra-550b-a55b")
MODEL_VL = os.environ.get("MODEL_VL", "nvidia/Nemotron-3.5-Super-VL")
MODEL_FAST = os.environ.get("MODEL_FAST", "nvidia/Nemotron-3_5-Lightning")


def load_env(path: Path | str = ROOT / ".env") -> None:
    """KEY=VALUE を os.environ に流し込む（既存の環境変数は尊重）。"""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class NebiusError(RuntimeError):
    pass


def _post(url: str, payload: dict, key: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST")
    backoff = 2.0
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(backoff); backoff *= 2; continue
            raise NebiusError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(backoff); backoff *= 2; continue
            raise NebiusError(f"接続失敗: {e.reason}") from e
    raise NebiusError("リトライ上限")


class Nebius:
    def __init__(self, key: str | None = None, base: str | None = None):
        load_env()
        self.key = key or os.environ.get("NEBIUS_API_KEY", "")
        self.base = (base or os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE)).rstrip("/")
        if not self.key:
            raise NebiusError("NEBIUS_API_KEY がありません（.env を確認）")

    def chat(self, model: str, messages: list[dict], *, temperature: float = 0.4,
             max_tokens: int = 4096, tools: list | None = None,
             reasoning_effort: str | None = None, timeout: int = 300) -> dict:
        payload: dict = {"model": model, "messages": messages,
                         "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return _post(self.base + "/chat/completions", payload, self.key, timeout)

    @staticmethod
    def text(resp: dict) -> str:
        try:
            return resp["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError) as e:
            raise NebiusError(f"想定外の応答: {json.dumps(resp)[:400]}") from e

    def models(self) -> list[str]:
        req = urllib.request.Request(self.base + "/models",
                                     headers={"Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return [m["id"] for m in json.loads(r.read().decode("utf-8")).get("data", [])]


def image_part(path: Path | str) -> dict:
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    suffix = Path(path).suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def frames_messages(system: str, user: str, frames: list[Path | str]) -> list[dict]:
    """フレーム画像群を1メッセージにまとめる（SuperVL 用）。"""
    content: list[dict] = [{"type": "text", "text": user}]
    content += [image_part(f) for f in frames]
    return [{"role": "system", "content": system},
            {"role": "user", "content": content}]


if __name__ == "__main__":
    n = Nebius()
    print("models:", [m for m in n.models() if "nemotron" in m.lower()][:20])
    for label, mid in (("PLANNER", MODEL_PLANNER), ("VL", MODEL_VL), ("FAST", MODEL_FAST)):
        try:
            r = n.chat(mid, [{"role": "user", "content": "1+1=? 数字だけ"}], max_tokens=16)
            print(f"{label:8s} {mid:45s} -> {n.text(r).strip()[:40]!r}")
        except Exception as e:
            print(f"{label:8s} {mid:45s} !! {e}")
