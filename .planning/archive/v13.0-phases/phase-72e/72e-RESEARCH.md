# Phase 72-E: EventGraph Node Parsing Fix - Research

**Researched:** 2026-05-23
**Domain:** UE5 Blueprint graph serialization / UEdGraph::Serialize()
**Confidence:** MEDIUM

## Summary

BP_FirstPersonCharacter.uasset 的 EventGraph 解析覆盖率约 56%（仅 9/16+ 节点正确解析）。通过代码审查，定位到 5 个问题的根因分布在 3 个模块中：序列化器（graph.py）、archive 读取器（archive.py）、以及蓝图元数据提取（variable_extractor.py）。

最关键的发现是 `read_name()` 在索引越界时返回字面字符串 `"None"` 而非 Python `None` 或空字符串，这直接导致函数名解析为 `"None"`。同时 `BlueprintMetadata.functions` 在 `extract_blueprint_metadata()` 中被硬编码为 `[]`，从未被填充。

**Primary recommendation:** 修复 5 个问题按优先级排序：(1) `read_name()` sentinel 值，(2) graph.py 节点收集 fallback 增强，(3) K2Node_Event 解析异常诊断，(4) 组件提取验证，(5) Blueprint.functions 从 EventGraph 提取。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FName/FString 读取 | Archive (序列化层) | -- | 所有字符串读取的基础层 |
| 节点收集/分发 | serializers/graph.py | graph/parser.py | 二进制解析在 serializers，高层分析在 parser |
| FMemberReference 解析 | serializers/graph.py | -- | 结构体反序列化职责 |
| 组件提取 | blueprint/component_extractor.py | -- | ExportMap 扫描职责 |
| Blueprint.functions 提取 | blueprint/variable_extractor.py | serializers/graph.py | 元数据提取在 blueprint，函数签名数据在 graph |

## Root Cause Analysis

### Issue 1: EventGraph 节点严重缺失 (9/16+)

**根因：`read_ue_graph()` 节点收集逻辑对 UE5 格式假设不完整**

**代码位置:** `src/uasset_read/serializers/graph.py` L1017-1055

**分析：**

`read_ue_graph()` 有两条节点收集路径：

1. **主路径（L1027-1036）：** 读取 `nodes_count` (i32)，然后循环读取 PackageIndex (i32) 并解析每个节点
2. **Fallback 路径（L1038-1055）：** 当 `nodes_count == 0` 时，扫描 ExportMap 中外层索引 (`outer_index.index == graph_export_idx`) 匹配且类名包含 "K2Node"/"EdGraphNode"/"Node" 的条目

**问题 A — 主路径无 fallback：** 如果 `nodes_count > 0`（即使是误读的值），fallback 路径不会执行。代码直接跳过 L1038-1055。如果主路径因为读取到的 nodes_count 不正确或 TArray 格式不匹配导致节点解析失败，节点不会加入 fallback 收集。

```python
# L1018: 直接读取 nodes_count，假设紧跟在 schema_index 之后
nodes_count = archive.read_i32()

# L1027-1036: 只在 nodes_count > 0 时执行主路径
for _ in range(nodes_count):
    node_index = archive.read_i32()
    if node_index > 0 and node_index <= len(export_map):
        ...

# L1038: 仅当 nodes_count == 0 时执行 fallback
if nodes_count == 0 and graph_export_idx > 0:
    ...
```

**问题 B — Fallback 类名过滤器不够宽松：** L1042 的过滤器：
```python
if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
```
这通过了 K2Node_CallFunction、K2Node_Event、K2Node_EnhancedInputAction、K2Node_Knot、EdGraphNode_Comment。但如果 class_name 解析失败（返回 `None`），节点被跳过。

**问题 C — UEdGraph 序列化格式假设：** 代码假设 UEdGraph 序列化格式为：
1. Schema (PackageIndex i32)
2. Nodes array (count + TArray<PackageIndex>)
3. GraphGuid (16 bytes)
4. bEditable (u8)

但 UE5 的 UEdGraph::Serialize() 可能在 Schema 和 Nodes 之间有其他字段（如 SerializedPropertyGuid 或其他编辑器独有数据），导致 `nodes_count` 从错误偏移读取。

