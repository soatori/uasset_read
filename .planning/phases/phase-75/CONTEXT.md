---
phase: 75
title: EventGraph 节点字段级对齐与残留 Pin 错位诊断
status: Planned
created: 2026-05-26
---

# Phase 75 上下文

Phase 74 已完成 `PinReference` null / non-null 布局修复，但再次解析完整样本后，缺失报告中的同类问题仍存在。现有端到端测试能通过关键拓扑断言，却没有覆盖 UE 文本序列化级字段，因此出现了“测试绿、实际输出仍缺失/错位”的状态。

## 当前复现

执行：

```bash
python -m pytest tests/test_phase73_bp_first_person_e2e.py tests/test_bp_first_person_reference_alignment.py -q
```

结果：

```text
14 passed, 9 warnings
```

但直接解析 `BP_FirstPersonCharacter.uasset` 仍会出现：

```text
LinkedTo read failed at pos 115013: Pin array count 779314540 exceeds MAX_LINKEDTO_PER_PIN 100
LinkedTo read failed at pos 119045: Pin array count 1886220099 exceeds MAX_LINKEDTO_PER_PIN 100
LinkedTo read failed at pos 123072: Pin array count 1886220099 exceeds MAX_LINKEDTO_PER_PIN 100
LinkedTo read failed at pos 128834: Pin array count -1862270976 exceeds MAX_LINKEDTO_PER_PIN 100
[P73-SUBPINS] Recovery ...
[P73-RECOVERY] LinkedTo ...
```

这说明 Phase 74 修复了 `SerializePin()` 引用布局的一类根因，但仍有上游字段消费长度不稳定，导致 `LinkedTo` 起点继续偏移。

## 字段级缺失样本

当前解析出的 EventGraph 拓扑正确：

- `EdGraphNode_Comment`: 3
- `K2Node_CallFunction`: 7
- `K2Node_EnhancedInputAction`: 4
- `K2Node_Event`: 4

但字段级输出仍有明显问题：

| 类型 | 现象 | 影响 |
|------|------|------|
| `K2Node_EnhancedInputAction` | `IA_MouseLook` / `IA_Look` / `IA_Move` 的 `ActionValue_X` 后续 pin 出现方向值 `67/114/136`、pin 名称变成路径或 `None` | Pin body 中某字段消费过少/过多，后续 `LinkedTo/SubPins` 全部错位 |
| `K2Node_EnhancedInputAction` | `AdvancedPinDisplay=Hidden` 未进入 node_data | 无法按 UE 文本参考重建节点状态 |
| `K2Node_EnhancedInputAction` | `ElapsedSeconds` / `TriggeredSeconds` 只在部分节点正确出现 | 分裂 pin 或 DefaultText/FText 消费仍不稳定 |
| `K2Node_Event` | `bOverrideFunction` 只有第一个事件为 True，其余 Touch/Thumbstick 事件解析为 False | `K2Node_Event` 特有字段或 bitfield 读取路径不可靠 |
| `K2Node_Event` | `Axis_X` 后出现伪 pin，如 `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter`、`StructProperty` | Event 节点 split pin 后续字段偏移 |
| `K2Node_FunctionEntry` | `ExtraFlags` / `bIsEditable` 未进入 node_data | 函数入口无法完整还原 UE 文本 |
| `EdGraphNode_Comment` | `FontSize` / `CommentDepth` 在部分节点为 None | Comment 节点字段覆盖不完整 |

## 关键判断

Phase 75 不应继续扩大 P73/P74 的恢复扫描窗口。当前问题已经不是“找不到一个可用的 LinkedTo count”，而是 `LinkedTo` 之前的 node/pin 字段消费长度仍与 UE 序列化不完全一致。

Phase 75 的目标是把事件相关节点从“拓扑可用”推进到“字段级与 UE 文本参考可对齐”，并用更严格的金标准测试阻止同类错位被绿色测试掩盖。

## 参考资产

- 完整样本：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`
- 缺失报告：`E:\Develop\uasset_read\references\uasset-format\references\assets\解析缺失报告.md`
- 文本金标准：`E:\Develop\uasset_read\references\蓝图节点文本参考.md`
- 对比说明：`E:\Develop\uasset_read\references\对比分析-uasset格式与蓝图节点文本参考.md`
