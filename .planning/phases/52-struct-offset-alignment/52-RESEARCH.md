# Phase 52: 函数图节点解析 - Research

**Researched:** 2026-05-17
**Domain:** UE Blueprint Function Graph / K2Node_FunctionEntry parsing
**Confidence:** HIGH

## Summary

Phase 52 的核心任务是从 .uasset 中识别和解析 `K2Node_FunctionEntry` 节点，区分 EventGraph 和 Function Graph，使解析器能提取函数级别的图结构。

**Primary recommendation:** 最小改动方案 — 修复 `read_ue_graph_node()` 中已解析但未使用的 `function_reference` 变量，添加 `K2Node_FunctionEntry` 到 `create_node_from_archive()` 分派，将 `K2Node_FunctionEntry` 加入 `START_EVENT_TYPES`。

**关键发现：** `read_ue_graph_node()` 已经解析了 `FunctionReference` PropertyTag（第 773-808 行），但该值仅存入局部变量，未传递给 `create_node_from_archive()` 或存入 `base_node`。对于 K2Node_FunctionEntry，当前它落入 "unknown type" 分支，`node_data` 为 `None` 或仅含 `_raw_properties`（仅记录 ExtraFlags 偏移而非值）。

**测试资产确认：** `BP_FirstPersonCharacter.uasset` 包含 4 个图：
- `EventGraph` (18 nodes) — K2Node_Event, K2Node_EnhancedInputAction, K2Node_CallFunction
- `Move` (11 nodes) — K2Node_FunctionEntry + K2Node_CallFunction + K2Node_Knot
- `Aim` (7 nodes) — K2Node_FunctionEntry + K2Node_CallFunction + K2Node_Knot
- `UserConstructionScript` (1 node) — 仅 K2Node_FunctionEntry

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 函数图区分策略
- **D-01:** 使用组合判断区分 EventGraph 和 Function Graph：graph_class 为主（UberEdGraph 通常是函数图容器），辅以 graph_name 模式和图中是否存在 K2Node_FunctionEntry 节点。三者组合判断，避免单一条件误判。

#### Knot 节点处理
- **D-02:** Knot 节点在函数调用链中采用透明穿透策略 — 不产生独立节点记录，数据流和执流直接穿透到下一个有意义的节点。目标是将 JSON 输出翻译为等价的 C++ 函数实现，Knot 作为 UE 编辑器内部的中继概念不需要映射到 C++。

#### 执行流整合
- **D-03:** 复用现有 build_execution_flows() 函数处理函数图执行流追踪，将 K2Node_FunctionEntry 加入 START_EVENT_TYPES。最小改动方案，利用已有的 exec pin 追踪逻辑。

### Claude's Discretion
- FunctionEntry 节点的具体字段读取深度由 researcher 根据 UE 源码确定（至少包含 FunctionReference）
- graph_name 的命名模式判断逻辑由 planner 根据实际情况设计

### Deferred Ideas (OUT OF SCOPE)
- Pure 函数的数据流追踪（DATA-01/02/03） — Phase 54
- JSON function_graphs 数组输出 — Phase 55
- 局部变量追踪 — v2 scope，不在 v9.0 范围内
- 控制流节点（Branch/DoOnce） — v2 scope，不在 v9.0 范围内

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 二进制序列化 (read_k2node_functionentry) | API / Backend | — | FArchive 解析层，直接读取 .uasset 二进制 |
| 节点数据模型 (K2NodeFunctionEntry) | API / Backend | — | 数据类定义，继承 UEdGraphNode |
| 节点工厂分派 (create_node_from_archive) | API / Backend | — | 工厂模式，按 class_name 分发 |
| 图类型判断 (is_function_graph) | API / Backend | — | 基于 graph_class + graph_name + 节点类型组合判断 |
| 执行流构建 (build_execution_flows) | API / Backend | — | 复用现有逻辑，仅需扩展 START_EVENT_TYPES |

## Standard Stack

本项目零运行时依赖，所有改动均为项目内代码修改，无需新增外部库。

### 需要修改的文件

| File | Change Type | Purpose |
|------|-------------|---------|
| `src/uasset_read/serializers/graph.py` | Modify | 添加 read_k2node_functionentry(), create_node_from_archive 分派, 修复 function_reference 传递 |
| `src/uasset_read/models/node_types.py` | Modify | 添加 K2NodeFunctionEntry dataclass |
| `src/uasset_read/models/__init__.py` | Modify | 导出 K2NodeFunctionEntry |
| `src/uasset_read/__init__.py` | Modify | 导出 read_k2node_functionentry, K2NodeFunctionEntry |
| `src/uasset_read/constants.py` | Modify | START_EVENT_TYPES 添加 K2Node_FunctionEntry |
| `src/uasset_read/graph/flow_builder.py` | Modify | format_node_dict 添加 function_entry_reference 提取 |

