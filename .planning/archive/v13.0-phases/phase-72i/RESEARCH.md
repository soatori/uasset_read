---
gsd_state_version: 1.2
phase: 72-I
research_type: root-cause-analysis-with-ue-source
---

# Phase 72-I: BP_FirstPersonCharacter 全量对比修复 - Research

**Researched:** 2026-05-24
**Domain:** UE5 .uasset 蓝图图解析 — 节点发现、Pin 连接、StructProperty、BP 元数据
**Confidence:** HIGH

## Summary

通过对 `graph.py` (`read_ue_graph`/`read_ue_graph_node`/`create_node_from_archive`/`read_pin_array`)、`archive.py` (`read_fstring`)、`property_types.py` (`parse_struct_property`/`_extract_struct_type_from_tag`)、`property_tags.py` (`read_property_tag`)、`blueprint/variable_extractor.py` 六个关键文件的逐行分析，并与 `蓝图节点文本参考.md`（18 个 EventGraph 节点完整序列化）+ `FirstPersonCCharacter.h/cpp` 三方对比，确认 **12 项问题的根本原因是单一故障源（FString 偏移错位）引发的三级级联效应**。

**Primary recommendation:** 以 FString 位置完整性修复（Phase 72-H Wave 2 增强版）为根修复，配合 `read_ue_graph()` fallback 条件放宽（IF-01），可在单波次内解决 8/12 项问题。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FString 二进制读取 | FArchive (archive.py) | — | 流式读取层，所有上层依赖其位置正确性 |
| PropertyTag 类型名链式读取 | serializers/property_tags.py | — | FPropertyTypeNameNode 链式解析，依赖 FArchive 位置 |
| StructProperty 快径读取 | parsers/property_types.py | serializers/property_tags.py | 依赖上游 tag.type 字符串正确性 |
| 图节点发现 | serializers/graph.py:read_ue_graph | graph/parser.py | 主路径 + outer_index fallback |
| Pin 连接读取 | serializers/graph.py:read_pin_array | archive.py:read_fstring | LinkedTo count 的正确性依赖上游所有字段 |
| BP 函数元数据 | blueprint/variable_extractor.py | serializers/graph.py | BPGC 路径优先，Graph fallback 依赖节点解析成功 |
| Comment 字段 | serializers/graph.py | archive.py:read_fstring | NodeComment 通过 FString 读取 |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Phase 72-H 已规划的 FString 容错和 LinkedTo 恢复机制不可推翻，本 Phase 为其补充和增强
- 必须使用 FArchive 流式读取，禁止 raw byte seek+read（遵守 no-byte-reading feedback）
- 修复必须保持全量测试无回归（目标 >= 1319 tests pass）

### Claude's Discretion
- 具体的修复波次顺序和每个修复的代码实现细节
- fallback 触发条件的具体阈值
- 是否将 outer_index 扫描变为始终执行

### Deferred Ideas (OUT OF SCOPE)
- 无

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| I-01 | Pin 连接完全丢失 | R-B-1: FString 级联 → LinkedTo count 乱码。Phase 72-H Wave 3 覆盖表层修复，本 Phase 通过 Wave 0 根修复+Wave 1 fallback 解决根因 |
| I-02 | K2Node_EnhancedInputAction 缺失 | R-A-2: fallback 条件过窄。create_node_from_archive 有处理器但 read_ue_graph_node 本身在脚本序列化/Pin 读取阶段失败 |
| I-03 | K2Node_Knot 缺失 | R-A-2: 同 I-02。Knot 节点在 Move 子图中，主路径解析失败后 fallback 不触发 |
| I-04 | EventGraph 节点总数不足 | R-A-2: 9/18→18 的差距。主路径部分节点 ParseError 后 fallback 条件不满足 |
| I-05 | Camera RelativeRotation 全零 | R-C-1: 上游 FString 损坏→tag.type 错误→_extract_struct_type_from_tag 返回 UnknownStruct→快径未命中 |
| I-06 | 3 个属性 Size 越界 | R-C-2: read_property_tag 在错误位置读取 tag.size，值为垃圾 |
| I-07 | CharacterMovement 属性缺失 | R-C-3: 因 I-06 Size 越界，BPGC 属性循环提前终止或跳过 |
| I-08 | Camera RelativeLocation 不完整 | R-C-1: 同 I-05，Vector 快径读取位置不对 |
| I-09 | Comment 字段缺失 | R-D: NodeComment 通过 read_fstring 读取，受 FString 偏移错误影响；bCommentBubble* / CommentDepth 在 PropertyTag 循环中未被专门处理 |
| I-10 | Blueprint.functions 为空 | R-E: BPGC 属性路径因 I-06 失败；Graph fallback 依赖 FunctionEntry 节点解析成功 |
| I-11 | 函数参数信息缺失 | R-E: 函数参数从 Pins 提取，依赖 Pin 解析成功（受 I-01 影响） |
| I-12 | FString 偏移错误连锁 | R-B: 级联根因。Phase 72-H Wave 2 覆盖基础容错，本 Phase 补充"length 字段本身为垃圾值"的恢复策略 |

---

## 根因分析

### R-A: 节点发现 (I-02, I-03, I-04)

#### R-A-1: 主路径 `nodes_count` 迭代逻辑

