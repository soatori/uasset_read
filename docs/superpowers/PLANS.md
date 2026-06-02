# uasset_read 开发计划汇总

> **For agentic workers:** 本文档汇总所有活跃和已完成的开发计划。每个计划的状态、进度和下一步行动已在此标明。

**更新日期**: 2026-06-02
**当前分支**: 0.3.8-dev (v0.3.8-dev)

---

## 计划状态总览

| # | 计划 | 状态 | 优先级 | 创建日期 | 说明 |
|---|------|------|--------|----------|------|
| 1 | [真实案例测试套件](#1-真实案例测试套件-design-2026-06-01) | ✅ 已实现 | — | 2026-06-01 | 5 个集成测试文件已创建并通过 |
| 2 | [N2C 模块剩余问题](#2-n2c-模块剩余问题-n2c-remaining) | ✅ 已完成 | 中 | 2026-06-02 | 单例改依赖注入 + 核心节点处理器 57 种 |
| 3 | [Blueprint VarGuid 解析修复](#3-blueprint-varguid-解析修复-fix-varguid) | ✅ 已完成 | 高 | 2026-06-02 | 2 个集成测试修复通过 + 7 个单元测试 |
| 4 | [UE 格式文档同步](#4-ue-格式文档同步-uasset-format) | 🟢 进行中 | 低 | — | docs/uasset-format/ 60+ 篇格式文档 |

---

## 1. 真实案例测试套件 (design-2026-06-01)

**状态**: ✅ 已实现
**原始文档**: `docs/superpowers/specs/2026-06-01-real-asset-test-suite-design.md`

### 实现结果

5 个测试文件全部已创建并运行：

| 文件 | 用例数 | 状态 |
|------|--------|------|
| `tests/test_real_asset_coverage.py` | 400+ | ✅ 通过 |
| `tests/test_engine_content.py` | 48 | ✅ 通过 |
| `tests/test_known_failures.py` | 回归测试 | ✅ 通过（xfail 正确标记） |
| `tests/test_formatter_outputs.py` | 6×7=42 | ✅ 通过 |
| `tests/test_asset_type_depth.py` | 6 类型 | ✅ 通过 |

### 下一步

无需操作。

---

## 2. N2C 模块剩余问题 (n2c-remaining)

**状态**: ✅ 已完成
**原始文档**: `docs/superpowers/plans/2026-06-02-n2c-remaining.md`

### Task 1: 单例模式改为依赖注入 ✅ 已完成

**实现结果**：
- `N2CProcessorRegistry` — 删除 `_instance`、`get_instance()`、`reset()`，新增 `get_registry()` + `reset_registry()`
- `N2CNodeTypeRegistry` — 删除 `_instance`、`get_instance()`、`reset()`，新增 `get_type_registry()` + `reset_type_registry()`
- 所有调用方已更新：`n2c/serializer.py`、`n2c/processors/__init__.py`、`graph/flow_builder.py`
- `n2c/__init__.py` 导出新 API

### Task 2: 补充核心节点处理器 ✅ 已完成

**实现结果**：专用处理器从 ~20 种提升到 57 种（覆盖率从 ~24% 到 ~45%）

| 模块 | 操作 | 覆盖类型 |
|------|------|----------|
| `flow_control.py` | 扩展 | MultiGate, DoOnce, Select, EaseFunction, ForEachEnum, MapForEach, SetForEach |
| `struct_ops.py` | 新建 | MakeStruct, BreakStruct, MakeArray, MakeMap, MakeSet |
| `variable_ops.py` | 新建 | LocalVariable, StructMemberGet, StructMemberSet, SetFieldsInStruct, CreateDelegate, ClearDelegate, RemoveDelegate, DelegateSet |
| `utilities.py` | 新建 | AsyncAction, Timeline, FormatText, MathExpression, GetEnumeratorName, GetEnumeratorNameAsString, GetNumEnumEntries, EnumEquality, EnumInequality |

### 下一步

无需操作。

---

## 3. Blueprint VarGuid 解析修复 (fix-varguid)

**状态**: ✅ 已完成
**原始文档**: `docs/superpowers/plans/2026-06-02-fix-blueprint-var-guid.md`

### 根因分析（实际修复时发现）

原计划诊断的根因（`_guid_from_description` 不处理 `StructValue`）正确但不充分。实际根因链：

1. `ArrayProperty` 内层为 `StructProperty` 时，`inner_tag` 不携带 `struct_type`
2. `_extract_struct_type_from_tag` 返回 `"UnknownStruct"`
3. `tag.size=0` 触发 opaque 短路返回
4. `_extract_blueprint_variable_descriptions` 无法从空 fields 提取 VarGuid

### 修复方案（5 个文件联动）

| 文件 | 修改 |
|------|------|
| `serializers/property_tags.py` | `_apply_property_type_to_tag` 提取 `inner_type_struct`（ArrayProperty 内层 StructProperty） |
| `parsers/property_parser.py` | `_apply_mapping_type_to_tag` 设置 `tag.inner_type_struct` |
| `models/properties.py` | `PropertyTag` 新增 `inner_type_struct` 字段 |
| `parsers/property_types.py` | `parse_array_property` 传递 `struct_type` 给 inner tag；`_TAGGED_FALLBACK_STRUCTS` 添加 BP struct 名 |
| `blueprint/variable_extractor.py` | `_guid_from_description` 支持 `StructValue(Guid, {A,B,C,D})` |

### 验证结果

- ✅ 7 个单元测试通过
- ✅ 2 个失败集成测试通过
- ✅ 完整测试套件 218 passed, 2 xfailed, 0 failures

### 变更文件

- `tests/test_variable_extractor.py`（新增 7 个单元测试）
- `src/uasset_read/blueprint/variable_extractor.py`
- `src/uasset_read/serializers/property_tags.py`
- `src/uasset_read/parsers/property_parser.py`
- `src/uasset_read/parsers/property_types.py`
- `src/uasset_read/models/properties.py`

---

## 4. UE 格式文档同步 (uasset-format)

**状态**: 🟢 进行中
**位置**: `docs/uasset-format/`

60+ 篇 Markdown 文件，覆盖：
- 资产类型（Animation, Audio, Blueprint, Level, Material, SkeletalMesh, StaticMesh, Texture, Widget, Particle）
- 序列化（BulkData, LinkerLoad/Save, PropertyTag, Version Compatibility）
- Cooked 格式（Cooked vs Uncooked, IoStore, Pak）
- 版本演进（Asset 版本, UE4/UE5 演进, Migration Guide）

这些文档为参考性资料，不涉及代码变更。

---

## 执行优先级

| 优先级 | 计划 | 理由 |
|--------|------|------|
| **P0** | ~~计划 3. VarGuid 修复~~ | ✅ 已完成 |
| **P1** | ~~计划 2. N2C 依赖注入~~ | ✅ 已完成 |
| **P2** | ~~计划 2. N2C 处理器补充~~ | ✅ 已完成 |
| **P3** | 待分配 | 等待新任务 |

---

## 计划自审

### 完整性检查
- [x] 所有 docs/superpowers/ 下的计划已纳入汇总
- [x] 计划 3 已完成（2 个集成测试修复，7 个单元测试通过）
- [x] 计划 2 已完成（N2C 单例重构 + 57 种处理器）
- [x] 测试套件：218 passed, 2 xfailed, 0 failures

### 下一步建议

所有代码计划已完成。文档同步（计划 4）为参考性资料，可按需更新。等待新任务分配。
