---
phase: 72i
title: BP_FirstPersonCharacter 全量对比修复（含 Phase 72-H 合并）
goal: 修复 12 项解析错误，使 BP_FirstPersonCharacter.uasset 解析覆盖率从 ~56% 提升至 >90%
requirements:
  - I-01: EventGraph connections >= 9
  - I-02: K2Node_EnhancedInputAction >= 4
  - I-03: K2Node_Knot >= 4
  - I-04: EventGraph nodes >= 13
  - I-05: Camera RelativeRotation = (0, 90, -90)
  - I-06: Size 越界属性正常解析
  - I-07: CharacterMovement 属性提取
  - I-08: Camera RelativeLocation ≈ (-2.8, 5.89, 0)
  - I-09: Comment 含 NodeComment
  - I-10: Blueprint.functions 含 4 函数
  - I-11: 函数参数信息非空
  - I-12: FString suspicious length < 3
  - FSTR-01: FString 读取完成后指针始终处于正确位置
  - FSTR-02: 非法二进制数据被识别后指针不滞留于错误位置
  - LINK-01: LinkedTo 数组 count 异常时启动滑动恢复机制
  - JSON-01: StructValue/MapValue/SetValue 嵌套 dataclass 可正确递归序列化为 JSON
depends_on: [phase-72g]
type: fix
status: planned
created: 2026-05-24
---

# Phase 72-I: BP_FirstPersonCharacter 全量对比修复（含 Phase 72-H 合并）

## 背景

BP_FirstPersonCharacter.uasset 解析输出与 UE 编辑器导出的蓝图节点文本参考 + C++ 对照源码三方对比，发现 12 项解析错误。这些问题存在一条**级联依赖链**：

```
FString 偏移错位 → LinkedTo count 异常 → Pin 连接丢失 (Connections=0)
PropertyTag 类型名链式解析偏移 → Struct 类型识别失败 → Vector/Rotator 快速路径不触发
节点发现主路径 nodes_count 不完整 → fallback 不触发 → 8 个节点遗漏
```

Phase 72-H（FString 容错 + LinkedTo 恢复 + StructValue JSON 递归序列化）尚未执行，其修复是 72-I 的 P0 前置条件。本计划将 72-H 的修复合并到 72-I 的波次中，因为两者的问题高度交织，分别执行会导致 72-I 的 Wave 2-3 无法验证。

## 参考基线

- **蓝图节点文本参考.md** — UE 编辑器导出的 EventGraph 全部 17 个节点的完整序列化文本（含 Pin 定义、LinkedTo、PinType 等）
- **FirstPersonCCharacter.h/cpp** — C++ 等价实现（DoMove/DoAim/DoJumpStart/DoJumpEnd 签名 + 组件属性）

## 波次计划

### Wave 1: StructValue JSON 递归序列化 + 节点发现 fallback 扩展

**目标:** 修复 JSON 输出崩溃问题，确保端到端输出可验证；扩展节点发现 fallback，使遗漏节点被发现

**文件:** `src/uasset_read/formatters/json_formatter.py`, `src/uasset_read/serializers/graph.py`

**改动:**

#### 1A. StructValue JSON 递归序列化（原 72-H Wave 1）

文件: `src/uasset_read/formatters/json_formatter.py` — `serialize_property_value()`

当前代码 L165-166 使用 `isinstance(value, dict)` 直接返回 dict，但 dict 内部可能包含未序列化的 dataclass 实例（如 StructValue 嵌套在 dict value 中）。同时 L168 使用 `hasattr()` 检测而非 `isinstance()`，不够精确。

修改：
- 将 `isinstance(value, dict)` 分支改为递归处理 dict 内部值：`{k: serialize_property_value(v, depth+1, max_depth) for k, v in value.items()}`
- 将 `hasattr` 检测替换为 `isinstance(value, StructValue)` / `isinstance(value, MapValue)` 等，精确匹配类型
- `list` 分支同样递归处理元素

#### 1B. 节点发现 fallback 扩展（I-02, I-03, I-04）

文件: `src/uasset_read/serializers/graph.py` — `read_ue_graph()` L1059-1090

当前条件 `if (nodes_count == 0 or len(nodes) == 0) and graph_export_idx > 0` 过于保守，主路径收集 9 个节点后 fallback 不触发。

