---
gsd_state_version: 1.0
milestone: v7.0
milestone_name: UE 加载方式对齐 — 对象图重建
status: planning
last_updated: "2026-05-14T00:00:00.000Z"
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# v7.0 — 状态: 规划中

## 问题: Phase 35e 失败根因

linked_to_raw 为空不是字节偏移问题，而是缺少 UE FLinkerLoad 对象图重建机制。

## 目标

| 当前 | 目标 |
|------|------|
| PackageIndex → 名字字符串 | → UObjectInstance 实际引用 |
| 无对象图 | 构建 Outer 树 |
| 重复解析 | 对象缓存 |

## Phase 分解

| Phase | 名称 | 工作量 |
|-------|------|--------|
| 41 | link/ 模块 | ~2h |
| 42 | 集成入口 | ~1h |
| 43 | PackageIndex 增强 | ~0.5h |
| 44 | 模型增强 | ~0.5h |
| 45 | 图序列化 linker 变体 | ~2h |
| 46 | 测试与验证 | ~3h |

## 验证标准

- 373 测试 0 回归
- linked_to_objects 非空且正确
- Outer 树可导航
- parse_uasset() 行为不变

*Updated: 2026-05-14*