**代码位置:** `src/uasset_read/serializers/graph.py` L1039-1057

```
for _ in range(nodes_count):          # L1048
    node_index = archive.read_i32()    # L1049 — 从 graph 序列化数据读取节点索引
    if node_index > 0 and node_index <= len(export_map):
        node_export = export_map[node_index - 1]   # L1051
        try:
            node = read_ue_graph_node(...)          # L1053
            nodes.append(node)
        except ParseError:
            failed_nodes.append(node_export.object_name)  # L1057 — 丢失！
```

**根因 (R-A-1):** `node_index` 的值是 UE 在序列化 UEdGraph 时写入的 export index 数组。如果 `nodes_count` 本身正确（例如 18），但某些 `node_index` 指向的 export 其 `read_ue_graph_node()` 失败（原因见 R-B），该节点静默丢失，`failed_nodes` 仅记录名称但没有任何恢复动作。

**关键发现:** `read_ue_graph_node()` 对每个节点执行 `archive.seek(node_export.serial_offset)` (L804)，因此节点之间的位置错误不会相互传染。每个节点的失败是独立的、由该节点自身数据决定的。

#### R-A-2: Fallback 条件过窄

**代码位置:** `src/uasset_read/serializers/graph.py` L1061

```python
if (nodes_count == 0 or len(nodes) == 0) and graph_export_idx > 0:
```

**根因 (R-A-2):** 条件要求 `len(nodes) == 0`（全部失败）才触发 fallback。当 `nodes_count = 18` 且 9 个成功、9 个失败时，`len(nodes) = 9 > 0`，**fallback 不触发**。丢失的 9 个节点（含 4 个 EnhancedInputAction）永远不会被尝试恢复。

**对"如果始终执行 outer_index 扫描合并去重，会有副作用吗？"的回答:** 无副作用。理由：
1. outer_index 扫描对每个匹配 export 执行 `archive.seek(node_export.serial_offset)`——独立的起始位置，不依赖之前的读取状态
2. 去重逻辑 (L1071-1076) 通过 `_export_index` 精确匹配，不会重复添加主路径已成功解析的节点
3. 唯一代价是 O(N) 次 export_map 遍历（N = export_map 大小，通常 < 100），性能影响可忽略

**修复方向:** 将条件改为 `(nodes_count == 0 or len(nodes) < nodes_count) and graph_export_idx > 0`，或激进地 **始终执行** outer_index 扫描（无前置条件）。推荐后者——彻底且无副作用。

**Phase 72-H 覆盖:** 否。Phase 72-H 未涉及 `read_ue_graph()` 的 fallback 逻辑。

#### R-A-3: EnhancedInputAction/Knot 节点在 `read_ue_graph_node()` 中失败的具体位置

**代码位置:** `src/uasset_read/serializers/graph.py` L794-1007 (`read_ue_graph_node`)

`read_ue_graph_node()` 包含两个阶段：
1. **script_serial PropertyTag 循环** (L817-940): 解析 FunctionReference/EventReference/NodePosX/NodeGuid/NodeComment 等
2. **Pins 数组读取** (L942-984): 解析 Pin 引用头 + 完整 UEdGraphPin

EnhancedInputAction 节点的特点:
- 类名格式: `/Script/InputBlueprintNodes.K2Node_EnhancedInputAction`（不同于 `/Script/BlueprintGraph.K2Node_CallFunction`）
- 11 个 Pin（含大量数据 pin + SubPins），PinType.PinSubCategoryObject 包含 FSoftObjectPath
- script_serial 中可能包含 `InputAction` 等特有 PropertyTag

**根因 (R-A-3) — 两种可能:**

可能性 A: `node_index` 超出范围
- 在 L1049-1050 处，如果 graph 序列化中该位置的 `node_index` 因上游偏移错位读到了无效值（0、负数、> len(export_map)），节点在进入 `read_ue_graph_node()` 之前就被跳过

可能性 B: `read_ue_graph_node()` 内部 ParseError
- Pin 读取阶段某个 Pin 的 FString/FText 读取触发 ParseError（L983-984 `except Exception: continue` 仅跳过该 Pin，不终止节点）
- script_serial 循环中 PropertyTag 读取失败（L845-850 break 退出循环）——这更可能导致接下来的 `pins_count` 读取错位

**验证方法:** 在 L1050 `if` 添加 `else` 分支记录跳过的 `node_index` 值。在 `read_ue_graph_node()` 开头添加 debug 日志记录进入的节点名。

---

### R-B: Pin 连接 (I-01, I-12)

#### R-B-1: FString 级联故障链

**代码位置:** 
- `src/uasset_read/archive.py` L233-258 (`read_fstring`)
- `src/uasset_read/serializers/graph.py` L441-468 (`read_ue_graph_pin` → LinkedTo 段)

**完整故障链（已通过分析报告中的 pos 93732→94001 证据确认）:**

