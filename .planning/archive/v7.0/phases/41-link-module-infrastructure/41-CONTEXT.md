# Phase 41: link/ 模块基础设施 - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

创建 `src/uasset_read/link/` 模块的三个核心类：`UObjectInstance`（对象实例数据类）、`PackageLinker`（两阶段加载协调器）、`LinkerParseResult`（返回结果类）。这是 v7.0 对象图重建的基础设施层，不涉及具体序列化逻辑修改。

</domain>

<decisions>
## Implementation Decisions

### 加载策略
- **D-01:** PackageLinker 采用严格两阶段加载：`link()` 只读头信息创建 UObjectInstance 壳（不反序列化属性），`preload(index)` 按需加载单个对象的序列化属性。完全对应 UE 的 FLinkerLoad 模式。

### 入口点设计
- **D-02:** 新增独立的 `parse_uasset_with_linker()` 函数作为并行入口点，现有 `parse_uasset()` 完全不变。返回新的 `LinkerParseResult` 类型。

### 模块导出
- **D-03:** link/ 模块使用子模块导入方式，用户通过 `from uasset_read.link import PackageLinker` 访问，不在 `uasset_read/__init__.py` 扁平导出。

### 数据复用
- **D-04:** PackageLinker 接收已解析的 `summary`、`import_map`、`export_map`、`name_map` 作为构造函数参数，不重新读取。复用在 `parse_uasset_with_linker()` 中已完成的头解析工作。

### Claude's Discretion
- 具体字段命名、错误处理策略、类型注解细节由下游 planner 根据代码库现有风格决定。
- `UObjectInstance` 已有的方法骨架（`get_full_name()`, `get_children()`, `ensure_preloaded()`）保留并补全实现。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心设计文档
- `.planning/milestones/v7.0-OBJECT-GRAPH.md` — v7.0 完整设计文档，包含 Phase 分解、UE FLinkerLoad 参考表、验证标准
- `.planning/STATE.md` — 当前 v7.0 状态（planning 中）
- `.planning/ROADMAP.md` §v7.0 — Phase 41-46 列表

### 现有代码参考
- `src/uasset_read/link/object_instance.py` — UObjectInstance 已部分实现的代码
- `src/uasset_read/serializers/object_resources.py` — PackageIndex/ObjectImport/ObjectExport 定义，需要新增 resolve_with_linker()
- `src/uasset_read/serializers/package_summary.py` — read_package_summary() 和 read_name_table()
- `src/uasset_read/parse_uasset.py` — 现有 parse_uasset() 流程，parse_uasset_with_linker() 参考其结构
- `src/uasset_read/archive.py` — FArchive 类，PackageLinker 内部使用

### v6.0 失败归档
- `.planning/milestones/v6.0-FAILED-ARCHIVE.md` — v6.0 Phase 35e 失败原因，避免重复相同错误

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **UObjectInstance** (`link/object_instance.py`): 已有 dataclass 骨架，包含 package_index、object_name、outer 等核心字段和 5 个方法骨架，需补全实现
- **FArchive** (`archive.py`): 完整的二进制读取器（read_u8/u32/i32/fstring/bool_ue5 等），PackageLinker 内部使用
- **PackageIndex** (`serializers/object_resources.py`): 已有 index/is_import/is_export 逻辑，需新增 resolve_with_linker() 方法
- **ObjectImport/ObjectExport** (`serializers/object_resources.py`): 已有序列化后的 raw 数据，PackageLinker 基于它们创建 UObjectInstance 包装

### Established Patterns
- **数据类模式**: 项目全部使用 `@dataclass` 定义数据结构（PackageFileSummary、ObjectImport/Export 等）
- **惰性加载模式**: object_instance.py 已定义 `_serialized_properties` + `_preloaded` + `ensure_preloaded()` 模式
- **双入口模式**: 类似 `read_ue_graph_pin()` / `read_ue_graph_pin_ue5()` 的变体函数模式
- **解析结果模式**: `ParseResult` dataclass 作为 parse_uasset() 返回类型，`LinkerParseResult` 应遵循相同风格

### Integration Points
- `parse_uasset_with_linker()` 在 `parse_uasset.py` 中新增，调用顺序：read_package_summary → read_name_table → read_import_map → read_export_map → PackageLinker(objects).link() → 返回 LinkerParseResult
- `PackageLinker` 构造函数接收：FArchive 实例 + summary + name_map + import_map + export_map
- `PackageIndex.resolve_with_linker(linker)` 需要访问 PackageLinker 的 `_export_objects` / `_import_objects` 列表

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the design decisions captured above — the phase scope is well-defined by the v7.0 milestone document.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 41-link/ 模块基础设施*
*Context gathered: 2026-05-14*
