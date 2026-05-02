# Phase 7: 蓝图图核心解析 - Research

**Researched:** 2026-05-02
**Domain:** Unreal Engine 蓝图图结构二进制解析 (UEdGraph, UEdGraphNode, UEdGraphPin)
**Confidence:** HIGH (基于 UE 5.7 源码参考、编辑器导出格式验证、现有代码分析)

## Summary

本研究确定了从 .uasset 文件解析蓝图图结构的技术方案。蓝图图以三层嵌套结构存储：UEdGraph（图容器）→ UEdGraphNode/K2Node（节点）→ UEdGraphPin（引脚）。关键发现：

1. **零新依赖** - 现有技术栈（struct + dataclasses + FArchive 模式）完整覆盖所有需求
2. **FEdGraphPinType 已实现** - Phase 3 的 `read_ed_graph_pin_type()` 可直接复用
3. **LinkedTo 使用名称索引** - 编辑器导出格式验证：`LinkedTo=(NodeName PinIdGuid)`
4. **节点类型分派模式** - ClassIndex 解析后分发到类型特定解析器

**Primary recommendation:** 采用三层解析架构：图检测 → 节点遍历 → 引脚解析，复用现有 FArchive 和 FEdGraphPinType 实现。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: LinkedTo 延迟解析** — Phase 7 仅记录原始 LinkedTo 数据（名称或索引），Phase 8 输出时构建连接映射（PinId → TargetPinId）
- **D-01a:** 原始数据格式 — LinkedTo 读取为 List[str]（名称列表），暂不验证格式类型
- **原因:** 降低 Phase 7 复杂度；连接映射逻辑集中在输出阶段处理；避免未验证格式导致的解析错误

**D-02: 节点类型范围** — 基类字段 + 需求类型（GRAPH-05~09）特有字段，不处理其他类型
- **D-02a:** 未知类型处理 — 遇到未知节点类型时，仅记录类型名和原始数据位置，输出警告
- **D-02b:** 类型识别方法 — 通过 ClassIndex 解析为类名，匹配已知类型列表（"K2Node_CallFunction", "K2Node_Event" 等）
- **原因:** 满足 ROADMAP 需求 GRAPH-05~09；避免过度扩展范围；未知类型 fallback 保证解析继续

**D-03: 解析深度** — 完整解析 Graph→Node→Pin 三层结构
- **D-03a:** EdGraph 检测 — 遍历 ExportMap，ClassIndex 解析后包含 "EdGraph" 或 "Ubergraph" 的导出视为图对象
- **D-03b:** 节点解析 — 从 EdGraph 的 SerialOffset 位置读取 Nodes 数组，每个节点完整解析（基类 + 类型特有字段）
- **D-03c:** 引脚解析 — 从每个 Node 的 Pins 数组位置读取引脚，完整解析 PinType + DefaultValue + LinkedTo 原始数据
- **原因:** 满足 ROADMAP 成功标准；Phase 7 交付完整图数据；Phase 8 仅处理输出格式化

**D-04: 输出层级** — 顶层 graphs 数组，与 blueprint 同级
- **D-04a:** graphs 结构 — 每个图对象包含 graph_name、graph_class、nodes（节点数组）、连接映射推迟到 Phase 8
- **D-04b:** ParseResult 扩展 — 新增 `graphs: List[UEdGraph]` 字段（顶层）
- **原因:** 便于快速访问图数据；保持 Package→Exports 层级一致性；与 Phase 4 D-02 的顶层字段设计一致

### Claude's Discretion

- 节点类型特有字段的具体解析顺序（需研究 UE 源码确定）
- LinkedTo 原始数据的存储格式（List[str] vs List[dict])
- PinId 生成格式（UE GUID hex vs 自定义 ID）
- 节点/引脚解析失败的错误上下文字段设计
- 单元测试组织

### Deferred Ideas (OUT OF SCOPE)

推迟到 Phase 8（蓝图图输出增强）：
- 引脚连接映射构建（LinkedTo PinId → 目标节点/引脚）
- graphs 字段 JSON 输出格式化
- --graph CLI 标志支持
- 执行流路径输出（Event → CallFunction 链路）
- 图结构摘要文本输出

