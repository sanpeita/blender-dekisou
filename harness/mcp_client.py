"""Blender MCP (MCP for Blender Pro) への最小クライアント。

依存ゼロ（stdlib のみ）。Streamable HTTP transport を直に喋る。
  POST http://127.0.0.1:9880/mcp   Content-Type: application/json
  Accept: application/json, text/event-stream

使い方:
    from mcp_client import BlenderMCP
    b = BlenderMCP()
    b.initialize()
    print(b.tools())
    print(b.call("get_scene_info", {}))
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

DEFAULT_URL = "http://127.0.0.1:9880/mcp"
PROTOCOL = "2025-06-18"


def resolve_token() -> str | None:
    """MCP のトークンを BLENDER_MCP_TOKEN → BLENDER_MCP_TOKEN_FILE → ~/.blender_mcp_token の順で探す。"""
    tok = os.environ.get("BLENDER_MCP_TOKEN")
    if tok:
        return tok
    path = os.environ.get("BLENDER_MCP_TOKEN_FILE") or os.path.join(
        os.path.expanduser("~"), ".blender_mcp_token")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


class MCPError(RuntimeError):
    pass


class BlenderMCP:
    def __init__(self, url: str = DEFAULT_URL, timeout: int = 300, token: str | None = None):
        self.url = url
        self.timeout = timeout
        self.token = token
        self.session_id: str | None = None
        self._id = 0

    # ---- transport -------------------------------------------------
    def _post(self, payload: dict) -> dict | None:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", "replace")
                ctype = (resp.headers.get("Content-Type") or "").lower()
        except urllib.error.HTTPError as e:
            raise MCPError(f"HTTP {e.code}: {e.read()[:400]!r}") from e
        except urllib.error.URLError as e:
            raise MCPError(f"接続できません ({self.url}): {e.reason}") from e

        if not raw.strip():
            return None  # notification への応答
        if "text/event-stream" in ctype:
            return self._parse_sse(raw)
        return json.loads(raw)

    @staticmethod
    def _parse_sse(raw: str) -> dict:
        for line in raw.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    return json.loads(data)
        raise MCPError(f"SSE に data 行がありません: {raw[:300]!r}")

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        resp = self._post({"jsonrpc": "2.0", "id": self._id, "method": method,
                           "params": params or {}})
        if resp is None:
            raise MCPError(f"{method}: 応答が空です")
        if "error" in resp:
            raise MCPError(f"{method}: {resp['error']}")
        return resp.get("result", {})

    # ---- API -------------------------------------------------------
    def initialize(self, client_name: str = "dekisou-harness") -> dict:
        res = self._rpc("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": "0.1.0"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return res

    def tools(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def tool_names(self) -> list[str]:
        return [t.get("name", "") for t in self.tools()]

    def call(self, name: str, arguments: dict | None = None) -> dict:
        """ツールを実行し、テキスト/JSON の中身を返す。"""
        res = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if res.get("isError"):
            raise MCPError(f"{name} がエラーを返しました: {res}")
        return self._unwrap(res)

    @staticmethod
    def _unwrap(res: dict):
        content = res.get("content") or []
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        if not texts:
            return res
        joined = "\n".join(texts)
        try:
            return json.loads(joined)
        except json.JSONDecodeError:
            return joined


if __name__ == "__main__":
    from models import load_env
    import os
    load_env()
    b = BlenderMCP(
        url=os.environ.get("BLENDER_MCP_URL", DEFAULT_URL),
        token=resolve_token())
    print("initialize:", b.initialize())
    names = b.tool_names()
    print(f"tools ({len(names)}):")
    for n in names:
        print("  -", n)
    print("scene:", b.call("get_scene_info", {}))
