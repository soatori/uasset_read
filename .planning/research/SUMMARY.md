# 研究摘要

**项目：** uasset_read — Python .uasset 解析器（面向 AI agent）
**综合日期：** 2026-05-02
**版本：** v2.0 蓝图图解析阶段
**状态：** v1.0 已完成，v2.0 研究完成（待实施）

---

## 执行摘要

本项目构建 Python 工具解析 Unreal Engine .uasset 文件，使 AI agent 能直接读取蓝图内容而无需 UE 编辑器依赖。

### 核心洞察

**洞察 1：架构稳定性** — 现有 v1.0 架构（FArchive → Deserializer → Model → Output 分层管道）完整支持蓝图图解析，无需重构。

**洞察 2：零新增依赖** — Python 3.10+ 标准库已完整覆盖 v2.0 蓝图图解析需求（struct、dataclasses、json、mmap），无需引入 construct、pydantic 等新库。

**洞察 3：蓝图图结构** — 蓝图图是层叠结构：`UEdGraph`（图容器）→ `UEdGraphNode[]`（节点列表）→ `UEdGraphPin[]`（引脚列表），通过 `LinkedTo`（PinId GUID 引用）和 `ParentPin/SubPins`（结构体拆分）实现连接。

**洞察 4：节点类型稳定** — 主要节点类型（K2Node_Event、K2Node_CallFunction、K2Node_Knot、EdGraphNode_Comment）序列化格式已从 UE 5.7 源码和编辑器导出验证。

**洞察 5：版本敏感** — FEdGraphPinType 等结构包含版本条件字段（container_type、bIsConst、bIsUObjectWrapper），解析器需版本感知。

---

## 技术栈摘要

### 现有技术栈（v1.0 → v2.0 一致）

| 层级 | 组件 | 说明 |
|------|------|------|
| **语言** | Python 3.10+ | match/case、类型提示、dataclasses |
| **二进制读取** | struct + mmap | u8/u32/u64/f32/f64、大文件映射 |
| **数据模型** | dataclasses | asdict() → JSON、清晰结构 |
| **JSON 输出** | json | 结构化 Agent 输入 |
| **CLI** | argparse | `python -m uasset_read` |
| **编码** | UTF-8 | UE 5.x 标准 |

### v2.0 蓝图图解析新增数据类

```python
@dataclass
class UEdGraphPinRef:
    """引脚引用（LinkedTo 条目）"""
    pin_name: str
    target_node: Optional[str] = None
    resolved_pin: Optional["UEdGraphPin"] = None

@dataclass
class UEdGraphPin:
    """节点引脚"""
    pin_name: str
    pin_type: "FEdGraphPinType"        # Phase 3 已实现
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    linked_to: List["UEdGraphPinRef"] = field(default_factory=list)
    not_connectable: bool = False
    default_value_readonly: bool = False
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uproperty: bool = False
    owning_node: Optional["K2Node"] = None

@dataclass
class K2Node:
    """蓝图节点基类（K2Node）"""
    class_name: str                      # "K2Node_Event", "K2Node_CallFunction"
    node_guid: str                       # FGuid hex
    node_pos_x: int = 0
    node_pos_y: int = 0
    pins: List["UEdGraphPin"] = field(default_factory=list)
    node_data: Optional["NodeData"] = None

@dataclass
class UEdGraph:
    """蓝图图"""
    graph_name: str                      # "Ubergraph", "Function", "Macro"
    graph_class: str                     # 所属蓝图类
    nodes: List["K2Node"] = field(default_factory=list)
    is_ubergraph: bool = False
    is_function_graph: bool = False
    is_macro_graph: bool = False

@dataclass
class BlueprintGraphMetadata:
    """蓝图图完整元数据"""
    ubergraph_pages: List["UEdGraph"] = field(default_factory=list)
    function_graphs: List["UEdGraph"] = field(default_factory=list)
    macro_graphs: List["UEdGraph"] = field(default_factory=list)
```

---

## 功能全景

