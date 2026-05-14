# Phase 43: PackageIndex 增强 — CONTEXT.md

**Date:** 2026-05-14
**Phase:** 043-packageindex-enhance
**Goal:** 实现 `resolve_with_linker()` — 将 PackageIndex 解析从字符串/dict 引用全面升级为通过 linker 返回 `UObjectInstance` 实际引用。

---

## Domain

Phase 43 位于 v7.0 里程碑的中间位置。Phase 41 提供了 `link/` 模块（`PackageLinker`、`UObjectInstance`），Phase 42 提供了 `parse_uasset_with_linker()` 入口。本 phase 将 `object_resources.py` 中所有旧的 PackageIndex 解析函数替换为 linker 版本，消除 dict 返回路径。

## Decisions

### 迁移策略 — 全面替换

用户选择**全面替换**所有旧的 dict 返回函数，而非新旧并存或渐进迁移。这意味着：
- 不保留兼容性 shim
- 不标记 deprecated
- 一次到位

### 替换范围 — 全部函数

以下函数全部替换为 linker 版本（返回 `UObjectInstance` 而非 dict）：
- `resolve_class_name` → linker 版
- `get_asset_class` → linker 版
- `detect_blueprint` → linker 版
- `resolve_parent_class` → linker 版
- `resolve_package_index_to_reference` → **完全移除**，不再提供 dict 转换

### 格式化层适配 — 完全移除 dict 返回

移除 `resolve_package_index_to_reference` 后，格式化层（JSON/Text/Mermaid）需要对象信息时：
- 直接使用 `UObjectInstance` 的属性（`.object_name`, `.object_class`, `.get_full_name()` 等）
- 需要 dict 格式的场景（如 JSON 输出）由格式化层自行构建
- 不保留独立的 to_dict() 辅助方法

## Canonical Refs

- `.planning/ROADMAP.md` — Phase 43 定义：`resolve_with_linker()`
- `.planning/STATE.md` — v7.0 状态：PackageIndex → UObjectInstance 实际引用
- `.planning/PROJECT.md` — v7.0 架构概览
- `src/uasset_read/link/linker.py` — `PackageLinker.resolve_package_index()`
- `src/uasset_read/link/object_instance.py` — `UObjectInstance` 数据类
- `src/uasset_read/serializers/object_resources.py` — 待替换的旧函数所在文件

## Code Context

### 可复用资产
- `PackageLinker.resolve_package_index(pkg_idx)` → `Optional[UObjectInstance]`（已有，liner:119-138）
- `UObjectInstance.get_full_name()` → 完整 UE 对象路径（已有，object_instance:88-104）
- `UObjectInstance.get_class_object()` → 解析 class 引用（已有，object_instance:106-114）
- `LinkerParseResult` — 包含 `linker`、`root_objects`、`all_objects`（已有）

### 调用方需要注意的文件
- `src/uasset_read/parsers/` — 属性解析器中调用 `resolve_package_index_to_reference` 的位置
- `src/uasset_read/formatters/` — 格式化层中需要适配 UObjectInstance 的位置
- `src/uasset_read/blueprint/` — 蓝图提取中调用 `resolve_class_name`/`resolve_parent_class` 的位置

## Deferred Ideas

无

---

*Created: 2026-05-14 | Mode: discuss (default)*
