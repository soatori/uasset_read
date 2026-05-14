# Phase 35b-PLAN.md

**里程碑**: v6.0 模块化重构 — Pin 连接深度调试与修复  
**创建日期**: 2026-05-13  
**依赖**: Phase 35 (JSON 序列化与图解析修复)  
**状态**: 计划中  
**优先级**: P0 - 阻塞

---

## 🎯 目标

深入调试修复 pin linked_to_raw 为空的根因，恢复 execution_flows 和 data_flows 的连接数据构建能力。

---

## 📊 问题概述

### 核心问题

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| read_pin_array 返回空列表 (array_count=0) | pin 连接数据丢失 | 🔴 P0 |
| pins_offset 动态扫描定位不准确 | 后续字段位置错误 | 🔴 P0 |
| UE5 UEdGraphPin 序列化格式版本差异未覆盖 | 解析失败 | 🟠 P1 |
| FText 跳过逻辑影响后续字段位置 | 序列化偏移 | 🟠 P1 |
| execution_flows 和 data_flows 无法构建 | 图分析功能失效 | 🟡 P2 |

---

## ✅ 成功标准

1. ✅ read_pin_array 能正确读取 LinkedTo 数组 (array_count > 0)
2. ✅ pin.linked_to_raw 包含正确的连接引用
3. ✅ execution_flows 能追踪从 Event 到 CallFunction 的完整链路
4. ✅ data_flows 能提取非 exec pins 的数据传递关系
5. ✅ BP_FirstPersonCharacter.uasset 的 EventGraph 能输出完整执行链路
6. ✅ 全部现有测试通过 (397+ passed, 0 failed)

---

## 📋 Plan 35b 周计划

### Week 1: 调试环境与根因分析

#### Task 35b-01: 调试环境搭建

**输出**: 
- 二进制分析工具 `tools/bin_analyzer.py`
- DEBUG_PIN_PARSING 增强 (详细日志)
- BP_FirstPersonCharacter.uasset 二进制偏移表

**验收**:
- ✅ 能定位任意字段的二进制偏移
- ✅ 能打印字段的十六进制值
- ✅ 能解码 UE5 序列化格式

#### Task 35b-02: UE5 UEdGraphPin 序列化格式验证

**输出**:
- `reports/UE5_PinSerialization_Format.md`
- 序列化顺序验证报告
- 版本差异对照表

**验收**:
- ✅ 确认所有字段的序列化顺序
- ✅ 确认版本差异点
- ✅ 确认序列化atu控制字节

### Week 2: 修复实施

#### Task 35b-03: read_pin_array 修复

**输出**:
- `serializers/graph.py` read_pin_array() 修复
- array_count 正确读取逻辑
- 容错处理增强

**验收**:
- ✅ array_count > 0 (非空)
- ✅ linked_to_raw 包含连接引用
- ✅ 历史测试通过

#### Task 35b-04: FText 跳过逻辑修复

**输出**:
- `serializers/graph.py` read_ftext_with_history() 增强
- history_type=255 (0xFF) 支持
- 异常长度容错

**验收**:
- ✅ FText 正确跳过
- ✅ 后续字段位置正确
- ✅ 无偏移错误

#### Task 35b-05: pins_offset 动态扫描修复

**输出**:
- `serializers/graph.py` pins_offset 计算修复
- 基于已知节点类型的 heuristic fallback
- 偏移验证增强

**验收**:
- ✅ pins_offset 计算准确
- ✅ 后续字段位置正确
- ✅ 偏移验证通过

### Week 3: 验证与集成

#### Task 35b-06: execution_flows / data_flows 集成测试

**输出**:
- `reports/ExecutionFlows_Validation.md`
- BP_FirstPersonCharacter.uasset 验证报告
- 历史测试回归报告

**验收**:
- ✅ execution_flows 包含完整链路 (IA_Jump → Jump → StopJumping)
- ✅ data_flows 包含数据传递关系
- ✅ 历史测试通过