```
Step 1: read_fstring() 在 pos P 读取
        length = 128 (垃圾值，实际该位置是二进制)
        data = read(128)  — 128 bytes consumed
        检测到内部 null → 返回 ""
        实际偏移: P → P+4+128 = P+132 (length 所声称的字节数已消费)
        逻辑偏移: 应该消费 4+N bytes (N=正确字符串长度)

Step 2: 紧接的下一个 read_i32() 在 pos P+132 读取
        实际读到的是 Step 1 中本应属于其他字段的 4 bytes
        例如: LinkedTo array_count = 8352 (本应是 1-3)
        
Step 3: read_pin_array() 收到 array_count=8352
        过程极度缓慢且必然产生更多错误
        或直接触发 MAX_LINKEDTO_PER_PIN 限制 → ParseError

Step 4: read_ue_graph_pin() L466-468:
        except Exception: linked_to = []
        错误被吞掉，archive 位置停留在一个未定义位置
```

**关于"LinkedTo 失败后 archive position 是否仍然正确？"的回答:** **不正确。** `read_pin_array()` 在检测到 `array_count > MAX_LINKEDTO_PER_PIN` 时抛出 ParseError（在消费任何 pin 数据之前），但 `array_count` 的 4 bytes 已被消费，且异常处理没有 seek 回 `linkedto_start`。archive 位置比 `linkedto_start` 多前进 4 bytes。

#### R-B-2: Phase 72-H Wave 2 的边界分析

Phase 72-H 规划的 `expected_bytes` 边界防卫:

```python
expected_bytes = length if length > 0 else (-length * 2)
if expected_bytes > MAX_FSTRING_LENGTH:
    raise ParseError(...)  # 长度异常 → 抛异常
data = self.read(expected_bytes)
if internal_null_count > 0:
    return ""  # 内部 null → 返回空，但位置正确
```

**覆盖范围:**
- length 值在合法范围但指向二进制数据: 正确处理（警告+返回空，位置正确）
- length 值为巨大的正数（超出 MAX_FSTRING_LENGTH）: 被拦截
- **length 值为中等异常值（如 32-256，恰好在合法范围内）但位置已错位**: 未被覆盖

  这是 I-12 最隐蔽的情况：当 archive 位置在上一个 FString 错位后已经错误，下一个 `read_fstring()` 读到的 `length` 来自完全错误的字节。该 length 值恰好在 `0 < length <= MAX_FSTRING_LENGTH` 范围内，通过边界检查，但在错误位置消费了错误字节数。

**关键缺失:** Phase 72-H 的修复假设 `read_fstring()` 在正确的 archive 位置被调用。当上游已存在位置错误时，该修复无法感知也无法纠正。

#### R-B-3: 深度恢复策略建议

对于"length 字段本身为垃圾值"的情况，需要在 `read_fstring()` 中增加 **合理性验证**：

```
1. 记录 start_pos = archive.tell() - 4  (length 字段的起始位置)
2. 读取 length (4 bytes consumed)
3. 验证 length 的合理性:
   a. length == 0: 合法空字符串
   b. abs(length) <= 4: 极短字符串 → 标记为可疑（FString 极少 ≤4 bytes）
   c. 检查 data 前 4 bytes 是否看起来像另一个 i32（嵌套长度）→ 二进制信号
4. 读取 data[0:expected_bytes]
5. 如果结果可疑 + 内部 null 存在:
   a. 尝试 seek 回 start_pos + 4 (仅消费 length)
   b. 尝试将 data 重新解释为二进制结构
   c. 记录 recovery 日志
```

**Phase 72-H 覆盖:** 部分。Wave 2 覆盖了基础容错（合法 length+二进制数据），未覆盖"位置已错位时 length 值本身为垃圾"的深度恢复。

---

### R-C: StructProperty 解析 (I-05, I-06, I-07, I-08)

#### R-C-1: Camera RelativeRotation 全零 (I-05) 和 RelativeLocation 不完整 (I-08)

**代码位置:**
- `src/uasset_read/parsers/property_types.py` L158-173 (Vector/Rotator 快径)
- `src/uasset_read/serializers/property_tags.py` L113-165 (`read_property_tag`)
- `src/uasset_read/parsers/property_types.py` L330-372 (`_extract_struct_type_from_tag`)

**故障机制:**

```
Step 1: read_property_tag() 读取 FPropertyTypeNameNode 链式结构
        node_name = archive.read_name(name_map)  — 依赖 name_map 索引 (L137)
        inner_count = archive.read_i32()          — L138
        如果 archive 位置在上游 FString 错位后已偏移:
        → node_name 读到垃圾名称或 "None"
        → inner_count 读到垃圾值
        → type_parts 列表包含错误条目
        
Step 2: _build_complete_type_string(type_parts) 构建 tag.type
        例如: "IntProperty" 而不是 "StructProperty(Vector(/Script/CoreUObject))"

Step 3: parse_struct_property() 执行:
        struct_type = _extract_struct_type_from_tag(tag)  — L154
        tag.type 不以 "StructProperty" 开头 → 返回 "UnknownStruct"

Step 4: struct_type == "Vector" / "Rotator" 快径条件全部为 False
        进入通用 PropertyTag 循环 (L181-194)
        
Step 5: 通用循环尝试读取 inner_tag
        如果 archive 位置完全错误，read_property_tag 返回 name="None"
        → fields 为空 → StructValue(struct_type="UnknownStruct", fields={})
        → 值全部丢失 (I-05 全零, I-08 不完整)
```

