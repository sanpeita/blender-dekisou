# Blender の Python コンソールで実行（Shift+F4）
#   exec(open(r"<path-to-repo>/harness/restart_mcp.py").read())
# 死んだサーバのスレッドを握り続けると再起動できないので、状態を強制リセットしてから立て直す。
#
# ポートは環境変数 BLENDER_MCP_PORT（既定 9880）。
# トークンは BLENDER_MCP_TOKEN_FILE、無ければ ~/.blender_mcp_token に書く（値は画面に出さない）。
import os
import time
import secrets
import bpy
from bl_ext.user_default.mcp_for_blender_pro import mcp_server as m

ADDON = "bl_ext.user_default.mcp_for_blender_pro"
prefs = bpy.context.preferences.addons[ADDON].preferences
# 9876 はこのアドオンで stop()→start() を繰り返すと同一ポートに LISTEN が二重に残るため移す
NEW_PORT = int(os.environ.get("BLENDER_MCP_PORT", "9880"))

TOKEN_FILE = os.environ.get("BLENDER_MCP_TOKEN_FILE") or os.path.join(
    os.path.expanduser("~"), ".blender_mcp_token")

# トークンは毎回作り直す（古い値を無効化するため）
prefs.mcp_token = secrets.token_urlsafe(24)

try:
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(prefs.mcp_token or "")
    print("token file:", TOKEN_FILE)
except Exception as exc:
    print("token write failed:", exc)

# 既存サーバを閉じる（失敗しても続行）
try:
    if m._server is not None:
        try:
            m._server.shutdown()
        except Exception:
            pass
        m._server.server_close()
except Exception as exc:
    print("close:", exc)
m._server = None
m._thread = None
time.sleep(1.5)

prefs.mcp_port = NEW_PORT
time.sleep(0.5)

ok = False
for attempt in range(3):
    try:
        m.start()
        ok = bool(m._server)
        break
    except Exception as exc:
        print("start retry", attempt + 1, type(exc).__name__, exc)
        m._server = None
        m._thread = None
        time.sleep(2.0)

print("RESTART ok=", ok, "port", prefs.mcp_port, "token_required", prefs.mcp_require_token)