**风险：** MEDIUM。修改节点收集逻辑可能导致已正常解析的资产出现回退。需要确保新逻辑只在现有逻辑失败时才激活。

---

### Issue 2: 函数调用名解析为 "None"

**根因：`read_name()` 索引越界时返回字面字符串 `"None"`，且可能被调用在错误位置**

**代码位置:**
- `src/uasset_read/archive.py` L260-269 — `read_name()` 定义
- `src/uasset_read/serializers/graph.py` L586 — `read_fmember_reference()` 调用点
- `src/uasset_read/serializers/graph.py` L850-851 — PropertyTag 层内 MemberName 读取

```python
# archive.py L260-269
def read_name(self, name_map: list) -> str:
    index = self.read_u32()
    number = self.read_u32()
    if 0 <= index < len(name_map):
        base_name = name_map[index]
        if number > 0:
            return f"{base_name}_{number}"
        return base_name
    return "None"  # <-- 问题：返回字面字符串 "None" 而非 Python None 或 ""
```

**影响链：**

1. `read_fmember_reference()` L586: `member_name = archive.read_name(name_map)` -- 如果 name_map 索引越界，`member_name = "None"`
2. PropertyTag 层 L850-851: `m_name = archive.read_name(name_map)` -- 同样的问题
3. `FMemberReference` 的 `member_name` 字段是 `str = ""`（默认空字符串），实际被赋值为 `"None"` 字符串

**关键判断：** `"None"` 出现有两种可能：
- **A. 索引确实越界：** name_map[index] 超出范围，说明 FName 序列化格式不对（可能 UE5 有额外的 CasePreservingIndex 字段）
- **B. 位置错位：** 由于前面的字段读取不正确，导致读取 FName 时位置偏移，读到的 index 值是垃圾数据

**验证方法：** 在 `read_name()` 中添加 debug 日志，输出 index、name_map 长度、当前位置，判断是 A 还是 B。

**风险：** HIGH。修改 `read_name()` 的返回值会影响所有调用方。如果改为返回 `""` 或 `None`，现有代码中检查 `== "None"` 的逻辑可能失效。建议保持返回值不变，但添加 `is_valid` 标记或 logging 帮助诊断。

---

### Issue 3: K2Node_Event 解析错误 (4/5 有 _parse_error=True)

**根因：`read_ue_graph_node()` 中 PropertyTag 循环或 Pins 数组读取触发异常**

**代码位置:**
- `src/uasset_read/serializers/graph.py` L794-986 — `read_ue_graph_node()` 全函数
- L818-919: script_serial PropertyTag 解析循环
- L929-963: Pins 数组读取
- L1046-1055: fallback 路径的 _parse_error 标记

**`_parse_error` 设置路径：**

路径 A -- `read_ue_graph` fallback（L1046-1055）：
```python
except ParseError:
    nodes.append(UEdGraphNode(
        ...
        node_data={"_parse_error": True, "node_name": node_export.object_name},
    ))
```

路径 B -- `create_node_from_archive`（L753-755）：
```python
if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
    return base_node  # 跳过分发
```

**可能的异常触发点：**

| 代码位置 | 可能异常 | 原因 |
|----------|---------|------|
| L830 `read_property_tag()` | ParseError | PropertyTag name/type/size 格式不匹配 |
| L847 `archive.read_i32()` | ParseError (offset 越界) | MemberParent 读取位置错误 |
| L849 `archive.read_fstring()` | ParseError (长度过大) | MemberScope FString 长度异常 |
| L851 `archive.read_name()` | 无异常但返回 "None" | 索引越界 |
| L886 `archive.read_name()` | 同上 | EventReference.MemberName 同样问题 |
| L929 `archive.read_i32()` (pins_count) | ParseError (negative/exceeds) | pins_count 读取位置错误 |
| L956 `read_ue_graph_pin()` | 各种异常 | Pin 读取链中的任何环节 |

**关键洞察：** K2Node_Event 的 script_serial 包含 `EventReference` 属性（而非 `FunctionReference`）。EventReference 的解析逻辑（L870-904）和 FunctionReference（L834-869）基本相同，但 L884 读取 MemberScope 时**没有将结果存入变量**（`archive.read_fstring()` 直接丢弃了），而 FunctionReference 路径 L849 也没有存入。这不会导致错误，但说明两者结构一致。

