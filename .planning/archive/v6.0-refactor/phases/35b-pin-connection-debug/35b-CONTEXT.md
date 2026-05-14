# Phase 35b: Pin 连接深度调试与修复

**里程碑**: v6.0 模块化重构（深度修复）
**创建日期**: 2026-05-12
**依赖**: Phase 35 (JSON 序列化与图解析修复)
**状态**: 规划中

## 一句话摘要

深入调试修复 pin linked_to_raw 为空的根因，恢复 execution_flows 和 data_flows 的连接数据构建能力。

## 问题来源

AUDIT-REPORT.md FINDING-2/5 + Phase 22 VERIFICATION.md + Phase 35 UAT Test 3

## 问题清单

| # | 优先级 | 问题 | 影响模块 | 严重程度 |
|---|--------|------|----------|----------|
| 1 | P0 | read_pin_array 返回空列表 (array_count=0) | serializers/graph.py | 🔴 阻塞 |
| 2 | P0 | pins_offset 动态扫描定位不准确 | serializers/graph.py | 🔴 阻塞 |
| 3 | P1 | UE5 UEdGraphPin 序列化格式版本差异未覆盖 | serializers/graph.py | 🟠 严重 |
| 4 | P1 | FText 跳过逻辑影响后续字段位置 | serializers/graph.py | 🟠 严重 |
| 5 | P2 | execution_flows 和 data_flows 无法构建（pin 连接缺失的连锁反应） | graph/flow_builder.py | 🟡 中等 |

## 根因分析（来自 Phase 22 验证）

Phase 22 验证报告明确指出：

1. **read_pin_array 返回空列表**：`uasset_read.py:3086` — array_count 始终为 0，表明 archive 位置错误或数据格式不匹配
2. **pins_offset 动态扫描问题**：`uasset_read.py:3213-3267` — 动态扫描找到的位置可能不准确，导致后续字段（包括 LinkedTo）读取位置偏移
3. **FText 处理问题**：history_type=255 的 FText 处理逻辑可能影响后续字段位置
4. **序列化格式理解不完整**：UE 5.7 的 UEdGraphPin 序列化格式可能存在版本特定的变化

## 成功标准

1. read_pin_array 能正确读取 LinkedTo 数组（array_count > 0）
2. pin.linked_to_raw 包含正确的连接引用
3. execution_flows 能追踪从 Event 到 CallFunction 的完整链路
4. data_flows 能提取非 exec pins 的数据传递关系
5. BP_FirstPersonCharacter.uasset 的 EventGraph 能输出 IA_Jump → Jump → StopJumping 执行链路
6. 全部现有测试通过（397+ passed, 0 failed），无回归

## 范围边界

- ✅ 修复 UE5 UEdGraphPin 序列化格式解析
- ✅ 修复 pins_offset 计算逻辑
- ✅ 修复 FText 跳过逻辑
- ✅ 恢复 linked_to_raw / execution_flows / data_flows 数据
- ❌ 不解析 BulkData 内容（v7.0 范围）
- ❌ 不解析字节码/Ubergraph 增强（v8.0 范围）

## 验收标准 (UAT)

| 测试项 | 期望结果 |
|--------|----------|
| parse BP_FirstPersonCharacter.uasset | pin.linked_to_raw 非空，包含连接引用 |
| execution_flows | 包含 IA_Jump → Jump → StopJumping 链路 |
| data_flows | 包含 ActionValue_X/Y 连接 |
| pytest tests/ | 397+ passed, 0 failed |
| Phase 22 历史测试 | 之前失败的 test_phase21_verification.py 全部通过 |

## 调试方法

1. 使用 DEBUG_PIN_PARSING 标志运行解析，详细记录每个字段的读取位置和值
2. 对比 UE 源码（UObject/EdGraph/EdGraphNode/EdGraphPin 序列化）验证序列化顺序
3. 手动分析 .uasset 二进制数据，验证 pins_offset、PinName、FText、PinToolTip、Direction、PinType、LinkedTo 的正确位置
4. 实现基于已知节点类型的 heuristic pins_offset 计算作为 fallback

## 计划分解

| Plan | 内容 |
|------|------|
| 35b-01 | 调试环境搭建：二进制分析工具 + DEBUG_PIN_PARSING 增强 |
| 35b-02 | read_ue_graph_pin 字段序列化顺序验证与修复 |
| 35b-03 | read_pin_array 修复：array_count 正确读取 |
| 35b-04 | FText 跳过逻辑修复 |
| 35b-05 | execution_flows / data_flows 集成测试验证 |
