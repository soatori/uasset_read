# Phase 45: 图序列化 linker 变体 - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 45 为图序列化层（`graph.py`）创建 linker 变体函数，确保所有 graph 读取函数在 linker 可用时能正确解析 PackageIndex 为 `UObjectInstance` 对象引用。这是 v7.0 里程碑中 linker 集成的最后一环——Phase 41-44 已完成了 link/ 模块、集成入口、PackageIndex 增强和模型增强，本 phase 聚焦序列化层的 linker 变体实现。

</domain>

<decisions>
## Implementation Decisions

### 函数设计模式 — 保持可选参数

- **D-01:** 保持当前的可选参数模式（`linker: Optional[PackageLinker] = None`），不创建独立的 `_with_linker()` 后缀函数。
- **D-02:** 所有 graph 序列化函数已在 Phase 43/44 中集成了 linker 参数，本 phase 确保这些函数的 linker 路径完整覆盖所有 PackageIndex 解析场景。
- **D-03:** 不引入函数重复——每个序列化函数只有一份实现，内部通过 `if linker is not None` 分支处理。

### 全面 PackageIndex 解析

- **D-04:** 为 `UEdGraphPin` 中所有 FPackageIndex 类型字段添加对应的 `UObjectInstance` 引用字段。不仅限于 `default_object`，还包括 `source_index` 等所有可解析的 PackageIndex。
- **D-05:** 当 linker 存在时，通过 `PackageIndex(pkg_idx).resolve_with_linker(linker)` 或等价方式解析为 `UObjectInstance`。
- **D-06:** 解析失败时存入 `None`，不抛出异常（空安全策略）。

### from_archive 方法 — 新创廽 from_archive_with_linker

- **D-07:** 为 `UEdGraph`、`UEdGraphNode`、`UEdGraphPin` 创建新的 `from_archive_with_linker()` 类方法，保留现有 `from_archive()` 方法不变。
- **D-08:** `from_archive_with_linker()` 接受 `linker: Optional[PackageLinker] = None` 参数，并向下传递给对应的 `read_*` 函数。
- **D-09:** 新方法命名为 `from_archive_with_linker`，与 `parse_uasset_with_linker` 命名风格一致。

### 测试策略 — 集成测试

- **D-10:** Phase 45 只做基本功能验证（方法存在、参数传递正确、无导入错误），不编写完整单元测试。
- **D-11:** 完整测试留给 Phase 46（测试与验证阶段），使用真实 UE 资产验证 linker 模式下的图解析结果。

### Claude's Discretion

- 具体字段命名风格（`_ref` vs `_object` vs `_instance` 后缀）由 planner 根据代码库现有风格决定。
- `from_archive_with_linker` 方法的类型注解细节由 planner 决定。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 核心设计文档
- `.planning/ROADMAP.md` §v7.0 — Phase 45 定义：图序列化 linker 变体
- `.planning/STATE.md` — v7.0 状态：PackageIndex → UObjectInstance 实际引用
- `.planning/PROJECT.md` — v7.0 架构概览
- `.planning/REQUIREMENTS.md` — LINK-05: 图序列化 linker 变体

### 现有代码参考
- `src/uasset_read/serializers/graph.py` — 所有图序列化函数（已集成 linker 参数）
- `src/uasset_read/models/core.py` — UEdGraph/Node/Pin 数据类（Phase 44 已添加 linked_to_objects 字段）
- `src/uasset_read/link/linker.py` — PackageLinker.resolve_package_index()
- `src/uasset_read/link/object_instance.py` — UObjectInstance 数据类
- `src/uasset_read/serializers/object_resources.py` — PackageIndex 定义

### 上游 Phase 决策
- `.planning/phases/041-link-module-infrastructure/41-CONTEXT.md` — link/ 模块设计决策
- `.planning/phases/043-packageindex-enhance/043-CONTEXT.md` — PackageIndex 全面 linker 化
- `.planning/phases/044-model-enhancement/044-CONTEXT.md` — UEdGraphPin linked_to_objects

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **PackageLinker.resolve_package_index()** (`link/linker.py:123-142`): 将 PackageIndex 解析为 UObjectInstance，所有 linker 解析的统一入口
- **read_pin_reference()** (`serializers/graph.py:325-361`): 已实现 linker 解析逻辑，可复用其模式
- **read_ue_graph_pin()** (`serializers/graph.py:393-590`): 已集成 linker 参数，包含 linked_to_objects 等字段提取逻辑
- **_rcn() / _gac()** (`serializers/graph.py:41-48`): 类名解析 helper，linker 版本优先

### Established Patterns
- **可选参数模式**: graph.py 中所有 read_* 函数已采用 `linker: Optional[PackageLinker] = None` 模式
- **延迟导入**: from_archive 方法使用延迟导入避免循环依赖
- **双入口模式**: `parse_uasset()` / `parse_uasset_with_linker()` 命名约定
- **数据类模式**: 项目全部使用 `@dataclass` 定义数据结构

### Integration Points
- `from_archive_with_linker()` 新方法需添加到 `models/core.py` 的三个类中
- graph.py 中的 read_* 函数已支持 linker，无需修改函数签名
- `__init__.py` 需要导出新的 `from_archive_with_linker` 方法（如果通过模块导出）

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for field naming conventions.

</specifics>

<deferred>
## Deferred Ideas

- **全面 PackageIndex 字段解析**（D-04/D-05 范围较大）：除 UEdGraphPin 外，UEdGraphNode 和 UEdGraph 中可能还有其他 FPackageIndex 字段需要 linker 解析。完整扫描留给后续 phase。

### Reviewed Todos (not folded)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 045-graph-serialization-linker*
*Context gathered: 2026-05-14*
