# Phase 7: 蓝图图核心解析 - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

实现蓝图图结构的基础解析（Graph → Node → Pin），从导出表中提取 UEdGraph、UEdGraphNode、UEdGraphPin 数据。此阶段交付完整图数据解析，连接映射和输出格式化在 Phase 8 处理。

**交付能力：**
- UEdGraph 导出类型识别（ClassIndex 包含 "EdGraph"）
- UEdGraph 基本信息（Schema、GraphGuid、Nodes 数量）
- UEdGraphNode 基类字段（NodeGuid、NodePosX/Y、NodeComment、Pins）
- UEdGraphPin 完整结构（PinId、PinName、Direction、PinType、DefaultValue、LinkedTo 原始数据、Flags）
- 5 种需求节点类型特有字段解析（K2Node_CallFunction、K2Node_Event、K2Node_Knot、EdGraphNode_Comment、K2Node_EnhancedInputAction）

**Requirements:** GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, GRAPH-06, GRAPH-07, GRAPH-08, GRAPH-09, GRAPH-10

**固定范围（来自 ROADMAP.md）：**
- 解析器能识别 UEdGraph 导出类型
- 解析器能提取 UEdGraph 基本信息
- 解析器能解析 UEdGraphNode 基类字段
- 解析器能解析 UEdGraphPin 完整结构
- 解析器能构建引脚连接映射（推迟到 Phase 8）

</domain>

<decisions>
## Implementation Decisions

### 引脚连接解析策略
- **D-01:** LinkedTo 延迟解析 —— Phase 7 仅记录原始 LinkedTo 数据（名称或索引），Phase 8 输出时构建连接映射（PinId → TargetPinId）
- **D-01a:** 原始数据格式 —— LinkedTo 读取为 List[str]（名称列表），暂不验证格式类型
- **原因:** 降低 Phase 7 复杂度；连接映射逻辑集中在输出阶段处理；避免未验证格式导致的解析错误

### 节点类型识别范围
- **D-02:** 节点类型范围 —— 基类字段 + 需求类型（GRAPH-05~09）特有字段，不处理其他类型
- **D-02a:** 未知类型处理 —— 遇到未知节点类型时，仅记录类型名和原始数据位置，输出警告
- **D-02b:** 类型识别方法 —— 通过 ClassIndex 解析为类名，匹配已知类型列表（"K2Node_CallFunction", "K2Node_Event" 等）
- **原因:** 满足 ROADMAP 需求 GRAPH-05~09；避免过度扩展范围；未知类型 fallback 保证解析继续

### 图数据解析深度
- **D-03:** 解析深度 —— 完整解析 Graph→Node→Pin 三层结构
- **D-03a:** EdGraph 检测 —— 遍历 ExportMap，ClassIndex 解析后包含 "EdGraph" 或 "Ubergraph" 的导出视为图对象
- **D-03b:** 节点解析 —— 从 EdGraph 的 SerialOffset 位置读取 Nodes 数组，每个节点完整解析（基类 + 类型特有字段）
- **D-03c:** 引脚解析 —— 从每个 Node 的 Pins 数组位置读取引脚，完整解析 PinType + DefaultValue + LinkedTo 原始数据
- **原因:** 满足 ROADMAP 成功标准；Phase 7 交付完整图数据；Phase 8 仅处理输出格式化

### 图输出层级设计
- **D-04:** 输出层级 —— 顶层 graphs 数组，与 blueprint 同级
- **D-04a:** graphs 结构 —— 每个图对象包含 graph_name、graph_class、nodes（节点数组）、连接映射推迟到 Phase 8
- **D-04b:** ParseResult 扩展 —— 新增 `graphs: List[UEdGraph]` 字段（顶层）
- **原因:** 便于快速访问图数据；保持 Package→Exports 层级一致性；与 Phase 4 D-02 的顶层字段设计一致

### Claude's Discretion
- 节点类型特有字段的具体解析顺序（需研究 UE 源码确定）
- LinkedTo 原始数据的存储格式（List[str] vs List[dict]）
- PinId 生成格式（UE GUID hex vs 自定义 ID）
- 节点/引脚解析失败的错误上下文字段设计
- 单元测试组织

</decisions>

<specifics>
## Specific Ideas