修改：
- 将 fallback 改为**始终执行**（条件改为 `if graph_export_idx > 0`）
- 保留去重逻辑（通过 `_export_index` 检查）
- 主路径和 fallback 结果合并，不再互斥
- 确保 K2Node_EnhancedInputAction 和 K2Node_Knot 的 class_index 能被 `_gac()` 正确解析为短类名

**验收:**
- `json.dumps(format_json_full(result))` 不抛 `TypeError`
- EventGraph 节点数 >= 13（覆盖 EnhancedInputAction x4 + Event x3 + CallFunction x2 + Comment x3 + FunctionEntry x1 + Knot x4）
- K2Node_EnhancedInputAction >= 4
- K2Node_Knot >= 4

**测试:** `python -m pytest tests/ -v -x -q`

---

### Wave 2: FString 容错增强 + LinkedTo 滑动恢复（P0 根因修复）

**目标:** 修复 FString 偏移错位根因，使 LinkedTo 数组能正确读取，恢复 Pin 连接

**文件:** `src/uasset_read/archive.py`, `src/uasset_read/serializers/graph.py`

**改动:**

#### 2A. FString 容错增强（原 72-H Wave 2, I-12 根因）

文件: `src/uasset_read/archive.py` — `read_fstring()` L233-258

当前问题：检测到内部 null 字节后返回空字符串 `""`，但 `length` 字段本身可能是错误值（因为前面某个字段偏移错位），消费了错误数量的字节，导致后续所有字段错位。

修改策略（必须遵守 no-byte-reading 规则，使用 FArchive 流式读取）：

1. **增加 `expected_bytes` 边界防卫**: 读取 `length` 后，检查 `archive.tell() + abs(length)` 是否超出 archive 数据范围。若超出，回退指针到读取 `length` 前的位置（使用 `archive.tell() - 4` 记录），抛出 `ParseError`，让上层 try/except 处理
2. **异常 length 回退指针**: 当 `length` 为异常值（超过 `MAX_FSTRING_LENGTH` 或导致边界越界），**恢复 `archive` 指针到调用 `read_fstring()` 之前的位置**，抛出 `ParseError` 而非继续读取
3. **内部 null 检测时确保偏移正确**: 检测到内部 null 字节后，不返回空字符串，而是继续消费 `length` 对应的字节数（保证偏移正确），然后返回 `""` 或记录 warning 返回解码结果
4. **区分合法/非法 null**: UTF-16 的 null 终止符 `b'\x00\x00'` 是合法的，不应触发内部 null 检测；只有 UTF-8 路径中出现 `b'\x00'` 才是异常

关键：在 `read_fstring()` 入口记录 `pos_before = archive.tell()`，失败时 `archive.seek(pos_before)` 回退。

#### 2B. LinkedTo 滑动恢复机制（原 72-H Wave 3, I-01 补救）

文件: `src/uasset_read/serializers/graph.py` — `read_pin_array()` L327-349

当 `array_count` 超出合理范围（`< 0` 或 `> MAX_LINKEDTO_PER_PIN`）时，当前直接抛出 `ParseError`，被上层 `read_ue_graph_pin()` L462-468 捕获后设 `linked_to = []`，但**不恢复指针位置**。

修改：

1. 在 `read_pin_array()` 中增加 recovery 路径：当 `array_count` 异常时，记录当前位置
2. 在当前指针 ±8 字节范围内扫描寻找合法 i32 count（0 <= count <= 20）
3. 验证候选 count 后的第一个 Pin reference 结构是否合理（检查 owning_node 是否在 export_map 范围内）
4. 恢复成功时返回解析结果，失败时返回空数组
5. 同时修复 `read_ue_graph_pin()` L462-468：LinkedTo 读取失败时，尝试基于 `node_export` 的 `script_serial_offset + script_serial_size` 计算正确位置并恢复

**验收:**
- FString 读取后 `archive.tell()` 位置正确（基于 length 字段 + 终止符）
- BP_FirstPersonCharacter.uasset 解析完成后 LinkedTo 错误数显著减少
- EventGraph `connections` >= 9
- FString suspicious length < 3

**测试:** `python -m pytest tests/ -v -x -q`

---

### Wave 3: 级联效果验证 + 剩余修复（I-05, I-06, I-07, I-08, I-09, I-10, I-11）

**目标:** 在 Wave 1-2 的根因修复后，验证级联效果；修复剩余独立问题

**文件:** `src/uasset_read/serializers/graph.py`, `src/uasset_read/blueprint/variable_extractor.py`, `src/uasset_read/parsers/property_types.py`