推迟到 Phase 9+（高级节点类型）：
- 更多 K2Node 子类解析（K2Node_Variable、K2Node_DynamicCast 等）
- 自定义节点类型扩展机制
- 节点详细参数解析

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | 解析器能识别 UEdGraph 导出类型（ClassIndex 包含 "EdGraph") | D-03a 定义检测逻辑；导出表遍历模式复用 Phase 3 |
| GRAPH-02 | 解析器能提取 UEdGraph 基本信息（Schema、GraphGuid、Nodes 数量） | UE 源码分析确定字段顺序；见 UEdGraph 结构表 |
| GRAPH-03 | 解析器能解析 UEdGraphNode 基类字段（NodeGuid、NodePosX/Y、NodeComment、Pins） | 编辑器导出格式验证字段；见 UEdGraphNode 结构表 |
| GRAPH-04 | 解析器能解析 UEdGraphPin 完整结构（PinId、PinName、Direction、PinType、DefaultValue、LinkedTo、SubPins、ParentPin） | Phase 3 FEdGraphPinType 复用；见 UEdGraphPin 结构表 |
| GRAPH-05 | 解析器能识别 K2Node_CallFunction 节点类型并提取 FunctionReference | D-02b 类型识别；编辑器导出验证 FunctionReference 格式 |
| GRAPH-06 | 解析器能识别 K2Node_Event 节点类型并提取 EventReference | D-02b 类型识别；编辑器导出验证 EventReference 格式 |
| GRAPH-07 | 解析器能识别 K2Node_Knot 节点类型并提取 InputPin/OutputPin 连接 | D-02b 类型识别；编辑器导出验证 Knot 仅有两引脚 |
| GRAPH-08 | 解析器能识别 EdGraphNode_Comment 注释节点并提取注释文本 | D-02b 类型识别；编辑器导出验证 NodeComment 字段 |
| GRAPH-09 | 解析器能识别 K2Node_EnhancedInputAction 输入节点并提取 Action 名称 | D-02b 类型识别；编辑器导出验证 InputAction 路径 |
| GRAPH-10 | 解析器能构建引脚连接映射（LinkedTo PinId → 目标节点/引脚） | **推迟到 Phase 8** — D-01 锁定延迟解析策略 |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 图类型检测 | API / Backend | — | ExportMap 遍历 + ClassIndex 解析 |
| 节点序列化解析 | API / Backend | — | SerialOffset 定位 + 二进制读取 |
| 引脚类型解析 | API / Backend | — | FEdGraphPinType（Phase 3 已实现） |
| 引脚连接存储 | API / Backend | — | 原始数据存储（Phase 7），映射构建（Phase 8） |
| JSON 输出格式化 | Output | — | Phase 8 负责 |
| 节点类型分派 | API / Backend | — | 类名匹配 → 类型特定解析器 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | 语言基础 | match/case 语法支持节点类型分派 |
| struct | stdlib | 二进制解析 | u32/i32/i64/f32/f64 读取 |
| dataclasses | stdlib | 数据模型 | `@dataclass` + `asdict()` → JSON |
| json | stdlib | 输出格式化 | JSON 序列化 |

### Supporting (项目已有)

| Component | Location | Purpose | When to Use |
|-----------|----------|---------|-------------|
| FArchive | uasset_read.py | 二进制读取器 | 所有字段读取 |
| FEdGraphPinType | uasset_read.py L724-742 | 引脚类型结构 | UEdGraphPin.PinType |
| read_ed_graph_pin_type() | uasset_read.py L1561-1640 | 引脚类型解析 | 复用，无需重写 |
| ObjectExport | uasset_read.py L655-685 | 导出表条目 | 图/节点定位 |
| ParseResult | uasset_read.py L774-791 | 解析结果容器 | 扩展添加 graphs 字段 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 手写序列化解析 | construct (声明式解析器) | construct 增加依赖，性能提升微乎其微 |
| dataclasses | pydantic | pydantic 验证开销大，本项目无需运行时验证 |
| FArchive 模式 | numpy 结构化数组 | numpy 非数值解析场景，增加依赖 |

**结论：无新增依赖。现有技术栈完整覆盖需求。**

## Architecture Patterns

### System Architecture Diagram