#### Task 35b-07: 全测试覆盖率

**输出**:
- `reports/TESTING_SUMMARY_35B.md`
- 411+ tests passed
- 零回归报告

**验收**:
- ✅ 411+ tests passed
- ✅ 0 failed
- ✅ 0 regression

---

## 🔧 调试方法

### 1. 二进制分析工具

```python
# tools/bin_analyzer.py
def analyze_pin_serialization(uasset_path, export_idx, node_idx):
    """分析指定节点的 pin 序列化数据"""
    # 读取节点的 serial_offset
    # 解析每个字段
    # 打印十六进制值
    # 验证序列化格式
```

### 2. DEBUG_PIN_PARSING 日志

```python
# serializers/graph.py
if DEBUG_PIN_PARSING:
    print(f"[PIN DEBUG] Reading pin at offset {archive.tell()}")
    print(f"[PIN DEBUG] Field: PinName, Value: {value}")
    print(f"[PIN DEBUG] Field: PinType, Offset: {archive.tell()}")
```

### 3. 手动二进制验证

```bash
# 使用 hexdump 或 Python 解析二进制
python tools/bin_analyzer.py BP_FirstPersonCharacter.uasset 35 5
```

---

## 📊 验收标准 (UAT)

| 测试项 | 期望结果 | 验证方法 |
|--------|----------|----------|
| parse BP_FirstPersonCharacter.uasset | pin.linked_to_raw 非空 | Python API 检查 |
| execution_flows | 包含 IA_Jump → Jump → StopJumping | 报告验证 |
| data_flows | 包含 ActionValue_X/Y 连接 | 报告验证 |
| pytest tests/test_graph_parsing.py | 全部通过 | pytest |
| pytest tests/test_property_parsing.py | 全部通过 | pytest |
| Phase 22 历史测试 | 之前失败的测试通过 | pytest |

---

## 📁 产出文件

### 代码变更
- `serializers/graph.py` - Pin 序列化修复
- `graph/flow_builder.py` - 流构建增强 (如果需要)

### 文档
- `reports/UE5_PinSerialization_Format.md` - 序列化格式报告
- `reports/ExecutionFlows_Validation.md` - 执行流验证报告
- `reports/TESTING_SUMMARY_35B.md` - 测试总结
- `reports/35B_FIXES.md` - 修复记录

### 工具
- `tools/bin_analyzer.py` - 二进制分析工具
- `tools/pin_debug_helper.py` - Pin 调试辅助脚本

---

## 🤝 依赖关系

```
Phase 35b (Pin 连接深度调试)
├── 依赖: Phase 35 (JSON 序列化与图解析修复)
├── 触发: Phase 35c (v6.0 里程碑完成)
├── 覆盖: Phase 22 历史测试
└── 验证: Phase 34 等价验证
```

---

## 📈 进度追踪

| Task | 状态 | 完成率 |
|------|------|--------|
| 35b-01 调试环境搭建 | 🔵 规划 | 0% |
| 35b-02 序列化格式验证 | 🔵 规划 | 0% |
| 35b-03 read_pin_array 修复 | 🔵 规划 | 0% |
| 35b-04 FText 跳过逻辑 | 🔵 规划 | 0% |
| 35b-05 pins_offset 修复 | 🔵 规划 | 0% |
| 35b-06 集成测试 | 🔵 规划 | 0% |
| 35b-07 全测试覆盖 | 🔵 规划 | 0% |

---

## 🎯 下一步行动

1. ✅ 创建 PLAN.md (本文件)
2. 🔶 开始 35b-01: 调试环境搭建
3. 🔶 实现二进制分析工具
4. 🔶 使用工具分析 BP_FirstPersonCharacter.uasset
5. 🔶 验证 pins_offset 计算逻辑

---

**计划创建时间**: 2026-05-13  
**估计完成时间**: 3 周  
**优先级**: P0 - 阻塞