### 表类型功能（Table Stakes）——v2.0 必须

| 功能 | 为什么表类型 | 复杂度 | v1.0 状态 | v2.0 计划 |
|------|-------------|--------|-----------|-----------|
| 解析 UEdGraph | 蓝图逻辑容器 | 低 | | ✓ v2.0 |
| 识别 UK2Node | 蓝图节点基类 | 低 | | ✓ v2.0 |
| 解析 UEdGraphPin | 引脚数据/执行流端点 | 中 | | ✓ v2.0 |
| 引脚类型提取 | FEdGraphPinType 10 字段 | 中 | ✓ Phase 3 | ✓ v2.0 复用 |
|LinkedTo连接 | 节点间连接 | 中 | | ✓ v2.0（名称索引）|
| 节点类型分辨 | 辨别 K2Node_CallFunction / Event | 中 | | ✓ v2.0 |

### 差异化功能（Differentiators）——v2.1+

| 功能 | 价值 | 复杂度 | 优先级 |
|------|------|--------|--------|
| 节点上下文信息 | AI 语义理解（如 "jump action"） | 高 | v2.1 后期 |
| 节点分组识别 | 注释框理解逻辑分组 | 低 | v2.1 早期 |
| 路径追踪 | 事件→函数调用完整路径 | 高 | v2.1 |
| 依赖倒排索引 | 输入动作反查使用位置 | 高 | v2.1+ |
| 类 C++ 伪代码生成 | 输出等价代码 | 极高 | v3.0 |

### 反功能（Anti-Features）——明确不支持

| 反功能 | 避免原因 |
|--------|----------|
| cooked 资产图结构提取 | 已剥离编辑器数据，仅保留字节码 |
| 蓝图字节码反编译 | 需专门 VM 解析器 |
| 节点执行模拟 | 需完整运行时环境 |
| 资产修改/写入 | 仅支持只读解析 |

---

## 架构摘要

### 分层管道（v1.0 → v2.0 一致）

```
.uasset 文件 → BinaryReader → AssetDeserializer → Models → OutputFormatter
```

### v2.0 新增组件

| 组件 | 职责 | 与谁通信 |
|------|------|----------|
| **GraphHandler** | 蓝图图解析协调 | Deserializer（接收上下文） |
| **PinParser** | UEdGraphPin 解析 | GraphHandler |
| **NodeDispatcher** | UK2Node 子类分派 | PinParser（节点类型识别后） |
| **LinkBuilder** | LinkedTo 引用解析 | PinParser（构建连接） |

### 数据流（v2.0 蓝图图解析）

```
1. 标识图导出（ClassIndex 包含 "EdGraph"）
   ↓
2. 对每个 UEdGraph 导出：
   ├─ read_schema() → FPackageIndex
   ├─ read_nodes_count() → int32
   ├─ 对每个节点引用：
   │  ├─ resolve_export_index() → NodeExport
   │  ├─ parse_node_base() → UEdGraphNode (Pins, Pos, Guid)
   │  ├─ detect_k2node_type() → 子类名
   │  └─ dispatch_to_k2node_handler() → K2Node 特定数据
   └─ build_connections() → LinkedTo → PinId 映射
   ↓
3. 输出：
   ├─ Graphs → Nodes → Pins 层级 JSON
   ├─ Connections 辅助结构
   └─ ExecutionOrder 辅助结构
```

---

## 关键陷阱与缓解

### 关键陷阱（导致重写）

| 陷阱 | 说明 | 缓解措施 | 阶段 |
|------|------|----------|------|
| **OuterIndex 缺失 TemplateIndex** | UE4 >= 506 在 SuperIndex 和 OuterIndex 间插入 TemplateIndex | 检查 `summary.file_version_ue4 >= 506`，条件读取 | v1.0 Phase 4 已修复 |
| **Cooked 资产检测缺失** | PKG_Cooked 标志指示图结构已移除 | 解析前检查 PackageFlags & 0x200 | v2.0 开始需添加 |
| **FEdGraphPinType 版本依赖** | ContainerType、bIsConst、bIsUObjectWrapper 依版本添加 | 版本条件分支读取 | v2.0 Phase 1 |
| **节点类型误判** | Blueprint/Class/EdGraph 导出非节点 | 检查类名以 "K2Node_" 开头 | v2.0 Phase 2 |
| **LinkedTo GUID 格式** | 存储为 PinId GUID，非索引 | 构建 pin_id → pin_object 字典二次查找 | v2.0 Phase 1 |

