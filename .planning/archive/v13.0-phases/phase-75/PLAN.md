---
phase: 75
title: EventGraph 节点字段级对齐修复计划
status: Planned
created: 2026-05-26
---

# Phase 75 计划

## 目标

让 `BP_FirstPersonCharacter.uasset` 的 EventGraph / FunctionGraph 不只通过连接拓扑测试，还能在关键事件节点字段、pin 列表、pin 类型和文本输出上对齐 UE 编辑器文本参考。

成功后应满足：

- 解析日志中 `LinkedTo read failed` 为 0，或只剩明确标注为非关键且可解释的低风险样本。
- `[P73-SUBPINS]` / `[P73-RECOVERY]` 不参与关键执行边和数据边恢复。
- `K2Node_EnhancedInputAction` 的 4 个输入动作节点都有完整 pins：5 个 exec pins、`ActionValue`、必要 split pins、`ElapsedSeconds`、`TriggeredSeconds`、`InputAction`。
- `K2Node_Event` 的 4 个触摸事件都有正确 `EventReference` 和 `bOverrideFunction=True`。
- `K2Node_FunctionEntry` 输出 `ExtraFlags`、`FunctionReference`、`bIsEditable`。
- `EdGraphNode_Comment` 不再被 unknown fallback 处理，字段缺省与字段解析失败可区分。

## 非目标

- 不重构整个 UObject / PropertyTag 解析架构。
- 不扩大 LinkedTo/SubPins 恢复扫描窗口。
- 不把 UE 文本序列化格式当作新的输入解析器。
- 不实现完整 EnhancedInput 编译展开逻辑。
- 不在 Phase 75 处理全部 FText history 类型，只处理会影响当前 Pin 对齐的路径。

## 总体策略

Phase 75 采用“先让错误显形，再修第一个错位点”的方式推进。不要同时改多个猜测点；每一轮只接受一种可证明的消费长度修正，并用 offset trace 验证 `LinkedTo` 起点是否回到正确位置。

核心闭环：

```text
字段级 golden test 失败
  -> 生成 pin offset 诊断
  -> 找到第一个异常 pin/字段
  -> 对照 UE/CUE4Parse 字段顺序
  -> 修一个消费长度错误
  -> 重跑字段级测试和 recovery 统计
```

判断“第一个错位点”的标准：

- 同一节点内，前一个 pin 的字段全部合理，当前 pin 开始出现异常 direction/name/category。
- trace 中某字段结束 offset 与预期下一字段起点不一致。
- `LinkedTo` count 读取到明显 ASCII / 路径 / FName index / GUID 片段组成的垃圾整数。
- 修复后，不靠 recovery 即可读出当前 pin 的 `LinkedTo/SubPins/ParentPin/PersistentGuid/BitField`。

## 涉及文件

计划中的实现改动应集中在以下文件：

| 文件 | 作用 | Phase 75 预期动作 |
|------|------|-------------------|
| `src/uasset_read/serializers/graph.py` | Graph/Node/Pin 主解析 | 补 PropertyTag 收集、移除事件盲读、修 Pin/FText 消费长度 |
| `src/uasset_read/models/node_types.py` | 节点数据模型 | 增加兼容性可选字段 |
| `src/uasset_read/formatters/blueprint_text_formatter.py` | 字段输出 | 输出完整 InputAction/Event/FunctionEntry/Comment 字段 |
| `src/uasset_read/graph/pin_trace.py` | Pin trace | 扩展字段 offset 和 recovery reason 输出 |
| `tests/test_phase75_event_node_field_alignment.py` | Golden 字段测试 | 新增 |
| `tests/test_phase75_pin_body_offset_diagnostics.py` | Pin body 诊断测试 | 新增 |

避免改动：

- `parse_uasset.py` 管线结构。
- `link/` 对象链接器架构。
- N2C 类型系统，除非字段输出已经稳定且需要兼容映射。

## 诊断数据结构

建议新增或复用一个只读诊断结构，不要求作为公共 API：

