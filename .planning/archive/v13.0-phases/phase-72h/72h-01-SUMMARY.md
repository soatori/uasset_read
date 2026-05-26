---
phase: 72h
plan: 01
type: summary
wave: 1-3
date: 2026-05-23
status: completed
---

# Phase 72-H: FString 容错 + LinkedTo 恢复 + StructValue JSON 递归序列化 — 执行摘要

## 目标

修复 BP_FirstPersonCharacter 解析中的三个核心阻断问题。

## 执行的 Wave

### Wave 1: StructValue JSON 递归序列化（P1）
- **文件**: `formatters/json_formatter.py` — `serialize_property_value()`
- **变更**:
  - `dict`/`list` 提前分支，递归处理内部值
  - `hasattr()` → `isinstance()` 使用具体类型检测
  - `asdict()` fallback 改为递归调用 `serialize_property_value`
- **测试**: 14 passed (`test_phase72h_json_serialization.py`)

### Wave 2: FString 根因诊断 + 防御增强（P0）
- **文件**: `archive.py` — `read_fstring()`
- **变更**:
  - 增加 `suspicious length` warning（abs(length) > MAX_FSTRING_LENGTH）
  - 内部 null 日志升级为详细诊断：length, encoding, null count, preview, hex, consumed bytes, end_pos
  - 保持 tolerant 模式：检测到内部 null 返回空字符串，指针始终正确消费
- **测试**: 9 passed (`test_phase72h_fstring_defense.py`)

### Wave 3: LinkedTo 日志增强（P2 降级）
- **文件**: `serializers/graph.py` — `read_pin_array()`
- **变更**:
  - 错误消息增加位置信息（`at pos X`）
  - 采用保守策略：异常 count 抛 ParseError，不尝试滑动恢复
  - 保持现有 `read_ue_graph_pin` L466-468 try/except 模式
- **测试**: 6 passed (`test_phase72h_linkedto_logging.py`)

## 回归测试

- 1359 passed, 123 skipped, 2 xpassed, 0 failed
- 排除 `test_skill_integration.py`（预存问题）和 `test_full_regression.py`（subprocess 递归）

## 验收标准

| 标准 | 状态 |
|------|------|
| json.dumps(format_json_full(result)) 不抛 TypeError | Wave 1 ✅ |
| 嵌套 3 层以上 StructValue 正确输出 | Wave 1 ✅ |
| FString 异常 length 记录 warning | Wave 2 ✅ |
| 内部 null 日志包含详细诊断信息 | Wave 2 ✅ |
| 每次 read_fstring 后 tell() 位置正确 | Wave 2 ✅ |
| LinkedTo 错误消息包含位置信息 | Wave 3 ✅ |
| 无回归 | 1359 passed ✅ |
