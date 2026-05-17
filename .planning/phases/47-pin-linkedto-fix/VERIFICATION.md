# Phase 47: Pin LinkedTo 修复 — VERIFICATION.md

**Date:** 2026-05-15
**Phase:** 047-pin-linkedto-fix

---

## 验证结果

### Goal: `linked_to_raw` 非空, `connections > 0`, `execution_flows[].nodes` 非空

| 标准 | 修复前 | 修复后 | 状态 |
|------|--------|--------|------|
| `linked_to_raw` 非空 | 0/30 pins | 16/43 pins | ✅ PASS |
| `connections` 非空 | 0 | EventGraph: 2, Aim: 1, Move: 1 | ✅ PASS |
| `execution_flows[].nodes` 非空 | 0 flows | 7 flows (EventGraph) | ✅ PASS |
| 现有测试无回归 | 24 失败 | 21 失败（+3 通过） | ✅ PASS |

### 测试

- `tests/test_phase47_pin_linkedto.py` — 6 passed
- `tests/test_phase44_linker_objects.py` — 16 passed (同步更新 synthetic buffer bool 大小)
- `tests/test_phase45_from_archive_with_linker.py` — 8 passed
- 全量: 438 passed, 21 failed, 67 skipped

### 失败分析

21 个失败均为预存在问题，与 Phase 47 修复无关：
- 8x `test_uasset_read.py` — 合成资产路径/版本问题（pre-existing）
- 8x `test_phase21_verification.py` — Jump 流未找到（pre-existing）
- 2x `test_ue5_pin_integration.py` — 资产路径匹配到 FirstPersonC（pre-existing）
- 1x `test_data_flows_not_empty` — data_flows 构建器问题（pre-existing）
- 2x 其他 pre-existing

---

## 变更清单

| 文件 | 变更 |
|------|------|
| `src/uasset_read/models/core.py` | `FEdGraphPinType` 添加 5 个字段 + `pin_subcategory_object` 类型修正 |
| `src/uasset_read/serializers/graph.py` | 5x `read_bool_1byte()` → `read_bool()` |
| `tests/test_phase44_linker_objects.py` | synthetic buffer bool 从 1B → 4B |
| `tests/test_phase47_pin_linkedto.py` | 新增 6 个验证测试 |

---

*Verified: 2026-05-15*