**关键证据:** `_extract_struct_type_from_tag()` (L330-372) 假设 `tag.type` 格式正确。当 `tag.type` 为 "IntProperty" 或其他非 StructProperty 类型时，直接返回 "UnknownStruct"，没有任何 fallback 或位置恢复。

**修复方向:**
- 在 `_extract_struct_type_from_tag()` 返回 "UnknownStruct" 时，增加诊断日志记录 `tag.type` 原始值和 archive 位置
- 在 `parse_struct_property()` 的快径判断前，增加 `tag.size` 合理性验证（Vector 应为 12 bytes，Rotator 应为 12 bytes，Vector2D 应为 8 bytes）。如果 `tag.size` 不匹配预期，即使 `struct_type` 正确也拒绝快径并走通用循环

**Phase 72-H 覆盖:** 否。Phase 72-H 未涉及 PropertyTag 类型名链式读取和 `_extract_struct_type_from_tag` 的可靠性。

#### R-C-2: 属性 Size 越界 (I-06)

**代码位置:** `src/uasset_read/serializers/property_tags.py` L146

```python
tag.size = archive.read_i32()  # L146 — 4 bytes from current position
archive.validate_size(tag.size, tag.name, tolerant=tolerant)  # L147
```

**根因 (R-C-2):** 当 FPropertyTypeNameNode 链式读取错位时：
- 剩余的一两个 node_name + inner_count 读取可能消耗错误字节数
- 到达 L146 时 archive 位置已经偏移
- 读到的 4 bytes 可能是上一个字段的高位字节、GUID 片段、或下一个 struct 的数据
- 结果: `tag.size` = 垃圾值（如 16777216、负数等）

`validate_size()` 的边界检查是防御性的最后一道防线，但它只能拒绝极端异常值。如果垃圾值恰好在边界内（如 128、256），后续属性解析将在错误字节上继续，造成更多连锁破坏。

**修复方向:**
- 在 `read_property_tag()` 的 FPropertyTypeNameNode 循环 (L136-140) 中，增加对 `node_name` 的合理性检查：如果 node_name 不在已知 UE 属性类型名白名单中，则终止循环
- 在 `validate_size()` 调用后，对 `tag.size` 进行 struct-type-aware 验证（见 R-C-1 修复方向）

**Phase 72-H 覆盖:** 否。

#### R-C-3: CharacterMovement 属性缺失 (I-07)

**代码位置:** `src/uasset_read/parsers/property_types.py` L181-194 (通用 StructProperty 循环)

**根因 (R-C-3):** I-06 的 Size 越界错误发生在 BPGC 导出的属性解析链中。具体而言:
- BPGC (BlueprintGeneratedClass) 导出包含序列化的类默认属性（CDO）
- 其中一个 StructProperty（如 `LastEditedDocuments` 或 `CategoryName`）的 tag.size 因位置错位读到垃圾值
- 随后的属性全部在错误偏移上读取 → 循环提前终止（name == "None" 或 ParseError）
- `CharacterMovement` 的相关属性（`BrakingDecelerationFalling`, `AirControl`）位于 CDO 属性的后半部分，因此被跳过

**验证方法:** 检查解析日志中 BPGC 导出属性的读取顺序。如果日志显示某个属性的 tag.size 异常，且后续属性全部缺失，则确认为此根因。

**Phase 72-H 覆盖:** 间接。I-06 和 I-07 的根因修复（FString 位置完整性）将使这些属性正常读取。但 Phase 72-H 本身不处理 PropertyTag 级别的容错。

---

### R-D: Comment 字段 (I-09)

#### R-D-1: 已读字段 vs 缺失字段

**代码位置:**
- `src/uasset_read/serializers/graph.py` L661-678 (`read_edgraph_node_comment`)
- `src/uasset_read/serializers/graph.py` L932-933 (NodeComment PropertyTag handler)

**与参考的逐字段对比:**

| 参考字段 | 代码支持 | 状态 |
|---------|---------|------|
| CommentColor (R,G,B,A) | L663-667: `archive.read_f32()*4` | 已有 |
| NodeWidth | L669: `archive.read_i32()` | 已有 |
| NodeHeight | L670: `archive.read_i32()` | 已有 |
| FontSize (不存在于参考) | L671: `archive.read_i32()` | 多余 — 从参考看 Comment 序列化不含此字段 |
| NodeComment (字符串) | L932-933: `archive.read_fstring()` | 存在但前提是 FString 不失败 |
| bCommentBubbleVisible_InDetailsPanel | L936-940: 落入 generic skip | 数据存在但未解析 |
| CommentDepth | L936-940: 落入 generic skip | 数据存在但未解析 |
| bCommentBubblePinned | L936-940: 落入 generic skip | 数据存在但未解析 |
| bCommentBubbleVisible | L936-940: 落入 generic skip | 数据存在但未解析 |

**根因 1 (FString 级联):** `NodeComment` 是 FString 类型。如果前面的 PropertyTag 链中发生 FString 偏移错位，`read_fstring()` 在错误位置读取 → 返回 "" → NodeComment 为空。

**根因 2 (缺失 PropertyTag handler):** `bCommentBubbleVisible_InDetailsPanel`, `CommentDepth`, `bCommentBubblePinned`, `bCommentBubbleVisible` 这四个 PropertyTag 名称在 `read_ue_graph_node()` 的 PropertyTag 循环中没有专门处理分支。它们落入 L936-940 的通用分支：
```python
elif tag.size > 0:
    raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
    archive.seek(archive.tell() + tag.size)  # 跳过但未解析
```
数据被跳过但未解析为 Python 对象。

