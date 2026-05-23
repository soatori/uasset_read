---
gsd_state_version: 1.2
phase: 72-I
research_type: root-cause-analysis
---

# Phase 72-I Research — BP_FirstPersonCharacter 全量对比修复

**Researched:** 2026-05-24
**Domain:** UE5 Blueprint 解析 — Pin 连接、节点发现、Struct 属性、元数据提取
**Confidence:** HIGH（基于三方对照：蓝图节点文本参考 + C++ 对照源码 + 当前 Python 输出）

## Summary

Phase 72-I 针对BP_FirstPersonCharacter解析中的12项错误进行全量对比修复。研究揭示了这些问题的根本原因存在一条**依赖链**：FString 偏移错误 → Pin 序列化错位 → LinkedTo 读取失败 → Connections=0，同时 PropertyTag 类型名解析和节点发现逻辑也存在独立缺陷。

**Primary recommendation:** 按依赖链顺序修复：先修复 FString/偏移根因，再修复节点发现和 Struct 解析，最后修复蓝图元数据提取。Phase 72-H 的 FString 容错修复是 P0 前置条件。

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 12 项对比问题全部修复（I-01 至 I-12）
- 验收标准以 CONTEXT.md 中的清单为准
- 参考基线：蓝图节点文本参考.md + FirstPersonCCharacter.h/cpp

### Claude's Discretion
- 修复优先级和分波策略
- 是否复用 Phase 72-H 的修复成果

### Deferred Ideas (OUT OF SCOPE)
- 其他 uasset 文件的解析修复
- 性能优化
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| I-01 | Pin 连接完全丢失 (Connections=0) | 见根因分析 A：LinkedTo 读取因 FString 偏移错位失败 |
| I-02 | K2Node_EnhancedInputAction 节点缺失 | 见根因分析 B：节点发现主路径 + fallback 路径均遗漏 |
| I-03 | K2Node_Knot 节点缺失 | 见根因分析 B：同 I-02 |
| I-04 | EventGraph 节点总数不足 (9/17) | 见根因分析 B：主路径 nodes_count 可能错误 + fallback 不完整 |
| I-05 | Camera RelativeRotation 全零 | 见根因分析 C：Rotator 快速路径已添加但可能未被调用 |
| I-06 | 3 个属性 Size 越界 | 见根因分析 C：PropertyTag 类型名链式解析偏移错位 |
| I-07 | CharacterMovement 属性缺失 | 见根因分析 C：同 I-06，Struct 内部字段偏移错误 |
| I-08 | Camera RelativeLocation 不完整 | 见根因分析 C：Vector 快速路径可能被跳过 |
| I-09 | EdGraphNode_Comment 字段缺失 | 见根因分析 D：Comment 节点字段不完整 |
| I-10 | Blueprint.functions 为空 | 见根因分析 E：BPGC 属性路径 + Graph fallback 均问题 |
| I-11 | 函数参数信息缺失 | 见根因分析 E：依赖 I-10 和 Pin 完整性 |
| I-12 | FString 偏移错误连锁 | 见根因分析 A：Phase 72-H 的核心目标 |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pin 连接序列化 | serializers/graph.py | archive.py | graph.py 负责 LinkedTo 二进制读取，archive.py 提供 FString 基础读取 |
| 节点发现 | serializers/graph.py | link/linker.py | graph.py 的 read_ue_graph 控制节点发现循环 |
| Struct 属性解析 | parsers/property_types.py | serializers/property_tags.py | property_types.py 负责 struct 字段分派，property_tags.py 提供类型名 |
| 蓝图元数据 | blueprint/variable_extractor.py | graph/flow_builder.py | variable_extractor 提取函数/变量，flow_builder 构建 connections |
| JSON 序列化 | formatters/json_formatter.py | — | serialize_property_value 负责递归序列化 |

---

## 代码根因分析

### 根因 A: FString 偏移错误 → LinkedTo 读取失败 → Connections=0 (I-01, I-12)

**当前状态（实测输出）：**

```
FString at pos 47499: length=4608, encoding=UTF-8, 3074 internal nulls
LinkedTo read failed at pos 52132: Invalid pin array count: -65536 (negative)
FString at pos 48395: length=4864, encoding=UTF-8, 3244 internal nulls
LinkedTo read failed at pos 53272: Invalid pin array count: -809614492 (negative)
```

**代码位置与根因：**

