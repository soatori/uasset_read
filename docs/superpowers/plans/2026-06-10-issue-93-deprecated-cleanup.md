# Issue #93 废弃函数及重复功能清理 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理所有标记为 deprecated 的函数、参数和模块，消除重复代码

**Architecture:** 分阶段清理：P0（立即清理已标记 deprecated 0.4.5 的代码）→ P1（清空 v0.5.0 废弃模块）→ P2（重复代码去重）→ P3（文档修正）

**Tech Stack:** Python 3.10+, pytest

---

## 当前进度（部分完成）

以下工作已在计划创建前完成：
- ✅ 删除 5 个废弃 formatter 文件（json/text/markdown/blueprint_text/blueprint_ue_text）
- ✅ 删除 `build_execution_flows()` 函数
- ✅ 从 `parse_package()` 删除 `aes_key` 和 `include_linker` 参数
- ✅ 从 `_parse_package_core()` 删除 `check_aes_key` 参数
- ✅ 清理 `__init__.py` 中的废弃导入

---

## Task 1: 完成 P0 — 清理 parse_uasset() 废弃参数

**Files:**
- Modify: `src/uasset_read/parse_uasset.py:756-779`

- [ ] **Step 1: 修改 parse_uasset() 函数签名**

从 `parse_uasset()` 中删除 `include_linker` 参数：

```python
def parse_uasset(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
) -> ParseResult:
    """
    兼容入口：解析 .uasset 文件。

    Internally delegates to parse_package(), so sidecar payload discovery is
    shared with .umap/package parsing.
    """
    return parse_package(
        path,
        tolerant=tolerant,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        mappings_path=mappings_path,
        game=game,
    )
```

- [ ] **Step 2: 验证修改**

