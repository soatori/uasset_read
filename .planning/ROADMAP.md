# 路线图 — v7.0（规划中）

**v6.0** ✅ 373 passed, 0 failed | [历史归档](archive/v6.0-refactor/ARCHIVE-INDEX.md)

## v7.0 Phase 分解

| Phase | 名称 | 目标 | 依赖 |
|-------|------|------|------|
| 41 | link/ 模块 | UObjectInstance, PackageLinker, LinkerParseResult | 无 |
| 42 | 集成入口 | parse_uasset_with_linker() | Phase 41 |
| 43 | PackageIndex | resolve_with_linker() | Phase 41 |
| 44 | 模型增强 | UEdGraphPin linked_to_objects | Phase 41 |
| 45 | 图序列化 | from_archive_with_linker() 方法 + default_object_ref | Phase 41, 44 |
| 46 | 测试验证 | 373 测试 0 回归 | Phase 42-45 |

**核心改变**: PackageIndex → UObjectInstance 实际引用，构建 Outer 对象树

### Phase 45: 图序列化 linker 变体

**Goal:** 为 UEdGraph/UEdGraphNode/UEdGraphPin 创建 from_archive_with_linker() 入口方法

**Requirements:** LINK-05

**Plans:** 1 plan

Plans:
- [ ] 045-01-PLAN.md — 创建 from_archive_with_linker() 方法 + default_object_ref 字段 + 基本验证测试

*Updated: 2026-05-14*
