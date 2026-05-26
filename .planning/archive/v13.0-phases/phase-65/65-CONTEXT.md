# Phase 65 — 图解析器修复

## 来源
来自 `.planning/phases/phase-64/64-GAP-REPORT.md` 的 GAP-01/02/03/06/07。

## 修复目标

| GAP | 问题 | 修复模块 |
|-----|------|---------|
| GAP-01 | FMemberReference 解析失败 (member_name='None') | `serializers/graph.py` read_fmember_reference |
| GAP-02 | Pin 连接全部为空 (linked_to_raw=[]) | `serializers/graph.py` read_ue_graph_pin / read_pin_array |
| GAP-03 | StructProperty → UnknownStruct | `parsers/` struct name mapping |
| GAP-06 | 执行流只有入口节点 | 依赖 GAP-02 修复，`graph/flow_builder.py` 自动解决 |
| GAP-07 | 函数签名全空 | `graph/flow_builder.py` 从 Function 节点 Pin 提取参数 |

## 参考源码
- `K2Node_CallFunction.cpp` — FK2Node_CallFunction::Serialize()
- `EdGraphPin.cpp` — UEdGraphPin::Serialize()
- `BlueprintEditorUtils.cpp` — FBlueprintEditorUtils::ReadPinReference()
- `BlueprintEditorUtils::PinReferenceSerializer`

## 验证目标
修复后对 `BP_FirstPersonCharacter.uasset` 运行解析，验证：
1. K2Node_CallFunction 的 function_reference 有正确的 MemberName
2. Pin 的 linked_to_raw 不为空
3. StructProperty 能识别 FVector/FRotator/FGuid
4. 执行流能追踪 FunctionEntry → CallFunction 链路
5. 函数签名有正确的参数列表