**改动:**

#### 3A. Pin 连接端到端验证（I-01 验证）

**Phase 72-G 已有代码：** `flow_builder.py` L654-661 — `linked_to_count == 0` 验证警告（诊断用），`build_connections_map()` L630-683 — connections 映射逻辑

在 Wave 2 修复 FString 偏移 + LinkedTo 恢复后，Pin 连接应自动恢复。

验证步骤（不新增功能代码，仅验证）：
1. 解析 BP_FirstPersonCharacter.uasset
2. 检查 EventGraph 的 `connections` 数组 >= 9（对照参考文档中 9 条 exec 连接）
3. 检查连接包含已知 exec 连接（如 IA_Look → Aim、IA_Move → Move、IA_Jump → Jump）
4. 如果 connections 仍不足：添加调试日志输出每个 Pin 的 `linked_to_raw` 长度，定位断裂点

#### 3B. Vector/Rotator 快速路径验证（I-05, I-08）

**Phase 72-G 已有代码：** `property_types.py` L156-173 — Vector/Rotator/Vector2D 快速路径（3*read_f32 直接读取）

在 Wave 2 修复 FString 偏移后，PropertyTag 类型名链式解析应恢复正常。

验证步骤（不重写快速路径，仅验证触发条件）：
1. 解析 BP_FirstPersonCharacter.uasset
2. 检查 Camera RelativeRotation = (Pitch=0, Yaw=90, Roll=-90)（对照 C++ `FRotator(0, 90, -90)`）
3. 检查 Camera RelativeLocation ≈ (X=-2.8, Y=5.89, Z=0)（对照 C++ `FVector(-2.8f, 5.89f, 0.0f)`）
4. 如果快速路径仍未触发：在 `_extract_struct_type_from_tag()` 调用后添加 `logger.debug("struct_type=%s tag.type=%s", struct_type, tag.type)` 诊断日志

#### 3C. PropertyTag Size 修复验证（I-06, I-07）

在 Wave 2 修复 FString 偏移后，LastEditedDocuments/CategoryName/BodyInstance 的 Size 字段应正常读取。

验证步骤：
1. 解析 BP_FirstPersonCharacter.uasset
2. 检查上述 3 个属性无 ParseError
3. 检查 CharacterMovement 包含 BrakingDecelerationFalling 和 AirControl 属性
4. 如果仍有 Size 越界：在 `read_property_tag()` 中 Size 越界时，seek 到 `tag_pos + tag.size` 恢复位置（而非抛异常中断）

#### 3D. Comment 字段补全（I-09）

文件: `src/uasset_read/serializers/graph.py` — `read_edgraph_node_comment()` L661-678

当前读取：comment_color(4f32) + node_width(i32) + node_height(i32) + font_size(i32)

NodeComment 通过 `read_ue_graph_node()` L932-933 的 PropertyTag 循环中读取（StrProperty `"NodeComment"` tag），不在此函数内。

修改：
- 在 PropertyTag 循环中显式处理 Comment 独有字段（如果存在）：
  - `bCommentBubbleVisible_InDetailsPanel` (BoolProperty)、`CommentDepth` (IntProperty)
- 验证 NodeComment 通过 `read_fstring()` 正确读取（受 Wave 2 FString 修复影响）

#### 3E. Blueprint.functions + 参数提取验证（I-10, I-11）

**Phase 72-G 已有代码：** `variable_extractor.py` L332-350 — `_extract_functions_from_bpgc_properties()`（BPGC 属性路径），L375+ — `_extract_functions_from_graphs()`（Graph fallback 路径）

Wave 1 的节点发现扩展 + Wave 2 的 Pin 连接修复后，BPGC 属性解析和 FunctionEntry 节点应更完整。

验证步骤（不重写提取逻辑，仅修复阻断性 bug）：
1. 解析 BP_FirstPersonCharacter.uasset
2. 验证 Blueprint.functions 含 DoMove/DoAim/DoJumpStart/DoJumpEnd
3. 验证每个函数参数含参数名 + 参数类型
4. 修复 Direction 比较兼容性：当前 `variable_extractor.py` 使用字符串比较 `"EGPD_Input"`/`"EGPD_Output"`，但 UEdGraphPin.direction 可能是整数 0/1。添加 `isinstance(direction, int)` 分支同时支持整数和字符串比较