```python
{
    "graph": "EventGraph",
    "node": "K2Node_EnhancedInputAction",
    "node_guid": "...",
    "node_name_hint": "IA_Move",
    "pin": "ActionValue_X",
    "pin_index": 6,
    "fields": [
        {"name": "PinName", "start": 119012, "end": 119020, "value": "ActionValue_X"},
        {"name": "PinFriendlyName", "start": 119020, "end": 119045, "value_preview": "Action Value X"},
        {"name": "LinkedTo.count", "start": 119045, "end": 119049, "value": 1886220099, "valid": false}
    ],
    "recovery": {
        "triggered": true,
        "kind": "P73-SUBPINS",
        "confidence": "medium",
        "reason": "valid null ref after bad count"
    }
}
```

字段要求：

- 每个字段都记录 `start/end/bytes/value_preview`。
- FText/FString 失败时记录 `exception` 和 `fallback_target`。
- `LinkedTo/SubPins/ParentPin/ReferencePassThroughConnection` 必须记录 count/ref 起点。
- 诊断文件只写 `temp/phase75/`，不提交。

## 数据正确性不变量

以下不变量用于快速判断是否偏移：

- Pin direction 只能是已知枚举值：`0` input、`1` output；当前样本不应出现 `67/114/136`。
- Pin name 不应包含 `/Game/`、`/Script/`，这些是对象路径，不是 pin 名。
- `K2Node_EnhancedInputAction` 的 exec pins 必须按 UE 逻辑均为 output exec。
- `ActionValue_X/Y`、`Axis_X/Y` 的 `ParentPin` 必须指向同节点的 `ActionValue` 或 `Axis`。
- `ElapsedSeconds` / `TriggeredSeconds` 的 `PinType` 必须是 `real/double`。
- `InputAction` pin 的 `DefaultObject` 可以是非 0 `FPackageIndex`，格式化层再解析为路径。
- `K2Node_Event.OutputDelegate.PinSubCategoryMemberReference` 必须与 node 的 `EventReference` 同名。
- `PersistentGuid` 可为全 0，但字段本身必须在正确 offset 消费 16 字节。
- `BitField` 后应到达当前 pin body 结束或下一个 owning pin header，不应落在 FString/FName 中间。

## PLAN-75-01: 建立字段级诊断基线

新增只读诊断脚本或测试辅助函数，输出到 `temp/phase75/`：

- 每个 graph 的节点类型计数。
- 每个 `K2Node_EnhancedInputAction` 的 `input_action_path`、`AdvancedPinDisplay`、pin name/direction/category/default/link 数量。
- 每个 `K2Node_Event` 的 `EventReference`、`bOverrideFunction`、split pin 状态。
- 每个 `K2Node_FunctionEntry` 的 `ExtraFlags`、`bIsEditable`、pins。
- 每个 pin 的 `LinkedTo` 起点 offset、失败 count、P73/P74 recovery reason。

验收：诊断输出能复现 Phase 75 上下文中的异常 pin 名称、异常 direction 和 `LinkedTo read failed` 位置。

### 实施细节

- 优先复用 `trace_mode=True`，不要引入第二套解析路径。
- 若当前 trace 只记录成功字段，扩展为成功/失败都记录。
- 诊断入口可以放在测试内 helper，也可以放在 `src/uasset_read/graph/pin_trace.py` 的只读函数。
- 不允许诊断函数改变解析结果；`trace_mode=False/True` 的 graph/node/pin/link 数量必须一致。

### 输出检查点

第一轮诊断至少应确认：

- 第一个异常 `LinkedTo` offset 属于哪个 graph/node/pin。
- 该 pin 的上一个字段是什么。
- 该字段是否是 FText/FString/FEdGraphPinType/FPackageIndex。
- recovery 是从哪里重同步到 `SubPins` 的。

## PLAN-75-02: 强化 golden tests，先暴露失败

新增 `tests/test_phase75_event_node_field_alignment.py`：

- `test_enhanced_input_nodes_match_reference_fields`
  - 断言 `IA_Look`、`IA_Move`、`IA_Jump`、`IA_MouseLook` 均存在。
  - 断言每个节点 `advanced_pin_display == "Hidden"` 或等价枚举值。
  - 断言 `Triggered/Started/Ongoing/Canceled/Completed` 都是 `EGPD_Output` exec pins。
  - 断言 `ElapsedSeconds`、`TriggeredSeconds` 为 output real/double 且 `advanced_view=True`。
  - 断言 `InputAction` pin 为 object pin，默认对象可解析到 `/Game/Input/Actions/...`。

