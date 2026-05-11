# Phase 32: 输出格式化模块 - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

## Phase Boundary

等价迁移旧版 `uasset_read.py` 中的输出格式化功能到 `src/uasset_read/formatters/` 模块。覆盖范围：
- `format_json_full()` (第 7188-7248 行) — 完整 JSON 输出
- `format_json_summary()` (第 7360-7428 行) — 精简 JSON 输出
- `format_text_full()` (第 7431-7534 行) — YAML 风格文本输出
- `format_text_summary()` (第 7537-7571 行) — 精简文本输出
- `format_markdown()` (第 7574-7667 行) — Markdown + Mermaid 流程图
- `format_blueprint_dict()` (第 7809-7968 行) — 蓝图元数据字典
- `format_node_dict()` (第 6621-6682 行) — 单节点 JSON 结构
- `format_graphs_json()` (第 6685-6834 行) — 图列表 JSON 结构
- `format_exports_list()` (第 7251-7331 行) — 导出列表格式化
- `format_properties_list()` (第 7334-7357 行) — 属性列表格式化
- `build_status_info()` (第 6953-7028 行) — 状态信息构建
- `build_graphs_summary()` (第 6953-7056 行) — 图摘要构建
- `build_schema_info()` (第 7059-7185 行) — Schema 信息（简易版）
- `_derive_node_name()` (第 6487-6498 行) — 节点名称派生
- `format_pin_ref()` (第 6501-6543 行) — Pin 引用格式化
- `format_variable_type()` (第 4861-4968 行) — 变量类型格式化
- `_is_control_flow_node()` / `_get_branch_type()` — 执行流辅助函数

**不包含：** CLI 入口（Phase 33）、正式 JSON Schema 定义（SCHEMA-01，延后）、节点可视化（Out of Scope）。

## Implementation Decisions

### 模块组织

- **D-01 (目录结构):** 新建 `src/uasset_read/formatters/` 目录，包含：
  - `formatters/json_formatter.py` — format_json_full, format_json_summary, format_exports_list, format_properties_list, format_blueprint_dict
  - `formatters/text_formatter.py` — format_text_full, format_text_summary
  - `formatters/markdown_formatter.py` — format_markdown
  - `formatters/helpers.py` — build_status_info, build_graphs_summary, build_schema_info, _derive_node_name, format_pin_ref, format_variable_type, format_node_dict, format_graphs_json
  - `formatters/__init__.py` — 扁平导出公共 API

### 输出格式兼容性

- **D-02 (字段清理):** 等价迁移允许清理旧版中的冗余历史字段。`imports`、`soft_references`、`circular_deps` 在 `format_json_full` 中可移除——这些依赖分析的字段不属于格式化模块的核心职责。
- **D-03 (等价边界):** 核心输出结构（status, output_version, summary, exports, blueprint, graphs_summary, errors）必须保持字段名和嵌套结构一致。移除的字段记录在决策中，不回退。

### CLI 归属

- **D-04 (CLI 分离):** CLI 入口和格式路由逻辑由 Phase 33 处理。Phase 32 的格式化模块只提供纯格式化函数，不包含任何 CLI 相关代码（arg 解析、路由、文件输出）。
- **D-05 (接口约定):** 格式化函数签名统一为 `format_xxx(result: ParseResult, ...) -> Dict | str`，由 Phase 33 的 CLI 根据命令行标志调用。

### Mermaid 生成

- **D-06 (独立函数):** Mermaid 流程图生成从 `format_markdown()` 中抽出为独立函数 `_build_mermaid_flowchart(execution_flows)` 放在 `formatters/helpers.py` 或 `formatters/markdown_formatter.py` 中。便于单独测试和复用。
- **D-07 (逻辑不变):** Mermaid 生成逻辑等价迁移——从 execution_flows 提取事件名和函数调用名，去掉参数部分，生成 `graph LR` 格式的 mermaid 代码块。

### Schema 处理

- **D-08 (简易迁移):** `build_schema_info()` 作为简易 schema 描述函数迁移到 formatters 模块，`include_schema` 参数保留在 `format_json_full` 中。
- **D-09 (扩展预留):** 在 `formatters/` 目录中预留 `schemas/` 子目录（Phase 32 创建空目录 + `__init__.py`），为后续正式 JSON Schema 定义（SCHEMA-01）预留扩展点。`build_schema_info()` 的返回值结构与未来 JSON Schema 保持兼容命名。

