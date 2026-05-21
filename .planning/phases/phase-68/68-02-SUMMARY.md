---
phase: 68
plan: 02
subsystem: N2C
tags: [type-registry, singleton, inheritance, cache]
dependency_graph:
  requires: [68-01]
  provides: [N2CNodeTypeRegistry]
  affects: [n2c/__init__.py]
tech_stack:
  added: [type_registry.py]
  patterns: [singleton, lazy-initialization, inheritance-fallback, memoization]
key_files:
  created:
    - src/uasset_read/n2c/type_registry.py
    - tests/n2c/test_type_registry.py
  modified:
    - src/uasset_read/n2c/__init__.py
    - tests/n2c/conftest.py
decisions:
  - "使用单例模式管理注册表，reset() 支持测试隔离"
  - "延迟初始化 _ensure_initialized() 避免导入循环"
  - "继承回退使用 visited set + max_depth=10 双重保护"
  - "缓存同时缓存精确匹配失败的结果（Unknown）"
metrics:
  duration_seconds: 120
  completed_date: "2026-05-22"
---

# Phase 68 Plan 02: N2CNodeTypeRegistry 单例实现 Summary

**Objective:** 实现 N2CNodeTypeRegistry 单例类，提供 class_name -> N2CNodeType 的精确匹配和继承链回退查找，使用缓存优化性能。

**One-liner:** N2CNodeTypeRegistry 单例类，支持精确匹配、继承回退、缓存优化和 Unknown fallback，123 种 K2Node 类型完整注册。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 创建 N2CNodeTypeRegistry 单例类 | `4687adc` | `src/uasset_read/n2c/type_registry.py` |
| 2 | 更新 n2c/__init__.py 导出 | `38f2be4` | `src/uasset_read/n2c/__init__.py` |
| 3 | 编写 TypeRegistry 单元测试 | `90df42d` | `tests/n2c/test_type_registry.py`, `tests/n2c/conftest.py` |

## Implementation Details

### N2CNodeTypeRegistry 核心方法

| Method | Purpose | Behavior |
|--------|---------|----------|
| `get_instance()` | 单例访问 | 延迟创建，线程安全 |
| `reset()` | 测试支持 | 清空单例，下次 get_instance 返回新实例 |
| `_ensure_initialized()` | 延迟初始化 | 首次 resolve 时填充 _type_map |
| `resolve(class_name)` | 类型解析 | 精确匹配 -> 缓存 -> 继承链 -> Unknown |
| `get_registered_types()` | 诊断 | 返回排序后的 class_name 列表 |

### resolve() 查找顺序

1. **精确匹配**: `_type_map[class_name]` — 直接查找 K2NODE_ENUM_NAMES 映射
2. **缓存命中**: `_resolve_cache[class_name]` — 返回之前解析的结果
3. **继承链**: 沿 `K2NODE_INHERITANCE` 向上查找父类，最多 10 层
4. **Unknown fallback**: 所有路径失败返回 `N2CNodeType.Unknown`

### 注册统计

- **已注册类型**: 123 种
- **继承关系**: 121 条（K2Node 为根）
- **覆盖率**: 100% K2NODE_ENUM_NAMES -> N2CNodeType 映射

## Test Results

- **17 个新测试**，全部通过
- **46 个 n2c 模块测试**，全部通过，无回归
- 覆盖: 单例管理 (2), 精确匹配 (3), 继承回退 (5), Unknown (2), 缓存 (2), 诊断 (3)

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tampering | type_registry.py | 继承链循环保护：visited set + max_depth=10 |
| threat_flag: import_cycle | type_registry.py | TYPE_CHECKING 延迟导入 + _ensure_initialized() |

## Known Stubs

None.

## Self-Check: PASSED