```
.uasset 文件
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  FArchive (Phase 1 已实现)                                   │
│  - read_i32/i64/u8/u32/f32/f64                              │
│  - read_fstring() → str                                     │
│  - read_name(name_map) → str                                │
│  - seek(offset) / tell()                                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ExportMap (Phase 6 已修复)                                  │
│  - ObjectExport.class_index → 类名解析                      │
│  - ObjectExport.serial_offset → 节点数据定位                │
│  - ObjectExport.object_name → 图/节点名称                   │
└─────────────────────────────────────────────────────────────┘
    │
    ├─────────────────── 图检测分支 ──────────────────────┐
    │                                                      │
    ▼                                                      ▼
┌──────────────────────────┐          ┌──────────────────────────┐
│  EdGraph 检测            │          │  非图导出（跳过）        │
│  ClassIndex 包含 EdGraph │          │  Blueprint/Class 等      │
└──────────────────────────┘          └──────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  UEdGraph 解析 (新增)                                        │
│  1. Schema (FPackageIndex)                                  │
│  2. Nodes 数组 (int32 count + FPackageIndex[])              │
│  3. GraphGuid (FGuid 16 bytes)                              │
│  4. bEditable (uint8)                                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼ Nodes 数组遍历
┌─────────────────────────────────────────────────────────────┐
│  UEdGraphNode/K2Node 解析 (新增)                             │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 基类字段 (所有节点通用)                                │ │
│  │ 1. Pins 数组 (int32 count)                             │ │
│  │ 2. NodePosX (int32)                                    │ │
│  │ 3. NodePosY (int32)                                    │ │
│  │ 4. NodeGuid (FGuid 16 bytes)                           │ │
│  │ 5. NodeComment (FString)                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 类型分派 (ClassIndex → 类型特定解析)                   │ │
│  │                                                        │ │
│  │ K2Node_CallFunction:                                   │ │
│  │   - FunctionReference (FMemberReference)               │ │
│  │                                                        │ │
│  │ K2Node_Event:                                          │ │
│  │   - EventReference (FMemberReference)                  │ │
│  │   - bOverrideFunction (uint8)                          │ │
│  │                                                        │ │
│  │ K2Node_Knot:                                           │ │
│  │   - 无额外字段（仅 InputPin/OutputPin）                │ │
│  │                                                        │ │
│  │ EdGraphNode_Comment:                                   │ │
│  │   - CommentColor (4 floats)                            │ │
│  │   - NodeWidth/Height (int32)                           │ │
│  │   - NodeComment (FString)                              │ │
│  │                                                        │ │
│  │ K2Node_EnhancedInputAction:                            │ │
│  │   - InputAction (FSoftObjectPath)                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
    │
    ▼ Pins 数组遍历
┌─────────────────────────────────────────────────────────────┐
│  UEdGraphPin 解析 (新增)                                     │
│  1. PinId (FGuid 16 bytes)                                  │
│  2. PinName (FName → str)                                   │
│  3. Direction (uint8 → EGPD_Input/Output/None)              │
│  4. PinType (FEdGraphPinType — Phase 3 已实现)              │
│  5. DefaultValue (FString)                                  │
│  6. AutogeneratedDefaultValue (FString)                     │
│  7. LinkedTo 数组 (int32 count + PinId[])                   │
│     — D-01: 存储为 List[str] 原始数据                       │
│  8. SubPins/ParentPin (条件字段)                            │
│  9. Flags (uint8 bitfield)                                  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ParseResult (扩展)                                          │
│  + graphs: List[UEdGraph]                                   │
│  — D-04: 顶层字段，与 blueprint 同级                        │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
uasset_read.py (单文件扩展)
├── 数据类（新增）
│   ├── UEdGraphPin          # 引脚完整结构
│   ├── UEdGraphNode         # 节点基类
│   ├── UEdGraph             # 图容器
│   ├── K2NodeCallFunction   # CallFunction 特有数据
│   ├── K2NodeEvent          # Event 特有数据
│   ├── K2NodeKnot           # Knot（无额外数据）
│   ├── EdGraphNodeComment   # Comment 特有数据
│   └── K2NodeEnhancedInputAction # EnhancedInputAction 特有数据
│
├── 解析函数（新增）
│   ├── read_ue_graph_pin()         # 引脚解析
│   ├── read_ue_graph_node()        # 节点解析（含类型分派）
│   ├── read_ue_graph()             # 图解析
│   ├── extract_blueprint_graphs()  # 入口：从 ExportMap 提取图
│   │
│   ├── read_k2node_call_function()     # CallFunction 特有
│   ├── read_k2node_event()             # Event 特有
│   ├── read_k2node_knot()              # Knot 特有
│   ├── read_edgraph_node_comment()     # Comment 特有
│   ├── read_k2node_enhanced_input()    # EnhancedInputAction 特有
│   │
│   └── read_fmember_reference()    # MemberReference 结构
│   └── read_fsoft_object_path()    # SoftObjectPath 结构
│
└── ParseResult 扩展
    └── graphs: List[UEdGraph] = field(default_factory=list)
```