1. **`archive.py:233-258` — `read_fstring()`**
   - 当 FString 的 length 字段本身就是错误值时（因为前面某个字段偏移错位），读取的 length 可能是二进制数据被解释为 i32
   - 当前代码在检测到 "internal null bytes" 时返回空字符串 `""`，但**已经消费了 `length` 字节的数据**
   - 问题：如果 `length` 本身就是错误值，消费的 `length` 字节可能不是正确的字节数，导致后续所有字段错位

2. **`graph.py:462-468` — `read_ue_graph_pin()` LinkedTo 读取**
   - `read_pin_array()` 读取 `array_count = archive.read_i32()` 后，因前面 FString 错位，读到的 i32 是垃圾数据
   - `array_count` 为负数或超大值 → 触发 `ParseError` → 被 `except` 捕获 → `linked_to = []`
   - **这是 Connections=0 的直接原因**：所有 Pin 的 linked_to_raw 都是空数组

3. **`flow_builder.py:656-661` — `build_connections_map()` 验证**
   - Phase 72-G 已添加 `linked_to_count == 0` 警告
   - 但这仅是检测，不修复

**依赖链：**
```
FString 内部 null 字节 → 返回 "" 但偏移可能错位 → 后续字段读到错误数据
  → LinkedTo array_count 为垃圾值 → ParseError → linked_to = []
    → build_connections_map() 无数据 → connections = 0
```

**与 Phase 72-H 的重叠：**
- Phase 72-H 计划修复：FString 容错增强 + LinkedTo 滑动恢复 + StructValue JSON 序列化
- **I-01 的根因在 Phase 72-H 的 Wave 2（FString 容错增强）**——如果 FString 读取后指针位置始终正确，LinkedTo 就不会读到垃圾数据
- **但 Phase 72-H 尚未执行**（当前分支 2.11-dev 上只有计划文档）

**风险评估：**
- Blast radius: HIGH — FString 影响 ~30 个读取位置
- 回归风险: MEDIUM — 修改 archive.py 影响全局

---

### 根因 B: 节点发现遗漏 → K2Node_EnhancedInputAction/Knot 缺失 (I-02, I-03, I-04)

**参考基线：** 蓝图节点文本参考.md 列出 17 个 EventGraph 节点

**节点清单（从参考文件提取）：**

| 类型 | 数量 | 实例名 |
|------|------|--------|
| K2Node_EnhancedInputAction | 4 | _2(IA_Look), _3(IA_Move), _5(IA_Jump), _0(IA_MouseLook) |
| K2Node_CallFunction | 8 | _1193(Jump), _9386(StopJumping), _5(Move), _4(Move), _11(Aim), _6(Aim), _7(Aim), _7346/7445(AddMovementInput) |
| K2Node_Event | 5 | _2(PrimaryThumbstick), _3(SecondaryThumbstick), _4(TouchJumpStart), _5(TouchJumpEnd) |
| EdGraphNode_Comment | 3 | _1(Camera Input), _4(Movement Input), _0(Jump Input) |
| K2Node_Knot | 4 | (连线转接) |
| K2Node_FunctionEntry | 1 | _0(Move) — 但实际上还应有 Aim/JumpStart/JumpEnd 的 FunctionEntry |

**代码位置与根因：**

1. **`graph.py:1039-1057` — `read_ue_graph()` 主路径**
   - 读取 `nodes_count = archive.read_i32()`
   - 循环 `nodes_count` 次，每次读取 `node_index = archive.read_i32()`
   - **问题**：如果 `nodes_count` 本身不正确（如 UE5 序列化格式差异），只读取部分节点
   - 当前解析得到 9 个节点，说明 `nodes_count` 可能只读到了 9

2. **`graph.py:1059-1090` — fallback 路径**
   - 条件：`nodes_count == 0 or len(nodes) == 0`
   - **问题**：当 `nodes_count > 0` 且 `len(nodes) > 0` 时，fallback 不触发
   - 当前 9 个节点已被主路径收集，所以 fallback 不执行
   - 遗漏的 8 个节点（4 EnhancedInputAction + 4 Knot）可能是 `nodes_count` 不包含它们

3. **节点类名解析 `graph.py:986`**
   - `class_name = _rcn(node_export.class_index, import_map, export_map, linker)`
   - K2Node_EnhancedInputAction 的 class_index 指向 import_map 中的 `/Script/InputBlueprintNodes.K2Node_EnhancedInputAction`
   - K2Node_Knot 的 class_index 指向 `/Script/BlueprintGraph.K2Node_Knot`
   - **如果这些 import 条目的 class_name 被解析为短名（去掉模块路径前缀），则应能正确匹配**
   - **但如果 `read_ue_graph()` 的主路径根本没有遍历到这些节点的 export，它们就不会被发现**

