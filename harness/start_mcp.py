# Blender の Python コンソールで実行する（Shift+F4）
#   exec(open(r"<path-to-repo>/harness/start_mcp.py").read())
#
# 注意: exec(open(...).read()) では __file__ が定義されないため、
# トークンの置き場は環境変数 BLENDER_MCP_TOKEN_FILE、無ければ ~/.blender_mcp_token。
import os
import time
import bpy
from bl_ext.user_default.mcp_for_blender_pro import mcp_server

ADDON = "bl_ext.user_default.mcp_for_blender_pro"
prefs = bpy.context.preferences.addons[ADDON].preferences

# トークンはファイルへ（チャットや画面に出さない）
TOKEN_FILE = os.environ.get("BLENDER_MCP_TOKEN_FILE") or os.path.join(
    os.path.expanduser("~"), ".blender_mcp_token")
try:
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(prefs.mcp_token or "")
    print("token file:", TOKEN_FILE)
except Exception as exc:
    print("token write failed:", exc)

# stop() 直後の start() は TIME_WAIT で bind に失敗して無音で死ぬ。間を空ける。
try:
    mcp_server.stop()
    time.sleep(2.0)
except Exception as exc:
    print("stop skipped:", exc)

for attempt in range(3):
    try:
        mcp_server.start()
        break
    except OSError as exc:
        print("start retry", attempt + 1, exc)
        mcp_server.stop()
        time.sleep(2.0)

print("MCP listening:", bool(mcp_server._server), "port", prefs.mcp_port,
      "require_token", prefs.mcp_require_token)
