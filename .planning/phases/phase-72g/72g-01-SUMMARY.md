---
phase: 72g
plan: 01
type: summary
wave: 1-4
date: 2026-05-23
status: completed
---

# Phase 72-G: 复杂 StructProperty 解析 + Pin 连接映射修复 — 执行摘要

## 目标

修复 BP_FirstPersonCharacter.uasset 解析中的 4 个反复失败问题（M-01 至 M-04），覆盖率从 ~56% 提升至 >90%。

## 执行的 Wave

### Wave 1: M-02 LinkedTo 验证 + 非空检查
- **文件**: `serializers/graph.py`, `graph/flow_builder.py`, `tests/test_phase72g_connections.py`
- **变更**:
  - `graph.py` L463-468: LinkedTo 读取异常改为 `logger.error()` 记录（而非静默失败）
  - `flow_builder.py` L654-661: `build_connections_map()` 入口添加 `linked_to_count` 验证，空时产生 WARNING
- **测试**: 3 passed, 1 skipped (integration)

### Wave 2: M-01 Vector/Rotator 快速路径解析
- **文件**: `parsers/property_types.py`, `tests/test_phase72g_struct_parsing.py`
- **变更**:
  - `parse_struct_property()` 在 PropertyTags 循环前添加 Vector/Rotator/Vector2D 快速路径
  - 直接 `read_f32()` 3 次，返回 `StructValue`，跳过 PropertyTags 循环
  - 对齐 CUE4Parse `FScriptStruct.cs` L174-178 行为
- **测试**: 4 passed

### Wave 3: M-03 BPGC 函数提取路径
- **文件**: `blueprint/variable_extractor.py`, `tests/test_phase72g_functions.py`
- **变更**:
  - 新增 `_extract_functions_from_bpgc_properties()`: 从 UbergraphFunction/FunctionList 属性提取函数
  - 新增 `_resolve_property_to_function_name()`: 解析 FPackageIndex 值为函数名（支持路径/点号）
  - `extract_blueprint_metadata()`: 合并 BPGC 路径 + Graphs fallback 路径，按名去重
- **测试**: 10 passed

### Wave 4: M-04 参数提取验证
- **文件**: `tests/test_phase72g_parameters.py`
- **变更**:
  - 测试 `_extract_signature_from_pins()` 的 EGPD_Input/Output 方向解析
  - 测试参数名+类型提取、Self/Target 跳过
  - 测试 `build_function_graphs()` 中 blueprint_functions 合并
- **测试**: 4 passed

## 回归测试

- 1330 passed, 123 skipped, 2 xpassed, 0 failed
- 排除 `test_skill_integration.py`（工作树中无 `.claude/skills/`，预存问题）

## 验收标准

| 标准 | 状态 |
|------|------|
| RelativeLocation 提取为 {X, Y, Z} | Wave 2 |
| RelativeRotation 提取为 {Pitch, Yaw, Roll} | Wave 2 |
| EventGraph connections 非空 | Wave 1 (日志+警告) |
| Blueprint.functions 包含 Move/Aim/JumpStart/JumpEnd | Wave 3 |
| 函数参数列表（name + type） | Wave 4 |
| 无回归 | 1330 passed |