4. **`graph.py:1068` — fallback 过滤条件**
   ```python
   if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
   ```
   - K2Node_EnhancedInputAction 和 K2Node_Knot 都以 "K2Node" 开头，理论上能通过过滤
   - **但 fallback 只在主路径为空时触发，而主路径已收集 9 个节点**

**根因结论：** 主路径 `nodes_count` 读取可能正确但只包含部分节点（UE5 的 UEdGraph::Serialize 可能只序列化直接引用的节点），K2Node_EnhancedInputAction 和 K2Node_Knot 可能通过其他引用关系被关联，需要 fallback 路径的 outer_index 扫描来发现。

**修复方案：** 即使主路径收集了节点，也执行 outer_index 扫描来补充遗漏节点（去重处理已有逻辑）。

---

### 根因 C: StructProperty 解析问题 → Rotation/Location/Size 错误 (I-05, I-06, I-07, I-08)

**参考基线：**

| 属性 | 参考值 | 当前输出 | 差异 |
|------|--------|----------|------|
| Camera RelativeRotation | (0, 90, -90) | (0, 0, 0) | 全零 |
| Camera RelativeLocation | (-2.8, 5.89, 0) | (0, -2.8125, 0) | X/Y 交换 + 精度 |
| LastEditedDocuments/CategoryName/BodyInstance | 正常解析 | ParseError | Size 越界 |

**代码位置与根因：**

1. **`property_types.py:156-173` — Vector/Rotator 快速路径（Phase 72-G 已添加）**
   - Phase 72-G 添加了 Vector/Rotator/Vector2D 的快速解析路径
   - **但存在前提条件**：`_extract_struct_type_from_tag(tag)` 必须正确提取类型名
   - 如果 PropertyTag 的类型名字符串解析失败（返回 "UnknownStruct"），快速路径不触发
   - **快速路径不触发时，走 PropertyTags 循环**，如果循环内部解析失败（如 BodyInstance），可能导致偏移错位

2. **`property_tags.py:113-165` — `read_property_tag()` 类型名链式读取**
   - UE5 格式：FPropertyTypeNameNode 链式格式
   - 读取循环：`pending = 1; while pending > 0: node_name + inner_count; pending = pending - 1 + inner_count`
   - **如果 `inner_count` 被错误读取（因偏移错位），会导致类型名字符串构建错误**
   - 例如：`StructProperty(Vector(/Script/CoreUObject))` 可能被构建为 `StructProperty(UnknownNode)`

3. **I-05 RelativeRotation 全零的具体分析：**
   - 快速路径已添加：`if struct_type == "Rotator": pitch/yaw/roll = archive.read_f32()`
   - **如果仍然全零，说明快速路径未被触发**——即 `_extract_struct_type_from_tag(tag)` 返回的不是 "Rotator"
   - 另一种可能：**属性根本没被解析到**——如果前面某个属性的 Size 错误导致跳过了太多字节，整个属性循环提前终止

4. **I-08 RelativeLocation 不完整的具体分析：**
   - 参考值 (-2.8, 5.89, 0) vs 当前 (0, -2.8125, 0)
   - X 和 Y 似乎被交换了，且 Z=0 正确
   - **Vector 快速路径读取顺序是 X, Y, Z**——如果 `struct_type` 不是 "Vector" 而走了 PropertyTags 循环，循环内的字段顺序可能不同
   - 另一种可能：这是另一个 Vector 属性（不是 RelativeLocation），当前解析顺序错乱

5. **I-06 Size 越界的具体分析：**
   - "3 个属性 Size 越界"——PropertyTag 的 size 字段读到了异常大的值
   - 根因：前面某个属性的读取消耗了不正确的字节数，导致后续 PropertyTag 的 name/type/size 字段被从错误位置读取

**关键发现：** Phase 72-G 的快速路径修复是正确的，但**如果前面有 FString 偏移错误或 PropertyTag 类型名链式解析错误，快速路径可能根本没机会执行**。这是一个级联错误。

---

### 根因 D: EdGraphNode_Comment 字段缺失 (I-09)

**参考基线：** 蓝图节点文本参考.md 中 Comment 节点含 CommentColor、NodeWidth、NodeHeight、NodeComment 等字段

**代码位置与根因：**