**最可能的原因：** script_serial_size 不正确，导致 PropertyTag 循环提前遇到垃圾数据或跳过有效数据，后续 Pins 数组读取时位置错位。

**风险：** MEDIUM。如果 script_serial_size 本身不正确，修复需要在读取前验证。

---

### Issue 4: First Person Mesh 组件缺失

**根因：组件提取逻辑可能遗漏了 SkeletalMeshComponent 类型的组件**

**代码位置:** `src/uasset_read/blueprint/component_extractor.py` L22-53

```python
def extract_components(export_map, import_map):
    for export in export_map:
        if not export.properties:
            continue
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name is None or "Component" not in class_name:
            continue
        # ... 提取
```

**分析：** 过滤器只检查 `class_name` 是否包含 `"Component"` 字符串。`SkeletalMeshComponent` 包含 "Component"，应该通过过滤。

**可能的原因：**
1. **`export.properties` 为空（L37 检查）：** First Person Mesh 的 ExportMap 条目可能没有解析出 properties（属性解析失败），导致被跳过
2. **`resolve_class_name` 返回 `None`：** class_index 指向的条目不存在或格式不正确
3. **组件在 SCS 结构中而非独立 Export：** UE 的 SimpleConstructionScript 组件可能在 BPGC 的序列化数据中，而非独立的 ExportMap 条目

**验证方法：** 检查 BP_FirstPersonCharacter.uasset 的 ExportMap，查找 class_name 包含 "SkeletalMesh" 或 "Mesh" 的条目，确认其 properties 是否非空。

**风险：** LOW。组件提取是独立模块，修复不影响 graph 解析。

---

### Issue 5: Blueprint.functions 为空

**根因：`extract_blueprint_metadata()` 硬编码 `functions=[]`，从未填充**

**代码位置:** `src/uasset_read/blueprint/variable_extractor.py` L429-436

```python
meta = BlueprintMetadata(
    is_blueprint=True,
    parent_class=parent_class,
    variables=variables,
    functions=[],    # <-- 硬编码空列表
    events=[],       # <-- 硬编码空列表
)
```

**分析：** `BlueprintMetadata` 的 `functions` 和 `events` 字段始终为空列表。没有代码从以下来源提取函数：
- **BlueprintGeneratedClass 的 FuncMap 属性**（UE 蓝图函数存储在 BPGC 的 FuncMap: TMap<FName, UFunction*> 中）
- **EventGraph 中的 K2Node_FunctionEntry 节点**（可以作为 fallback）
- **UStruct exports（Function 类型的导出）**

**修复策略：**
1. **主要路径：** 从 BPGC 的 `FuncMap` 属性提取函数列表。这需要解析 BPGC export 的 tagged properties，找到 `FuncMap`（TMapProperty），遍历其键值对。
2. **Fallback 路径：** 从 EventGraph 的 `K2Node_FunctionEntry` 节点提取函数名和签名（已有代码在 `flow_builder.py` 的 `build_function_graphs()` 中做了类似工作，但那是从图层面，不是从 BlueprintMetadata 层面）。

**相关代码参考：** `graph/flow_builder.py` L945-1132 `build_function_graphs()` 已经从 FunctionEntry 节点提取函数名、签名、执行流。可以复用此逻辑来填充 `BlueprintMetadata.functions`。

**风险：** MEDIUM。新增函数提取逻辑不影响现有变量提取，但需要确保 FuncMap 解析不会破坏属性读取位置。

---

## Fix Strategy by Issue

### Issue 1 Fix: 节点收集增强

**文件:** `src/uasset_read/serializers/graph.py` L1017-1055

**策略：**
1. 在主路径（L1027-1036）执行后，如果 `len(nodes) == 0`，**仍然执行 fallback 路径**（不只是 `nodes_count == 0` 时）。
2. 在 fallback 路径中，增加对已经收集过的节点的去重检查（避免重复解析）。
3. 放宽类名过滤器：除了现有的 K2Node/EdGraphNode/Node 匹配，增加对 `"SCS_Node"` 和其他可能包含节点数据的类型的支持。