- `test_touch_event_nodes_match_reference_fields`
  - 断言 4 个 `K2Node_Event` 名称：`Primary Thumbstick`、`Secondary Thumbstick`、`Touch Jump Start`、`Touch Jump End`。
  - 断言 `bOverrideFunction=True`。
  - 断言 delegate pin 的 `PinSubCategoryMemberReference.member_name` 与 `EventReference.member_name` 一致。
  - 断言 `Primary/Secondary Thumbstick` 的 `Axis_X/Axis_Y` split pins 无乱码名称、方向为 output。

- `test_function_entry_nodes_match_reference_fields`
  - 断言 `Move` / `Aim` FunctionEntry 有 `ExtraFlags=201457664`、`bIsEditable=True`。
  - 断言参数 pins 分别为 `Left / Right`、`Forward / Backward`、`Yaw`、`Pitch`。

- `test_no_low_confidence_pin_recovery_for_golden_edges`
  - 解析过程中捕获日志。
  - 断言关键 pin 不依赖 `[P73-SUBPINS]` / low confidence recovery。

这些测试应先失败，失败信息必须指向字段级差异，而不是只报连接数量不足。

### 测试实现建议

测试 helper：

- `_find_graph(parsed_asset, "EventGraph")`
- `_nodes_by_semantic_name(graph)`
- `_pins_by_name(node)`
- `_assert_pin(node, name, direction, category, subcategory=None)`
- `_assert_no_garbage_pin_names(node)`

乱码/伪 pin 判定：

- pin name 为空、`None`、`/Game/`、`/Script/`、`StructProperty`、`ObjectProperty` 均失败。
- direction 不在 `{0, 1, "EGPD_Input", "EGPD_Output"}` 均失败。
- pin category 包含 `/Game/` 或明显对象路径均失败。

日志捕获：

- 用 `caplog` 捕获 `LinkedTo read failed`、`[P73-SUBPINS]`、`[P73-RECOVERY]`。
- 先允许测试失败并打印 offending node/pin，修复完成后收紧为 0。

### 最小 golden 集

先锁定这些节点，避免一开始测试面过大：

- `K2Node_EnhancedInputAction`:
  - `IA_Move`
  - `IA_Look`
  - `IA_Jump`
  - `IA_MouseLook`
- `K2Node_Event`:
  - `Primary Thumbstick`
  - `Secondary Thumbstick`
  - `Touch Jump Start`
  - `Touch Jump End`
- `K2Node_FunctionEntry`:
  - `Move`
  - `Aim`
- `EdGraphNode_Comment`:
  - `Camera Input`
  - `Movement Input`
  - `Jump Input - Jump can be configured in the CharacterMovementComponent`

## PLAN-75-03: 修正 node PropertyTag 收集层

集中修 `read_ue_graph_node()` 的 PropertyTag 处理：

- 收集 `AdvancedPinDisplay`，保存原始 int 和格式化枚举名。
- 收集 `bOverrideFunction`、`bInternalEvent`、`CustomFunctionName`、`FunctionFlags`。
- 收集 `ExtraFlags`、`bIsEditable`、`CustomGeneratedFunctionName`。
- 收集 `MoveMode`、`NodeDetails`、comment bubble 相关字段。
- 对 bool PropertyTag 统一处理 inline bool 与 value body 两种形态。
- 对未显式序列化的字段标记为 `missing_default`，避免误判为解析失败。

关键约束：节点特有字段优先来自 PropertyTag。只有 PropertyTag 不存在且源码确认有尾部二进制兼容字段时，才允许 fallback 顺序读取。

### PropertyTag 读取规范

新增内部 helper，避免每个字段手写 bool/int/name：

```python
def _read_tag_bool(archive, tag) -> bool:
    if tag.size > 0:
        return archive.read_i32() != 0
    return tag.bool_val != 0

def _read_tag_i32(archive, tag) -> int:
    value = archive.read_i32()
    archive.seek(tag.value_end_offset)
    return value
```

要求：

- 每个分支读完后必须 seek 到 `tag.value_end_offset`，除非 `read_property_tag` 已处理 inline bool。
- 未识别字段只进入 `raw_properties[tag.name]` 的结构化预览，不能随意按 FString 猜。
- `FunctionReference` / `EventReference` 内部 struct 解析也必须尊重 `value_end`。

### 字段映射