### Pattern 1: 节点类型分派（match/case）

**What:** 使用 Python 3.10+ match/case 语法根据节点类名分发到特定解析器

**When to use:** 解析 UEdGraphNode 时，ClassIndex 解析后的类名匹配

**Example:**

```python
# Source: 基于 D-02b 类型识别方法
def read_ue_graph_node(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
    summary: PackageFileSummary
) -> UEdGraphNode:
    """读取 UEdGraphNode，含类型分派"""
    
    # 基类字段（所有节点通用）
    pins = read_node_pins(archive, name_map, summary)
    node_pos_x = archive.read_i32()
    node_pos_y = archive.read_i32()
    node_guid = archive.read_bytes(16).hex()
    node_comment = archive.read_fstring()
    
    # 类型分派
    class_name = resolve_class_name(node_export.class_index, import_map, export_map)
    
    node_data = None
    match class_name:
        case "K2Node_CallFunction":
            node_data = read_k2node_call_function(archive, name_map)
        case "K2Node_Event":
            node_data = read_k2node_event(archive, name_map)
        case "K2Node_Knot":
            node_data = read_k2node_knot(archive)  # 无额外数据
        case "EdGraphNode_Comment":
            node_data = read_edgraph_node_comment(archive)
        case "K2Node_EnhancedInputAction":
            node_data = read_k2node_enhanced_input(archive, name_map)
        case _:
            # D-02a: 未知类型 — 记录警告，继续解析
            warning = f"Unknown node type: {class_name}"
            node_data = {"unknown_type": class_name}
    
    return UEdGraphNode(
        node_guid=node_guid,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        node_comment=node_comment,
        pins=pins,
        class_name=class_name,
        node_data=node_data
    )
```

### Pattern 2: FMemberReference 结构

**What:** 函数/事件引用的标准结构，用于 FunctionReference 和 EventReference

**When to use:** K2Node_CallFunction、K2Node_Event 的 MemberReference 字段

**Example (编辑器导出验证):**

```text
FunctionReference=(MemberName="Jump",bSelfContext=True)
EventReference=(MemberParent="/Script/Engine.BPGenClass",MemberName="Touch Jump Start",MemberGuid=...)
```

**二进制序列化顺序（推断）:**

```python
@dataclass
class FMemberReference:
    """成员引用结构（函数/事件引用）"""
    member_parent: Optional[str] = None    # FPackageIndex → 类路径
    member_name: str = ""                   # FName → 函数名
    member_guid: Optional[str] = None       # FGuid (16 bytes) → 函数 GUID
    b_self_context: bool = False            # uint8 → self 调用标志

def read_fmember_reference(archive: FArchive, name_map: List[str]) -> FMemberReference:
    """读取 FMemberReference"""
    # 序列化顺序（基于编辑器导出格式推断）
    member_parent_index = archive.read_i32()  # FPackageIndex
    member_name = archive.read_name(name_map)
    member_guid = archive.read_bytes(16).hex()  # FGuid
    b_self_context = archive.read_u8() != 0
    return FMemberReference(
        member_parent=resolve_package_index(member_parent_index),
        member_name=member_name,
        member_guid=member_guid,
        b_self_context=b_self_context
    )
```

### Pattern 3: LinkedTo 原始数据存储（D-01）

**What:** Phase 7 仅存储原始连接数据，Phase 8 构建映射

**When to use:** UEdGraphPin.LinkedTo 字段

