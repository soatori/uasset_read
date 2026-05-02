# Phase 6: 导出表修复 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 06-export-table-fix
**Areas discussed:** TemplateIndex版本阈值, OuterIndex bug表现, 错误上下文增强, UE4/UE5结构差异, 修复范围, 依赖数组处理, 测试验证

---

## TemplateIndex 版本阈值

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 UE4 >= 506 | UE4 文件（legacy > -8）且 file_version_ue4 >= 506 时读取。UE5 文件是否总是读取？ | |
| UE4 >= 506 + UE5 | 所有 UE5 文件也读取 TemplateIndex（因为 UE5 版本总是 >= 506） | |
| 仅 cooked 文件 | 仅 cooked 文件读取（根据注释"only used in the new cooked loader"） | |

**User's choice:** 评估 → 最终选择：统一检查 file_version_ue4 >= 506
**Notes:** FPackageFileVersion.operator>= 仅比较 FileVersionUE4。UE5 文件也有 FileVersionUE4（约 522），自动满足条件。

---

## OuterIndex Bug 表现

| Option | Description | Selected |
|--------|-------------|----------|
| 偏移错位 | 缺少 TemplateIndex 导致 OuterIndex 实际读取的是 TemplateIndex 的值 | |
| OuterIndex 正确 | OuterIndex 读取正确，但 TemplateIndex 缺失影响其他功能 | |
| 不确定，需测试 | 需要实际测试文件来确认 bug 表现 | ✓ |

**User's choice:** 不确定，需测试
**Notes:** 用户希望通过测试验证 bug 表现。

---

## TemplateIndex 条件（第二轮）

| Option | Description | Selected |
|--------|-------------|----------|
| 统一检查 file_version_ue4 >= 506 | 简单直接：所有文件检查 file_version_ue4 >= 506。UE5 文件的 UE4 版本通常 >= 522，自动满足条件 | Recommended |
| 区分 UE4/UE5 | 区分文件类型：UE4 文件检查 >= 506，UE5 文件单独检查（可能用 UE5 版本阈值） | |
| 仅 UE4 文件 | 仅 UE4 文件读取，UE5 文件跳过 TemplateIndex。与 ObjectResource.cpp 一致但可能不符合 UE5 实际 | |

**User's choice:** 评估 → 最终决策：统一检查 file_version_ue4 >= 506
**Notes:** 基于 FPackageFileVersion 的 operator>= 实现，UE4 版本检查适用于所有文件。

---

## 错误上下文增强（BUG-03）

| Option | Description | Selected |
|--------|-------------|----------|
| 导出表解析阶段 | 导出表解析阶段的错误包含：当前导出索引、期望偏移、实际偏移 | ✓ |
| 版本检查失败 | TemplateIndex 条件读取失败时记录：版本号、阈值 | ✓ |
| 偏移验证失败 | 偏移错位时记录：字段名、期望位置、实际位置 | ✓ |

**User's choice:** 全选
**Notes:** 用户希望全面的错误上下文信息。

---

## 修复范围

| Option | Description | Selected |
|--------|-------------|----------|
| 最小修复：仅 TemplateIndex + 错误上下文 | 仅修复 TemplateIndex 缺失（BUG-01/02/03）。其他字段推迟到后续阶段 | Recommended |
| 完整修复：所有缺失字段 | 完整实现所有缺失字段（bool flags, PackageGuid, 依赖数组等） | ✓ |
| 中等修复：TemplateIndex + 基本字段 | 修复 TemplateIndex + bool flags（9-11）+ PackageFlags，其他推迟 | |

**User's choice:** 完整修复：所有缺失字段
**Notes:** 用户明确选择完整实现 FObjectExport 结构。

---

## 依赖数组处理

| Option | Description | Selected |
|--------|-------------|----------|
| 读取但不解析 | 读取依赖数组字段（FirstExportDependency + 4 个数组），但不解析内容，仅记录偏移和数量 | Recommended |
| 完整解析 | 完整解析依赖数组结构（需要理解 FExportDependency 信息） | |
| 跳过，推迟到 Phase 10 | 跳过依赖数组，推迟到 Phase 10（依赖分析阶段） | ✓ |

**User's choice:** 跳过，推迟到 Phase 10
**Notes:** 依赖数组与 Phase 10 的依赖图功能直接相关。

---

## 测试验证

| Option | Description | Selected |
|--------|-------------|----------|
| OuterIndex 值对比 | 对比修复前后 OuterIndex 值，确认偏移错位已修复 | ✓ |
| TemplateIndex 非零验证 | 检查 TemplateIndex 是否正确读取（非零值表示成功） | ✓ |
| UE 编辑器文件验证 | 使用 UE 编辑器导出的文件进行验证 | ✓ |
| Lyra 资产对比 | 对比 Lyra 资产修复前后 JSON 输出 | ✓ |

**User's choice:** 全选
**Notes:** 多角度验证确保修复正确性。

---

## Claude's Discretion

- 版本常量命名（VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 506）
- bool flags 的 Python 命名风格（b_forced_export vs bForcedExport）
- 条件字段的默认值选择
- 错误消息格式和详细程度
- 单元测试组织

## Deferred Ideas

推迟到 Phase 10：
- FirstExportDependency 字段解析
- 4 个依赖数组解析（SerializationBeforeSerializationDependencies, CreateBeforeSerializationDependencies, SerializationBeforeCreateDependencies, CreateBeforeCreateDependencies）

推迟到 v3：
- 导出表哈希验证
- 导出条目完整性检查