- "LinkedTo 延迟解析" —— 用户选择降低 Phase 7 复杂度，连接映射推迟
- "完整解析 Graph→Node→Pin" —— 用户确认满足 ROADMAP 成功标准
- "顶层 graphs 字段" —— 与 blueprint 同级，便于快速访问

</specifics>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（核心）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Public/K2Node.h` —— K2Node 基类定义
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Private/K2Node.cpp` —— K2Node 序列化实现
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Public/EdGraph/EdGraphNode.h` —— UEdGraphNode 定义
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Private/EdGraph/EdGraphNode.cpp` —— UEdGraphNode 序列化
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Public/EdGraph/EdGraphPin.h` —— UEdGraphPin 定义（第 76-225 行）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Private/EdGraph/EdGraphPin.cpp` —— UEdGraphPin 序列化（第 163-346 行）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Public/EdGraph/EdGraph.h` —— UEdGraph 定义
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Private/EdGraph/EdGraph.cpp` —— UEdGraph 序列化

### 节点类型源码（需求类型）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Classes/K2Node_CallFunction.h` —— GRAPH-05
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Classes/K2Node_Event.h` —— GRAPH-06
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Classes/K2Node_Knot.h` —— GRAPH-07
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Classes/EdGraphNode_Comment.h` —— GRAPH-08
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/BlueprintGraph/Classes/K2Node_EnhancedInputAction.h` —— GRAPH-09

### 项目现有代码
- `uasset_read.py` 第 724-742 行 —— FEdGraphPinType dataclass（Phase 3 已实现）
- `uasset_read.py` 第 1561-1640 行 —— read_ed_graph_pin_type() 函数（Phase 3 已实现）
- `uasset_read.py` 第 1267-1400 行 —— read_export_map() 函数（Phase 6 已修复）
- `uasset_read.py` 第 636-680 行 —— ObjectExport dataclass
- `uasset_read.py` 第 774-791 行 —— ParseResult dataclass（需扩展 graphs 字段）

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束
- `.planning/REQUIREMENTS.md` —— GRAPH-01~10 需求定义
- `.planning/ROADMAP.md` —— Phase 7 成功标准
- `.planning/phases/06-export-table-fix/06-CONTEXT.md` —— Phase 6 决策（导出表完整结构）
- `.planning/phases/03-blueprint-extraction/03-CONTEXT.md` —— Phase 3 决策（FEdGraphPinType）
- `.planning/research/SUMMARY_BLUEPRINT.md` —— 蓝图图解析研究摘要

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FEdGraphPinType dataclass:** Phase 3 已实现完整结构（pin_category, pin_sub_category, container_type, is_reference, is_const 等）
- **read_ed_graph_pin_type() 函数:** Phase 3 已实现，版本感知解析，可直接复用
- **FArchive 类:** 所有读取方法已实现（read_name, read_fstring, read_i32, read_u8 等）
- **ObjectExport dataclass:** Phase 6 已修复完整结构，包含 class_index、serial_offset 等
- **ErrorContext dataclass:** Phase 5 D-18 已定义，可扩展图解析错误上下文

### Established Patterns
- **导出表遍历:** Phase 3 extract_blueprint_metadata() 遍历 ExportMap 模式可复用
- **ClassIndex 解析:** get_asset_class() 函数解析类名模式可复用
- **版本条件读取:** Phase 6 大量版本检查模式可复用
- **dataclass + field(default):** 条件字段使用默认值模式

### Integration Points
- ParseResult: 需扩展添加 graphs 字段
- extract_blueprint_metadata(): 可扩展检测图导出类型
- JSON 输出: Phase 8 需更新 format_json() 包含 graphs 字段
- read_export_map(): 已修复，可直接遍历

</code_context>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### Phase 8（蓝图图输出增强）
- 引脚连接映射构建（LinkedTo PinId → 目标节点/引脚）
- graphs 字段 JSON 输出格式化
- --graph CLI 标志支持
- 执行流路径输出（Event → CallFunction 链路）
- 图结构摘要文本输出

### Phase 9+（高级节点类型）
- 更多 K2Node 子类解析（K2Node_Variable、K2Node_DynamicCast 等）
- 自定义节点类型扩展机制
- 节点详细参数解析

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-blueprint-graph-core*
*Context gathered: 2026-05-02*