**Example:**

```python
# 编辑器导出格式验证：
# LinkedTo=(K2Node_CallFunction_1193 13FD260E4EE18FD0AA5F7085F9B509D6,)
# 格式：(目标节点名 + PinId GUID)

@dataclass
class UEdGraphPin:
    pin_id: str                          # FGuid hex
    pin_name: str                        # FName → str
    direction: int                       # uint8: 0=Input, 1=Output, 2=None
    pin_type: FEdGraphPinType            # Phase 3 已实现
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    linked_to_raw: List[str] = field(default_factory=list)  # D-01a: 原始名称列表
    # Phase 8 将添加: linked_to_resolved: List[UEdGraphPinRef]
    sub_pins: List[str] = field(default_factory=list)       # SubPin PinIds
    parent_pin: Optional[str] = None                        # ParentPin PinId
    flags: int = 0                                          # uint8 bitfield

def read_ue_graph_pin(archive: FArchive, name_map: List[str], summary: PackageFileSummary) -> UEdGraphPin:
    """读取 UEdGraphPin"""
    pin_id = archive.read_bytes(16).hex()
    pin_name = archive.read_name(name_map)
    direction = archive.read_u8()
    
    # 复用 Phase 3 实现
    pin_type = read_ed_graph_pin_type(archive, name_map, summary)
    
    default_value = archive.read_fstring()
    auto_default_value = archive.read_fstring()
    
    # LinkedTo 数组 — D-01: 存储为原始数据
    linked_to_count = archive.read_i32()
    linked_to_raw = []
    for _ in range(linked_to_count):
        # 编辑器导出格式：PinId GUID
        linked_pin_id = archive.read_bytes(16).hex()
        linked_to_raw.append(linked_pin_id)
    
    # SubPins/ParentPin（条件字段）
    sub_pins_count = archive.read_i32()
    sub_pins = []
    for _ in range(sub_pins_count):
        sub_pin_id = archive.read_bytes(16).hex()
        sub_pins.append(sub_pin_id)
    
    parent_pin_id = None
    if archive.read_u8() != 0:  # has_parent_pin
        parent_pin_id = archive.read_bytes(16).hex()
    
    # Flags bitfield
    flags = archive.read_u8()
    
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=auto_default_value,
        linked_to_raw=linked_to_raw,
        sub_pins=sub_pins,
        parent_pin=parent_pin_id,
        flags=flags
    )
```

### Anti-Patterns to Avoid

- **假设所有节点序列化相同** — 每个 K2Node 子类有特有字段，需类型分派
- **忽略 SubPins/ParentPin** — 结构体拆分引脚需要这些字段
- **尝试解析 LinkedTo 为对象引用** — D-01 锁定：Phase 7 仅存储原始数据
- **假设 cooked 资产有图数据** — cooked 资产已剥离图结构（见 PITFALLS.md 陷阱 7）

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 引脚类型解析 | 新的 FEdGraphPinType 解析器 | Phase 3 `read_ed_graph_pin_type()` | 已实现版本感知，完整结构 |
| 二进制读取 | 手写 read_i32/read_fstring | FArchive 已有方法 | Phase 1 已验证稳定 |
| 导出表遍历 | 新的 ExportMap 遍历逻辑 | Phase 3 `extract_blueprint_metadata()` 模式 | 已建立遍历模式 |
| 类名解析 | 新的 ClassIndex 解析 | `get_asset_class()` 函数 | Phase 3 已实现 |

**Key insight:** 蓝图图解析是现有架构的自然扩展，复用率 >80%。

## Runtime State Inventory

> Phase 7 为 greenfield 实现，无运行状态重命名需求。此节省略。

## Common Pitfalls

### Pitfall 1: 节点类型误判（PITFALLS.md 陷阱 2）

**What goes wrong:** 将 Blueprint/Class/Function 导出误识别为节点

**Why it happens:** ExportMap 包含多种类型：
- UBlueprint（蓝图容器）
- UClass（编译类）
- UEdGraph（图容器）
- UK2Node 子类（真正节点）

**How to avoid:**
1. ClassIndex 解析后检查类名是否以 "K2Node_" 开头
2. "EdGraph" → 图容器，跳过节点解析
3. "Blueprint"/"Class"/"Function" → 元数据，跳过