### 中等陷阱

| 陷阱 | 说明 | 缓解 |
|------|------|------|
| SubPin/ParentPin 关系 | 结构体拆分的子引脚需ParentPin 引用 | 解析时构建双向引用 |
| NodeGuid vs 导出索引 | 外部工具使用 Guid，内部用索引 | 输出双引用 |
| 多图页面（Ubergraph/Function/Macro） | 蓝图可含多个图 | 先收集所有 UEdGraph 导出 |

### 次要陷阱

| 陷阱 | 说明 |
|------|------|
| 节点注释（EdGraphNode_Comment） | 无执行引脚，需特殊标记 |
| 临时变量节点（K2Node_TemporaryVariable） | 非蓝图变量，标记为 temporary |

---

## v2.0 实施优先级（Phase 6）

### Phase 6.1：核心图节点（Week 1-2）——最高优先级

**目标：** 解析 UEdGraph → UEdGraphNode → UEdGraphPin → FEdGraphPinType

**交付：**
- `parse_graphs()` 函数
- `BlueprintGraph`, `BlueprintNode`, `BlueprintPin` dataclasses
- 连接映射：`pin_id → pin_object` 字典

**关键实现：**
```python
def parse_graphs(export_map, name_map, archive, summary):
    graph_exports = [e for e in export_map if is_graph_export(e, name_map)]
    for ge in graph_exports:
        graphs.append(parse_graph(ge, export_map, name_map, archive, summary))
    return graphs
```

---

### Phase 6.2：节点类型分派（Week 3）

**目标：** K2Node_CallFunction / Event / Knot / Comment

**交付：**
- `parse_k2node_callfunction()`
- `parse_k2node_event()`
- `parse_k2node_knot()`
- `parse_comment_node()`

---

### Phase 6.3：引脚类型与连接（Week 4）

**目标：** 完整 FEdGraphPinType + LinkedTo 构建

**交付：**
- `parse_pin_type()`（版本感知）
- `LinkedTo` 解析（PinId GUID → 目标引用）
- SubPin/ParentPin 处理

---

### Phase 6.4：输出集成（Week 5）

**目标：** JSON 输出包含蓝图图结构

**交付：**
- `--graph` CLI 选项
- Graph/Node/Pin in JSON
- 执行流可视化辅助（execution_order 字段）

---

## Cookbook：节点类型识别

| 类名 | 名称空间 | 类型 | 解析策略 |
|------|----------|------|----------|
| K2Node_Event | BlueprintGraph | 节点 | EventReference + OutputDelegate |
| K2Node_CallFunction | BlueprintGraph | 节点 | FunctionReference + 参数引脚 |
| K2Node_VariableGet | BlueprintGraph | 节点 | VariableReference |
| K2Node_Knot | BlueprintGraph | 节点 | InputPin/OutputPin 转发 |
| K2Node_EnhancedInputAction | InputBlueprintNodes | 节点 | InputAction + 多 exec 引脚 |
| EdGraphNode_Comment | UnrealEd | 注释 | 无引脚，仅 NodeComment |
| UEdGraph | BlueprintGraph | 容器 | 跳过（包 Nodes） |
| Blueprint | Engine | 容器 | 跳过（蓝图元数据） |

---

## 版本兼容性矩阵

### FEdGraphPinType 字段添加

