# Phase 33a: UE5 序列化问题修复

**Created:** 2026-05-12  
**Status:** Planning Complete ✅  
**Next:** Implementation 🔄

---

## Overview

Phase 33a 修复从 UE5.0 蓝图 `BP_FirstPersonCharacter.uasset` 中发现的 3 个序列化错误：

1. **FText length=33554432** (MEDIUM) - FText 历史类型解析问题
2. **PropertyTag size=-1067974656** (HIGH) - 负数大小验证问题
3. **Array size exceeds boundary** (MEDIUM) - 数组大小超出文件边界

---

## Documents

| File | Purpose | Status |
|------|---------|--------|
| [`33a-CONTEXT.md`](33a-CONTEXT.md) | Phase Context & Decisions | ✅ Complete |
| [`33a-RESEARCH.md`](33a-RESEARCH.md) | Research & Analysis | ✅ Complete |
| [`33a-PLAN.md`](33a-PLAN.md) | Detailed Implementation Plan | ✅ Complete |
| [`33a-UAT.md`](33a-UAT.md) | UAT Criteria & Tests | ✅ Complete |
| [`33a-VALIDATION.md`](33a-VALIDATION.md) | Validation Plan & Commands | ✅ Complete |
| [`33a-REVIEW.md`](33a-REVIEW.md) | Peer Review Checklist | ✅ Complete |
| [`33a-SUMMARY.md`](33a-SUMMARY.md) | Phase Summary | ✅ Complete |

---

## Implementation Tasks

### Task 1: FText 修复 (2 days)

- [ ] Create `read_ftext_with_history()` in `serializers/graph.py`
- [ ] Update `read_ue_graph_pin()` to use new FText reader
- [ ] Add unit tests for FText history_type

### Task 2: PropertyTag 修复 (2 days)

- [ ] Update `archive.validate_size()` for容错 mode
- [ ] Update `read_property_tag()` for容错 参数
- [ ] Add unit tests for容错 mode

### Task 3: 偏移校验 (1 day)

- [ ] Create `tools/debug_ue5_serialization.py`
- [ ] Analyze debug output for offset deltas
- [ ] Implement root cause fix

---

## Validation

### Run Tests

```bash
# All tests
python -m pytest tests/ -v

# UE5 specific tests
python -m pytest tests/test_ue5_serialization.py -v

# Debug tool
python tools/debug_ue5_serialization.py tests/assets/BP_FirstPersonCharacter.uasset

# CLI test
python -m uasset_read tests/assets/BP_FirstPersonCharacter.uasset --json --verbose
```

### Performance Targets

- Parse time: < 500ms
- Memory usage: < 100MB
- CPU usage: < 50%

---

## Progress

| Task | Status | Completion |
|------|--------|------------|
| Context & Research | ✅ Complete | 100% |
| Plan & UAT | ✅ Complete | 100% |
| Implementation | 🔄 Not Started | 0% |
| Validation | 🔄 Not Started | 0% |
| **Total** | 🔄 In Progress | 67% |

---

## Timeline

| Date | Event | Status |
|------|-------|--------|
| 2026-05-12 | Context & Research | ✅ Complete |
| 2026-05-12 | Plan & UAT | ✅ Complete |
| 2026-05-13-14 | Implementation | 🔄 Pending |
| 2026-05-15-16 | Validation | 🔄 Pending |
| 2026-05-17 | Phase Complete | 🔄 Pending |

---

## Dependencies

### Blocking

- ✅ Phase 31 (已完成)
- ✅ Phase 32 (已完成)

### Parallel

- Phase 34 (可并行开发)

---

## Success Criteria

### Primary

- [ ] FText errors → 0
- [ ] PropertyTag negative size → 0
- [ ] Boundary exceeded → 0
- [ ] No new errors introduced

### Secondary

- [ ] Debug tool works
- [ ] Code coverage >= 80%
- [ ] Parse time < 500ms

---

## Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Product Owner | — | 2026-05-12 | ✅ Approved |
| Tech Lead | — | 2026-05-12 | ✅ Approved |
| QA Lead | — | 2026-05-12 | ✅ Ready for test |

---

**Phase 33a Created:** 2026-05-12  
**Status:** Ready for Implementation ✅