**验收:**
- Camera RelativeRotation = (0, 90, -90)
- Camera RelativeLocation ≈ (-2.8, 5.89, 0)
- LastEditedDocuments/CategoryName/BodyInstance 无 ParseError
- CharacterMovement 含 BrakingDecelerationFalling + AirControl
- Comment 含 NodeComment
- Blueprint.functions 含 DoMove/DoAim/DoJumpStart/DoJumpEnd
- 函数参数信息非空

**测试:** `python -m pytest tests/ -v`

---

## 验收标准

| ID | 标准 | 验证方式 |
|----|------|----------|
| I-01 | EventGraph connections >= 9 | 解析输出检查 `connections` 数组长度 |
| I-02 | K2Node_EnhancedInputAction >= 4 | 解析输出统计该类型节点数 |
| I-03 | K2Node_Knot >= 4 | 解析输出统计该类型节点数 |
| I-04 | EventGraph nodes >= 13 | 解析输出统计节点总数 |
| I-05 | Camera RelativeRotation = (0, 90, -90) | 解析输出检查 Rotation 字段值 |
| I-06 | LastEditedDocuments/CategoryName/BodyInstance 无 ParseError | 解析输出无对应错误 |
| I-07 | CharacterMovement 含 BrakingDecelerationFalling + AirControl | 解析输出检查属性列表 |
| I-08 | Camera RelativeLocation ≈ (-2.8, 5.89, 0) | 解析输出检查 Location 字段值 |
| I-09 | Comment 含 NodeComment | 解析输出检查 Comment 节点字段 |
| I-10 | Blueprint.functions 含 4 函数 | 解析输出检查 functions 列表 |
| I-11 | 函数参数信息非空 | 解析输出检查参数列表 |
| I-12 | FString suspicious length < 3 | 日志检查 warning 数量 |

## 风险分析

| 风险 | 概率 | 缓解 |
|------|------|------|
| FString 容错过度保守，误判合法字符串 | 中 | 保留原有 `errors='replace'` 解码路径，仅在边界越界时回退指针 |
| LinkedTo 恢复机制引入误恢复 | 中 | 双重验证（count 合理性 0-20 + Pin reference 结构验证） |
| Wave 2 修改 archive.py 影响全局解析 | 低 | 仅修改 `read_fstring` 一个方法，全量回归测试 1339+ tests |
| 节点发现 fallback 扩展引入重复节点 | 低 | 已有 `_export_index` 去重逻辑 |
| 快速路径仍未触发（根因不在 FString） | 低 | Wave 3 添加调试日志定位具体原因 |
| Direction 比较使用字符串而非整数 | 中 | 同时支持字符串和整数比较 |

## 多源覆盖审计

| 来源 | 项目 | 覆盖计划 |
|------|------|----------|
| GOAL | 解析覆盖率 >90% | Wave 1-3 全链路修复 |
| REQ I-01 | Pin 连接丢失 | Wave 2 (2A+2B) + Wave 3 (3A) |
| REQ I-02 | EnhancedInputAction 缺失 | Wave 1 (1B) |
| REQ I-03 | K2Node_Knot 缺失 | Wave 1 (1B) |
| REQ I-04 | 节点总数不足 | Wave 1 (1B) |
| REQ I-05 | RelativeRotation 全零 | Wave 3 (3B) |
| REQ I-06 | Size 越界 | Wave 3 (3C) |
| REQ I-07 | CharacterMovement 缺失 | Wave 3 (3C) |
| REQ I-08 | RelativeLocation 不完整 | Wave 3 (3B) |
| REQ I-09 | Comment 字段缺失 | Wave 3 (3D) |
| REQ I-10 | Blueprint.functions 空 | Wave 3 (3E) |
| REQ I-11 | 函数参数缺失 | Wave 3 (3E) |
| REQ I-12 | FString 偏移错误 | Wave 2 (2A) |
| RESEARCH | StructValue JSON 递归序列化 | Wave 1 (1A) |
| RESEARCH | 节点发现 fallback 扩展 | Wave 1 (1B) |
| RESEARCH | FString 容错增强 | Wave 2 (2A) |
| RESEARCH | LinkedTo 滑动恢复 | Wave 2 (2B) |
| CONTEXT | 72-H 合并 | Wave 1 (1A) + Wave 2 (2A+2B) |
| DEFERRED | 其他 uasset 文件修复 | 不覆盖（out of scope） |
| DEFERRED | 性能优化 | 不覆盖（out of scope） |