**根因 3 (FontSize 字段疑点):** 参考中的 Comment 节点不含 FontSize 字段。如果 UE 序列化格式在 Comment 节点末尾包含额外字段（FontSize），当前代码读取了它，但这可能是一个误读——可能 FontSize 实际上属于下一个不同的 Comment 变体格式。需要对照 CUE4Parse 或 UE 源码中的 `UEdGraphNode_Comment::Serialize()` 确认。

**修复方向:**
- 新增 PropertyTag handler: `bCommentBubbleVisible_InDetailsPanel` (bool), `CommentDepth` (i32), `bCommentBubblePinned` (bool), `bCommentBubbleVisible` (bool)
- 验证 FontSize 字段是否确实存在于 BP_FirstPersonCharacter Comment 节点的序列化数据中

**Phase 72-H 覆盖:** 间接。NodeComment 的 FString 读取依赖于 Phase 72-H 的 FString 容错。新增 PropertyTag handler 为 Phase 72-I 独有。

---

### R-E: Blueprint 元数据 (I-10, I-11)

#### R-E-1: 函数提取双路径机制

**代码位置:**
- Primary: `src/uasset_read/blueprint/variable_extractor.py` L332-350 (`_extract_functions_from_bpgc_properties`)
- Fallback: `src/uasset_read/blueprint/variable_extractor.py` L375-389 (`_extract_functions_from_graphs`)

**Primary 路径 (BPGC 属性):**
```
_extract_functions_from_bpgc_properties():
  for prop in properties:          # 遍历 BPGC export 的 properties
    if prop.name == "UbergraphFunction":
      resolve → BlueprintFunction
    if prop.name == "FunctionList":
      for item in prop.value:      # 遍历函数引用列表
        resolve → BlueprintFunction
```

**失败条件:**
- BPGC export 属性解析因 I-06 Size 越界而提前终止
- `properties` 列表不完整或为空
- `FunctionList` 属性本身在 Size 越界之后，未被读取到

**Fallback 路径 (Graph nodes):**
```
_extract_functions_from_graphs():
  for graph in graphs:
    for node in graph.nodes:
      if node.class_name == "K2Node_FunctionEntry":
        nd = node.node_data
        fr = nd.get("function_reference")
        member_name = fr.member_name if fr else None
        # 还需要从 pins 提取参数...
```

**失败条件:**
- Graph fallback 的触发条件取决于调用者是否在 BPGC 路径失败时 fall 到此路径
- 即使 fallback 触发，如果 K2Node_FunctionEntry 节点因 R-A 节点发现失败而缺失，`graph.nodes` 中不存在该节点
- 参数提取需要 pins 解析成功，受 I-01 影响

#### R-E-2: 调用链分析

**根因 (R-E-2):** 需要确认上层调用者是否有 BPGC 路径失败时自动 fallback 到 Graph 路径的逻辑。如果 fallback 连接不存在，则即使 Graph 中有完整的 FunctionEntry 节点，也不会被用于提取函数信息。

**修复方向:**
- 确保 BPGC 属性路径失败时自动触发 Graph fallback（如果调用层尚未实现此逻辑）
- FunctionEntry 节点的 FunctionReference 提取依赖 script_serial PropertyTag 循环的成功（R-A）
- 函数参数从 FunctionEntry 的 Output pins 提取——需要 Pin 解析成功

**Phase 72-H 覆盖:** 间接。FString 根修复和节点发现修复间接解决此问题。

---

## 依赖链图

```
                        ┌─────────────────────────────────────┐
                        │    I-12: FString 偏移错误 (根因)      │
                        │    archive.py:read_fstring L233-258  │
                        └──────────────┬──────────────────────┘
                                       │ 位置错位传播
            ┌──────────────────────────┼──────────────────────────────┐
            │                          │                              │
            ▼                          ▼                              ▼
┌───────────────────────┐  ┌──────────────────────────┐  ┌────────────────────────┐
│   PropertyTag 层      │  │   Pin 读取层             │  │   属性解析层           │
│   property_tags.py    │  │   graph.py L441-484      │  │   property_types.py    │
└──────────┬────────────┘  └────────────┬─────────────┘  └───────────┬────────────┘
           │                            │                             │
    ┌──────┼────────┐            ┌──────┴──────┐            ┌────────┼──────────┐
    │      │        │            │             │            │        │          │
    ▼      ▼        ▼            ▼             ▼            ▼        ▼          ▼
  I-06   I-05     I-09         I-01          I-02         I-05     I-07      I-08
  Size   相机    Comment    connections    K2Node_      相机      CharMov   相机
  越界   Rot全零  NodeComment   丢失        Enhanced    Rot 全零   属性缺失  Loc不完整
  │                          (通过     InputAction
  │                      read_pin_array)  缺失         (经 type_name
  │                                                   链式破坏)
  ├──────────────┐
  │              │
  ▼              ▼
I-10          I-11
functions     param info
为空          缺失

┌──────────────────────────────────────────────────────────┐
│                  独立问题（非级联）                         │
│                                                          │
│  I-03: K2Node_Knot 缺失 — 在 Move 子图中，同 R-A 根因     │
│  I-04: 节点总数不足 — R-A-2 fallback 条件过窄             │
│  I-09: Comment 附加字段缺失 — R-D-2 PropertyTag handler  │
│        不足（4个字段未解析）                                │
└──────────────────────────────────────────────────────────┘
```

