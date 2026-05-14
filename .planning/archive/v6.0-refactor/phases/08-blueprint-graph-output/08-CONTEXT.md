# Phase 8: 蓝图图输出增强 - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

完善 JSON 和文本输出格式，包含蓝图图数据和连接映射。此阶段交付图数据的输出格式化，不包含新的图解析逻辑（Phase 7 已完成解析）。

**交付能力：**
- 引脚连接映射构建（LinkedTo 原始数据 → PinId 连接映射）
- graphs 字段 JSON 输出格式化（层级结构）
- 执行流路径输出（Event → CallFunction 链路）
- CLI --graph 标志支持
- 文本输出图结构摘要（节点数、连接数、执行流概览）

**Requirements:** GRAPH-11, GRAPH-12, OUT2-01, OUT2-02, OUT2-03, OUT2-04

**固定范围（来自 ROADMAP.md）：**
- JSON 输出包含蓝图图层级结构（Graph → Nodes → Pins）
- JSON 输出包含执行流路径（从 Event → CallFunction 链路）
- JSON 输出包含完整的蓝图图数据（与 blueprint 字段同级的 graphs 字段）
- JSON 输出包含高级属性解析结果（替换原始字符串值）
- CLI 支持 --graph 标志仅输出蓝图图数据
- 文本输出包含图结构摘要（节点数、连接数、执行流概览）

**依赖：** Phase 7（蓝图图核心解析）—— graphs 数据结构已定义，LinkedTo 存储为原始名称列表

</domain>

<decisions>
## Implementation Decisions

### 连接映射构建
- **D-08-01:** PinName 全图匹配 —— LinkedTo 原始数据通过搜索所有节点的引脚，找到 PinName 匹配的引脚，返回其 PinId
  - **原因:** 简单实现，满足 Phase 7 D-01a 的原始数据格式假设；同名引脚冲突通过 NodeGuid 区分
- **D-08-02:** NodeGuid + PinName 表示 —— 连接使用 `{node_guid, pin_name}` 组合表示，而非 PinId GUID hex
  - **原因:** 可读性好，可直接定位节点和引脚；避免 GUID hex 查找的额外步骤
- **D-08-03:** Graph.connections 位置 —— 连接映射放在图层级 `Graph.connections` 数组，而非引脚层级
  - **原因:** 便于统计连接数和遍历图；避免 Pin.linked_to 的交叉引用
- **D-08-04:** 警告 + 原始数据 —— 匹配失败时输出 warning 字段和原始 LinkedTo 数据
  - **原因:** 保留信息供调试；与 Phase 4 D-13 的引用解析失败处理一致
- **D-08-05:** 单向表示 —— 每个连接仅出现一次（Output Pin → Input Pin 方向）
  - **原因:** 避免重复；符合执行流语义（数据从 Output 流向 Input）
- **D-08-06:** `{from, to}` 对象结构 —— 每个连接元素为 `{from: {node_guid, pin_name}, to: {node_guid, pin_name}}`
  - **原因:** 结构清晰，便于 JSON 处理；比数组格式更易读

### 执行流路径
- **D-08-07:** Event → CallFunction 链路 —— 从 Event 节点（K2Node_Event）开始，沿连接追踪到 CallFunction 节点
  - **原因:** 满足 GRAPH-12 需求；AI agent 可理解蓝图逻辑流程
- **D-08-08:** 节点详细信息序列 —— 每条执行流为节点对象序列 `[{node_guid, node_type, function_name}, ...]`
  - **原因:** 信息丰富，便于理解执行流；比 GUID 序列更直观
- **D-08-09:** execution_flows 数组 —— 每个 Graph 对象包含 `execution_flows` 数组组织多条执行流
  - **原因:** 每个 Event 生成一条执行流；便于查看每个事件的处理逻辑
- **D-08-10:** 分支处停止 —— 遇到控制流节点（If、Switch）时停止追踪
  - **原因:** 简化实现；AI agent 可自行分析分支逻辑；避免复杂的分支路径表示
- **D-08-11:** 循环检测并停止 —— 追踪时检测已访问节点，遇到循环时停止并标记
  - **原因:** 避免无限循环；蓝图可能有回环逻辑（如 Loop 节点）