1. **`graph.py:661-678` — `read_edgraph_node_comment()`**
   - 当前只读取：comment_color(4 float) + node_width + node_height + font_size
   - **缺失字段**：bCommentBubbleVisible_InDetailsPanel、CommentDepth、bCommentBubblePinned、bCommentBubbleVisible
   - 但更重要的是 **NodeComment**——这个字符串在 `read_ue_graph_node()` 的 PropertyTag 循环中解析（L932-933），不在 `read_edgraph_node_comment()` 中
   - 如果 PropertyTag 循环在 Comment 节点上也遇到偏移错误，NodeComment 可能读取失败

2. **`graph.py:771` — fallback 处理**
   - 当前日志显示：`Fallback processing for unknown type: EdGraphNode_Comment`
   - **这条日志不应该出现**——因为 `create_node_from_archive()` 中已有 `EdGraphNode_Comment` 的分支
   - 如果出现，说明 `class_name` 没有被正确解析为 `EdGraphNode_Comment`

**修复方案：**
- 验证 `read_edgraph_node_comment()` 的字段完整性
- 确保 NodeComment 通过 PropertyTag 循环正确解析

---

### 根因 E: Blueprint.functions 为空 + 参数缺失 (I-10, I-11)

**参考基线：** C++ 类有 4 个蓝图可调用函数：DoMove, DoAim, DoJumpStart, DoJumpEnd

**代码位置与根因：**

1. **`variable_extractor.py:532-540` — 函数提取（Phase 72-G 已修改）**
   - 主路径：`_extract_functions_from_bpgc_properties(properties)` — 从 BPGC export 属性提取
   - Fallback：`_extract_functions_from_graphs(graphs)` — 从 K2Node_FunctionEntry 节点提取
   - 两者合并去重

2. **主路径问题：`_extract_functions_from_bpgc_properties()`**
   - 查找 `prop.name == "UbergraphFunction"` 和 `prop.name == "FunctionList"`
   - **问题**：如果 BPGC export 的属性解析本身失败（因 I-06 Size 越界），`properties` 可能为空或不完整
   - `UbergraphFunction` 的 value 是 ObjectProperty（FPackageIndex），需要解析为函数名
   - `FunctionList` 是 ArrayProperty，如果内部元素类型解析失败，value 也可能为空

3. **Fallback 路径问题：`_extract_functions_from_graphs()`**
   - 查找 `K2Node_FunctionEntry` 节点
   - **如果节点发现遗漏（I-02/I-04），FunctionEntry 节点可能不在 graphs 中**
   - 从 `node_data.function_reference.member_name` 提取函数名
   - **但当前 node_data 可能为 `{"_raw_properties": {...}}`**（未知类型 fallback），不含 function_reference

4. **I-11 参数缺失：**
   - 参数从 FunctionEntry 节点的 pins 提取
   - **依赖 Pin 序列化的完整性**——如果 Pin 读取失败（因 I-01 LinkedTo 错误），pins 列表可能不完整
   - Direction 比较使用整数 (`0`/`1`) 而非字符串 (`"EGPD_Input"`/`"EGPD_Output"`)——**需验证 UEdGraphPin.direction 的实际值**

**关键依赖：** I-10 和 I-11 都依赖 I-01（Pin 完整性）和 I-02/I-04（节点发现）

---

## 修复优先级排序（基于依赖链）

| 优先级 | 问题 | 依赖 | 说明 |
|--------|------|------|------|
| P0-1 | I-12 FString 偏移错误 | Phase 72-H | 根因修复，所有下游问题的源头 |
| P0-2 | I-01 Pin 连接丢失 | I-12 | FString 修复后 LinkedTo 自动恢复 |
| P1-1 | I-04 EventGraph 节点不足 | 无 | fallback 路径扩展，独立修复 |
| P1-2 | I-02 K2Node_EnhancedInputAction 缺失 | I-04 | 节点发现修复后自动恢复 |
| P1-3 | I-03 K2Node_Knot 缺失 | I-04 | 同上 |
| P1-4 | I-06 Size 越界 | I-12 | FString 修复后 PropertyTag 对齐恢复 |
| P2-1 | I-05 RelativeRotation 全零 | I-12, P1-4 | 快速路径已存在，需验证触发条件 |
| P2-2 | I-07 CharacterMovement 属性缺失 | I-12, P1-4 | 同上 |
| P2-3 | I-08 RelativeLocation 不完整 | I-12, P1-4 | 同上 |
| P2-4 | I-09 Comment 字段缺失 | I-04 | 节点发现 + 字段完整性 |
| P2-5 | I-10 Blueprint.functions | I-04, I-01 | 依赖节点和 Pin 完整性 |
| P3-1 | I-11 函数参数缺失 | I-10, I-01 | 依赖函数和 Pin 完整性 |