| PropertyTag | 目标字段 | 类型 |
|-------------|----------|------|
| `AdvancedPinDisplay` | `raw_properties["AdvancedPinDisplay"]` | int/enum |
| `bOverrideFunction` | `raw_properties["bOverrideFunction"]` | bool |
| `bInternalEvent` | `raw_properties["bInternalEvent"]` | bool |
| `CustomFunctionName` | `raw_properties["CustomFunctionName"]` | FName |
| `FunctionFlags` | `raw_properties["FunctionFlags"]` | int |
| `ExtraFlags` | `raw_properties["ExtraFlags"]` | int |
| `bIsEditable` | `raw_properties["bIsEditable"]` | bool |
| `CustomGeneratedFunctionName` | `raw_properties["CustomGeneratedFunctionName"]` | FName |
| `MoveMode` | `raw_properties["MoveMode"]` | byte/int |
| `NodeDetails` | `raw_properties["NodeDetails"]` | FText preview |

## PLAN-75-04: 移除事件节点尾部盲读

修正 `read_k2node_event()`：

- `EventReference` 已由 PropertyTag 提供时，不再从当前位置调用 `read_fmember_reference()`。
- `bOverrideFunction` 已由 PropertyTag 提供时，不再调用 `archive.read_bool()`。
- fallback 读取必须受 `node_export.script_serial_size` / 字段 trace 验证保护。
- 返回 `b_internal_event`、`custom_function_name`、`function_flags` 附加字段，不破坏既有 `event_reference` / `b_override_function`。

验收：4 个 Touch Interface 事件均为 `bOverrideFunction=True`，且不会因为尾部盲读改变 pin 起点。

### 决策树

`read_k2node_event()` 进入时：

1. `raw_properties` 有 `event_reference` 或 `EventReference`：直接使用。
2. 没有 EventReference，但剩余字节可由 trace 验证为 `FMemberReference`：执行 legacy fallback。
3. 否则不消费字节，返回空 reference 并记录诊断。

`bOverrideFunction`：

1. `raw_properties` 有 `bOverrideFunction`：使用该值。
2. 没有该字段，且源码/版本判断确认存在 legacy tail bool：读取。
3. 否则默认 `False`，但标记 `source="default_missing"`。

禁止：

- 在 `read_ue_graph_node()` 已经完成 PropertyTag 循环后，再无条件读 `archive.read_bool()`。
- 因为 `bOverrideFunction` 缺失而消费 pin array 起点。

## PLAN-75-05: 修正 EnhancedInputAction 字段与 pin 完整性

修正 `read_k2node_enhanced_input()`：

- `InputAction` 保留完整对象路径、短名和原始 `FPackageIndex`。
- `AdvancedPinDisplay` 从基类 PropertyTag 进入 node_data。
- `trigger_events` 只从 exec pin 名称派生，不把 pin 顺序错位当作合法事件。
- 对 expected pin set 做诊断校验：缺失 `ElapsedSeconds` / `TriggeredSeconds` / `InputAction` 时记录前一个字段 offset。

验收：4 个 EnhancedInputAction pin 列表不再出现 `None`、路径名伪 pin、异常 direction 值。

### InputAction 表示

建议 node_data 同时保留：

```python
{
    "input_action_path": "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Move.IA_Move'",
    "input_action_short_name": "IA_Move",
    "input_action_package_index": -45,
    "advanced_pin_display": "Hidden",
    "advanced_pin_display_raw": 1,
}
```

兼容要求：

- 既有 `input_action_path` 若已有调用方依赖短名，可以暂时保持短名。
- 新增完整路径字段用 `input_action_object_path` 或等价名称承载。
- formatter 可以优先显示短名，同时在 verbose/debug 模式输出完整路径。

### Pin set 校验

EnhancedInputAction expected pins：

```text
Triggered, Started, Ongoing, Canceled, Completed,
ActionValue,
ElapsedSeconds, TriggeredSeconds,
InputAction
```

对于 `ActionValue_X/Y`：

- `IA_Move` / `IA_Look` / `IA_MouseLook` 应有 split pins。
- `IA_Jump` 可没有 vector split pins，但仍应有 timing pins 和 InputAction pin。
- 如果 split pin 缺失，诊断必须指向 parent `ActionValue` 的 `SubPins` offset。

## PLAN-75-06: 回到 Pin body 偏移点，修最小根因