## Architecture Patterns

### 现有节点解析模式

当前代码遵循严格模式：

```
read_ue_graph_node() 
  → 解析 PropertyTags (FunctionReference, EventReference, NodePosX/Y, NodeGuid, NodeComment)
  → 解析 Pins 数组
  → 创建 base_node (UEdGraphNode)
  → create_node_from_archive() 按 class_name 分派
    → read_k2node_*() 读取节点特有字段
    → 设置 base_node.node_data
```

**关键问题：** `read_ue_graph_node()` 第 748 行声明了 `function_reference: Optional[FMemberReference] = None`，在第 773-808 行正确解析，但该变量**未被使用**——它既未存入 `base_node`，也未传给 `create_node_from_archive()`。

### K2Node_FunctionEntry 在 UE 源码中的继承层次

```
UK2Node_FunctionEntry
  └── UK2Node_FunctionTerminator    ← FunctionReference (FMemberReference)
        └── UK2Node_EditablePinBase ← bIsEditable, UserDefinedPins
              └── UK2Node
                    └── UEdGraphNode
```

**K2Node_FunctionEntry 特有字段**（来自 `K2Node_FunctionEntry.h`）：
- `FName CustomGeneratedFunctionName` — 可选的自定义生成函数名
- `FKismetUserDeclaredFunctionMetadata MetaData` — 函数元数据（Tooltip, Category, Keywords 等）
- `TArray<FBPVariableDescription> LocalVariables` — 局部变量数组
- `bool bEnforceConstCorrectness` — 是否强制 const 正确性
- `int32 ExtraFlags` — 函数标志（FUNC_Static, FUNC_Const, FUNC_BlueprintPure 等）

**继承自 K2Node_FunctionTerminator**：
- `FMemberReference FunctionReference` — 函数引用（MemberName, MemberParent 等）

**二进制序列化：** 所有 UPROPERTY 字段在 .uasset 中通过 script_serial 的 PropertyTag 格式存储。`read_ue_graph_node()` 已经能正确解析 `FunctionReference`，但当前未将其存入 node_data。

### 推荐的修改方案

**方案 A（推荐 — 最小改动）：**

1. `read_ue_graph_node()` 将解析的 `function_reference` 存入一个临时字典，通过 `create_node_from_archive()` 传入
2. 添加 `read_k2node_functionentry()` — 从 `_node_refs` 参数获取已解析的 function_reference，返回 dict
3. `create_node_from_archive()` 添加 `elif class_name == "K2Node_FunctionEntry"` 分支
4. `constants.py` 中 `START_EVENT_TYPES` 添加 `"K2Node_FunctionEntry"`
5. `flow_builder.py` 中 `_get_start_event_name()` 添加 FunctionEntry 处理

**方案 B（重构 — 较大改动）：**

重构 `read_ue_graph_node()` 统一将所有已解析的 PropertyTag 引用存入 base_node，修改所有现有节点读取器。这超出了 Phase 52 的范围。

## FunctionEntry 的 PropertyTag 结构

根据 UE 源码和实际测试资产，K2Node_FunctionEntry 的 script_serial 中包含以下 PropertyTag：

| PropertyTag | Type | 出现频率 | 说明 |
|-------------|------|----------|------|
| FunctionReference | Struct | 100% | 函数名（MemberName）、可选的 MemberParent |
| ExtraFlags | IntProperty | 常见 | 函数标志位（FUNC_* 组合） |
| NodePosX | IntProperty | 100% | 编辑器位置 X |
| NodePosY | IntProperty | 100% | 编辑器位置 Y |
| NodeGuid | GuidProperty | 100% | 节点唯一标识 |
| bIsEditable | BoolProperty | 常见 | 是否可编辑 |

**实际测试数据：**
- Move FunctionEntry: `FunctionReference=(MemberName="Move")`, `ExtraFlags=201457664`
- Aim FunctionEntry: `FunctionReference=(MemberName="Aim")`, `ExtraFlags=201457664`
- UserConstructionScript: `FunctionReference` 存在（从 export 名推断）

**注意：** 对于自定义函数（非继承），`FunctionReference` 的 `MemberParent` 为 None，只有 `MemberName` 有值。这是正常行为 — 自定义函数的父类是蓝图自身。

## Function Graph 与 EventGraph 的区分

**关键发现：** 在测试资产中，**所有图的 `graph_class` 都是 `"EdGraph"`**，没有 "UberEdGraph"。`"UberEdGraph"` 是项目内代码中使用的命名（GRAPH_TYPE_MAP 中映射到 "uber"），但在实际 .uasset 中图容器统一序列化为 `EdGraph`。