**伪代码：**
```python
# 主路径后，增加条件 fallback
if len(nodes) == 0 and graph_export_idx > 0:
    collected_indices = set(id(n) for n in nodes)  # 去重
    for node_export in export_map:
        if node_export.outer_index.index == graph_export_idx:
            if id(node_export) in collected_indices:
                continue  # 已收集
            node_class = _gac(...)
            if node_class and (node_class.startswith("K2Node") or ...):
                ...
```

### Issue 2 Fix: read_name() sentinel 修复

**文件:** `src/uasset_read/archive.py` L260-269

**策略：** 不改变返回值类型（保持返回 str），但：
1. 返回空字符串 `""` 替代 `"None"` 字符串
2. 添加 warning 日志，包含 index、name_map 长度、archive position
3. 所有消费 `read_name()` 结果的代码需要更新 `== "None"` 检查为 `== ""` 或 `not value`

**或者更安全的方案：** 保持 `"None"` 返回值不变，但增加一个 `read_name_safe()` 方法返回 `(str, bool)` 元组（值 + 是否有效），让关键调用方（如 `read_fmember_reference`）使用新方法。

**需要更新的位置：**
- `serializers/graph.py` L586: `member_name = archive.read_name(name_map)`
- `serializers/graph.py` L851: `m_name = archive.read_name(name_map)`
- `serializers/graph.py` L886: `m_name = archive.read_name(name_map)`
- `serializers/property_tags.py` L128: `tag.name = archive.read_name(name_map)` — `"None"` 是 PropertyTag 终止标记，必须保持

**风险缓解：** PropertyTag 的 `"None"` 终止标记（`property_tags.py` L130-131）依赖字面字符串 `"None"`，不能修改。建议新增方法而非修改现有方法。

### Issue 3 Fix: K2Node_Event 解析诊断

**文件:** `src/uasset_read/serializers/graph.py` L794-986

**策略：**
1. **先诊断再修复：** 在 `read_ue_graph_node()` 的关键位置添加 try/except + logging，记录异常类型、位置、和已读取的字段值。
2. **重点检查：**
   - `script_serial_size` 是否正确（与 ExportMap 中的值比较）
   - PropertyTag 循环中每个 tag 的 name/type/size
   - Pins 数组读取前的位置校验
3. **可能的修复：** 如果发现 script_serial_size 不正确，在 PropertyTag 循环中添加边界保护（`archive.tell() < script_end` 已有，但可能需要更早的退出条件）。

### Issue 4 Fix: 组件提取验证

**文件:** `src/uasset_read/blueprint/component_extractor.py` L22-53

**策略：**
1. 添加 debug logging：记录每个被跳过的 export 及其原因（properties 为空 / class_name 不含 Component / class_name 为 None）
2. 如果 First Person Mesh 在 ExportMap 中但 properties 为空，检查属性解析器是否正确处理了该类型
3. 如果 First Person Mesh 不在独立 Export 中，可能需要从 SCS（SimpleConstructionScript）的序列化数据中提取

### Issue 5 Fix: Blueprint.functions 填充

**文件:** `src/uasset_read/blueprint/variable_extractor.py` L429-436

**策略：**
1. **Primary path:** 解析 BPGC 的 `FuncMap` 属性。FuncMap 是 `TMap<FName, UObject*>` 格式，需要：
   - 在属性解析中找到 `FuncMap` PropertyTag
   - 读取 TMap：count (i32) + count * (FName + PackageIndex)
   - 对每个函数条目，解析 UFunction 的签名（参数、返回值、flags）
2. **Fallback path:** 从 EventGraph 的 `K2Node_FunctionEntry` 节点提取（复用 `flow_builder.py` 的逻辑）：
   - 遍历 graph.nodes，找到 class_name == "K2Node_FunctionEntry" 的节点
   - 从 node_data.function_reference 获取函数名
   - 从 pins 提取签名（已有 `_extract_signature_from_pins()` 函数）

**参考：** `graph/flow_builder.py` L988-1028 已有 FunctionEntry 到签名的提取逻辑。

## Standard Stack