基于 Phase 75 诊断定位第一个错位点，优先检查这些字段：

- `PinFriendlyName` 的 FText history 类型和失败回退是否准确消费。
- `PinToolTip` 是否始终按 FString，不按 FText。
- `FEdGraphPinType.PinSubCategoryMemberReference` 是否按版本完整消费。
- `DefaultTextValue` 的 FText fallback 是否错误吞掉后续 `LinkedTo`。
- `DefaultObject` / `PinSubCategoryObject` 的 `FPackageIndex` 是否按 int32 消费并保留原始值。

修复原则：

- 只改第一个可证明的消费长度错误。
- 禁止在 FText/FString 失败后直接继续读 `LinkedTo`。
- 每个容错分支必须写 trace reason 和候选 offset。

### Pin body 字段顺序检查表

按 CUE4Parse/UE 顺序逐项确认：

| 顺序 | 字段 | 类型 | 常见错位信号 |
|------|------|------|--------------|
| 1 | `PinName` | FName/FString | pin 名变对象路径或 `None` |
| 2 | `PinFriendlyName` | FText | 下一个 `SourceIndex` 变巨大值 |
| 3 | `SourceIndex` | int32 | `PinToolTip` 起点落到 FText 中 |
| 4 | `PinToolTip` | FString | direction 变 ASCII 或大整数 |
| 5 | `Direction` | enum byte/int | 出现 `67/114/136` |
| 6 | `PinType` | FEdGraphPinType | category 变路径或 PropertyTag 名 |
| 7 | `DefaultValue` | FString | `DefaultObject` 变字符串片段 |
| 8 | `AutogeneratedDefaultValue` | FString | `DefaultTextValue` 起点错 |
| 9 | `DefaultObject` | FPackageIndex | FText history_type 异常 |
| 10 | `DefaultTextValue` | FText | `LinkedTo.count` 垃圾 |
| 11 | `LinkedTo` | TArray PinRef | count 超阈值 |
| 12 | `SubPins` | TArray PinRef | SubPins 被误当 LinkedTo |
| 13 | `ParentPin` | PinRef | 多读/少读 16 字节 |
| 14 | `ReferencePassThroughConnection` | PinRef | PersistentGuid 起点错 |
| 15 | `PersistentGuid` | FGuid | bitfield 错 |
| 16 | `BitField` | uint32 | 下一个 pin header 错 |

### FText/FString 容错规则

- `PinToolTip` 永远按 FString，不做 FText fallback。
- `PinFriendlyName` / `DefaultTextValue` 的 FText fallback 只能回退到经过验证的下一个字段起点。
- 如果 `DefaultTextValue` 解析失败，必须验证接下来 4 字节是否是合法 `LinkedTo` count；不合法则整 pin 标记失败，不能继续构建连接。
- FString 长度异常不得直接吞掉并 seek 到猜测位置，必须记录候选和失败原因。

## PLAN-75-07: Formatter 与模型兼容扩展

在不破坏公共字段语义的前提下补充可选字段：

- `K2NodeEvent`: `b_internal_event`、`custom_function_name`、`function_flags`。
- `K2NodeEnhancedInputAction`: `input_action_short_name`、`input_action_object_path`、`advanced_pin_display`。
- `K2NodeFunctionEntry`: `extra_flags`、`b_is_editable`。
- `EdGraphNodeComment`: `move_mode`、`node_details`、字段来源状态。

formatter 输出应避免 `_parse_error`、`\x00` 和明显乱码。

### 兼容策略

- dataclass 新字段必须有默认值。
- 旧 `node_data` dict 调用方仍可通过原 key 访问。
- formatter 先处理 dict，再处理 dataclass，保持现有混合模式。
- JSON 输出新增字段为可选，不删除旧字段。

### 输出目标

对齐 `references/蓝图节点文本参考.md` 的核心字段：

```text
InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Move.IA_Move'"
AdvancedPinDisplay=Hidden
EventReference=(MemberParent="...",MemberName="Primary Thumbstick",MemberGuid=...)
bOverrideFunction=True
ExtraFlags=201457664
bIsEditable=True
```

## PLAN-75-08: 收敛恢复逻辑

在字段主路径稳定后：

