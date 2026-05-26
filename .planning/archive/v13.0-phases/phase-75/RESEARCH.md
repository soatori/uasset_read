---
phase: 75
title: UE/CUE4Parse 事件节点源码检索记录
status: Planned
created: 2026-05-26
---

# Phase 75 源码检索记录

## UE 源码依据

### UEdGraphNode 基类字段

路径：`E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Classes\EdGraph\EdGraphNode.h`

关键字段：

- `NodePosX` / `NodePosY`
- `NodeWidth` / `NodeHeight`
- `AdvancedPinDisplay`
- `NodeComment`
- `NodeGuid`
- comment bubble 相关 editor-only bitfield

判断：`AdvancedPinDisplay` 是 `UEdGraphNode` 基类属性，不是 `K2Node_EnhancedInputAction` 私有字段。解析器应在通用 PropertyTag 层收集，再由 formatter/node_data 暴露。

### K2Node_EnhancedInputAction

路径：

- `E:\Develop\lib\UnrealEngine\Engine\Plugins\EnhancedInput\Source\InputBlueprintNodes\Public\K2Node_EnhancedInputAction.h`
- `E:\Develop\lib\UnrealEngine\Engine\Plugins\EnhancedInput\Source\InputBlueprintNodes\Private\K2Node_EnhancedInputAction.cpp`

关键字段与行为：

- `UPROPERTY() TObjectPtr<const UInputAction> InputAction`
- `AllocateDefaultPins()` 中设置 `AdvancedPinDisplay = ENodeAdvancedPins::Hidden`
- 创建 exec pins: `Triggered`, `Started`, `Ongoing`, `Canceled`, `Completed`
- 创建 value pin: `ActionValue`
- 创建 advanced data pins: `ElapsedSeconds`, `TriggeredSeconds`
- 有 `InputAction` 时创建 object pin `InputAction`，默认值为输入资源名

判断：`ElapsedSeconds` / `TriggeredSeconds` 不应作为 node_data 里的独立属性强读，而应来自 pin array。若它们缺失或后续 pin 变成乱码，优先怀疑 pin body 中 `PinFriendlyName` / `PinToolTip` / `FEdGraphPinType` / `DefaultTextValue` 消费长度错误。

### K2Node_Event

路径：

- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node_Event.h`
- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Private\K2Node_Event.cpp`

关键字段：

- `FMemberReference EventReference`
- `uint32 bOverrideFunction:1`
- `uint32 bInternalEvent:1`
- `FName CustomFunctionName`
- `uint32 FunctionFlags`

判断：`EventReference` 应优先来自 PropertyTag；`bOverrideFunction` 是 PropertyTag/bitfield 语义，不能在属性循环后盲目读取一个 bool。当前只有首个事件为 True，其余为 False，说明 `read_k2node_event()` 的尾部 fallback 可能在已由 PropertyTag 解析后仍消费了错误位置。

### K2Node_FunctionEntry

路径：

- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node_FunctionEntry.h`
- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Private\K2Node_FunctionEntry.cpp`

关键字段：

- `FunctionReference`
- `ExtraFlags`
- `bIsEditable`
- `CustomGeneratedFunctionName`
- 用户定义 pins / 局部变量缓存只在需要时处理

判断：Phase 75 只要求恢复 UE 文本参考中出现的 `ExtraFlags`、`FunctionReference`、`bIsEditable` 和函数入口 pins，不进入完整局部变量缓存序列化。

### EdGraphNode_Comment

路径：

- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\UnrealEd\Public\EdGraphNode_Comment.h`
- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\UnrealEd\Private\EdGraphNode_Comment.cpp`

关键字段：

- `CommentColor`
- `FontSize`
- `MoveMode`
- `NodeDetails`
- `CommentDepth`
- `NodeWidth` / `NodeHeight` 来自基类

判断：Comment 节点不应走未知 fallback。缺失的 `FontSize` / `CommentDepth` 应按 PropertyTag 是否存在区分“默认值未序列化”和“解析失败”，不能统一显示为异常。

## CUE4Parse 依据

路径：

- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Exports\EdGraph\UEdGraphPin.cs`
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Exports\EdGraph\UEdGraphPinReference.cs`
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\Engine\EdGraph\FEdGraphPinType.cs`

观察：

- CUE4Parse 对 `UEdGraphPin` 和 `FEdGraphPinType` 的字段顺序很明确。
- CUE4Parse 未提供 `K2Node_EnhancedInputAction` / `K2Node_Event` 的专用节点类解析，节点特有字段仍依赖通用 UObject PropertyTag。
- 因此 Phase 75 的节点特有字段修复应以 UE UPROPERTY + 项目 PropertyTag 解析为主，CUE4Parse 只作为 pin body 顺序参考。

## 当前项目落点

- `src/uasset_read/serializers/graph.py`
  - `read_ue_graph_node()`
  - `read_ue_graph_pin()`
  - `read_k2node_event()`
  - `read_k2node_enhanced_input()`
  - `read_k2node_functionentry()`
  - `read_edgraph_node_comment()`
- `src/uasset_read/models/node_types.py`
- `src/uasset_read/formatters/blueprint_text_formatter.py`
- `tests/test_phase73_bp_first_person_e2e.py`
- 新增 Phase 75 字段级 golden tests