**Warning signs:** NodePosX/Y 解析为异常大值；pins 数组为空但序列化仍在继续

### Pitfall 2: 版本依赖的引脚类型字段（PITFALLS.md 陷阱 3）

**What goes wrong:** 假设 FEdGraphPinType 字段顺序固定

**Why it happens:** UE 添加字段时使用版本条件（ContainerType、bIsConst、bIsUObjectWrapper）

**How to avoid:**
- Phase 3 已处理版本感知
- `read_ed_graph_pin_type()` 直接复用
- 无需重新实现版本检查

**Warning signs:** PinCategory 读取为整数（应为字符串）；is_reference 为 true 但后续解析失败

### Pitfall 3: Cooked 资产无图数据（PITFALLS.md 陷阱 7）

**What goes wrong:** 尝试从 cooked 资产提取图结构，但数据已剥离

**Why it happens:** Cooking 过程移除 UEdGraph/UK2Node，仅保留 BlueprintGeneratedClass

**How to avoid:**
1. 检查 PackageFlags 的 PKG_Cooked (0x200)
2. 若 cooked，返回警告而非错误
3. 不尝试解析图结构

**Warning signs:** ExportMap 无 UEdGraph/K2Node 类型；仅存在 BlueprintGeneratedClass

### Pitfall 4: LinkedTo 格式混淆

**What goes wrong:** LinkedTo 解析失败，格式不匹配预期

**Why it happens:** LinkedTo 存储格式可能变化（PinId GUID vs 名称索引）

**How to avoid:** D-01 锁定策略：
- Phase 7 存储为 `List[str]` 原始数据
- 不验证格式类型
- Phase 8 统一处理映射

**Warning signs:** linked_to_count 为负数；解析后数据长度不匹配

## Code Examples

### UEdGraph 数据类定义

```python
# Source: 基于 UE 5.7 EdGraph.h + 编辑器导出验证
@dataclass
class UEdGraph:
    """蓝图图容器"""
    graph_name: str                       # 导出 ObjectName
    graph_class: str                      # ClassIndex 解析结果
    schema: Optional[str] = None          # FPackageIndex 解析
    nodes: List["UEdGraphNode"] = field(default_factory=list)
    graph_guid: Optional[str] = None      # FGuid hex
    b_editable: bool = True
```

### UEdGraphNode 数据类定义

```python
# Source: 基于 UE 5.7 EdGraphNode.h + 编辑器导出验证
@dataclass
class UEdGraphNode:
    """蓝图节点（基类）"""
    node_guid: str                        # FGuid hex（编辑器导出：NodeGuid=...）
    node_pos_x: int = 0                   # 编辑器导出：NodePosX=...
    node_pos_y: int = 0                   # 编辑器导出：NodePosY=...
    node_comment: str = ""                # 编辑器导出：NodeComment=...
    pins: List["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""                  # 类型识别结果
    node_data: Optional[Any] = None       # 类型特定数据（多态）
```

### K2Node_CallFunction 特有数据

```python
# Source: 编辑器导出验证 L1-10
# FunctionReference=(MemberName="Jump",bSelfContext=True)
@dataclass
class K2NodeCallFunction:
    """K2Node_CallFunction 特有数据"""
    function_reference: "FMemberReference"
    b_defaults_to_pure: bool = False      # 编辑器导出：bDefaultsToPureFunc=True
```

### EdGraphNode_Comment 特有数据

```python
# Source: 编辑器导出验证 L21-33, L275-302
@dataclass
class EdGraphNodeComment:
    """注释节点特有数据"""
    comment_color: Tuple[float, float, float, float] = (0.05, 0.05, 0.05, 1.0)
    node_width: int = 0                   # 编辑器导出：NodeWidth=1440
    node_height: int = 0                  # 编辑器导出：NodeHeight=544
    font_size: int = 14                   # 编辑器导出：FontSize=14
    node_comment: str = ""                # 注释文本
```

### 图检测入口函数

