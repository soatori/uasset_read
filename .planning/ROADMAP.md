# 路线图 — v7.0（规划中）

**v6.0** ✅ 373 passed, 0 failed | [历史归档](archive/v6.0-refactor/ARCHIVE-INDEX.md)

## v7.0 Phase 分解

| Phase | 名称 | 目标 | 状态 |
|-------|------|------|------|
| 41 | link/ 模块 | UObjectInstance, PackageLinker, LinkerParseResult | ✅ 完成 |
| 42 | 集成入口 | parse_uasset_with_linker() | ✅ 完成 |
| 43 | PackageIndex | resolve_with_linker() | ✅ 完成 |
| 44 | 模型增强 | UEdGraphPin linked_to_objects | ✅ 完成 |
| 45 | 图序列化 | from_archive_with_linker() 方法 + default_object_ref | ✅ 完成 |
| 46 | 测试验证 | 373 测试 0 回归 | ⏳ 待执行 |

**核心改变**: PackageIndex → UObjectInstance 实际引用，构建 Outer 对象树

### Phase 45: 图序列化 linker 变体 ✅

**Goal:** 为 UEdGraph/UEdGraphNode/UEdGraphPin 创建 from_archive_with_linker() 入口方法

**Requirements:** LINK-05

**Plans:** 1 plan

Plans:
- [x] 045-01-PLAN.md — 创建 from_archive_with_linker() 方法 + default_object_ref 字段 + 基本验证测试

**Status:** UAT passed (8/8 tests)

**Test Results:**
- `UEdGraphPin.from_archive_with_linker()`: ✅
- `UEdGraphNode.from_archive_with_linker()`: ✅
- `UEdGraph.from_archive_with_linker()`: ✅
- `default_object_ref` field: ✅
- `default_object` linker resolution: ✅
- Backward compatibility: ✅
- Regression testing: ✅ (450 passed, 10 pre-existing failures)

*Updated: 2026-05-14*
