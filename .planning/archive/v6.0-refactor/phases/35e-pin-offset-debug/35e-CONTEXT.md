# Phase 35e: Pin Offset 根因诊断与 UE5 C++ 参考验证

**里程碑**: v6.0 模块化重构（深度修复）
**创建日期**: 2026-05-13
**依赖**: 无（继承自 Phase 35b 的成果和遗留问题）
**状态**: 活跃
**优先级**: P0 - 阻塞

## 来源

Phase 35e 继承了 Phase 35b（已跳过，合并至此）的修复成果和遗留问题：

### 已继承的修复（代码已合入）

| 修复 | 文件 | 提交 |
|------|------|------|
| read_bool_ue5() 方法 | `archive.py` | `b9839f2` |
| PinType bool 字段 1 字节修正 | `serializers/graph.py` | `7252a5e` |
| BitField u32 读取修正 | `serializers/graph.py` | `4302180` |
| FText b_has_culture UE5 修正 | `serializers/graph.py` | `4302180` |
| 二进制跟踪工具 | `tools/binary_trace_pin.py` | 35b-04 |
| 集成测试（部分通过） | `tests/test_ue5_pin_integration.py` | `4302180` |

### 已修复的字节漂移（共 ~12 字节）

| 字段 | 修正 | 字节数 |
|------|------|--------|
| bIsReference | 4→1 字节 | -3 |
| bIsWeakPointer | 4→1 字节 | -3 |
| bIsConst | 4→1 字节 | -3 |
| bIsUObjectWrapper | 4→1 字节 | -3 |
| BitField | 1→4 字节 | +3 |
| FText b_has_culture | 4→1 字节 | -3 |
| FText custom 8B skip | 新增 | +8 |
| **净变化** | | **+8 字节** |

### 遗留问题

应用所有 35b 修复后仍有约 **4 字节偏移**未解决：
- Direction → PinCategory FName 之间读到了垃圾值（`0x00FF0000`）
- linked_to_raw 仍为空（0/10 pins）
- execution_flows/data_flows 不完整

## 问题来源

Phase 35b 的 UAT 验证失败 + AUDIT-REPORT.md FINDING-2/5

## 根因假设

根据 UE5 源码（EdGraphPin.cpp L1838-1964）和 Phase 35b 的二进制分析：

1. **Direction 字段格式**：UE5 可能使用不同的字节标记（如 `ff`）或额外的 padding
2. **FName 对齐**：PinCategory FName 可能需要 4 字节对齐
3. **pins_offset 计算**：动态扫描逻辑未考虑某些 UE5 特定字段

## 可用工具

- `tools/binary_trace_pin.py` — 35b-04 创建的二进制跟踪工具
- DEBUG_PIN_PARSING 日志（在 `serializers/graph.py` 中）

## 成功标准

- 通过 UE5 EdGraphPin.cpp 源码确认精确的字段边界
- 二进制跟踪工具验证所有字段位置
- linked_to_raw 非空（至少 1 个 pins 有连接）
- execution_flows 和 data_flows 正确构建
- pytest tests/ 返回 397+ passed, 0 failed（或证明是已知问题）

## 范围边界

- ✅ 分析 UE5 EdGraphPin.cpp L1838-1964 序列化格式
- ✅ 定位 Direction/FName 之间的 4 字节偏移
- ✅ 修复 graph.py 中的 read_ue_graph_pin() 序列化逻辑
- ✅ 验证 linked_to_raw、execution_flows、data_flows
- ❌ 不修改 UE4 兼容逻辑（向后兼容）

## 计划分解

| Plan | 描述 | 文件 | 依赖 |
|------|------|------|------|
| 35e-01 | UE5 EdGraphPin.cpp 字段边界分析 | — | — |
| 35e-02 | 二进制跟踪工具增强与 pin body 映射 | `tools/binary_trace_pin.py` | 35e-01 |
| 35e-03 | Direction/FName 4 字节偏移修复 | `serializers/graph.py` | 35e-02 |
| 35e-04 | 集成测试验证 | `tests/` | 35e-03 |

## 参考

- Phase 35b 文档：`.planning/phases/35b-pin-connection-debug/`
- 35b-SKIP.md：合并说明
- 35b-SUMMARY.md：执行总结（含详细字节漂移分析）
- 35b-RESEARCH.md：研究笔记