因此 D-01 中的 "graph_class 为主" 判断策略需要调整：

**实际区分策略（基于实证）：**
1. 检查图中是否存在 `K2Node_FunctionEntry` 节点 → 是则为 Function Graph
2. 检查图中是否存在 `K2Node_Event` 节点 → 是则为 EventGraph
3. graph_name 模式辅助判断（EventGraph 通常名为 "EventGraph"，Function Graph 名为函数名如 "Move"、"Aim"）

## Package Legitimacy Audit

> 本阶段为零运行时依赖修改，不安装任何外部包。所有改动为项目内 Python 代码变更。

**不適用 — No external packages to audit.**

## Common Pitfalls

### Pitfall 1: FunctionReference 解析但未使用
**What goes wrong:** `read_ue_graph_node()` 第 748 行声明了 `function_reference` 变量，第 773-808 行正确解析，但该变量未传递给下游函数，导致 K2Node_FunctionEntry 无法获取函数名。
**Why it happens:** 代码演进过程中，FunctionReference 的解析是为了 K2Node_CallFunction/K2Node_Event，但后续改为在 `read_k2node_*()` 中重新读取（从 archive 位置）。然而对于 FunctionEntry，FunctionReference 只存在于 PropertyTag 中，不存在于直接序列化流中。
**How to avoid:** 将 `function_reference` 作为参数传入 `create_node_from_archive()`，在 FunctionEntry 分派分支中使用。
**Warning signs:** `node_data` 为 `None` 或仅含 `_raw_properties`。

### Pitfall 2: ExtraFlags 值未被读取
**What goes wrong:** 当前 `raw_properties` 仅记录 ExtraFlags 的偏移和大小（`{'size': 4, 'offset': 129631}`），未实际读取值。
**Why it happens:** 未知 PropertyTag 的处理策略是记录位置而非读取内容（避免读取错误的类型）。
**How to avoid:** 在 `read_ue_graph_node()` 中为已知 PropertyTag（ExtraFlags）添加显式分支，读取 i32 值。

### Pitfall 3: 图类型判断依赖不存在的 "UberEdGraph"
**What goes wrong:** 代码中 GRAPH_TYPE_MAP 映射 `UberEdGraph→"uber"`，但实际 .uasset 中所有图都是 `EdGraph` 类型。
**Why it happens:** "UberEdGraph" 可能是旧版 UE 或特定场景下的命名，在 UE5.7 的 FirstPerson 示例中不存在。
**How to avoid:** 使用节点类型组合判断（D-01 策略），而非依赖 graph_class。

### Pitfall 4: 修改 START_EVENT_TYPES 影响 EventGraph
**What goes wrong:** 将 K2Node_FunctionEntry 加入 START_EVENT_TYPES 后，`build_execution_flows()` 会对 EventGraph 中的 FunctionEntry 也尝试追踪（虽然 EventGraph 中通常没有 FunctionEntry）。
**Why it happens:** START_EVENT_TYPES 是全局集合，应用于所有图。
**How to avoid:** 由于 EventGraph 中不含 K2Node_FunctionEntry，此风险极低。但需在测试中验证 EventGraph 的执行流输出不变。

## Code Examples

### read_k2node_functionentry 模式（复用已有的 read_k2node_event 模式）

```python
# Source: 基于现有 read_k2node_event() 模式
def read_k2node_functionentry(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,  # 从 read_ue_graph_node 传入
) -> Dict[str, Any]:
    """读取 K2Node_FunctionEntry 特有字段。

    FunctionReference 已在 read_ue_graph_node() 中从 PropertyTag 解析，
    直接复用传入的值。ExtraFlags 同样在 PropertyTag 中已解析。
    """
    return {
        "function_reference": function_reference,
    }
```

### create_node_from_archive 分派扩展

```python
# 在现有 elif 链中添加
elif class_name == "K2Node_FunctionEntry":
    fr = node_refs.get('function_reference')
    base_node.node_data = read_k2node_functionentry(
        archive, name_map, import_map, export_map, linker,
        function_reference=fr,
    )
```

### _get_start_event_name 扩展（flow_builder.py）

```python
elif node.class_name == "K2Node_FunctionEntry":
    nd = node.node_data
    if nd:
        if isinstance(nd, dict):
            fr = nd.get("function_reference")
        else:
            fr = getattr(nd, 'function_reference', None)
        if fr:
            mn = getattr(fr, 'member_name', None) if not isinstance(fr, dict) else fr.get("member_name")
            if mn and mn != "None":
                return mn
    return node.class_name
```

### Function Graph 判断函数