**推荐波次：**
- Wave 1: I-12 (FString) + I-04 (节点发现 fallback 扩展) — 独立并行
- Wave 2: I-01 + I-02 + I-03 + I-06 — Wave 1 后验证
- Wave 3: I-05 + I-07 + I-08 + I-09 + I-10 + I-11 — Wave 2 后验证

---

## 与已有 Phase 的重叠分析

| 问题 | Phase 72-G | Phase 72-H | 本 Phase |
|------|-----------|-----------|---------|
| I-12 FString 偏移 | 未修 | **Wave 2 目标** | 依赖 72-H 完成 |
| I-01 Connections=0 | M-02 添加验证日志 | **Wave 3 目标** | 验证 72-H 修复效果 |
| I-05 Rotation 全零 | M-01 添加快速路径 | — | 验证快速路径是否生效 |
| I-06 Size 越界 | M-01 类型名提取增强 | — | 验证 PropertyTag 对齐 |
| I-10 functions 空 | M-03 添加 BPGC 路径 | — | 验证 BPGC 解析完整性 |
| I-11 参数缺失 | M-04 添加参数提取 | — | 验证 Pin 数据完整性 |
| I-02/I-03 节点缺失 | 未覆盖 | 未覆盖 | **本 Phase 新增修复** |
| I-04 节点不足 | 未覆盖 | 未覆盖 | **本 Phase 新增修复** |
| I-08 Location 不完整 | 未覆盖 | 未覆盖 | **本 Phase 新增修复** |
| I-09 Comment 字段 | 未覆盖 | 未覆盖 | **本 Phase 新增修复** |
| StructValue JSON 崩溃 | 未覆盖 | **Wave 1 目标** | 阻塞 JSON 输出验证 |

**结论：**
- I-02/I-03/I-04/I-08/I-09 是 Phase 72-G 和 72-H **均未覆盖**的新问题
- I-05/I-06/I-07/I-10/I-11 在 Phase 72-G 有修复，但可能因 FString 偏移级联而未生效，需在 72-H 完成后重新验证
- **Phase 72-H 是 Phase 72-I 的前置依赖**，必须在 72-H 完成后再执行 72-I

---

## 风险评估

| 修复点 | Blast Radius | 回归风险 | 说明 |
|--------|-------------|---------|------|
| I-12 FString 容错 | HIGH — 全局 | MEDIUM | archive.py 修改影响所有解析 |
| I-04 fallback 扩展 | LOW — 仅 graph.py | LOW | 仅增加节点发现，不影响已有节点 |
| I-01 LinkedTo 恢复 | MEDIUM — graph.py | LOW | 72-H 的滑动恢复机制 |
| I-05/I-08 快速路径 | LOW — property_types.py | LOW | 已有代码，仅需验证触发 |
| I-06 Size 越界 | MEDIUM — property_tags.py | MEDIUM | PropertyTag 解析是核心路径 |
| I-09 Comment 字段 | LOW — graph.py | LOW | 仅读取额外字段 |
| I-10 functions 提取 | LOW — variable_extractor.py | LOW | 已有 BPGC 路径，需验证 |
| I-11 参数提取 | LOW — variable_extractor.py | LOW | 依赖 Pin 完整性 |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | 运行时 | 项目基础 |
| pytest | current | 测试 | 已有测试框架 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| 无新增依赖 | — | — | 本 Phase 不引入外部包 |

**安装：** 无需安装新包

---

## Architecture Patterns

### 系统架构图

```
.uasset 文件
    │
    ▼
FArchive (archive.py)
    │ read_i32, read_f32, read_fstring, read_name
    │
    ├─→ PropertyTag 读取 (property_tags.py)
    │       │ FPropertyTypeNameNode 链式解析
    │       ▼
    │   parse_property_value (property_parser.py)
    │       │ 类型分派
    │       ▼
    │   parse_struct_property (property_types.py)
    │       │ Vector/Rotator 快速路径 → StructValue
    │       │ 通用 PropertyTags 循环 → StructValue
    │       ▼
    │   PropertyValue (name, type, value)
    │
    ├─→ Graph 读取 (graph.py)
    │       │ read_ue_graph → nodes_count → node_index → read_ue_graph_node
    │       │                                          → read_ue_graph_pin → LinkedTo
    │       │ fallback: outer_index 扫描
    │       ▼
    │   UEdGraph (nodes, pins, connections)
    │
    └─→ Blueprint 元数据 (variable_extractor.py)
            │ BPGC 属性: UbergraphFunction + FunctionList
            │ Graph 节点: K2Node_FunctionEntry
            ▼
        BlueprintMetadata (variables, functions, events)
```

