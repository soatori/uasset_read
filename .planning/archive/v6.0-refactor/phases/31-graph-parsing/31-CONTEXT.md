# Phase 31: 蓝图图解析模块 - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

## Phase Boundary

等价迁移旧版 `uasset_read.py` 中的蓝图图解析功能到 `src/uasset_read/graph/` 模块。覆盖范围：
- `extract_blueprint_graphs()` (第 3095-3143 行) — 遍历 ExportMap 识别 EdGraph/UberEdGraph
- `read_ue_graph()` (第 4552-4631 行) — 读取单个图的 schema、nodes、graph_guid
- `read_ue_graph_node()` (第 3976-4100 行) — 读取节点的 guid、pos、pins
- `read_ue_graph_pin()` (第 3588-3973 行) — 读取引脚完整结构
- `read_ed_graph_pin_type()` (第 3191-3300 行) — 解析 FEdGraphPinType
- 5 种节点类型读取器 — call_function、event、knot、comment、enhanced_input
- `read_fmember_reference()` (第 4311-4380 行) — FMemberReference 解析
- `build_execution_flows()` (第 6836-6891 行) — 执行流追踪
- `build_data_flows()` (第 6894-6950 行) — 数据流构建
- `build_connections_map()` (第 6546-6620 行) — Pin 连接映射

**不包含：** UberGraph/事件分发图增强（v8.0）、BulkData 解析（v7.0）、输出格式化（Phase 32）。

## Implementation Decisions

### 模块组织

- **D-01 (目录结构):** 新建 `src/uasset_read/graph/` 目录（与 parsers/ 同级），包含：
  - `graph/parser.py` — extract_blueprint_graphs、read_ue_graph 入口
  - `graph/node_reader.py` — read_ue_graph_node、read_ue_graph_pin、节点类型读取器
  - `graph/flow_builder.py` — build_execution_flows、build_data_flows、build_connections_map
  - `graph/__init__.py` — 扁平导出公共 API

### from_archive 实现策略

- **D-02 (委托模式):** models/core.py 中的 `from_archive` stub 保持为委托入口，内部调用 `serializers/graph.py` 中的独立函数。保持 Phase 29 的 D-06（数据/序列化解耦）。
- **D-03 (serializers/graph.py):** 图相关的底层二进制读取函数放在 `serializers/graph.py`，被 models 的 from_archive 委托调用。包含：read_fed_graph_pin_type、read_ue_graph_pin、read_ue_graph_node、read_ue_graph、read_fmember_reference。
- **D-04 (节点类型读取器):** 5 种节点类型的特定读取器（read_k2node_call_function 等）也放在 `serializers/graph.py`，通过 node_factory 调用。

### 执行流/数据流构建

- **D-05 (归属):** build_execution_flows、build_data_flows、build_connections_map 放在 `graph/flow_builder.py` — 与图解析同域，属于图分析能力，不属于格式化。
- **D-06 (输入输出):** 这些函数消费 `List[UEdGraph]` 和 `UEdGraph`，产出 `List[Dict]` 结构，由 Phase 32 的格式化模块消费。

### 节点类型扩展机制

- **D-07 (工厂模式):** 使用 `NodeFactory.create(archive, class_name, ...)` 模式 — 根据 class_name 分派到对应的节点读取函数。比 match/case 更易扩展，比注册表更简单。
- **D-08 (工厂位置):** `serializers/graph.py` 中定义 `create_node_from_archive()` 工厂函数（或独立的 `serializers/node_factory.py` 如果函数过多）。
- **D-09 (已知类型):** 初始支持 5 种：K2Node_CallFunction、K2Node_Event、K2Node_Knot、EdGraphNode_Comment、K2Node_EnhancedInputAction。未知类型回退到 UEdGraphNode 基类。

### Claude's Discretion

- 工厂函数的精确接口签名由规划阶段确定
- graph/ 目录下文件的精确划分（parser.py vs node_reader.py 的边界）由规划阶段确定
- 内部辅助函数命名由规划阶段确定

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 旧版源码参考（迁移源）