```python
def is_function_graph(graph: UEdGraph) -> bool:
    """判断一个图是否为函数图（非事件图）。

    组合判断策略（D-01）：
    1. 图中存在 K2Node_FunctionEntry → Function Graph
    2. 图中存在 K2Node_Event → EventGraph
    3. graph_name 模式辅助（EventGraph 通常名为 "EventGraph"）
    """
    node_types = {n.class_name for n in graph.nodes}
    if "K2Node_FunctionEntry" in node_types:
        return True
    if "K2Node_Event" in node_types:
        return False
    # Fallback: graph_name 模式
    return graph.graph_name.lower() != "eventgraph"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 无 FunctionEntry 支持 | 需要添加完整解析 | Phase 52 | 能区分函数图和事件图 |
| FunctionReference 解析但未使用 | 需要传递给 create_node_from_archive | 现有 bug | 修复后 FunctionEntry 可获得函数名 |
| START_EVENT_TYPES 仅含 Event 类型 | 需要添加 FunctionEntry | Phase 52 | 执行流追踪可处理函数图 |

**Deprecated/outdated:**
- `UberEdGraph` 作为 Function Graph 标识：在实际 .uasset 中所有图都是 `EdGraph` 类型，需用节点类型组合判断

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 所有测试资产的图 `graph_class` 都是 `"EdGraph"`（非 `"UberEdGraph"`） | Function Graph 区分 | 如果存在 UberEdGraph 类型的图，当前判断逻辑需要扩展 |
| A2 | K2Node_FunctionEntry 的 FunctionReference 只存在于 PropertyTag 中（不在直接序列化流中） | Code Examples | 如果 UE 版本不同导致序列化方式变化，需要调整解析逻辑 |
| A3 | `ExtraFlags=201457664` 在测试资产中是固定值 — 可能包含 FUNC_BlueprintEvent 等标志 | PropertyTag 结构 | 不同函数可能有不同标志，但这不影响 Phase 52 的核心功能 |

## Open Questions (RESOLVED)

1. **ExtraFlags 的具体位含义：** `201457664` (0x0C020000) 包含哪些 FUNC_* 标志？— **[RESOLVED: 无需解决]** Phase 52 只需存储 ExtraFlags 原始值，不需要解析具体位含义。后续 Phase 53/54 如需判断函数类型（Pure/Impure）时可再研究。
2. **UserConstructionScript FunctionEntry 的 FunctionReference：** 该节点的 `node_data` 为 `None`（无 raw_properties），需要确认其 script_serial 是否正确解析。— **[RESOLVED: 无需解决]** UserConstructionScript 是 Blueprint 构造函数图，不在 v9.0 函数调用链解析范围内（TEST-01~04 仅覆盖 Move/Aim/Jump/StopJumping）。Phase 52 只需确保解析器不崩溃即可。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 全部代码 | ✓ | 3.14.3 | — |
| pytest | 测试 | ✓ | 9.0.3 | — |
| BP_FirstPersonCharacter.uasset | 测试资产 | ✓ | UE5.7 | — |
| UnrealEngine Source | 参考验证 | ✓ | UE5.7 | — |

**无缺失依赖。**

## Sources

### Primary (HIGH confidence)
- UE C++ 源码: `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node_FunctionEntry.h` — 完整类定义和字段
- UE C++ 源码: `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Private\K2Node_FunctionEntry.cpp` — Serialize() 实现
- UE C++ 源码: `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node_FunctionTerminator.h` — FunctionReference 字段定义
- UE C++ 源码: `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node_EditablePinBase.h` — bIsEditable, UserDefinedPins
- 项目源码: `src/uasset_read/serializers/graph.py` — 现有节点解析模式
- 项目源码: `src/uasset_read/constants.py` — START_EVENT_TYPES, GRAPH_TYPE_MAP
- 项目源码: `src/uasset_read/graph/flow_builder.py` — 执行流构建逻辑
- 项目源码: `src/uasset_read/models/node_types.py` — K2Node dataclass 定义
- 实际测试资产解析: `BP_FirstPersonCharacter.uasset` — 4 个图的节点类型和 PropertyTag 内容
- 项目参考: `reference/蓝图节点文本参考.md` — UE 编辑器导出的完整节点文本

### Secondary (MEDIUM confidence)
- 项目 CLAUDE.md — 架构和项目组织
- `.planning/REQUIREMENTS.md` — FUNC-01/02 需求定义

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — 无外部依赖，全部为项目内代码
- Architecture: HIGH — 基于 UE 源码 + 实际 .uasset 解析验证
- Pitfalls: HIGH — 通过实际代码审查和测试资产分析确认
- PropertyTag 结构: HIGH — 通过实际解析输出 + UE 源码验证

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (30 天 — 稳定代码库)