### 推荐项目结构

```
src/uasset_read/
├── archive.py              # FString 容错 (Phase 72-H)
├── serializers/
│   ├── graph.py            # 节点发现 fallback + LinkedTo + Comment
│   └── property_tags.py    # PropertyTag 类型名解析
├── parsers/
│   ├── property_types.py   # Vector/Rotator 快速路径 (已有)
│   └── property_parser.py  # 属性分派
├── blueprint/
│   └── variable_extractor.py  # BPGC 函数提取 (已有)
├── graph/
│   └── flow_builder.py     # connections 映射
└── formatters/
    └── json_formatter.py   # StructValue 递归序列化 (Phase 72-H)
```

### Pattern 1: 级联错误恢复

**What:** 当一个字段的读取失败时，不应导致后续所有字段错位
**When to use:** FString 读取、PropertyTag 读取、Pin 序列化
**Example:**

```python
# 当前代码（graph.py L462-468）
try:
    linked_to = read_pin_array(archive, ...)
except Exception as e:
    logger.error("LinkedTo read failed at pos %d: %s", linkedto_start, e)
    linked_to = []  # 错误：位置可能错位

# 改进：失败后尝试恢复到正确位置
try:
    linked_to = read_pin_array(archive, ...)
except Exception as e:
    logger.error("LinkedTo read failed at pos %d: %s", linkedto_start, e)
    linked_to = []
    # 恢复：根据 tag.size 或预期结构跳到正确位置
    expected_end = linkedto_start + expected_linkedto_size
    archive.seek(expected_end)
```

### Anti-Patterns to Avoid

- **静默丢弃异常数据：** `except Exception: linked_to = []` 不恢复位置，导致后续读取全部错位
- **假设 nodes_count 完整：** UE5 UEdGraph 的 nodes_count 可能不包含通过 outer_index 关联的节点
- **单路径发现：** 只依赖主路径或只依赖 fallback，不合并两者

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FString 偏移恢复 | 自定义 seek-back 逻辑 | Phase 72-H 的 `expected_bytes` 边界防卫 | 已有计划，不重复实现 |
| Pin 连接映射 | 手动遍历 linked_to_raw | `build_connections_map()` | 已有完整实现 |
| 类型名提取 | 自定义字符串解析 | `_extract_struct_type_from_tag()` + `_build_complete_type_string()` | 已有完整实现 |

---

## Common Pitfalls

### Pitfall 1: FString 检测内部 null 后返回空字符串但不恢复位置

**What goes wrong:** `read_fstring()` 检测到内部 null 字节后返回 `""`，但 `length` 字段对应的字节已经消费，如果 `length` 本身就是错误值，后续位置全部错位
**Why it happens:** 代码假设 `length` 字段正确，只检查了数据内容（是否有 null 字节），没检查 `length` 是否合理
**How to avoid:** Phase 72-H 的 `expected_bytes` 边界防卫 + 异常 length 回退指针
**Warning signs:** 日志中大量 "FString contains internal null bytes" + "suspicious length"

### Pitfall 2: 节点发现 fallback 只在主路径为空时触发

**What goes wrong:** 主路径收集了 9 个节点后 fallback 条件 `nodes_count == 0 or len(nodes) == 0` 为 False，遗漏 8 个节点
**Why it happens:** 条件过于保守，UE5 的 UEdGraph 可能只序列化部分节点引用
**How to avoid:** 始终执行 outer_index 扫描，与主路径合并去重
**Warning signs:** EventGraph 节点数少于预期，K2Node_EnhancedInputAction 缺失

### Pitfall 3: 快速路径添加后未验证触发条件

**What goes wrong:** Vector/Rotator 快速路径已添加，但 `_extract_struct_type_from_tag()` 可能返回 "UnknownStruct"，快速路径不触发
**Why it happens:** PropertyTag 类型名链式解析受前面偏移错误影响
**How to avoid:** 在快速路径不触发时添加调试日志，验证 `struct_type` 的实际值
**Warning signs:** Rotation 全零，Location 不完整

### Pitfall 4: ParentPin/ReferencePassThrough 条件读取