No new packages needed. All fixes are within existing codebase modules.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FName 序列化格式 | 自定义 FName 解析 | UE C++ `FArchive& operator<<(FName&)` 镜像 | UE 有复杂的 name_map 索引 + instance number 格式，手写易出错 |
| TMap 属性解析 | 手动解析 TMap 二进制 | `parsers/property_types.py` 已有的 TMap 解析 | 已有容器属性解析基础设施 |
| FunctionEntry 签名提取 | 重新实现 Pin 扫描 | `flow_builder.py` 的 `_extract_signature_from_pins()` | 已有经过测试的签名提取逻辑 |

## Common Pitfalls

### Pitfall 1: "None" 字符串 vs Python None
**What goes wrong:** `read_name()` 返回字面字符串 `"None"`，消费方可能误以为是有效名称
**Why it happens:** 索引越界时的 fallback 行为设计为返回 `"None"`（可能是为了与 UE 的 FName::None 对应）
**How to avoid:** 关键调用方（FMemberReference 解析）应检查结果是否为 `"None"` 并记录 warning

### Pitfall 2: archive 位置偏移调试困难
**What goes wrong:** 某个字段读取不正确导致后续所有字段错位
**Why it happens:** FArchive 是流式读取，一个错误偏移会连锁影响后续所有读取
**How to avoid:** 在关键读取点前后记录 `archive.tell()` 位置，使用已知偏移验证
**Warning signs:** 字符串字段读到二进制数据、size 字段读到超大值

### Pitfall 3: script_serial_size 不可靠
**What goes wrong:** ExportMap 中的 script_serial_size 与实际序列化数据大小不一致
**Why it happens:** UE 编辑器可能在不同版本间改变了序列化格式
**How to avoid:** PropertyTag 循环应同时检查 `archive.tell() < script_end` AND tag.name == "None" 终止标记

## Code Examples

### 安全的 read_name 调用模式（用于关键路径）
```python
# Source: archive.py L260-269 + 建议的增强
def read_name(self, name_map: list) -> str:
    index = self.read_u32()
    number = self.read_u32()
    if 0 <= index < len(name_map):
        base_name = name_map[index]
        if number > 0:
            return f"{base_name}_{number}"
        return base_name
    # 保持 "None" 返回值（PropertyTag 终止标记依赖它）
    # 但添加日志帮助诊断
    logger = logging.getLogger(__name__)
    logger.debug("read_name: index %d out of range (name_map len=%d) at pos %d",
                 index, len(name_map), self.tell() - 8)
    return "None"
```

### 节点收集 fallback 增强
```python
# Source: graph.py L1037-1055 修改建议
# 修改条件：nodes_count == 0 OR 主路径未收集到节点
if (nodes_count == 0 or len(nodes) == 0) and graph_export_idx > 0:
    logger.debug("Using outer_index fallback for graph %s (nodes_count=%d, collected=%d)",
                 graph_export.object_name, nodes_count, len(nodes))
    for node_export in export_map:
        if node_export.outer_index.index == graph_export_idx:
            node_class = _gac(node_export, import_map, export_map, linker)
            if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                # ... 现有逻辑
```

