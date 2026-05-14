# Phase 22: 节点序列化修复 - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning (gap closure)
**Source:** Phase 21 VERIFICATION.md — ISSUE-01

<domain>
## Phase Boundary

修复 Phase 21 发现的关键问题：`read_ue_graph_node` 未正确跳过 UObject 基类序列化数据，导致 pins 解析失败。

**Problem Statement:**
- 当前代码直接定位到 `node_export.serial_offset`，读取的是 UObject 基类数据而非 pins 数组
- UObject::Serialize() 先执行，序列化基类属性（引用数组等）
- UEdGraphPin::SerializeAsOwningNode(Ar, Pins) 在 Super::Serialize() 之后执行
- pins_count 读取为错误值（如 41984），触发 ParseError 或返回空数据

**Impact:**
- execution_flows 无法追踪（无 pin 连接信息）
- data_flows 缺少连接信息（节点 pins 为空）
- function_reference 缺失（节点数据未解析）
- node_guid 存在但为空（fallback 节点）

**Goal:** 正确解析节点数据，使 TEST-02/03/04 通过验证

</domain>

<decisions>
## Implementation Decisions

### 问题定位 (from Phase 21 VERIFICATION)
- **D-22-01:** UObject 基类数据跳过 — 必须在读取 pins 之前跳过 UObject::Serialize() 数据
- **D-22-02:** 使用 UE 源码参考 — UObject::Serialize() 实现确定跳过字节数

### 修复策略
- **D-22-03:** 研究 UObject 序列化格式 — 确定基类数据的结构（属性数量、引用数组等）
- **D-22-04:** 找到正确偏移量 — 确定 UObject 数据结束位置，从正确位置开始读取 pins
- **D-22-05:** 或使用属性迭代器 — 可能需要迭代属性而非直接定位

### 验证方法
- **D-22-06:** 重新运行 Phase 21 测试 — TEST-02/03/04 必须通过
- **D-22-07:** 精确匹配 expected 值 — execution_flows、data_flows、function_reference 正确

### Claude's Discretion
- UObject 基类序列化的具体字节数（需研究 UE 源码）
- 属性迭代器的实现方式（如果适用）
- 是否需要修改其他相关函数

</decisions>

<specifics>
## Specific Ideas

**UE 源码参考路径:**
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Private/UObject/UObjectSerialize.cpp` — UObject::Serialize() 实现
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphNode.cpp` — UEdGraphNode::Serialize()
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp` — UEdGraphPin::SerializeAsOwningNode()

**当前代码问题位置:**
- `uasset_read.py:read_ue_graph_node()` — 需修复的函数
- 约 4900+ 行代码中查找 `def read_ue_graph_node`

**Expected 修复后结果:**
- TEST-02: execution_flows 包含 IA_Jump → Jump → StopJumping 链路
- TEST-03: data_flows 包含 ActionValue_X/Y → 参数连接
- TEST-04: function_reference.MemberName 正确提取，node_guid 非空

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE 源码参考（关键）
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Private/UObject/UObjectSerialize.cpp` — UObject::Serialize() 实现（确定基类数据跳过方式）
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphNode.cpp` — UEdGraphNode 序列化
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp` — UEdGraphPin::SerializeAsOwningNode()

### Prior Phase Context
- `.planning/phases/21-验证测试/21-VERIFICATION.md` — 问题发现和根因分析
- `.planning/phases/21-验证测试/21-01-SUMMARY.md` — 执行结果和修复建议
- `.planning/phases/18-Pin序列化解析/18-CONTEXT.md` — Phase 18 原始规划

### 测试验证
- `tests/test_phase21_verification.py` — 验证测试文件
- `.planning/REQUIREMENTS.md` — TEST-01~04 规范

</canonical_refs>

<deferred>
## Deferred Ideas

None — 单一修复目标，完成后 v4.0 里程碑完成。

</deferred>

---
*Phase: 22-节点序列化修复*
*Context gathered: 2026-05-04 via gap closure from Phase 21 VERIFICATION*