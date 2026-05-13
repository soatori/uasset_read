# Phase 41: link/ 模块基础设施 - Discussion Log

**Date:** 2026-05-14
**Mode:** Default (interactive)

## Discussion Summary

### 架构设计 — 加载策略

**Q:** PackageLinker 的 link() 方法应该采用哪种加载策略？

**Decision:** 两阶段分离 — link() 只读头信息建壳，preload() 按需加载属性。完全对应 UE 的 FLinkerLoad 模式。

**Rationale:** 用户明确要求对应 UE 的 FLinkerLoad 两阶段加载模式（Link → Preload），避免一次性加载全部属性的内存开销。

### 接口设计 — 入口点

**Q:** 新入口函数 parse_uasset_with_linker() 应该如何暴露？

**Decision:** 新增函数 — parse_uasset_with_linker() 作为独立入口，返回 LinkerParseResult。现有 parse_uasset() 完全不变。

**Rationale:** 符合 v7.0 设计原则"增量采用"，确保现有代码路径零影响。

### 模块导出

**Q:** link/ 模块的公共 API 应该如何导出？

**Decision:** 子模块导入 — 用户通过 `from uasset_read.link import PackageLinker` 访问。

**Rationale:** 保持命名空间清晰，link/ 作为独立子模块，不与核心 API 混在一起。

### 数据复用

**Q:** PackageLinker 与现有序列化器的关系：应该接收已解析数据还是自己重新读取？

**Decision:** 接收已解析数据 — PackageLinker 接收 summary/import_map/export_map/name_map 作为参数，不重复读取。

**Rationale:** 复用 parse_uasset_with_linker() 中已完成的头解析工作，避免重复代码和双重 seek/read。

## Decisions Summary

| # | Area | Decision |
|---|------|----------|
| D-01 | 加载策略 | 两阶段分离 (link + preload) |
| D-02 | 入口点 | 新增独立函数 |
| D-03 | 模块导出 | 子模块导入 |
| D-04 | 数据复用 | 接收已解析数据 |

## Deferred Ideas

None.