Run: `python -c "from uasset_read import parse_uasset; import inspect; sig = inspect.signature(parse_uasset); print(list(sig.parameters.keys()))"`
Expected: `['path', 'tolerant', 'include_parent_assets', 'asset_roots', 'mappings_path', 'game']`（无 `include_linker`）

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/parse_uasset.py
git commit -m "refactor: 删除 parse_uasset() 废弃的 include_linker 参数"
```

---

## Task 2: P1 — 清空 objects/__init__.py 模块内容

**Files:**
- Modify: `src/uasset_read/objects/__init__.py`
- Note: 保留 `exports/` 子目录

- [ ] **Step 1: 清空 objects/__init__.py 内容**

将文件内容替换为空模块（保留目录结构）：

```python
"""UObject 类型体系（已弃用）

此模块已弃用，功能已迁移至 uasset_read.parsers.asset_types。
保留目录结构以容纳 exports/ 子模块。
"""
```

- [ ] **Step 2: 验证 exports 子模块仍可访问**

Run: `python -c "from uasset_read.objects.exports.material import UMaterialInstance; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/objects/__init__.py
git commit -m "refactor: 清空 objects/__init__.py（v0.5.0 废弃清理）"
```

---

## Task 3: P1 — 清空 bulk/__init__.py 模块内容

**Files:**
- Modify: `src/uasset_read/bulk/__init__.py`

- [ ] **Step 1: 清空 bulk/__init__.py 内容**

将文件内容替换为空模块：

```python
"""Bulk Data 系统（已弃用）

此模块已弃用，BulkData 功能将在未来版本中重新设计。
保留目录结构。
"""
```

- [ ] **Step 2: 验证内部模块仍可访问**

Run: `python -c "from uasset_read.bulk.structures import FBulkDataHeader; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/bulk/__init__.py
git commit -m "refactor: 清空 bulk/__init__.py（v0.5.0 废弃清理）"
```

---

## Task 4: P2 — serializers/__init__.py 重复导入去重

**Files:**
- Modify: `src/uasset_read/serializers/__init__.py:10-21, 50-63`

- [ ] **Step 1: 修复重复导入**

当前第 14-15 行和第 19-20 行有重复导入。修改为：

```python
from uasset_read.serializers.object_resources import (
    PackageIndex, ObjectImport, ObjectExport,
    read_import_map, build_imports_list, read_soft_object_paths,
    detect_circular_deps, read_export_map, get_asset_class,
    resolve_class_name, resolve_class_name_with_linker,
    get_asset_class_with_linker,
    detect_blueprint, detect_blueprint_generated_class,
    detect_blueprint_with_linker,
    validate_package_index, find_main_blueprint_generated_class,
    resolve_parent_class, resolve_parent_class_with_linker,
)
```

- [ ] **Step 2: 修复重复 __all__ 条目**

当前第 57-58 行和第 62-63 行有重复。修改为：

```python
__all__ = [
    'PackageFileSummary', 'GenerationInfo', 'EngineVersion', 'CustomVersion',
    'read_package_summary', 'read_name_table',
    'VersionContainer', 'build_version_container', 'EUEVersion',
    'PackageIndex', 'ObjectImport', 'ObjectExport',
    'read_import_map', 'build_imports_list', 'read_soft_object_paths',
    'detect_circular_deps', 'read_export_map', 'get_asset_class',
    'resolve_class_name', 'resolve_class_name_with_linker',
    'get_asset_class_with_linker',
    'detect_blueprint', 'detect_blueprint_generated_class',
    'detect_blueprint_with_linker',
    'validate_package_index', 'find_main_blueprint_generated_class',
    'resolve_parent_class', 'resolve_parent_class_with_linker',
    # 图序列化
    'read_ue_graph', 'read_ue_graph_node', 'read_ue_graph_pin',
    'read_ed_graph_pin_type', 'read_fmember_reference',
    'create_node_from_archive',
    # K2Node readers
    'read_k2node_call_function',
    'read_k2node_event',
    'read_k2node_knot',
    'read_edgraph_node_comment',
    'read_k2node_enhanced_input',
    'read_k2node_functionentry',
    'read_k2node_message',
    'read_k2node_call_delegate',
    'read_k2node_call_array_function',
    'read_k2node_call_parent_function',
    'read_k2node_function_result',
    'read_k2node_create_widget',
    'read_k2node_add_delegate',
    'read_k2node_macro_instance',
    'read_k2node_assign_delegate',
    'read_k2node_get_data_table_row',
    'read_k2node_load_asset',
    'read_k2node_spawn_actor_from_class',
    # Pin trace diagnostics
    'get_pin_trace_events',
    'reset_pin_trace_events',
]
```

- [ ] **Step 3: 验证导入正常**

Run: `python -c "from uasset_read.serializers import resolve_class_name_with_linker, get_asset_class_with_linker, detect_blueprint_with_linker, resolve_parent_class_with_linker; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/serializers/__init__.py
git commit -m "refactor: serializers/__init__.py 去除重复导入导出"
```

---

## Task 5: P3 — 修正 helpers.py 状态模型文档

**Files:**
- Modify: `src/uasset_read/formatters/helpers.py:46`

- [ ] **Step 1: 修正过时的状态描述**

将第 46 行从：
```python
"status": "解析结果状态（success/fail/error）",
```

修改为：
```python
"status": "解析结果状态（success/partial/failed）",
```

- [ ] **Step 2: Commit**

```bash
git add src/uasset_read/formatters/helpers.py
git commit -m "docs: 修正 helpers.py 状态模型文档为 success/partial/failed"
```

---

## Task 6: 验证清理完成

**Files:**
- 无新文件

- [ ] **Step 1: 验证无 deprecated:: 0.4.5 标记残留**

Run: `grep -r "deprecated:: 0.4.5" src/`
Expected: 无输出

- [ ] **Step 2: 验证无 deprecated:: 0.3.3 标记残留**

Run: `grep -r "deprecated:: 0.3.3" src/`
Expected: 无输出

- [ ] **Step 3: 运行单元测试**

Run: `python scripts/test_matrix.py unit`
Expected: 全部通过

- [ ] **Step 4: 运行质量门禁**

Run: `python scripts/test_matrix.py quality`
Expected: 通过

- [ ] **Step 5: 最终 Commit（如有修复）**

```bash
git add -A
git commit -m "test: issue#93 废弃清理完成验证"
```

---

## 验收标准检查清单

- [ ] 所有 P0 函数/参数已删除，`grep -r "deprecated:: 0.4.5" src/` 无结果
- [ ] 所有 P0 函数/参数已删除，`grep -r "deprecated:: 0.3.3" src/` 无结果
- [ ] P1 模块内容已清空（保留目录结构）
- [ ] P2 重复导入/导出已去重
- [ ] P3 状态模型文档已修正
- [ ] `python scripts/test_matrix.py unit` 全部通过
- [ ] `python scripts/test_matrix.py quality` 通过

---

## 不处理项（经审计确认保留）

以下经审计确认需要保留，不纳入清理范围：

- `EX_DeprecatedOp4A`（UE 官方废弃 opcode，用于诊断）
- `core.py` 中 `ParseError` 重导出（标准模块导出模式）
- `serializers/graph/__init__.py` 的 re-export（模块拆分后的标准做法）
- `legacy` 相关常量/函数（描述 UE 版本历史，非项目废弃）
- `pak/constants.py` 中的 deprecated 标志（用于解析旧版 pak）
- `unused` 标记的变量（必须读取以保持偏移对齐）
- `pak/structures.py` 中的 `read_fstring()`（与 `archive.py` 用途不同，pak 有特定版本处理逻辑）
- `format_transform_value`（确认无重复，仅定义在 `models/transforms.py`）