### Claude's Discretion

- helpers.py 中辅助函数的精确划分由规划阶段确定
- formatters/__init__.py 的导出列表由规划阶段确定
- 内部辅助函数命名由规划阶段确定

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 旧版源码参考（迁移源）

- `uasset_read.py` §7188-7248 — format_json_full() 完整 JSON
- `uasset_read.py` §7251-7331 — format_exports_list()
- `uasset_read.py` §7334-7357 — format_properties_list()
- `uasset_read.py` §7360-7428 — format_json_summary() 精简 JSON
- `uasset_read.py` §7431-7534 — format_text_full() YAML 风格
- `uasset_read.py` §7537-7571 — format_text_summary() 精简文本
- `uasset_read.py` §7574-7667 — format_markdown() Markdown + Mermaid
- `uasset_read.py` §7809-7968 — format_blueprint_dict()
- `uasset_read.py` §6621-6682 — format_node_dict()
- `uasset_read.py` §6685-6834 — format_graphs_json()
- `uasset_read.py` §6501-6543 — format_pin_ref()
- `uasset_read.py` §6487-6498 — _derive_node_name()
- `uasset_read.py` §4861-4968 — format_variable_type()
- `uasset_read.py` §6953-7056 — build_status_info / build_graphs_summary
- `uasset_read.py` §7059-7185 — build_schema_info() 简易 schema
- `uasset_read.py` §7360-7428 — build_status_info (status 三元分类)

### 前期决策

- `.planning/phases/29-core-data-models/29-CONTEXT.md` — D-01 至 D-14（dataclass 定义、命名、序列化策略）
- `.planning/phases/30-property-parsing/30-CONTEXT.md` — D-01 至 D-09（parsers 模块组织、分派策略）
- `.planning/phases/31-graph-parsing/31-CONTEXT.md` — D-01 至 D-09（graph 模块、flow builder 产出格式）
- `.planning/ROADMAP.md` §Phase 32 — Phase 32 目标、成功标准

### 现有模块模式

- `src/uasset_read/models/result.py` — ParseResult dataclass（格式化函数的输入）
- `src/uasset_read/models/core.py` — UEdGraph/Node/Pin dataclass
- `src/uasset_read/models/properties.py` — PropertyTag/PropertyValue dataclass
- `src/uasset_read/models/blueprint.py` — BlueprintMetadata dataclass
- `src/uasset_read/constants.py` — 常量模块
- `src/uasset_read/__init__.py` — 公共 API 导出模式

## Existing Code Insights

### Reusable Assets

- **ParseResult (models/result.py):** 格式化函数的主要输入，包含 summary, export_map, blueprint, graphs, imports, soft_references, circular_deps, errors 字段
- **dataclass asdict():** 已有的序列化模式，格式化函数可直接使用
- **零运行时依赖:** pyproject.toml 中 `dependencies = []`

### Established Patterns

- **函数式格式化:** 纯函数接收 dataclass 返回 dict/str，无副作用
- **扁平导入:** 所有模块通过 `__init__.py` 统一导出
- **分层架构依赖方向:** formatters → models → (graph, parsers) → serializers → archive，单向依赖
- **output_version 字段:** 当前锁定为 "4.0"，格式化输出中必须包含

### Integration Points

- `formatters/json_formatter.py` 消费 ParseResult + graph 模块产出的 flow 数据
- `formatters/text_formatter.py` 消费 ParseResult + graph 模块的 execution_flows
- `formatters/markdown_formatter.py` 消费 ParseResult + mermaid 构建函数
- `src/uasset_read/__init__.py` 需导出所有格式化函数
- Phase 33 的 CLI 模块将调用这些格式化函数
- 测试适配：tests/test_output_formatting.py 需更新导入路径

## Specific Ideas

无特定要求 — 采用上述讨论的架构设计。

## Deferred Ideas

- 正式 JSON Schema 定义（SCHEMA-01）— 延后至 v9.0 (Phase 48)
- CLI 入口和格式路由 — Phase 33 处理
- 节点可视化 — Out of Scope
- C++ 代码生成器 — 延后

---

*Phase: 32-输出格式化模块*
*Context gathered: 2026-05-12*
