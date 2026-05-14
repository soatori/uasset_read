# 路线图 — v7.0（规划中）

**v6.0** ✅ 373 passed, 0 failed | [历史归档](archive/v6.0-refactor/ARCHIVE-INDEX.md)

## v7.0 Phase 分解

| Phase | 名称 | 目标 | 状态 |
|-------|------|------|------|
| 41 | link/ 模块 | UObjectInstance, PackageLinker, LinkerParseResult | ✅ 完成 |
| 42 | 集成入口 | parse_uasset_with_linker() | ✅ 完成 |
| 43 | PackageIndex | resolve_with_linker() | ✅ 完成 |
| 44 | 模型增强 | UEdGraphPin linked_to_objects | ✅ 完成 |
| 44a | 移除旧版本兼容代码 | 删除UE4/旧版本条件分支和常量 | ⏳ 待执行 |
| 44b | 替换直接字节读取 | 消除struct.unpack，统一使用FArchive方法 | ⏳ 待执行 |
| 44c | 清理测试工具 | 删除废弃测试和调试脚本 | ⏳ 待执行 |
| 45 | 图序列化 | from_archive_with_linker() 方法 + default_object_ref | ✅ 完成 |
| 46 | 测试验证 | 373 测试 0 回归 | ⏳ 待执行 |

**核心改变**: PackageIndex → UObjectInstance 实际引用，构建 Outer 对象树

### Phase 44a: 移除旧版本兼容代码 ⏳

**Goal:** 删除所有 UE4/旧版本兼容路径，仅保留 UE5 当前版本支持。

**涉及文件:**
- `src/uasset_read/constants.py` — 删除 UE4 版本常量
- `src/uasset_read/serializers/package_summary.py` — 删除 `is_ue4_file` 分支和 UE4 条件读取
- `src/uasset_read/serializers/object_resources.py` — 删除 UE4 版本条件分支
- `src/uasset_read/serializers/property_tags.py` — 删除 UE4 格式路径
- `src/uasset_read/serializers/graph.py` — 删除 UE4 FEdGraphPinType 序列化路径
- `src/uasset_read/parsers/property_parser.py` — 删除 UE4 版本条件
- `src/uasset_read/archive.py` — 删除 `read_bool()` UE4 路径
- `src/uasset_read/formatters/json_formatter.py` — 删除 legacy_version 输出
- 相关测试 fixtures 更新

**验证:** `grep -rn 'is_ue4_file\|UE4_\|legacy_file_version >' src/` 返回 0 结果

### Phase 44b: 替换直接字节读取 ⏳

**Goal:** 消除所有绕过 FArchive 的直接 struct.unpack 调用。

**涉及文件:**
- `src/uasset_read/parsers/property_types.py` — Int16 读取改用 FArchive 方法
- `src/uasset_read/serializers/graph.py` — 颜色分量读取改用 `archive.read_f32()`
- `src/uasset_read/archive.py` — 添加 `read_i16()` 方法

**验证:** `grep -rn 'struct.unpack' src/` 仅返回 archive.py 内部实现

### Phase 44c: 清理测试工具 ⏳

**Goal:** 清空所有废弃/调试测试文件。

**删除:**
- `tests/test_property_parsing.py` — DEPRECATED (已跳过整个模块)
- `tools/` 下全部调试脚本
- `temp/` 下全部调试文件

**验证:** `tools/` 和 `temp/` 目录为空，所有测试通过

### Phase 45: 图序列化 linker 变体 ✅

**Goal:** 为 UEdGraph/UEdGraphNode/UEdGraphPin 创建 from_archive_with_linker() 入口方法

**Requirements:** LINK-05

**Plans:** 1 plan

Plans:
- [x] 045-01-PLAN.md — 创建 from_archive_with_linker() 方法 + default_object_ref 字段 + 基本验证测试

**Status:** UAT passed (8/8 tests)

**Test Results:**
- `UEdGraphPin.from_archive_with_linker()`: ✅
- `UEdGraphNode.from_archive_with_linker()`: ✅
- `UEdGraph.from_archive_with_linker()`: ✅
- `default_object_ref` field: ✅
- `default_object` linker resolution: ✅
- Backward compatibility: ✅
- Regression testing: ✅ (450 passed, 10 pre-existing failures)

### 阶段 45 过渡条件

阶段 45 开始前必须满足（44a→44b→44c 全部完成后）：

| # | 条件 | 验证方法 |
|---|------|----------|
| 1 | 不存在直接字节读取代码 | `grep -r 'struct.unpack' src/` 返回 0 结果（除 archive.py） |
| 2 | 不存在兼容其他版本的代码 | `grep -r 'is_ue4_file\|UE4_\|legacy_file_version >' src/` 返回 0 结果 |
| 3 | 清空测试工具 | `tools/` 和 `temp/` 目录为空 |
| 4 | 可用 BP_FirstPersonCharacter.uasset 完整解析 | `uasset-read` 成功执行并输出结构化结果 |

*Updated: 2026-05-14*
