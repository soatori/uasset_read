---
phase: 72h
title: FString 容错 + LinkedTo 恢复 + StructValue JSON 递归序列化
goal: 修复 BP_FirstPersonCharacter 解析中的三个核心阻断问题：FString 内部 null 字节导致偏移错位、LinkedTo 数组 count 异常崩溃、StructValue 嵌套 dataclass JSON 序列化失败
requirements:
  - FSTR-01: FString 读取完成后指针始终处于正确位置
  - FSTR-02: 非法二进制数据被识别后指针不滞留于错误位置
  - LINK-01: LinkedTo 数组 count 异常时启动滑动恢复机制
  - JSON-01: StructValue/MapValue/SetValue 嵌套 dataclass 可正确递归序列化为 JSON
depends_on: [phase-72g]
type: fix
status: planned
created: 2026-05-23
---

# Phase 72-H: FString 容错 + LinkedTo 恢复 + StructValue JSON 递归序列化

## 背景

BP_FirstPersonCharacter.uasset 解析报告（`temp/BP_FirstPersonCharacter_Analysis_Report.md`）揭示了三个核心阻断问题：

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| 1 | FString 内部 null 字节 → 偏移错位 | 30+ 个 LinkedTo 读取失败 | 识别到二进制数据后返回 `""`，但 `length` 字段本身可能已错误 |
| 2 | LinkedTo 数组 count 异常（如 8352、16777216） | 全部 Pin 连接丢失 | 前面字段偏移错位导致读到错误 i32 |
| 3 | StructValue JSON 序列化崩溃 | `--json` 全量输出失败 | `asdict()` 不递归处理 dict 内的 dataclass |

**依赖链**：FString 错位 → LinkedTo count 异常 → Pin 连接丢失

## 修复策略

### Wave 1: StructValue JSON 递归序列化（独立，P1）

**文件**: `src/uasset_read/formatters/json_formatter.py` — `serialize_property_value()`

**改动**: 重写序列化逻辑，增加 `dict` 分支递归处理，使用 `isinstance()` 替代 `hasattr()` 检测。

**验收**:
- `json.dumps(format_json_full(result))` 不抛 `TypeError`
- 嵌套 3 层以上的 StructValue 正确输出

### Wave 2: FString 容错增强（P0 根因修复）

**文件**: `src/uasset_read/archive.py` — `read_fstring()`

**改动**:
1. 增加 `expected_bytes` 边界防卫，防止巨大错误 length 导致过度读取
2. 对异常 length 回退指针并抛 `ParseError`，而非继续读取
3. 检测内部 null 字节时，确保指针已消费正确字节数
4. 区分"合法内部 null（UTF-16 终止符）"与"非法二进制数据"

**关键约束**: 必须使用 FArchive 流式读取，禁止 raw byte seek+read（遵守 no-byte-reading feedback）

**验收**:
- 20+ 个之前报 `FString contains internal null bytes` 的位置不再触发崩溃
- 每次调用后 `archive.tell()` 位置正确（基于 length 字段 + 终止符）

### Wave 3: LinkedTo 滑动恢复机制（P2 补救）

**文件**: `src/uasset_read/serializers/graph.py` — `read_pin_array()`

**改动**:
1. 在 `read_pin_array()` 中增加 recovery 路径：当 `array_count` 超出合理范围时
2. 在 ±8 字节范围内扫描寻找合法 i32 count（0 ≤ count ≤ 20）
3. 验证候选 count 后的第一个 Pin reference 结构是否合理
4. 恢复失败时返回空数组（不阻断后续解析）

**验收**:
- BP_FirstPersonCharacter.uasset 解析完成后，LinkedTo 错误数显著减少
- 恢复机制不引入新的误恢复（不会将合法的非-zero count 误判为异常）

## 验收标准

| ID | 标准 | 验证方式 |
|----|------|----------|
| 72H-01 | `uasset-read BP_FirstPersonCharacter.uasset --json` 不抛 `TypeError` | CLI 运行 |
| 72H-02 | 无 `LinkedTo read failed` 错误（或仅有 recovery 日志） | 日志检查 |
| 72H-03 | JSON 输出包含非空 connections | 输出验证 |
| 72H-04 | 全量测试无回归（≥ 1339 tests pass） | `pytest tests/ -v` |
| 72H-05 | 新增测试覆盖 3 个修复点 | `pytest tests/test_phase72h_*.py -v` |

## 风险分析

| 风险 | 概率 | 缓解 |
|------|------|------|
| FString 容错过度保守，误判合法字符串 | 中 | 保留原有 `errors='replace'` 解码路径 |
| LinkedTo 恢复机制引入误恢复 | 中 | 双重验证（count 合理性 + Pin reference 结构验证） |
| Wave 2 修改 archive.py 影响全局解析 | 低 | 只修改 `read_fstring` 一个方法，全量回归测试 |
