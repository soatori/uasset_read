---
phase: 01-core-parsing
plan: 02
status: completed_with_notes
date: 2026-04-28
---

# Phase 1 Gap Closure Summary

## 完成工作

### Bug 修复

1. **UE5_VERSION_MIN 修复**
   - 原：1000（拒绝真实 UE5 文件）
   - 改：0（接受版本 521-522）

2. **LegacyUE3Version 字段**
   - 添加字段读取（仅 legacy != -4）
   - 添加到 PackageFileSummary dataclass
   - 修正构造函数传参

3. **条件方向修复**
   - 原：`if legacy >= -8`（错误）
   - 改：`if legacy <= -8`（正确，参考 UE 源码 line 139）

4. **Python dataclass 字段顺序**
   - 无默认值字段必须在有默认值字段之前

5. **Inline 名称处理**
   - legacy < -5: NameCount + inline names（无 NameOffset）
   - legacy >= -5: NameCount + NameOffset（标准格式）
   - 添加 inline 名称跳过逻辑

### 测试结果

- **合成测试：** 13/13 通过 ✓
- **Lyra 真实文件：** 解析失败（已知限制）

## 已知限制

Lyra Character_Default.uasset (legacy=-7) 失败原因：
- Pos 212 的 NameOffset 值为 1701736270（ASCII "None")
- 表明文件使用 inline names，但 legacy=-7 >= -5
- UE 文件格式可能存在其他变体，需要额外研究

## 技术总结

| 问题 | 根因 | 解决 |
|------|------|------|
| UE5Version 拒绝 | 硬编码最小版本 | 改为 0 |
| name_offset 错位 | 缺少 LegacyUE3Version | 添加字段读取 |
| 条件判断错误 | 方向反了 | <= 替代 >= |
| 测试数据错误 | helper 格式不匹配 | 修正 inline/标准切换 |

## 后续建议

Phase 1 核心解析器已完成（合成测试通过）。真实文件兼容性问题可在 Phase 5 优化阶段处理，或作为单独研究任务。

---

*完成日期: 2026-04-28*