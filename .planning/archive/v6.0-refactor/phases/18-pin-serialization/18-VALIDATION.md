---
phase: 18
slug: 18-pin-serialization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/conftest.py |
| **Quick run command** | `python -m pytest tests/test_ue_graph_pin.py -x -v` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_ue_graph_pin.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | PIN-01 | T-18-01 | CustomVersion GUID validation | unit | `pytest tests/test_ue_graph_pin.py::test_custom_version_constants -x` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | PIN-05 | T-18-02 | BitField bit positions | unit | `pytest tests/test_ue_graph_pin.py::test_bitfield_constants -x` | ❌ W0 | ⬜ pending |
| 18-02-01 | 02 | 2 | PIN-04 | T-18-03 | Pin reference format | unit | `pytest tests/test_ue_graph_pin.py::test_pin_reference_format -x` | ❌ W0 | ⬜ pending |
| 18-02-02 | 02 | 2 | PIN-04 | T-18-04 | Pin array format | unit | `pytest tests/test_ue_graph_pin.py::test_pin_array_format -x` | ❌ W0 | ⬜ pending |
| 18-03-01 | 03 | 3 | PIN-01~05 | T-18-05 | Complete pin serialization | integration | `pytest tests/test_ue_graph_pin.py::test_pin_complete_fields -x` | ❌ W0 | ⬜ pending |
| 18-04-01 | 04 | 4 | PIN-02 | T-18-06 | PinType version checks | unit | `pytest tests/test_ue_graph_pin.py::test_pin_type_version_checks -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ue_graph_pin.py` — stubs for PIN-01~05
- [ ] CustomVersion 常量定义
- [ ] FPackageIndex 解析辅助函数
- [ ] FText 解析函数（若未实现）

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UE 5.7 资产 Pin 数据验证 | PIN-01~05 | 需要实际 UE 5.7 编辑器资产 | 1. 解析 BP_FirstPersonCharacter.uasset 2. 对比 JSON pin_id 与 UE 编辑器显示 3. 验证 linked_to 节点引用 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

## Threat Model Reference

| Threat ID | Description | Mitigation Location |
|-----------|-------------|---------------------|
| T-18-01 | GUID 格式错误导致版本判断失败 | 18-01-PLAN Task 1 |
| T-18-02 | BitField 位置错误导致显示属性错误 | 18-01-PLAN Task 2 |
| T-18-03 | OwningNode 缺失导致连接无法构建 | 18-02-PLAN Task 1 |
| T-18-04 | Pin array 越界读取 | MAX_LINKEDTO_PER_PIN 限制 |
| T-18-05 | 字段顺序错位导致解析失败 | 18-03-PLAN Task 1 |
| T-18-06 | 版本检查缺失导致格式错误 | 18-04-PLAN Task 1 |

---

*Created: 2026-05-04 via gsd-plan-phase workflow*