### Blueprint.functions 从 FunctionEntry 提取
```python
# Source: flow_builder.py L988-1028 + variable_extractor.py 集成
def _extract_functions_from_graphs(graphs: List[UEdGraph]) -> List[BlueprintFunction]:
    """从 EventGraph 的 FunctionEntry 节点提取函数元数据（Fallback 路径）。"""
    functions = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name == "K2Node_FunctionEntry":
                nd = node.node_data
                if nd:
                    fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                    if fr:
                        func = BlueprintFunction(
                            name=fr.member_name if fr.member_name != "None" else "Unknown",
                            return_type="",
                            parameters=[],
                            function_flags=0,
                        )
                        # 从 pins 提取签名
                        from uasset_read.graph.flow_builder import _extract_signature_from_pins
                        sig = _extract_signature_from_pins(node)
                        func.return_type = sig.get("return_type", "")
                        func.parameters = sig.get("parameters", [])
                        functions.append(func)
    return functions
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | UE5 UEdGraph::Serialize() 格式与 UE4 基本一致（Schema + Nodes + GraphGuid + bEditable） | Issue 1 | 如果格式有额外字段，主路径 nodes_count 永远读错 |
| A2 | FName 序列化格式为 (u32 index + u32 instance) 两字段 | Issue 2 | 如果 UE5 有 CasePreservingIndex 第三字段，所有 read_name 调用都错位 |
| A3 | First Person Mesh 在 ExportMap 中有独立条目 | Issue 4 | 如果嵌入 SCS 序列化数据，需要完全不同的提取路径 |
| A4 | BPGC 的 FuncMap 属性包含函数列表 | Issue 5 | 如果函数存储在别处（如 FunctionMap），需要调整提取路径 |

## Open Questions

1. **UE5 UEdGraph::Serialize() 的确切格式**
   - What we know: 代码假设 Schema(i32) + Nodes(TArray<PkgIdx>) + GraphGuid(16B) + bEditable(u8)
   - What's unclear: UE5 是否有额外的 SerializedPropertyGuid 或其他字段
   - Recommendation: 对比 UE 5.7 EdGraph.cpp 源码中 UEdGraph::Serialize() 实现

2. **FName 在 UE5 中的序列化格式是否包含 CasePreservingIndex**
   - What we know: `read_name()` 读取 2 个 u32（index + number）
   - What's unclear: UE5 可能序列化为 3 个 u32（index + CasePreservingIndex + number）
   - Recommendation: 检查 UE 5.7 FName 序列化代码或 CUE4Parse 的 FName 读取实现

3. **BP_FirstPersonCharacter.uasset 的实际 ExportMap 内容**
   - What we know: 9/16+ 节点被解析
   - What's unclear: 缺失的 7+ 节点的 class_name、outer_index、serial_size 是什么
   - Recommendation: 运行解析器并 dump ExportMap 信息，特别是 class_name 包含 "K2Node" 的条目

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml (tool.pytest.ini_options) |
| Quick run command | `python -m pytest tests/test_graph_parsing.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| 72E-01 | EventGraph 节点解析覆盖率 > 90% | integration | `python -m pytest tests/test_graph_parsing.py::test_eventgraph_node_count -x` | Need to create |
| 72E-02 | function_reference.member_name != "None" | unit | `python -m pytest tests/test_graph_parsing.py::test_function_name_not_none -x` | Need to create |
| 72E-03 | K2Node_Event 无 _parse_error | unit | `python -m pytest tests/test_graph_parsing.py::test_event_nodes_no_parse_error -x` | Need to create |
| 72E-04 | First Person Mesh 组件存在 | integration | `python -m pytest tests/test_graph_parsing.py::test_skeletal_mesh_component -x` | Need to create |
| 72E-05 | Blueprint.functions 非空 | unit | `python -m pytest tests/test_graph_parsing.py::test_blueprint_functions_not_empty -x` | Need to create |

### Wave 0 Gaps
- [ ] 需要针对 BP_FirstPersonCharacter.uasset 的集成测试（确认 test asset 路径可用）
- [ ] 现有 test_graph_parsing.py 需要扩展以覆盖 5 个 issue
- [ ] 可能需要添加 debug dump 工具来可视化 ExportMap 节点结构

## Security Domain

N/A — 此 phase 为纯解析逻辑修复，不涉及网络输入、用户输入、或安全敏感操作。

## Sources

### Primary (HIGH confidence)
- Code review: `src/uasset_read/serializers/graph.py` (1073 lines) — node collection, PropertyTag parsing
- Code review: `src/uasset_read/archive.py` (287 lines) — read_name(), read_fstring()
- Code review: `src/uasset_read/blueprint/variable_extractor.py` (603 lines) — extract_blueprint_metadata()
- Code review: `src/uasset_read/blueprint/component_extractor.py` (82 lines) — extract_components()
- Code review: `src/uasset_read/graph/flow_builder.py` (1133 lines) — build_function_graphs(), _extract_signature_from_pins()

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` — Phase 72-E issue list and severity
- CLAUDE.md — project architecture and module layout

### Tertiary (LOW confidence)
- A1-A4 assumptions about UE5 serialization format (need UE source code verification)

## Metadata

**Confidence breakdown:**
- Standard stack: N/A (no new packages)
- Root cause analysis: MEDIUM — code review identifies likely causes, needs binary-level verification
- Fix strategies: MEDIUM — strategies are sound but depend on root cause being correct
- Pitfalls: HIGH — based on observed code patterns

**Research date:** 2026-05-23
**Valid until:** 14 days (stable codebase, fixes are internal)
