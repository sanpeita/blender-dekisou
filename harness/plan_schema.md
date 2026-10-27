# script.json / style.json スキーマ

Ultra が出す台本と、SuperVL が出す型。どちらも JSON のみ（前後に文章を書かせない）。

## style.json — SuperVL が過去回から抽出する「型」

```json
{
  "series": "blender-dekisou",
  "sample_count": 10,
  "duration_sec": {"median": 42, "min": 28, "max": 59},
  "hook": {
    "template": "Blenderって無理そう？{pain} → {one_move}",
    "first_caption_within_sec": 0.8,
    "pain_is_stated_as_question": true
  },
  "pacing": {
    "shots": 7,
    "avg_shot_sec": 5.4,
    "zoom_ins_per_video": 2
  },
  "telop": {
    "chars_per_card_max": 18,
    "cards": 5,
    "position": "lower-third",
    "font_size_px_1080": 64
  },
  "operation_visibility": {
    "cursor_visible": true,
    "slow_motion_on_key_op": true,
    "ui_highlight": true
  },
  "tone": "断定しない・一緒に確認する・失敗しても戻れると言う"
}
```

## script.json — Ultra が出す台本＋工程表

```json
{
  "theme": "ナイフで切れ目を作る",
  "title": "Blenderって無理そう？切れ目はナイフで入れる",
  "duration_target_sec": 45,
  "promise": "この1手だけ見えればOK",
  "steps": [
    {
      "id": 1,
      "caption": "切れ目を入れたい場所を選ぶ",
      "narration": "まずは、切れ目を入れたいところを選びます。",
      "action": {"kind": "python", "code": "bpy.ops.object.select_all(action='DESELECT')"},
      "camera": {"kind": "viewport", "focus": "object", "zoom": 1.2},
      "hold_sec": 4.0,
      "reveal": "何を触るかだけ"
    }
  ],
  "closing": {
    "caption": "できそう？",
    "narration": "これだけでも、もう入口は越えています。"
  }
}
```

### 制約（バリデータで強制する）

- `steps` は 4〜8。9以上は「全部教える」になるので却下（シリーズの思想に反する）
- `duration_target_sec` は 30〜60
- 各 `caption` は 18文字以内
- 各 `action` は **1ステップ1操作**。複数操作を1つに詰めない（見えなくなる）
- `action.kind` は `python`（bpy実行）か `tool`（MCPツール名＋引数）のみ
- 危険操作（`bpy.ops.wm.quit_blender`, ファイル削除, `save_mainfile` 上書き）は禁止リストで弾く

## 検証フェーズ（SuperVL → Ultra 差し戻し）

生成フレームを3〜6枚渡し、次を JSON で答えさせる。

```json
{
  "score": 0.0,
  "problems": [
    {"step_id": 3, "kind": "telop_unreadable|object_offscreen|cursor_invisible|too_much_on_screen", "detail": "..."}
  ],
  "retry_steps": [3]
}
```

`score < 0.7` なら `retry_steps` だけ Ultra に作り直させる（全体を作り直さない＝コストとトークンの節約）。