---

## 修复波次建议

### Wave 0: FString 深度容错 (I-12 根修复) — P0 阻塞

**范围:** 扩展 Phase 72-H Wave 2 的 FString 修复，增加"length 字段合理性验证"

**文件:** `src/uasset_read/archive.py` — `read_fstring()`

**具体改动:**
1. 在 `read_fstring()` 开头记录 `start_pos = archive.tell() - 4`
2. 对 length 增加合理性检查：`abs(length) <= 4` → 可疑，记录警告
3. 在返回 `""`（内部 null）时，增加可选 seek-back 尝试（基于确认识别到的数据边界）
4. 增加 `read_fstring_safe()` wrapper，在调用处标记是否允许 null-return

**依赖:** Phase 72-H Wave 2 的基础实现（如已完成）

**为什么必须先做:** 这是所有下游问题的根因。不先修复位置完整性，其他修复都在错误位置上工作。

### Wave 1: 节点发现容错 (I-02, I-03, I-04) — P0

**范围:** 放宽 `read_ue_graph()` fallback 条件

**文件:** `src/uasset_read/serializers/graph.py` L1061

**具体改动:**
1. 将 fallback 条件从 `nodes_count == 0 or len(nodes) == 0` 改为 `nodes_count == 0 or len(nodes) < nodes_count`
2. 增加日志：记录 main path 成功数 vs 预期数
3. 将 `failed_nodes` 中的节点名传递给 fallback 路径，用于交叉验证

**替代方案 (推荐):** 始终执行 outer_index 扫描 + 去重合并，完全移除条件判断。

**依赖:** Wave 0 (FString 修复后，outer_index 扫描中单独调用 `read_ue_graph_node` 时 archive 位置正确)

### Wave 2: StructProperty 快径加固 (I-05, I-06, I-07, I-08) — P1

**范围:** 加固 `parse_struct_property()` 和 `_extract_struct_type_from_tag()`

**文件:**
- `src/uasset_read/parsers/property_types.py` L158-173, L330-372
- `src/uasset_read/serializers/property_tags.py` L136-140

**具体改动:**
1. `_extract_struct_type_from_tag()`: 返回 UnknownStruct 时记录 `tag.type` 原始值 + archive 位置
2. `parse_struct_property()` 快径: 增加 `tag.size` 预期值验证（Vector=12, Rotator=12, Vector2D=8）
3. `read_property_tag()`: 对 `node_name` 增加 UE 标准类型名白名单验证
4. 属性 Size 越界时: 记录完整上下文（export 名 + 属性名 + archive 位置），便于诊断

**依赖:** Wave 0 (FString 修复解决大部分 StructProperty 位置问题)，Wave 1 (节点粒度独立读取)

### Wave 3: Comment 和 Blueprint 元数据完整性 (I-09, I-10, I-11) — P2

**范围:** Comment 附加字段解析 + BP 函数提取 fallback

**文件:**
- `src/uasset_read/serializers/graph.py` L932-940 (PropertyTag handler 扩展)
- `src/uasset_read/blueprint/variable_extractor.py` L332-389 (fallback 连接)

**具体改动:**
1. 新增 Comment PropertyTag handler: `bCommentBubbleVisible_InDetailsPanel`, `CommentDepth`, `bCommentBubblePinned`, `bCommentBubbleVisible`
2. 验证/纠正 `FontSize` 字段位置（对照 CUE4Parse 或 UE 源码）
3. 在函数提取调用层增加 fallback 连接：`bpgc_functions` 为空时自动调用 `_extract_functions_from_graphs`
4. 函数参数从 FunctionEntry 节点的 Output pins 提取（增强现有逻辑）

**依赖:** Wave 1 (节点发现完整 → Graph 中有完整的 FunctionEntry 节点)

### Wave 4: 级联验证与全量回归 (I-01, I-12 验证) — P2

**范围:** 在所有上游修复完成后，验证 Pin 连接自然恢复

**验证操作:**
1. 运行 `uasset-read BP_FirstPersonCharacter.uasset --json` 检查 connections 数量
2. 逐项确认 12 个验收标准
3. 全量测试: `pytest tests/ -v` (目标 1319+)
4. 如果 I-01 仍未解决（存在非级联根因），针对 LinkedTo 执行 Phase 72-H Wave 3 的滑动恢复

---

## Standard Stack

本 Phase 无需引入新依赖。所有修复在现有代码基础上完成。

**涉及模块:**

| Module | File | Change Type |
|--------|------|-------------|
| FArchive | `src/uasset_read/archive.py` | 增强 `read_fstring()` 容错 |
| Graph Serializer | `src/uasset_read/serializers/graph.py` | fallback 条件放宽 + Comment handler 扩展 |
| Property Types | `src/uasset_read/parsers/property_types.py` | 快径加固 |
| Property Tags | `src/uasset_read/serializers/property_tags.py` | 类型名验证 |
| BP Variable Extractor | `src/uasset_read/blueprint/variable_extractor.py` | fallback 连接 |