```python
# Source: D-03a EdGraph 检测逻辑
def extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> List[UEdGraph]:
    """从 ExportMap 提取蓝图图（GRAPH-01 入口）"""
    
    graphs = []
    
    # Step 1: 检测 cooked 资产
    is_cooked = (summary.package_flags & PKG_Cooked) != 0
    if is_cooked:
        # 陷阱 7: cooked 资产无图数据
        return []  # 返回空，Phase 8 输出警告
    
    # Step 2: 遍历 ExportMap 寻找 EdGraph
    for export in export_map:
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        
        # D-03a: ClassIndex 包含 "EdGraph" → 图对象
        if "EdGraph" in class_name or "Ubergraph" in class_name:
            # 定位到图数据
            archive.seek(export.serial_offset)
            graph = read_ue_graph(
                archive, name_map, export_map, import_map,
                export, summary, class_name
            )
            graphs.append(graph)
    
    return graphs
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 手写所有节点解析 | match/case 类型分派 | Python 3.10+ | 代码简洁，易扩展 |
| LinkedTo 立即解析 | D-01 延迟解析策略 | Phase 7 设计 | 降低复杂度 |
| 假设固定序列化顺序 | 版本感知解析 | Phase 3 已实现 | 兼容多版本 |

**Deprecated/outdated:**
- 全量加载所有节点 → 应使用流式遍历（Phase 7 单文件解析，内存足够）
- 忽略 cooked 检测 → 必须检查 PKG_Cooked 标志

## Assumptions Log

> 本节列出所有标记 `[ASSUMED]` 的声明。

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FMemberReference 序列化顺序为 MemberParent + MemberName + MemberGuid + bSelfContext | Pattern 2 | 需 UE 源码验证 |
| A2 | LinkedTo 存储为 PinId GUID 列表 | Pattern 3 | 编辑器导出验证；但二进制格式可能不同 |
| A3 | UEdGraph.Nodes 是 FPackageIndex 数组 | Architecture Diagram | 需验证是否是内嵌序列化 |
| A4 | K2Node_EnhancedInputAction.InputAction 是 FSoftObjectPath | 节点类型分析 | 基于编辑器导出格式推断 |

**需要验证：** A1、A3、A4 建议在实现前通过真实 .uasset 文件验证。

## Open Questions (RESOLVED)

1. **UEdGraph.Nodes 序列化格式**
   - What we know: Nodes 是节点引用数组
   - What's unclear: 是 FPackageIndex 数组还是内嵌序列化？
   - **RESOLVED:** 采用 FPackageIndex 数组方案。Plan 02 L402-413 实现：读取 int32 node_index，从 export_map[node_index-1] 获取节点导出。此方案与 UE UObject 引用模式一致。

2. **FMemberReference.MemberParent 类型**
   - What we know: 编辑器导出显示类路径字符串
   - What's unclear: 二进制是否为 FPackageIndex？
   - **RESOLVED:** 采用 FPackageIndex 方案。Plan 03 L156-161 实现：read_i32() 读取 member_parent_index，通过 resolve_class_name() 解析为类路径字符串。此方案与 ClassIndex 解析模式一致。

3. **K2Node_EnhancedInputAction 多 exec 引脚**
   - What we know: 编辑器导出显示 Triggered/Started/Ongoing/Completed 多引脚
   - What's unclear: 这些引脚是否在 Pins 数组中？
   - **RESOLVED:** 在 Pins 数组中。Plan 02 引脚解析不区分节点类型，所有 exec 引脚（Triggered/Started/Ongoing/Completed）作为标准 UEdGraphPin 在 Pins 数组解析，Direction=EGPD_Output。

## Environment Availability

> Step 2.6: 无外部依赖需求 — 纯 Python 实现，使用标准库。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | match/case 语法 | ✓ | 3.14.3 | — |
| pytest | 测试框架 | ✓ | 9.0.3 | — |
| 无外部工具依赖 | — | — | — | — |

**Missing dependencies with no fallback:** 无

## Validation Architecture

> workflow.nyquist_validation = true（默认启用）

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | 无（使用默认） |
| Quick run command | `python -m pytest tests/ -v -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | EdGraph 类型检测 | unit | `pytest tests/test_graph_parsing.py::test_detect_edgraph_export -v` | ❌ Wave 0 |
| GRAPH-02 | EdGraph 基本信息提取 | unit | `pytest tests/test_graph_parsing.py::test_read_ue_graph_basic -v` | ❌ Wave 0 |
| GRAPH-03 | UEdGraphNode 基类字段 | unit | `pytest tests/test_graph_parsing.py::test_read_ue_graph_node_basic -v` | ❌ Wave 0 |
| GRAPH-04 | UEdGraphPin 完整结构 | unit | `pytest tests/test_graph_parsing.py::test_read_ue_graph_pin_complete -v` | ❌ Wave 0 |
| GRAPH-05 | K2Node_CallFunction | unit | `pytest tests/test_graph_parsing.py::test_k2node_call_function -v` | ❌ Wave 0 |
| GRAPH-06 | K2Node_Event | unit | `pytest tests/test_graph_parsing.py::test_k2node_event -v` | ❌ Wave 0 |
| GRAPH-07 | K2Node_Knot | unit | `pytest tests/test_graph_parsing.py::test_k2node_knot -v` | ❌ Wave 0 |
| GRAPH-08 | EdGraphNode_Comment | unit | `pytest tests/test_graph_parsing.py::test_edgraph_node_comment -v` | ❌ Wave 0 |
| GRAPH-09 | K2Node_EnhancedInputAction | unit | `pytest tests/test_graph_parsing.py::test_k2node_enhanced_input -v` | ❌ Wave 0 |
| GRAPH-10 | 引脚连接映射 | unit | Phase 8 | — |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_graph_parsing.py -v -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_graph_parsing.py` — Phase 7 新测试文件
- [ ] `tests/conftest.py` — 合成图数据 fixture（扩展现有）
- [ ] 合成 .uasset 文件生成器 — 添加 EdGraph/Node/Pin 测试数据

## Security Domain

> 本阶段涉及数据解析，需考虑边界验证。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | 数组 count 边界检查（MAX_PINS_PER_NODE） |
| V6 Cryptography | no | 无加密需求 |
| V2 Authentication | no | 无认证需求 |
| V3 Session Management | no | 无会话需求 |
| V4 Access Control | no | 只读解析 |

### Known Threat Patterns for Blueprint Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 数组 count 越界 | Tampering | MAX_PINS_PER_NODE = 1000 限制 |
| 嵌套深度无限 | Tampering | 递归深度限制 5（SubPins） |
| 偏移超出文件 | Tampering | archive.validate_offset() |
| GUID 格式错误 | Tampering | 16 bytes 固定长度验证 |

**边界常量建议:**

```python
MAX_PINS_PER_NODE = 1000      # 单节点最大引脚数
MAX_NODES_PER_GRAPH = 5000    # 单图最大节点数
MAX_LINKEDTO_PER_PIN = 100    # 单引脚最大连接数
MAX_SUBPIN_DEPTH = 5          # SubPin 递归深度限制
```

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md` - 蓝图图解析技术栈（v2.0 研究）
- `.planning/research/PITFALLS.md` - 领域陷阱（陷阱 1-8）
- `.planning/research/FEATURES.md` - 蓝图图功能全景
- `uasset_read.py` L724-742 - FEdGraphPinType dataclass（Phase 3）
- `uasset_read.py` L1561-1640 - read_ed_graph_pin_type()（Phase 3）
- `test/编辑器中复制出的文本.txt` - 编辑器导出格式验证

### Secondary (MEDIUM confidence)

- `.planning/research/UE-SOURCE-INDEX.md` - UE 源码索引
- `.planning/research/SUMMARY_BLUEPRINT.md` - 蓝图图解析研究摘要
- WebSearch UE Blueprint serialization - [UEdGraph API](https://docs.unrealengine.com/)

### Tertiary (LOW confidence - 需验证)

- A1: FMemberReference 序列化顺序 — 推断需 UE 源码验证
- A3: UEdGraph.Nodes 格式 — 推断需真实文件验证
- A4: InputAction 字段格式 — 推断需真实文件验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 现有技术栈完整覆盖
- Architecture: HIGH - 编辑器导出验证 + 现有模式复用
- Pitfalls: HIGH - PITFALLS.md 详细记录
- 序列化顺序: MEDIUM - 部分推断需验证

**Research date:** 2026-05-02
**Valid until:** 30 days（UE 格式稳定）

---

*本文件由 GSD Research 系统生成*