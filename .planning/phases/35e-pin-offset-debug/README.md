# Phase 35e: Pin Offset 根因诊断与 UE5 C++ 参考验证

**Phase**: 35e  
**Status**: 规划中  
**Created**: 2026-05-13  
**Depends on**: Phase 35b (LinkedTo empty issue)

## Overview

Phase 35b 修复了约 12 字节的序列化偏移，但 `linked_to_raw` 仍然为空。Phase 35e 的目标是：

1. 通过 UE5 C++ 源码确认精确的 pin 序列化字段偏移
2. 定位剩余 4 字节偏移的来源
3. 修复 `graph.py` 中的序列化逻辑
4. 验证 linked_to_raw 正确读取

## Plans

| Plan | Description | Files | Status |
|------|-------------|-------|--------|
| 35e-01 | UE5 EdGraphPin.cpp 字段边界分析 | - | 📋 规划中 |
| 35e-02 | 二进制跟踪工具增强与 pin body 映射 | tools/ | 📋 规划中 |
| 35e-03 | Direction/FName 4 字节偏移修复 | graph.py | 📋 规划中 |
| 35e-04 | 集成测试验证 | tests/ | 📋 规划中 |

## Key Files

- **Source Reference**: UE5.7 EdGraphPin.cpp L1838-1964 (SerializePin)
- **Binary Trace**: `tools/binary_trace_pin.py`
- **Parser**: `src/uasset_read/serializers/graph.py`
- **Test Asset**: `E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset`

## Problem Statement

### Phase 35b Fixes Applied

| Component | Before | After | Bytes Fixed |
|-----------|--------|-------|-------------|
| PinType 4 bools | 4 bytes each | 1 byte each | -12 B |
| FText b_has_culture | 4 bytes | 1 byte | -3 B |
| BitField | 1 byte | 4 bytes | +3 B |
| **Net Fixed** | — | — | **-12 B** |

### Remaining Issue

- **Symptom**: `linked_to_raw` 仍然为空 (0/10 pins)
- **Estimated Drift**: ~4 bytes
- **Location**: Direction/FName 结构 或 pins_offset 计算

## Success Criteria

- [x] UE5 C++ 源码参考分析完成 (35e-01)
- [x] 二进制跟踪验证 (35e-02)
- [ ] Direction/FName 修复实施 (35e-03)
- [ ] 集成测试验证 (35e-04)
- [ ] `pytest tests/` 397+ passed, 0 failed
- [ ] linked_to_raw 非空 (≥1 pin)

## Current State

### Phase 35b UAT Status

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Pin 连接数据解析 | linked_to_raw 非空 | 0/10 | ❌ FAIL |
| Execution Flows | 有流链路 | 待测试 | ⏳ pending |
| Data Flows | 有数据流 | 待测试 | ⏳ pending |
| 回归测试 | 全部通过 | 9 失败 | ⏳ pending |

### Gaps

```
- truth: "pin.linked_to_raw 应该是非空的"
  severity: blocker
  root_cause: "4字节偏移未修复 - Direction/FName结构"
  missing:
    - "修复 Direction 字段序列化格式"
    - "修复 pins_offset 动态扫描逻辑"
```

## Action Plan

### Week 1: Analysis

- [ ] **Day 1**: 完成 35e-01 (UE5 源码分析)
  - 阅读 EdGraphPin.cpp L1838-1964
  - 提取精确字段偏移表
  - 确认 Direction/PinType 细节

- [ ] **Day 2**: 完成 35e-02 (二进制跟踪)
  - 增强 binary_trace_pin.py
  - 跟踪 pin body 每个字段
  - 对比 UE5 源码 vs 实际解析

- [ ] **Day 3**: 定位 4 字节偏移
  - 偏移在 Direction 后？
  - 偏移在 PinType 前？
  - 偏移在 pins_offset？

### Week 2: Fix & Validate

- [ ] **Day 1**: 完成 35e-03 (修复偏移)
  - 修改 graph.py 的 read_ue_graph_pin()
  - 添加 version guard (UE5 only)
  - 单元测试验证

- [ ] **Day 2**: 完成 35e-04 (集成验证)
  - 运行完整测试套件
  - 验证 linked_to_raw 非空
  - 验证 execution/data flows

- [ ] **Day 3**: Final validation
  - UAT 重新运行
  - Phase 35b UAT 更新
  - Commit & merge

## Verification Commands

```bash
# Step 1: Check current state
python -c "
from uasset_read import parse_uasset
r = parse_uasset('E:/Develop/lib/UnrealEngine/.../BP_FirstPersonCharacter.uasset')
event_g = [g for g in r.graphs if g.graph_name == 'EventGraph'][0]
pins = [p for n in event_g.nodes for p in n.pins]
linked = [p for p in pins if getattr(p, 'linked_to_raw', [])]
print(f'linked_to_raw: {len(linked)}/{len(pins)} pins')
"

# Step 2: Run binary trace
python tools/binary_trace_pin.py \
  --asset tests/assets/BP_FirstPersonCharacter.uasset \
  --node-export-idx 40 \
  --pin-index 0

# Step 3: Run full test suite
pytest tests/ --tb=short -q
```

## Related Documentation

- **Phase 35b**: `.planning/phases/35b-pin-connection-debug/`
- **Related Issues**: AUDIT-REPORT.md FINDING-2/5
- **UE5 Source**: EdGraphPin.cpp L1838-1964

## Notes

- Phase 35e 取代 Phase 35b 的 35b-05 (Integration tests) 作为下一个计划
- Phase 35b 标记为 "部分完成"，linked_to_raw empty 作为已知限制
- Phase 35e 成功后，Phase 35b 可关闭

## Next Actions

1. **立即**: 开始 35e-01 (UE5 源码参考分析)
2. **完成**: 审查计划并批准执行

---

**Next Phase**: 35e (Pin Offset Debug)  
**Blocker**: Phase 35b (UAT failed - linked_to_raw empty)  
**Plan**: 35e-01 → 35e-02 → 35e-03 → 35e-04
