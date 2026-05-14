---
phase: 35e
type: summary
created: 2026-05-13
status: planning
plans: 4
---

# Phase 35e: Pin Offset 根因诊断与 UE5 C++ 参考验证 - 摘要

## Phase Overview

| Property | Value |
|----------|-------|
| Phase | 35e |
| Name | Pin Offset 根因诊断与 UE5 C++ 参考验证 |
| Status | 规划中 |
| Created | 2026-05-13 |
| Dependencies | Phase 35b (阻塞) |
| Priority | P0 - 阻塞 |

## 问题陈述

Phase 35b 的 fixes (35b-01 到 35b-05) 修复了约 12 字节的偏移：
- PinType 4 bools: -12B (4→1 字节 each)
- FText b_has_culture: -3B (4→1 字节)
- BitField: +3B (1→4 字节)

但 `linked_to_raw` 仍然为空 (0/10 pins)，表明存在另一个约 4 字节的偏移未修复。

## 目标

通过 UE5 C++ 源码参考和二进制跟踪工具，精确定位并修复 UE5 pin 序列化的 4 字节偏移问题。

## 计划分解

| Plan | Description | Files | Status |
|------|-------------|-------|--------|
| 35e-01 | UE5 EdGraphPin.cpp 字段边界分析 | - | 规划中 |
| 35e-02 | 二进制跟踪工具增强与 pin body 映射 | tools/binary_trace_pin.py | 规划中 |
| 35e-03 | Direction/FName 4 字节偏移修复 | graph.py | 规划中 |
| 35e-04 | 集成测试验证 | tests/test_ue5_pin_*.py | 规划中 |

## 成功标准

- [ ] 提供 EdGraphPin.cpp L1838-1964 的精确字段偏移表
- [ ] 定位 Direction/FName 之间的 4 字节偏移来源
- [ ] linked_to_raw 非空 (≥1 pin with connections)
- [ ] execution_flows 正确构建 (EventGraph jump chain)
- [ ] data_flows 正确构建 (Move graph ActionValue_X/Y)
- [ ] `pytest tests/` 397+ passed, 0 failed
- [ ] 二进制跟踪显示零偏移 (≤0 bytes drift)

## 验收标准 (UAT)

| Test | Expected | Current |
|------|----------|---------|
| UE5 C++ reference analysis | EdGraphPin fields mapped | Not yet done |
| Binary trace verification | All fields at correct offset | Not yet done |
| linked_to_raw non-empty | ≥1 pin has links | 0/10 (FAIL) |
| execution_flows populated | Contains Jump chain | Empty |
| data_flows populated | Contains ActionValue_X/Y | Empty |
| Full test suite | 397+ pass, 0 fail | 456 pass, 9 fail |

## 子计划详情

### 35e-01: UE5 C++ 源码参考分析

**目标**：通过 UE5 EdGraphPin.cpp L1838-1964 确认精确字段偏移

**关键洞见**：
- Direction 使用 `TEnumAsByte` (1 byte)
- BitField 使用 `uint32` (4 bytes)
- PinType 序列化顺序和大小
- 可能的 4 字节 padding 位置

**输出**：`.planning/phases/35e-pin-offset-debug/35e-01-SUMMARY.md`

### 35e-02: 二进制跟踪增强

**目标**：逐字段跟踪 pin body，对比 UE5 源码 vs 实际解析

**工具**：`tools/binary_trace_pin.py`
- 跟踪每个字段的二进制偏移
- 标记预期偏移 vs 实际偏移
- 生成 drift 报告

**输出**：`.planning/phases/35e-pin-offset-debug/35e-02-SUMMARY.md`

### 35e-03: 偏移修复

**目标**：根据跟踪结果，修复 graph.py 中的序列化逻辑

**可能修复**：
1. Direction 后添加 4 字节跳过 (如果需要 padding)
2. PinType FName 对齐修正
3. pins_offset 动态扫描改进

**输出**：`.planning/phases/35e-pin-offset-debug/35e-03-SUMMARY.md`

### 35e-04: 集成测试验证

**目标**：验证所有修复效果

**测试文件**：
- `tests/test_ue5_pin_offset_verification.py` (new)
- `tests/test_ue5_pin_integration.py` (existing)
- `tests/test_phase21_verification.py` (unskipped tests)

**成功标准**：
- linked_to_raw: ≥1 pins non-empty
- execution_flows: EventGraph has Jump chain
- data_flows: Move graph has ActionValue_X/Y
- Full suite: 397+ passed, 0 new failures

**输出**：`.planning/phases/35e-pin-offset-debug/35e-04-SUMMARY.md`

## 风险评估

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 4 字节来源判断错误 | MEDIUM | High | Binary trace validation |
| Break UE4 compatibility | LOW | Medium | Version check guards |
| Introduce new drift | LOW | Critical | Test coverage + rollback |

## 与 Phase 35b 的关系

- **Phase 35b**: identify the problem (empty linked_to_raw)
- **Phase 35e**: identify the root cause + fix
- **Next Phase**: validate + release

## 下一步行动

1. **立即**: 开始 35e-01 (UE5 C++ 源码参考分析)
2. **完成 35e-01**: 运行 35e-02 (二进制跟踪)
3. **完成 35e-02**: 实施 35e-03 (修复)
4. **完成 35e-03**: 运行 35e-04 (验证)
5. **完成 35e-04**: 更新 Phase 35b UAT + close

## 资源

- **源码参考**：UE5.7 EdGraphPin.cpp L1838-1964
- **二进制分析**：tools/binary_trace_pin.py
- **测试资产**：BP_FirstPersonCharacter.uasset
- **现有文档**：.planning/phases/35b-pin-connection-debug/

---

**Last Updated**: 2026-05-13  
**Phase Status**: Planning  
**Next Action**: Execute 35e-01 (UE5 C++ source reference)