**What goes wrong:** UE5 中 ParentPin 和 ReferencePassThroughConnection 的 GUID 只在 `b_null_ptr == 0` 时存在，Phase 72-G 之前始终读取 16 字节 GUID
**Why it happens:** 旧代码假设 UE5 始终写入 24 字节（null + owning + guid），实际格式是条件写入
**How to avoid:** Phase 72-G 已修复为条件读取，需验证修复生效
**Warning signs:** Pin 读取位置偏移，LinkedTo 数据错位

---

## Code Examples

### 示例 1: 节点发现 fallback 扩展

```python
# graph.py read_ue_graph() — 当前条件
if (nodes_count == 0 or len(nodes) == 0) and graph_export_idx > 0:
    # fallback only when main path empty

# 改进：始终执行 outer_index 扫描
if graph_export_idx > 0:
    # 合并 outer_index 关联节点（去重）
    for node_export in export_map:
        if node_export.outer_index.index == graph_export_idx:
            # ...existing dedup logic
```

### 示例 2: 快速路径验证日志

```python
# property_types.py parse_struct_property()
struct_type = _extract_struct_type_from_tag(tag)

if struct_type in ("Vector", "Rotator", "Vector2D"):
    logger.debug("Fast-path triggered for struct_type=%s at pos %d", struct_type, archive.tell())
else:
    logger.debug("PropertyTags loop for struct_type=%s (tag.type=%s) at pos %d", struct_type, tag.type, archive.tell())
```

### 示例 3: EdGraphNode_Comment 完整字段

```python
# graph.py read_edgraph_node_comment()
# 当前：comment_color(4f) + node_width + node_height + font_size
# 参考基线还有：bCommentBubbleVisible_InDetailsPanel, CommentDepth, etc.
# 这些字段在 PropertyTag 循环中通过 NodeComment 读取
# 确保 read_ue_graph_node() 的 PropertyTag 循环正确解析 NodeComment
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vector/Rotator 用 PropertyTags 循环 | 快速路径直接读取 3 float | Phase 72-G | 性能提升 + 准确性提升 |
| LinkedTo 失败静默返回 [] | 添加验证日志 | Phase 72-G | 可诊断但未修复 |
| functions 仅从 Graph 提取 | BPGC 属性 + Graph 双路径 | Phase 72-G | 覆盖更多函数 |
| ParentPin 始终读 24B | 条件读取 8B/24B | Phase 72-G | 修复偏移错位 |
| FString null_ratio 过滤 | 内部 null 字节检测 + 返回空 | Phase 72-G 前后 | 容错策略变化 |

**Deprecated/outdated:**
- null_ratio > 0.3 的二进制检测方式：已被 `'\x00' in result` 替代

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 72-H 会修复 FString 偏移错误 | 根因 A | I-01 无法修复，需自行实现 |
| A2 | nodes_count 读取正确但只含部分节点 | 根因 B | 节点遗漏原因不同 |
| A3 | K2Node_EnhancedInputAction 的 class_index 能被正确解析为短类名 | 根因 B | fallback 仍无法发现这些节点 |
| A4 | Vector/Rotator 快速路径代码正确，但触发条件未满足 | 根因 C | 快速路径本身有 bug |
| A5 | Direction 字段使用整数 0/1 而非字符串 | 根因 E | 参数提取的 Direction 比较失败 |
| A6 | read_edgraph_node_comment() 的字段序列化顺序正确 | 根因 D | Comment 节点解析偏移 |

---

## Open Questions

1. **Phase 72-H 是否已完成？**
   - What we know: 72-H 有计划文档但尚未执行（无实现代码）
   - What's unclear: 执行时间线
   - Recommendation: Phase 72-I 的 Wave 1 可先执行节点发现修复（不依赖 72-H），FString 相关修复等 72-H 完成后验证

2. **UE5 UEdGraph Serialize 是否只序列化直接子节点？**
   - What we know: 当前 `nodes_count` 读取到 9，参考基线有 17
   - What's unclear: UE5 是否通过 outer_index 关联其余节点
   - Recommendation: 实现始终执行的 outer_index 扫描来发现所有关联节点

3. **_extract_struct_type_from_tag() 对实际 BP_FirstPersonCharacter PropertyTag 的返回值是什么？**
   - What we know: 快速路径已添加但 Rotation 仍全零
   - What's unclear: 是否因 FString 偏移导致类型名解析失败
   - Recommendation: 在快速路径前添加 struct_type 调试日志

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 运行时 | Yes | 3.14 | -- |
| pytest | 测试 | Yes | current | -- |
| BP_FirstPersonCharacter.uasset | 测试资产 | Yes | -- | -- |
| 蓝图节点文本参考.md | 参考基线 | Yes | -- | -- |

**Missing dependencies with no fallback:** 无

**Missing dependencies with fallback:** 无

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml |
| Quick run command | `python -m pytest tests/ -v -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| I-01 | EventGraph connections >= 9 | integration | `pytest tests/test_phase72i_connections.py -v` | Wave 0 |
| I-02 | K2Node_EnhancedInputAction >= 4 | integration | `pytest tests/test_phase72i_nodes.py -v` | Wave 0 |
| I-03 | K2Node_Knot >= 4 | integration | `pytest tests/test_phase72i_nodes.py -v` | Wave 0 |
| I-04 | EventGraph nodes >= 13 | integration | `pytest tests/test_phase72i_nodes.py -v` | Wave 0 |
| I-05 | Camera RelativeRotation = (0, 90, -90) | unit | `pytest tests/test_phase72i_structs.py -v` | Wave 0 |
| I-06 | Size 越界属性正常解析 | unit | `pytest tests/test_phase72i_structs.py -v` | Wave 0 |
| I-07 | CharacterMovement 属性提取 | unit | `pytest tests/test_phase72i_structs.py -v` | Wave 0 |
| I-08 | Camera RelativeLocation ≈ (-2.8, 5.89, 0) | unit | `pytest tests/test_phase72i_structs.py -v` | Wave 0 |
| I-09 | Comment 含 NodeComment | unit | `pytest tests/test_phase72i_nodes.py -v` | Wave 0 |
| I-10 | Blueprint.functions 含 4 函数 | unit | `pytest tests/test_phase72i_functions.py -v` | Wave 0 |
| I-11 | 函数参数信息非空 | unit | `pytest tests/test_phase72i_functions.py -v` | Wave 0 |
| I-12 | FString suspicious length < 3 | integration | `pytest tests/test_phase72i_fstring.py -v` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -v -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green + BP_FirstPersonCharacter.uasset 解析输出验证