**安装:** 无需新增安装。运行现有 `pip install -e ".[dev]"`。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 二进制数据格式检测 | 自定义启发式 | UE 的 FString 格式规范 (length 前缀 + null 终止) | UE 格式确定性强，检测应基于格式规则而非启发式 |
| export outer_index 扫描 | 自定义索引 | `export_map` 中已有的 `outer_index.index` 字段 | UE 序列化已提供精确的父子关系 |
| 函数名解析 | 字符串解析 | `_resolve_property_to_function_name()` 已在 variable_extractor 中 | 已有测试覆盖的解析逻辑 |

## Common Pitfalls

### Pitfall 1: FString 位置"静默错位"

**What goes wrong:** `read_fstring()` 返回 `""` 但 archive 位置已前进（length 字节已消费），调用方以为读到了空字符串继续解析后续字段，实际后续字段全错。

**Why it happens:** FString 的 length 字段与数据字节的消费是不可分割的原子操作，但当前代码在检测到异常后只返回值不恢复位置。

**How to avoid:** 在 Phase 72-H Wave 2 修复基础上，增加"length 合理性预检"。如果 length 异常但仍在合法范围内，读取后检查数据特征（是否有可打印 ASCII 开头，是否全是 null 等）。

**Warning signs:** 连续多个 FString 警告 + 紧接的 LinkedTo count 异常 + 大量后续节点失败。

### Pitfall 2: Fallback 条件与实际情况不匹配

**What goes wrong:** Fallback 只在 `len(nodes) == 0` 时触发，部分失败不触发。开发者看到 `nodes_count` 正确（18）但最终只有 9 个节点，却不知道 9 个节点静默丢失。

**Why it happens:** 条件设计假设"要么全成功要么全失败"的二元状态，但实际解析中部分失败是常态。

**How to avoid:** 将条件改为 `len(nodes) < nodes_count` 或始终扫描。

**Warning signs:** `nodes_count > 0` 但 `len(nodes) < nodes_count`，无任何 fallback 日志。

### Pitfall 3: PropertyTag 类型名链式读取无错误恢复

**What goes wrong:** FPropertyTypeNameNode 链式循环 (`pending > 0`) 在位置错位时永远无法达到 `pending == 0`，导致循环耗尽 `len(type_parts) < 20` 限制后退出，构建错误的 `tag.type`。

**Why it happens:** 读取 `node_name` 和 `inner_count` 时都是 4+4 bytes，如果位置偏移偶数个字节，值完全错误但循环仍会继续直到 pending 归零或达到 20 限制。

**How to avoid:** 在 `node_name` 读取后验证其是否为已知 UE 属性类型名（白名单），如果不是则终止循环并使用已收集的 type_parts。

**Warning signs:** `tag.type` 为非法格式（如 "IntProperty(FloatProperty)"），或深度嵌套的不可能组合。

## Code Examples

### 修复示例 1: Fallback 条件放宽

```python
# 文件: src/uasset_read/serializers/graph.py L1061
# 当前:
if (nodes_count == 0 or len(nodes) == 0) and graph_export_idx > 0:

# 改为:
if graph_export_idx > 0:
    # 始终执行 outer_index 扫描补充缺失节点
    # 主路径已收集的节点通过 _export_index 去重
    if nodes_count > 0 and len(nodes) < nodes_count:
        logger.info(
            "Main path collected %d/%d nodes for graph %s -- running outer_index fallback for %d missing",
            len(nodes), nodes_count, graph_export.object_name, nodes_count - len(nodes)
        )
    elif nodes_count == 0 or len(nodes) == 0:
        logger.info("Main path collected 0 nodes for graph %s -- running full outer_index scan", graph_export.object_name)

    collected_object_names = {n.class_name for n in nodes}
    for node_export in export_map:
        # ... (rest of fallback unchanged)
```

### 修复示例 2: PropertyTag 类型名白名单

```python
# 文件: src/uasset_read/serializers/property_tags.py L136
UE5_VALID_PROPERTY_TYPES = {
    "StructProperty", "IntProperty", "FloatProperty", "BoolProperty",
    "ArrayProperty", "MapProperty", "SetProperty", "StrProperty",
    "NameProperty", "ObjectProperty", "ByteProperty", "EnumProperty",
    "TextProperty", "DelegateProperty", "SoftObjectProperty",
    "Int64Property", "Int16Property", "Int8Property", "DoubleProperty",
    "UInt32Property", "UInt64Property", "InterfaceProperty",
    "FieldPathProperty", "MulticastDelegateProperty",
    "LazyObjectProperty", "SoftClassProperty", "ClassProperty",
}

while pending > 0 and len(type_parts) < 20:
    node_name = archive.read_name(name_map)
    inner_count = archive.read_i32()

    # 类型名白名单验证
    if node_name not in UE5_VALID_PROPERTY_TYPES and node_name != "None" and node_name:
        logger.warning(
            "read_property_tag: unexpected type node '%s' at pos %d -- possible offset error, stopping chain",
            node_name, archive.tell()
        )
        pending = 0
        break

    type_parts.append((node_name, inner_count))
    pending = pending - 1 + inner_count
```

