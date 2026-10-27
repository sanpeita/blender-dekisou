"""Blender 内で実行する小片（MCP execute_code に渡す文字列）。

生成コードと違い、こちらは検証済みの固定処理だけを置く。
"""

# 選択中オブジェクトを囲むワイヤーフレームのマーカーを出し直す。
# 「どこを見ればいいか」を視聴者に示すためのもので、最終工程の後に消す。
MARK = r'''
import bpy

obj = bpy.context.active_object
for o in list(bpy.data.objects):
    if o.name.startswith("__mark"):
        bpy.data.objects.remove(o, do_unlink=True)

# 編集モードのまま primitive_cube_add を呼ぶと poll() に落ちるので、いったん OBJECT に戻す
prev_mode = obj.mode if obj is not None else 'OBJECT'
if obj is not None and prev_mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

if obj is not None and obj.type == 'MESH':
    bpy.ops.mesh.primitive_cube_add(size=1)
    m = bpy.context.active_object
    m.name = "__mark"
    m.dimensions = tuple(max(0.05, d) * 1.16 for d in obj.dimensions)
    m.location = obj.location
    m.rotation_euler = obj.rotation_euler
    m.display_type = 'WIRE'
    m.show_in_front = True
    m.color = (1.0, 0.42, 0.05, 1.0)
    m.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

if obj is not None and prev_mode == 'EDIT':
    bpy.ops.object.mode_set(mode='EDIT')
print("marked", obj.name if obj else None, "mode", obj.mode if obj else None)
'''

CLEAR_MARK = r'''
import bpy
for o in list(bpy.data.objects):
    if o.name.startswith("__mark"):
        bpy.data.objects.remove(o, do_unlink=True)
print("markers cleared")
'''

# 3Dビューに戻す（コンソールのままだと録画に3Dビューが写らない）
TO_VIEW3D = r'''
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'CONSOLE':
        area.type = 'VIEW_3D'
print([a.type for a in bpy.context.screen.areas])
'''

# 選択対象へ寄ってから寄りを強める
FRAME_SELECTED = r'''
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_selected()
                    r3d = area.spaces[0].region_3d
                    r3d.view_distance = max(3.6, r3d.view_distance * 0.85)
'''

# シーン全体が入るように引く（複数オブジェクトを見せるとき）
VIEW_ALL = r'''
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_all()
                    r3d = area.spaces[0].region_3d
                    r3d.view_distance = max(14.0, r3d.view_distance)
# MCP 経由の変更はビューの再描画が遅れるので明示的に更新する
bpy.context.view_layer.update()
for area in bpy.context.screen.areas:
    area.tag_redraw()
'''

# シーンを空にする
CLEAR_SCENE = r'''
import bpy
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
# select_all + delete は非表示や別コレクションを取りこぼすので、データから直接消す
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)
# 消したあと再描画しないと、録画に前のシーンの絵が残る
bpy.context.view_layer.update()
for area in bpy.context.screen.areas:
    area.tag_redraw()
print("cleared", len(bpy.data.objects))
'''
