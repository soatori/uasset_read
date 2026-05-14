# Phase 45: 图序列化 linker 变体 — Discussion Log

**Date:** 2026-05-14
**Mode:** discuss (default)

## Discussion Summary

### Area 1: 函数设计模式

**Question:** 图序列化函数应该采用哪种设计？当前代码已集成 linker 参数，但 ROADMAP 提到的是 'linker 变体'。

**Options:**
1. 保持可选参数模式（推荐）— 零 API 变化，向后兼容
2. 创建独立变体函数 — 职责单一但大量重复
3. 统一入口 + 内部分发 — 需要重构现有代码

**Decision:** 保持可选参数模式。当前 graph.py 已正确集成 linker 参数，不需要创建重复函数。

### Area 2: 默认对象 linker 解析

**Question:** default_object 字段当前只存储 FPackageIndex 的 int 值，是否需要通过 linker 解析为 UObjectInstance？

**Options:**
1. 添加默认对象引用（推荐）— 只解析 default_object
2. 保持原始 int 值 — 格式化层自行查找
3. 全面 PackageIndex 解析 — 所有 PackageIndex 字段都解析

**Decision:** 全面 PackageIndex 解析。不仅 default_object，还包括 source_index 等所有可解析的 PackageIndex 字段。

### Area 3: 图导出 linker 状态

**Question:** UEdGraph/UEdGraphNode/UEdGraphPin 的 from_archive 类方法是否需要更新以支持 linker 参数传递？

**Options:**
1. 更新 from_archive（推荐）— 添加可选参数
2. 不更新 from_archive — linker 模式只通过底层函数
3. 新方法 from_archive_with_linker — 零风险，增加 API 表面积

**Decision:** 创建新方法 `from_archive_with_linker`，保留现有 `from_archive` 不变。命名与 `parse_uasset_with_linker` 一致。

### Area 4: 测试策略

**Question:** Phase 45 的测试策略是什么？Phase 46 是集中测试验证阶段。

**Options:**
1. 基本功能验证（推荐）— 只验证方法存在和参数传递
2. 完整单元测试 — 覆盖所有路径
3. 仅集成测试 — 使用真实 UE 资产验证

**Decision:** 仅集成测试。Phase 45 只做基本功能验证，完整测试留给 Phase 46。

## Decisions Captured

| ID | Decision | Category |
|----|----------|----------|
| D-01 | 保持可选参数模式 | 函数设计 |
| D-02 | 不创建重复函数 | 函数设计 |
| D-03 | 一份实现内部处理 | 函数设计 |
| D-04 | 所有 FPackageIndex 字段解析 | PackageIndex 解析 |
| D-05 | linker 解析路径 | PackageIndex 解析 |
| D-06 | 解析失败存 None | PackageIndex 解析 |
| D-07 | 创建 from_archive_with_linker | from_archive 方法 |
| D-08 | 接受 linker 参数向下传递 | from_archive 方法 |
| D-09 | 命名与 parse_uasset_with_linker 一致 | from_archive 方法 |
| D-10 | 基本功能验证 | 测试策略 |
| D-11 | 完整测试留给 Phase 46 | 测试策略 |

## Deferred Ideas

- 全面 PackageIndex 字段解析（除 UEdGraphPin 外的其他类）

---

*Phase: 045-graph-serialization-linker*
*Discussion completed: 2026-05-14*