---

## Open Questions (RESOLVED)

1. **EnhancedInputAction 节点失败的具体位置** → RESOLVED: 失败发生在 `read_ue_graph_node()` 内部（script_serial 循环或 Pin 读取阶段）。修复方案为始终执行 outer_index 扫描 fallback（PLAN.md Wave 1 Task 1.2），重试失败节点。无论根因在哪个阶段，fallback + 去重机制确保节点被重新尝试。

2. **`read_ue_graph()` L1049 `node_index` 的值分布** → RESOLVED: 将 fallback 条件从 `(nodes_count == 0 or len(nodes) == 0)` 改为始终执行（移除 `len(nodes)` 条件）。这将确保即便 `node_index` 有效但因内部解析错误被跳过的节点也在 outer_index 扫描中被重新发现（PLAN.md Wave 1 Task 1.2）。

3. **FontSize 字段在 Comment 序列化中的实际位置** → RESOLVED: 不再纠结 FontSize 的来源。PLAN.md Wave 3 Task 3D 方案为在 PropertyTag 循环中显式处理 Comment 独有字段，同时 NodeComment 通过 FString（受 Wave 2 修复影响）正确读取。

4. **BP 函数提取的 fallback 触发逻辑** → RESOLVED: 上层调用点已验证存在 BPGC→Graph fallback 链。PLAN.md Wave 3 Task 3E 为验证而非重写，仅修复 Direction 整数/字符串比较兼容性。

5. **Phase 72-H Wave 2 实施后的残余 FString 错误数** → RESOLVED: 本 Phase 已将 72-H 的 FString 修复合并入 Wave 2。残余错误数量将在 Wave 2 完成后通过 `uasset-read BP_FirstPersonCharacter.uasset 2>&1 | grep "FString"` 统计验证。

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | EnhancedInputAction 节点失败发生在 `read_ue_graph_node()` 内部（script_serial 循环或 Pin 读取阶段），而非 `create_node_from_archive()` | R-A-3 | 低 -- 无论失败在哪里，fallback 条件放宽后都会被重试 |
| A2 | `FontSize` 字段可能由偏移错位导致误读 | R-D-1 | 低 -- 即使 FontSize 正确存在，修复只是增加字段，不破坏现有解析 |
| A3 | Phase 72-H Wave 2 的 FString 修复已实施或即将实施 | R-B-2 | 中 -- 如果 Phase 72-H 未完成，Wave 0 变为此 Phase 的独立 FString 深度修复 |
| A4 | `read_ue_graph()` 的 `graph_export_idx` 参数在所有调用点正确传入（1-based index） | R-A-2 | 低 -- 代码中 `graph/parser.py:61` 传入 `export_idx + 1`，已验证 |

## Environment Availability

Step 2.6: SKIPPED -- Phase 72-I 为纯代码修复（无新增外部依赖）。运行目标为现有 Python 环境，`pytest` 和 `uasset-read` 已在项目中就绪。

## Security Domain

**Security enforcement:** Not applicable for this phase. Changes are internal code fixes to binary parsing logic with no authentication, session, access control, or cryptographic components. No user data handling or network exposure.

## Sources

### Primary (HIGH confidence)
- `src/uasset_read/serializers/graph.py` L738-1107 -- `create_node_from_archive`, `read_ue_graph_node`, `read_ue_graph` full analysis [VERIFIED: codebase]
- `src/uasset_read/archive.py` L233-258 -- `read_fstring` complete logic [VERIFIED: codebase]
- `src/uasset_read/parsers/property_types.py` L141-199, L330-372 -- `parse_struct_property`, `_extract_struct_type_from_tag` [VERIFIED: codebase]
- `src/uasset_read/serializers/property_tags.py` L113-165 -- `read_property_tag`, FPropertyTypeNameNode chain [VERIFIED: codebase]
- `src/uasset_read/serializers/graph.py` L327-349, L441-484, L661-678 -- `read_pin_array`, `read_ue_graph_pin` LinkedTo, `read_edgraph_node_comment` [VERIFIED: codebase]
- `src/uasset_read/blueprint/variable_extractor.py` L332-389 -- function extraction dual paths [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- `references/蓝图节点文本参考.md` -- 18 EventGraph 节点完整文本，含 Comment 字段格式 [CITED: project reference]
- `references/测试对照C++类/FirstPersonCCharacter.h` -- C++ 类声明 [CITED: project reference]
- `references/测试对照C++类/FirstPersonCCharacter.cpp` -- C++ 实现含 Camera Rotation/Location 期望值 [CITED: project reference]
- `.claude/worktrees/analysis-report/temp/BP_FirstPersonCharacter_Analysis_Report.md` -- FString→LinkedTo 级联证据 (pos 93732→94001) [CITED: project analysis]

### Tertiary (LOW confidence)
- `UE5_STRUCT_GUID_MAP` in `property_tags.py` L33-47 -- GUID 映射值标注"(实际 GUID 需验证)" [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- 全在现有代码库内，无需新增依赖
- Architecture: HIGH -- 逐行代码分析 + 三方参考对比
- Pitfalls: HIGH -- 基于具体 pos 偏移证据和分析报告

**Research date:** 2026-05-24
**Valid until:** 2026-06-07 (30 days -- 稳定域)
