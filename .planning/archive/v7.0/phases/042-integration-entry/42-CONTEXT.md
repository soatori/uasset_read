# Phase 42: 集成入口 — parse_uasset_with_linker() - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

在 `parse_uasset.py` 中新增 `parse_uasset_with_linker()` 函数，作为使用 PackageLinker 的并行入口点。现有 `parse_uasset()` 完全不变。此函数串联 Phase 41 已实现的 link/ 模块，形成完整的 linker 解析管线。

</domain>

<spec_lock>
## Locked Requirements (from v7.0-OBJECT-GRAPH.md)

- **不修改现有序列化器** — PackageLinker 坐于现有序列化器之上
- **增量采用** — 新增并行入口点，现有代码路径不变
- **parse_uasset() 行为完全不变** — 零回归
- **373 测试全部通过**

</spec_lock>

<decisions>
## Implementation Decisions

### 返回类型
- **D-01:** `parse_uasset_with_linker()` 返回独立的 `LinkerParseResult`，不复用或扩展 `ParseResult`。保持类型边界清晰。

### 错误处理
- **D-02:** linker 链路失败时搜集 errors 到 `LinkerParseResult.errors` 中（类似现有 `tolerant` 模式）。不静默回退到 `parse_uasset()`，不直接抛异常。调用方可检查 `is_success` 和 `errors` 判断状态。

### 结果聚合
- **D-03:** 提取 blueprint metadata / graphs / dependencies 后处理为内部 `_post_process()` 函数，`parse_uasset()` 和 `parse_uasset_with_linker()` 共享调用。避免代码重复，保证两套入口的后处理逻辑一致。

### API 签名
- **D-04:** `parse_uasset_with_linker(path: str, tolerant: bool = True, preload_all: bool = False)` 与 `parse_uasset()` 保持一致的 `path` + `tolerant` 签名，增加 `preload_all` 控制是否预加载所有 exports（默认 False，符合两阶段加载惰性设计）。

### 模块导出
- **D-05:** `parse_uasset_with_linker` 从 `uasset_read.parse_uasset` 模块导入，不在顶层 `uasset_read/__init__.py` 扁平导出。与 Phase 41 D-03 保持一致。

### Claude's Discretion
- 具体变量命名、错误消息文本、类型注解细节由下游 planner 根据代码库现有风格决定。
- `_post_process()` 函数的具体参数列表（需要哪些参数）由 planner 分析两个入口的公共后处理步骤后确定。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心设计文档
- `.planning/milestones/v7.0-OBJECT-GRAPH.md` — v7.0 完整设计文档，包含 Phase 分解、UE FLinkerLoad 参考表、验证标准
- `.planning/STATE.md` — 当前 v7.0 状态（planning 中）
- `.planning/ROADMAP.md` §v7.0 — Phase 41-46 列表
- `.planning/phases/41-link-module-infrastructure/41-CONTEXT.md` — 上游 Phase 41 的决策文档

### 现有代码参考
- `src/uasset_read/parse_uasset.py` — 现有 parse_uasset() 流程，parse_uasset_with_linker() 参考其结构，也是新增函数的目标文件
- `src/uasset_read/link/__init__.py` — link/ 模块导出
- `src/uasset_read/link/linker.py` — PackageLinker 核心类
- `src/uasset_read/link/result.py` — LinkerParseResult 数据类
- `src/uasset_read/link/object_instance.py` — UObjectInstance 数据类
- `src/uasset_read/models/result.py` — ParseResult 数据类（参考风格，但不复用）
- `src/uasset_read/serializers/package_summary.py` — read_package_summary() 和 read_name_table()
- `src/uasset_read/serializers/object_resources.py` — read_import_map, read_export_map, 等

### v6.0 失败归档
- `.planning/milestones/v6.0-FAILED-ARCHIVE.md` — v6.0 Phase 35e 失败原因

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **parse_uasset.py 现有管线** — 完整的头读取 → 属性解析 → blueprint 提取 → graph 提取 → 依赖分析流程，可作为 `_post_process()` 提取的基础
- **LinkerParseResult** (`link/result.py`) — 已有 summary/name_map/import_map/export_map/linker/root_objects/all_objects/errors/is_success 等字段
- **PackageLinker** (`link/linker.py`) — link() 创建 UObjectInstance 壳，preload(index) 惰性加载属性
- **UObjectInstance** (`link/object_instance.py`) — 完整的对象表示，含 get_full_name()、get_children()、ensure_preloaded() 等方法

### Established Patterns
- **数据类模式**: `@dataclass` + field(default_factory=list)
- **容错模式**: try/except 收集 errors 到结果列表，最终设置 is_success
- **双入口模式**: 类似 read_ue_graph_pin() / read_ue_graph_pin_ue5() 的变体函数
- **延迟导入**: parse_uasset.py 中 graph 模块使用 try/except ImportError 延迟导入
- **FArchive 双开模式**: blueprint 提取时创建第二个 FArchive 实例以复用偏移状态

### Integration Points
- `parse_uasset_with_linker()` 调用顺序：read_package_summary → read_name_table → read_import_map → read_export_map → PackageLinker(objects).link() → 后处理 → 返回 LinkerParseResult
- `_post_process()` 需要接收：archive, summary, name_map, import_map, export_map, 以及目标结果对象
- Phase 41 已实现的 link/ 模块可直接使用，无需修改

</code_context>

<specifics>
## Specific Ideas

No additional requirements beyond the decisions captured above.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 42-integration-entry*
*Context gathered: 2026-05-14*