| 字段 | 添加版本 | 条件 |
|------|----------|------|
| container_type | FFrameworkObjectVersion::EdGraphPinContainerType | Version >= X |
| is_const | VER_UE4_SERIALIZE_PINTYPE_CONST | UE4 >= 4.8, UE5 >= 5.0 |
| is_uobject_wrapper | FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag | UE5 >= 5.0 |

### FObjectExport 字段添加

| 字段 | 添加版本 | 条件 |
|------|----------|------|
| TemplateIndex | UE4 >= 506 (VER_UE4_TemplateIndex_IN_COOKED_EXPORTS) | file_version_ue4 >= 506 |
| 64 位 SerialSize/Offset | UE4 >= 508 (VER_UE4_64BIT_EXPORTOFFSETS) | file_version_ue4 >= 508 |

---

## 置信度评估

### 核心区域

| 区域 | 置信度 | 依据 |
|------|--------|------|
| 包结构 | 高 | UE 5.7 源码直接确认 |
| 导入/导出格式 | 高 | UE 5.7 源码直接确认 |
| 属性序列化 | 中 | 复杂但有文档 |
| 蓝图元数据 | 高 | v1.0 Phase 3 已验证 |
| **蓝图图结构** | **高** | **WebSearch + 编辑器导出直接验证** |
| **引脚类型系统** | **高** | **FEdGraphPinType API 文档确认** |
| **节点类型分类** | **高** | **编辑器导出示例直接确认** |
| **连接机制** | **高** | **LinkedTo (node pin_id) 格式直接确认** |

### v2.0 新增评估

| 区域 | 置信度 | 说明 |
|------|--------|------|
| 节点类型识别 | 高 | 编辑器导出格式直接确认 |
| 引脚类型版本感知 | 中 | 部分字段版本阈值需实测确认 |
| LinkedTo GUID 映射 | 中 | 需真实文件验证 PinId GUID 格式 |
| 图嵌套处理 | 中 | FunctionGraph 内部节点需测试验证 |

---

## 需求缺口与待验证

### v2.0 需调研的领域

1. **节点类完整目录**
   - K2Node_ 开头的节点类（BlueprintGraph）
   - Enhanced Input 相关节点（InputBlueprintNodes）
   - 插件蓝图节点处理

2. **节点特有数据序列化**
   - FunctionReference/EventReference 结构
   - ExtraFlags 字段含义
   - 各节点类型特有字段偏移

3. **版本阈值确认**
   - FFrameworkObjectVersion::EdGraphPinContainerType 的确切版本号
   - UE4/UE5 的分界点验证

4. **真实文件验证**
   - LyraStarterGame/BP_Character.uasset 图结构解析
   - PinId GUID 格式验证
   - LinkedTo 解析测试

---

## 下一步行动

### 立即行动

1. **验证Cooked检测**：在 Phase 6 开始前添加 PackageFlags PKG_Cooked 检查
2. **选择测试文件**：LyraStarterGame/BP_Character.uasset 验证图解析
3. **启动 Phase 6 规划**：/gsd-plan-phase 6

### Phase 6 规划要点

- 优先实现 UEdGraphPin（LinkedTo + PinType）
- 基础节点类型（CallFunction / Event / Knot）
- 版本条件读取框架
- JSON 输出格式设计

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `STACK.md` | 技术栈推荐（零新增依赖确认） |
| `FEATURES.md` | 功能全景（表类型/差异化/反功能） |
| `ARCHITECTURE.md` | 系统架构模式（分层管道） |
| `PITFALLS.md` | 常见陷阱（OuterIndex/TemplateIndex、Cooked检测） |
| `UE-SOURCE-INDEX.md` | UE 源码参考索引 |

---

## 源文件信息

- **研究日期：** 2026-05-02
- **综合者：** GSD Research Synthesizer
- **v1.0 完成：** 2026-04-27（5 个阶段）
- **v2.0 研究：** 2026-05-02（蓝图图解析）
- **置信度：** 核心解析高，蓝图图高（v2.0 更新）

---

*综合自：STACK.md、FEATURES.md、ARCHITECTURE.md、PITFALLS.md*