- `uasset_read.py` §3095-3143 — extract_blueprint_graphs() 入口
- `uasset_read.py` §3191-3300 — read_ed_graph_pin_type()
- `uasset_read.py` §3588-3973 — read_ue_graph_pin() 完整引脚读取
- `uasset_read.py` §3976-4100 — read_ue_graph_node() 节点读取
- `uasset_read.py` §4311-4380 — read_fmember_reference()
- `uasset_read.py` §4383-4421 — read_k2node_call_function()
- `uasset_read.py` §4422-4460 — read_k2node_event()
- `uasset_read.py` §4461-4477 — read_k2node_knot()
- `uasset_read.py` §4478-4521 — read_edgraph_node_comment()
- `uasset_read.py` §4522-4551 — read_k2node_enhanced_input()
- `uasset_read.py` §4552-4631 — read_ue_graph() 图容器读取
- `uasset_read.py` §6546-6620 — build_connections_map()
- `uasset_read.py` §6621-6682 — format_node_dict()（Phase 32 消费，但 graph 需要产出兼容结构）
- `uasset_read.py` §6685-6750 — format_graphs_json()（Phase 32 消费）
- `uasset_read.py` §6836-6891 — build_execution_flows()
- `uasset_read.py` §6894-6950 — build_data_flows()
- `uasset_read.py` §6432 — START_EVENT_TYPES 常量
- `uasset_read.py` §64-68 — MAX_PINS_PER_NODE、MAX_NODES_PER_GRAPH、MAX_LINKEDTO_PER_PIN

### UE 源码参考

- `EdGraph.cpp` — UEdGraph 序列化格式
- `EdGraphPin.cpp` L1838-1964 — UEdGraphPin 序列化顺序
- `EdGraphNode.h` + `K2Node.h` — UEdGraphNode 字段定义

### 现有模块模式

- `src/uasset_read/models/core.py` — 已有数据类定义 + from_archive stubs（需实现）
- `src/uasset_read/models/node_types.py` — 5 种节点类型子类定义
- `src/uasset_read/constants.py` — 已有常量和版本阈值
- `src/uasset_read/exceptions.py` — ParseError, UAssetError
- `src/uasset_read/archive.py` — FArchive 接口
- `src/uasset_read/serializers/package_summary.py` — from_archive 模式参考
- `src/uasset_read/serializers/object_resources.py` — PackageIndex/ObjectExport 模式
- `src/uasset_read/__init__.py` — 公共 API 导出模式

### 前期决策

- `.planning/phases/29-core-data-models/29-CONTEXT.md` — D-01 至 D-14（命名、模块、继承、序列化策略）
- `.planning/phases/30-property-parsing/30-CONTEXT.md` — D-01 至 D-09（parsers 模块组织、分派策略）
- `.planning/ROADMAP.md` §Phase 31 — Phase 31 目标、成功标准

## Existing Code Insights

### Reusable Assets

- **FArchive (archive.py):** read_i32/read_u32/read_u8/read_fstring/read_bytes/read_guid/read_bool 等方法已就位
- **常量 (constants.py):** PACKAGE_FILE_TAG、版本号阈值（FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE=15、FFRAMEWORK_VERSION_PINS_STORE_FNAME=19 等）、安全边界常量需补充
- **安全边界常量:** 需要从 uasset_read.py §64-68 迁移 MAX_PINS_PER_NODE=1000、MAX_NODES_PER_GRAPH=5000、MAX_LINKEDTO_PER_PIN=100
- **START_EVENT_TYPES:** 需要从 uasset_read.py §6432 迁移事件类型集合
- **resolve_class_name / get_asset_class:** serializers/object_resources.py 中已有，graph 解析依赖

### Established Patterns

- **dataclass + from_archive stub → serializer 委托:** Phase 29 D-06 + Phase 31 D-02 已锁定
- **扁平导入:** 所有模块通过 `__init__.py` 统一导出
- **分层架构依赖方向:** graph → models → serializers → archive，单向依赖
- **函数式解析:** serializers 中已建立独立函数返回 dataclass 的模式
- **零运行时依赖:** pyproject.toml 中 `dependencies = []`

### Integration Points

- **models/core.py 需要更新:** FEdGraphPinType、UEdGraphPin、UEdGraphNode、UEdGraph、FMemberReference 的 from_archive 从 stub 改为实际委托调用
- **graph/__init__.py 需要创建:** 导出 extract_blueprint_graphs、build_execution_flows、build_data_flows 等公共 API
- **serializers/graph.py 需要创建:** 图二进制读取函数
- **constants.py 需要补充:** 图解析相关安全边界常量和 START_EVENT_TYPES
- **Phase 30 产出消费:** graph 解析在属性解析之后运行，消费已解析的 ExportMap
- **Phase 32 产出提供:** graph 模块产出图数据结构，供输出格式化模块消费
- **测试适配:** tests/test_graph_parsing.py 需更新导入路径

## Specific Ideas

无特定要求 — 采用上述讨论的架构设计。

## Deferred Ideas

- UberGraph/事件分发图增强 — 属于 v8.0 (Phase 42)
- UBlueprintGeneratedClass 字节码反编译 — 属于 v8.0 (Phase 44)
- .umap/World 资产解析 — 属于 v9.0 (Phase 46)
- JSON Schema 验证 — 属于 v9.0

---

*Phase: 31-蓝图图解析模块*
*Context gathered: 2026-05-12*