- `LinkedTo count=0` 必须结合后续 `SubPins/ParentPin/PersistentGuid/BitField` 验证。
- `[P73-SUBPINS]` 只保留诊断用途。
- 低置信 recovery 不参与连接图构建。
- 对所有 recovery 事件输出 graph/node/pin/name/offset/reason，便于下一阶段继续定位。

### Recovery 分级

| 等级 | 定义 | 是否参与连接图 |
|------|------|----------------|
| high | count/ref 均验证通过，后续结构也验证通过 | 可以 |
| medium | count 可解释，后续结构部分验证 | 暂不参与关键 golden edges |
| low | 仅通过扫描找到疑似 count | 禁止 |
| salvage | 为保持解析继续的重同步 | 禁止 |

完成 Phase 75 后，关键连接必须来自 high confidence 主路径或等价验证路径。

## 执行顺序

1. 写 Phase 75 字段级 failing tests。
2. 用诊断输出定位第一个 pin body 错位。
3. 修 node PropertyTag 收集，移除事件节点盲读。
4. 修 EnhancedInputAction / FunctionEntry / Comment node_data。
5. 修第一个可证明的 Pin/FText/FMemberReference 消费长度错误。
6. 收敛 recovery，验证关键边不用 salvage。
7. 全量回归。

## Wave 拆分

### Wave 0: 基线与失败测试

产出：

- `tests/test_phase75_event_node_field_alignment.py`
- `tests/test_phase75_pin_body_offset_diagnostics.py`
- `temp/phase75/` 诊断输出

退出条件：

- 新测试能稳定失败。
- 失败信息指出具体 graph/node/pin/field。
- 现有 Phase 73/74 测试仍保持当前状态。

### Wave 1: PropertyTag 与事件节点字段

产出：

- `AdvancedPinDisplay`、`bOverrideFunction`、`ExtraFlags`、`bIsEditable` 正确进入 node_data。
- `read_k2node_event()` 不再无条件尾部读 bool。

退出条件：

- 4 个 `K2Node_Event` 的 `bOverrideFunction=True`。
- `Move/Aim` FunctionEntry 字段可见。
- 不引入新的 pin count 异常。

### Wave 2: EnhancedInputAction 完整字段

产出：

- InputAction 短名/完整路径/FPackageIndex 都可追踪。
- `AdvancedPinDisplay=Hidden` 可输出。
- `trigger_events` 仅基于合法 exec pins。

退出条件：

- 4 个 EnhancedInputAction 的 expected pin set 通过。
- 不再出现路径名伪 pin 或异常 direction。

### Wave 3: Pin body 首个错位修复

产出：

- 修正第一个可证明的 FText/FString/FEdGraphPinType 消费错误。
- `LinkedTo read failed` 数量降为 0，或剩余条目都有明确非关键原因。

退出条件：

- 关键执行边/数据边不用 low confidence 或 salvage recovery。
- `trace_mode=False/True` 解析数量一致。

### Wave 4: Formatter 与全量回归

产出：

- 文本/JSON 输出字段完整、无乱码。
- 文档记录最终 offset 修复点。

退出条件：

- Phase 75 新测试通过。
- Phase 73/74 回归通过。
- `python -m pytest tests/ -q` 通过或仅剩既有明确 xfail/skip。

## 风险与回滚

| 风险 | 触发信号 | 处理 |
|------|----------|------|
| PropertyTag helper 影响其他节点 | 大量旧测试失败 | 只在 graph node parser 内部使用，不改全局 parser |
| FText fallback 变严格导致解析中断 | 节点数量下降 | 保持 tolerant 模式继续节点级解析，但禁用该 pin 的连接构建 |
| 新字段破坏 JSON/formatter | 输出快照失败 | 字段默认值为 None，formatter 分支兼容 dict/dataclass |
| recovery 收敛过早导致连接减少 | Phase 73 edges 失败 | 先只在 Phase 75 golden edges 禁用低置信连接，最后再全局收敛 |

## 完成定义

Phase 75 只有在以下条件都满足时才算完成：

- 新增字段级 golden tests 通过。
- 直接解析完整样本不再输出关键 `LinkedTo read failed`。
- `K2Node_EnhancedInputAction`、`K2Node_Event`、`K2Node_FunctionEntry`、`EdGraphNode_Comment` 字段与文本参考核心项一致。
- 关键执行边和数据边来自可信主路径，不依赖 salvage。
- 全量回归通过。
