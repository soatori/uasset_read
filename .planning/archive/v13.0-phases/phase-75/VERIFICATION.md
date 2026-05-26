---
phase: 75
title: EventGraph 字段级对齐验证计划
status: Planned
created: 2026-05-26
---

# Phase 75 验证计划

## 当前基线

已执行：

```bash
python -m pytest tests/test_phase73_bp_first_person_e2e.py tests/test_bp_first_person_reference_alignment.py -q
```

结果：

```text
14 passed, 9 warnings
```

但同一资产直接解析仍出现多处 `LinkedTo read failed` 和 `[P73-SUBPINS]`，并且字段级诊断显示 EnhancedInput/Event pin body 仍有错位。因此 Phase 75 必须新增更严格的字段级 golden tests。

## 新增测试文件

计划新增：

```text
tests/test_phase75_event_node_field_alignment.py
tests/test_phase75_pin_body_offset_diagnostics.py
```

## 预期失败快照

Phase 75 实施前，新测试应暴露这些失败之一：

- `IA_Move` / `IA_Look` / `IA_MouseLook` 的 pin 列表中出现异常 direction，例如 `67/114/136`。
- `K2Node_Event` 中 `Secondary Thumbstick` / `Touch Jump Start` / `Touch Jump End` 的 `bOverrideFunction` 为 False。
- `ActionValue_X` 后出现路径名伪 pin。
- 捕获到 `LinkedTo read failed` 或 `[P73-SUBPINS]` 参与关键 pin。

这些失败是预期红灯，不应通过放宽断言处理。

## 必须通过的断言

### EnhancedInputAction

| 项 | 标准 |
|----|------|
| 节点数量 | EventGraph 中 4 个 |
| InputAction | `IA_Look`、`IA_Move`、`IA_Jump`、`IA_MouseLook` |
| AdvancedPinDisplay | 全部为 Hidden |
| Exec pins | `Triggered`、`Started`、`Ongoing`、`Canceled`、`Completed` 全部为 output exec |
| Value pins | `ActionValue` 及 split pins 不乱码 |
| Timing pins | `ElapsedSeconds`、`TriggeredSeconds` 为 output real/double，advanced view |
| Object pin | `InputAction` 默认对象路径可解析到 `/Game/Input/Actions/...` |

### K2Node_Event

| 项 | 标准 |
|----|------|
| 节点数量 | EventGraph 中 4 个 |
| EventReference | `Primary Thumbstick`、`Secondary Thumbstick`、`Touch Jump Start`、`Touch Jump End` |
| bOverrideFunction | 4 个均为 True |
| Delegate pin | `OutputDelegate` 的 member reference 与 EventReference 一致 |
| Axis split pins | `Axis_X`、`Axis_Y` 方向和类型正确，无路径/PropertyTag 伪 pin |

### K2Node_FunctionEntry

| 项 | 标准 |
|----|------|
| Move | `ExtraFlags=201457664`，`bIsEditable=True`，参数 `Left / Right`、`Forward / Backward` |
| Aim | `ExtraFlags=201457664`，`bIsEditable=True`，参数 `Yaw`、`Pitch` |
| UserConstructionScript | 保持现有解析，不引入回归 |

### EdGraphNode_Comment

| 项 | 标准 |
|----|------|
| unknown fallback | 不出现 `Fallback processing for unknown type: EdGraphNode_Comment` |
| 尺寸 | `NodeWidth` / `NodeHeight` 与文本参考一致 |
| 颜色 | `CommentColor` 可输出 |
| 缺省字段 | `FontSize` / `CommentDepth` 区分默认缺省和解析失败 |

### Pin/Recovery

| 项 | 标准 |
|----|------|
| LinkedTo | 完整样本关键 pin 不出现 `LinkedTo read failed` |
| Recovery | 关键连接不依赖 `[P73-SUBPINS]` 或 low confidence recovery |
| 输出文本 | 不包含 `_parse_error`、`\x00`、路径名伪 pin、明显乱码 pin name |

## 测试粒度

### `tests/test_phase75_event_node_field_alignment.py`

建议测试项：

- `test_eventgraph_node_counts_remain_stable`
- `test_enhanced_input_expected_pin_sets`
- `test_enhanced_input_advanced_pin_display_and_input_action_paths`
- `test_touch_interface_event_references_and_override_flags`
- `test_function_entry_flags_and_parameters`
- `test_comment_node_fields_and_no_unknown_fallback`
- `test_blueprint_text_output_has_no_garbage`

### `tests/test_phase75_pin_body_offset_diagnostics.py`

建议测试项：

- `test_trace_mode_does_not_change_parse_result_counts`
- `test_bad_linkedto_count_records_node_pin_and_field_offset`
- `test_default_text_failure_cannot_be_silently_treated_as_linkedto`
- `test_low_confidence_recovery_is_excluded_from_golden_edges`
- `test_pin_direction_values_are_valid_for_first_person_eventgraph`

## 日志验收

修复完成后，针对完整样本捕获日志：

```text
LinkedTo read failed
[P73-SUBPINS]
[P73-RECOVERY]
Fallback processing for unknown type: EdGraphNode_Comment
Fallback processing for unknown type: K2Node_EnhancedInputAction
```

验收规则：

- 关键 golden edges 相关节点不得出现这些日志。
- 若仍有非关键 recovery，必须在 `linkedto_recovery_summary.txt` 中列出 graph/node/pin/reason。
- unknown fallback 不应覆盖 Phase 75 目标节点类型。

## 回归命令

分阶段执行：

```bash
python -m pytest tests/test_phase75_event_node_field_alignment.py tests/test_phase75_pin_body_offset_diagnostics.py -q
python -m pytest tests/test_phase73_bp_first_person_e2e.py tests/test_phase73_linkedto_recovery.py tests/test_bp_first_person_reference_alignment.py -q
python -m pytest tests/ -q
```

建议每个 Wave 的最小命令：

```bash
# Wave 0
python -m pytest tests/test_phase75_event_node_field_alignment.py tests/test_phase75_pin_body_offset_diagnostics.py -q

# Wave 1/2
python -m pytest tests/test_phase75_event_node_field_alignment.py tests/test_phase73_bp_first_person_e2e.py -q

# Wave 3
python -m pytest tests/test_phase75_pin_body_offset_diagnostics.py tests/test_phase73_linkedto_recovery.py tests/test_phase74_pin_reference_layout.py -q

# Wave 4
python -m pytest tests/ -q
```

## 诊断输出要求

实现阶段可生成临时文件到：

```text
temp/phase75/
```

推荐输出：

- `event_node_fields.json`
- `pin_body_offsets.json`
- `linkedto_recovery_summary.txt`
- `golden_diff.md`

这些文件只用于诊断，不提交。

## 完成记录模板

```text
Date:
Commit/branch:
Commands:
Results:
LinkedTo failures:
P73/P74 recovery count:
First fixed offset:
Remaining gaps:
```

## Phase 75 验收表

| 验收项 | 目标值 | 记录 |
|--------|--------|------|
| Phase 75 字段级测试 | 全部通过 | 待填 |
| Phase 73/74 回归 | 全部通过 | 待填 |
| 全量测试 | 通过 | 待填 |
| `LinkedTo read failed` | 0 或非关键可解释 | 待填 |
| low confidence recovery 参与关键边 | 0 | 待填 |
| EnhancedInputAction 乱码 pin | 0 | 待填 |
| K2Node_Event `bOverrideFunction` | 4/4 True | 待填 |
| FunctionEntry `ExtraFlags/bIsEditable` | Move/Aim 均可见 | 待填 |