### CLI --graph 标志
- **D-08-12:** 独立可组合标志 —— --graph 不与 --json/--text/--summary 互斥，可组合使用
  - **原因:** 用户可组合使用（如 --json --graph）；与 Phase 4 D-27 的可选标志设计一致
- **D-08-13:** 输出范围取决于 --verbose —— 默认仅输出 graphs 字段，与 --verbose 组合时输出完整结构 + graphs
  - **原因:** 默认专注图数据；--verbose 提供完整上下文

### Claude's Discretion
- Graph 对象的具体字段列表（graph_name, graph_class, nodes, connections, execution_flows 的完整结构）
- 文本输出图结构摘要的具体格式（节点数、连接数、执行流概览的 YAML 风格）
- 连接映射的验证机制（同名引脚冲突处理）
- 执行流节点详细信息的具体字段（node_guid, node_type, function_name之外是否包含更多）
- 单元测试组织

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（零运行时依赖）
- `.planning/REQUIREMENTS.md` —— GRAPH-11, GRAPH-12, OUT2-01~04 需求定义
- `.planning/ROADMAP.md` —— Phase 8 成功标准
- `.planning/phases/07-blueprint-graph-core/07-CONTEXT.md` —— Phase 7 决策（graphs 数据结构、LinkedTo 原始数据）
- `.planning/phases/04-output-and-cli/04-CONTEXT.md` —— Phase 4 决策（JSON 结构、CLI 标志设计）

### 项目现有代码
- `uasset_read.py` 第 783-838 行 —— UEdGraphPin, UEdGraphNode, UEdGraph 数据类（Phase 7 已实现）
- `uasset_read.py` 第 870 行 —— ParseResult.graphs 字段（Phase 7 D-04b）
- `uasset_read.py` 第 2856-2999 行 —— format_json_full(), format_json_summary(), format_exports_list()（Phase 4 已实现）
- `uasset_read.py` 第 3044-3122 行 —— format_text_full(), format_text_summary()（Phase 4 已实现）
- `uasset_read.py` 第 3208-3302 行 —— create_parser(), main() CLI 实现（Phase 4 已实现）

### UE 源码参考（输出格式参考）
- 无直接 UE 源码参考 —— 输出格式为项目自定义设计

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **UEdGraph/UEdGraphNode/UEdGraphPin dataclasses:** Phase 7 已实现完整结构，可直接 asdict() → JSON
- **format_json_full():** Phase 4 已实现，需扩展添加 graphs 字段输出
- **format_text_full():** Phase 4 已实现，需扩展添加图结构摘要
- **create_parser():** Phase 4 已实现 argparse 结构，需添加 --graph 标志
- **ParseResult.graphs:** Phase 7 D-04b 已添加顶层字段

### Established Patterns
- **dataclasses + asdict():** JSON 输出直接兼容（Phase 1 D-06）
- **分级输出:** --json 完整版 / --summary 精简版（Phase 4 D-01）
- **互斥输出标志:** --json/--text/--summary 三选一（Phase 4 D-24）
- **YAML 风格文本:** 2 空格缩进层级结构（Phase 4 D-17）
- **顶层 blueprint 字段:** 与 exports 同级（Phase 4 D-04）

### Integration Points
- format_json_full(): 需添加 graphs 字段输出
- format_json_summary(): 需添加 graphs 摘要
- format_text_full(): 需添加图结构摘要区块
- create_parser(): 需添加 --graph 标志（不与现有标志互斥）
- Graph 数据遍历: 需实现连接映射构建和执行流追踪

</code_context>

<specifics>
## Specific Ideas

- "PinName 全图匹配" —— 用户确认简单实现优先
- "NodeGuid + PinName 表示连接" —— 用户选择可读性优于紧凑性
- "execution_flows 数组组织多条执行流" —— 用户确认每个 Event 一条执行流
- "--graph 独立可组合" —— 用户选择灵活性

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### Phase 9（高级属性类型）
- OUT2-02 高级属性解析结果输出（需先实现 Phase 9 的属性解析）

### v3（高级输出）
- 完整控制流图（考虑所有控制流节点分支）
- 连接验证机制（同名引脚冲突处理）
- 更多节点类型的执行流追踪（K2Node_Variable、K2Node_DynamicCast 等）
- 图可视化输出（SVG/DOT 格式）

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-blueprint-graph-output*
*Context gathered: 2026-05-02*