### Wave 0 Gaps
- [ ] `tests/test_phase72i_connections.py` — covers I-01
- [ ] `tests/test_phase72i_nodes.py` — covers I-02, I-03, I-04, I-09
- [ ] `tests/test_phase72i_structs.py` — covers I-05, I-06, I-07, I-08
- [ ] `tests/test_phase72i_functions.py` — covers I-10, I-11
- [ ] `tests/test_phase72i_fstring.py` — covers I-12

---

## Security Domain

> 本 Phase 仅涉及解析逻辑修复，无安全敏感操作。ASVS 类别均不适用。

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | -- |
| V3 Session Management | no | -- |
| V4 Access Control | no | -- |
| V5 Input Validation | no | -- |
| V6 Cryptography | no | -- |

---

## Sources

### Primary (HIGH confidence)
- `src/uasset_read/serializers/graph.py` — 代码分析 [VERIFIED: codebase]
- `src/uasset_read/archive.py` — 代码分析 [VERIFIED: codebase]
- `src/uasset_read/parsers/property_types.py` — 代码分析 [VERIFIED: codebase]
- `src/uasset_read/blueprint/variable_extractor.py` — 代码分析 [VERIFIED: codebase]
- `references/蓝图节点文本参考.md` — 参考基线 [VERIFIED: project reference]
- `references/测试对照C++类/FirstPersonCCharacter.h` — 参考基线 [VERIFIED: project reference]
- `references/测试对照C++类/FirstPersonCCharacter.cpp` — 参考基线 [VERIFIED: project reference]

### Secondary (MEDIUM confidence)
- `.planning/phases/phase-72g/RESEARCH.md` — Phase 72-G 根因分析 [CITED: project docs]
- `.planning/phases/phase-72h/PLAN.md` — Phase 72-H 计划 [CITED: project docs]
- BP_FirstPersonCharacter.uasset 实测输出 — 当前状态验证 [VERIFIED: runtime output]

### Tertiary (LOW confidence)
- CUE4Parse UEdGraph.cs 序列化模式 — 节点发现参考 [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- FString/LinkedTo 根因: HIGH — 实测日志确认级联错误
- 节点发现遗漏: MEDIUM — 推测 nodes_count 不完整，需验证
- Struct 属性错误: MEDIUM — 快速路径已添加，但触发条件未验证
- 元数据提取: MEDIUM — 依赖上游修复
- Comment 字段: LOW — 需深入验证序列化顺序

**Research date:** 2026-05-24
**Valid until:** 2026-06-24 (UE5 format stable)
