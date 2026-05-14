---
gsd_state_version: 1.0
milestone: v7.0
milestone_name: UE 加载方式对齐 — 对象图重建
status: in_progress
last_updated: "2026-05-14T00:00:00.000Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 1
  completed_plans: 1
  percent: 17
---

# v7.0 — 状态: 进行中

## 问题: Phase 35e 失败根因

linked_to_raw 为空不是字节偏移问题，而是缺少 UE FLinkerLoad 对象图重建机制。

## 目标

| 当前 | 目标 |
|------|------|
| PackageIndex → 名字字符串 | → UObjectInstance 实际引用 |
| 无对象图 | 构建 Outer 树 |
| 重复解析 | 对象缓存 |

## Phase 分解

| Phase | 名称 | 状态 |
|-------|------|------|
| 41 | link/ 模块 | ✅ 完成 |
| 42 | 集成入口 | ✅ 完成 |
| 43 | PackageIndex 增强 | ✅ 完成 |
| 44 | 模型增强 | ✅ 完成 |
| 45 | 图序列化 linker 变体 | ✅ 完成 (UAT passed) |
| 46 | 测试与验证 | ⏳ 待执行 |

## 验证标准

- 373 测试 0 回归 ✅ (450 passed, 10 pre-existing failures)
- linked_to_objects 非空且正确 ✅ (Phase 44 verified)
- Outer 树可导航 ✅ (Phase 44 verified)
- parse_uasset() 行为不变 ✅ (Phase 44 verified)

*Updated: 2026-05-14*
