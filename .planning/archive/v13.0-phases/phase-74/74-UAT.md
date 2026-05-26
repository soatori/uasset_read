---
status: complete
phase: 74-pin-reference-layout
source: [test_phase74_pin_reference_layout.py]
started: "2026-05-26T00:00:00Z"
updated: "2026-05-26T16:30:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. Null PinReference 消费 4 字节
expected: null PinReference 应只消费 4 字节 bool，archive 位置应在 4。测试使用 bool=1 (null) + 32 字节填充，验证 archive.tell() == 4
result: pass

### 2. Non-null PinReference 消费 24 字节
expected: non-null PinReference 应消费 24 字节 (bool + OwningNode + PinGuid)，验证返回结果包含 owning_node 和 pin_guid，archive 位置在 24
result: pass

### 3. validate_pin_reference_at 支持 4 字节 null
expected: validate_pin_reference_at() 对 null 引用应返回有效结构，serialized_size 应为 4，且不移动 archive 位置
result: pass

### 4. PinArray null 元素不吞没下一个元素
expected: PinArray 中的 null 元素不应导致后续元素读取失败。测试包含 null (bool=1) + valid 元素，验证返回数组包含 1 个有效元素
result: pass

### 5. Owning Pin Body 从 PinName 开始
expected: 提供 header_owning_node 和 header_pin_id 时，read_ue_graph_pin() 应正确识别 PinName 位置，解析出 pin_name == "execute"
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]

---

*UAT Complete: Phase 74*
*Total: 5 passed* 
*Full test suite: 1435 passed, 0 regressions*
