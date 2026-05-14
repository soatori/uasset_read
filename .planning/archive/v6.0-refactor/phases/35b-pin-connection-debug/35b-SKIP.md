---
phase: "35b"
status: skipped
merged_into: "35e"
merged_into_path: "../35e-pin-offset-debug/"
date: "2026-05-13"
reason: "35b 修复了约 12 字节偏移但 linked_to_raw 仍为空，剩余约 4 字节的 pin offset 根因问题需要 UE5 C++ 源码参考才能解决，因此合并至 Phase 35e 继续"
---

# Phase 35b — 已跳过（合并至 Phase 35e）

## 成果已合入代码库

| Plan | 内容 | 提交 |
|------|------|------|
| 35b-01 | read_bool_ue5() + PinType bool 修复 | `b9839f2`, `7252a5e`, `a110f9e` |
| 35b-02 | BitField u32 修复 | `4302180` |
| 35b-03 | FText b_has_culture 修复 | `4302180` |
| 35b-04 | 二进制跟踪工具 `tools/binary_trace_pin.py` | 已创建 |
| 35b-05 | 集成测试（部分通过） | `4302180` |

## 遗留问题（由 Phase 35e 负责）

- **4 字节偏移**：Direction → PinCategory FName 之间的未知偏移
- **linked_to_raw 为空**：0/10 pins 有连接数据
- **execution_flows/data_flows 不完整**

## 引用

- 35b-PLAN.md — 原始计划文档
- 35b-SUMMARY.md — 执行总结（含字节漂移分析表）
- 35b-RESEARCH.md — 研究笔记
- 35b-VALIDATION.md — 验证记录
- 35b-UAT.md — 用户验收测试
