# 死代码与冗余功能清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除项目中确认无用的死代码：孤立的 objects/ 和 bulk/ 模块、未使用的常量、零调用的辅助函数。

**Architecture:** 按依赖关系从底层模块向上逐层清理。先删除完全孤立的模块（bulk/、objects/），再清理 constants.py 和 formatters/helpers.py 中的死代码，最后修复文档。每步 TDD：先确认测试通过/更新测试，再删除代码。

**Tech Stack:** Python 3.10+, pytest

---

## 文件结构总览

### 删除的文件/目录

| 路径 | 原因 |
|---|---|
| `src/uasset_read/bulk/structures.py` | BulkDataFlags, FBulkDataHeader 零外部引用 |
| `src/uasset_read/bulk/__init__.py` | 空弃用声明，删除后移除整个 bulk/ 目录 |
| `src/uasset_read/objects/uobject.py` | UObject 基类仅 objects/ 内部使用 |
| `src/uasset_read/objects/registry.py` | ObjectTypeRegistry 仅 objects/ 内部使用 |
| `src/uasset_read/objects/exports/__init__.py` | 导出汇总仅 objects/ 内部使用 |
| `src/uasset_read/objects/exports/helpers.py` | 仅 objects/ 内部使用 |
| `src/uasset_read/objects/exports/mesh.py` | UStaticMesh 等仅 objects/ 内部 + 1 个测试 |
| `src/uasset_read/objects/exports/texture.py` | UTexture2D 等仅 objects/ 内部 + 1 个测试 |
| `src/uasset_read/objects/exports/material.py` | UMaterial 等仅 objects/ 内部 + 1 个测试 |
| `src/uasset_read/objects/__init__.py` | 空弃用声明 |
| `src/uasset_read/formatters/helpers.py` | 3 个函数零调用 |

### 修改的文件

| 路径 | 修改内容 |
|---|---|
| `src/uasset_read/constants.py` | 移除 4 个未使用常量 + 4 个重复 EXIT_* |
| `src/uasset_read/__init__.py` | 移除 formatters 辅助函数导出 + 修正文档注释 |
| `src/uasset_read/formatters/__init__.py` | 清空为空模块（保留目录） |
| `tests/test_cue4parse_gap_completion.py` | 移除 3 个依赖 objects/ 的测试 |

---

### Task 1: 更新测试 — 移除依赖 objects/ 的测试

**Files:**
- Modify: `tests/test_cue4parse_gap_completion.py:23-25,227-260,644-650`

- [ ] **Step 1: 确认当前测试状态**

Run: `python -m pytest tests/test_cue4parse_gap_completion.py -v --tb=short 2>&1 | head -40`
Expected: 确认哪些测试通过/失败

- [ ] **Step 2: 移除 objects/ 导入和依赖测试**

在 `tests/test_cue4parse_gap_completion.py` 中：

删除第 23-25 行的导入：
```python
from uasset_read.objects.exports.material import UMaterialInstance
from uasset_read.objects.exports.mesh import UStaticMesh
from uasset_read.objects.exports.texture import UTexture2D
```

删除 `test_asset_metadata_deserializers_populate_structured_fields` 函数（约 L227-260）：
```python
def test_asset_metadata_deserializers_populate_structured_fields():
    tex = UTexture2D()
    ...
    assert mesh.lod_groups[0]["section_count"] == 1
```

删除 `test_asset_deserializers_record_opaque_offsets` 函数（约 L644-650）：
```python
def test_asset_deserializers_record_opaque_offsets():
    tex = UTexture2D()
    ...
    assert tex.raw_size == 45
```

- [ ] **Step 3: 运行测试确认无 import 错误**

Run: `python -m pytest tests/test_cue4parse_gap_completion.py -v --tb=short`
Expected: 剩余测试全部 PASS，无 ImportError

- [ ] **Step 4: Commit**

```bash
git add tests/test_cue4parse_gap_completion.py
git commit -m "test: 移除依赖 objects/ 废弃模块的测试"
```

---

### Task 2: 删除 bulk/ 目录

**Files:**
- Delete: `src/uasset_read/bulk/structures.py`
- Delete: `src/uasset_read/bulk/__init__.py`

- [ ] **Step 1: 确认无引用**

Run: `python -c "from uasset_read.bulk import structures" 2>&1`
Expected: 仅 structures.py 自身，无外部 import

Run: `python -m pytest tests/ -k "bulk" -v --tb=short 2>&1 | head -20`
Expected: 无测试依赖 bulk 模块本身（bulk_data 字段是 IR 层的，不是 bulk/ 模块）

- [ ] **Step 2: 删除文件**

```bash
rm src/uasset_read/bulk/structures.py
rm src/uasset_read/bulk/__init__.py
rmdir src/uasset_read/bulk
```

- [ ] **Step 3: 运行全量测试确认无影响**

Run: `python -m pytest tests/test_api_cleanup.py tests/test_ir_structures.py tests/test_renderers.py -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add -A src/uasset_read/bulk/
git commit -m "refactor: 删除孤立的 bulk/ 模块（零外部引用）"
```

---

### Task 3: 删除 objects/ 目录

**Files:**
- Delete: `src/uasset_read/objects/` 整个目录（8 个文件）

- [ ] **Step 1: 确认无外部引用**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -5`
Expected: Task 1 已移除唯一依赖，全部 PASS

- [ ] **Step 2: 删除整个目录**

```bash
rm -rf src/uasset_read/objects/
```

- [ ] **Step 3: 运行全量测试**

Run: `python scripts/test_matrix.py unit`
Expected: 全部 PASS（objects/ 完全孤立）

- [ ] **Step 4: Commit**

```bash
git add -A src/uasset_read/objects/
git commit -m "refactor: 删除孤立的 objects/ 模块（已迁移至 parsers/asset_types）"
```

---

### Task 4: 清理 constants.py 死代码

**Files:**
- Modify: `src/uasset_read/constants.py`

- [ ] **Step 1: 移除 ALL_SUPPORTED_LEGACY_VERSIONS（L27）**

删除：
```python
# 支持的所有 LegacyFileVersion（UE4 + UE5）
ALL_SUPPORTED_LEGACY_VERSIONS = UE4_LEGACY_VERSIONS | UE5_LEGACY_VERSIONS
```

- [ ] **Step 2: 移除 MAX_TYPENODE_NODES（L94-98）**

删除整个区块：
```python
# ============================================================================
# FPropertyTypeName 最大节点数（UE 源码限制）
# ============================================================================

MAX_TYPENODE_NODES = 20                # FPropertyTypeName 最大节点数
```

注意：L107-110 的 `MAX_PROPERTY_TYPE_NODES = 50` 保留（被 serializers/property_tags.py 使用）。

- [ ] **Step 3: 移除 VER_UE4_EDGRAPHPINTYPE_SERIALIZATION（L162）**

删除：
```python
VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 323       # FEdGraphPinType 自定义序列化起点
```

保留 L163-164 的 `VER_UE4_MEMBERREFERENCE_IN_PINTYPE` 和 `VER_UE4_SERIALIZE_PINTYPE_CONST`（被 pin_types.py 使用）。

- [ ] **Step 4: 移除 EXIT_* 常量（L379-386）**

删除整个区块：
```python
# ============================================================================
# CLI退出代码
# ============================================================================

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3
```

这些已在 `cli.py:16-19` 独立定义并使用。

- [ ] **Step 5: 运行测试确认无影响**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -5`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/constants.py
git commit -m "refactor: 清理 constants.py 中 4 处未使用常量/重复定义"
```

---

### Task 5: 清理 formatters/helpers.py 和 __init__.py

**Files:**
- Delete: `src/uasset_read/formatters/helpers.py`
- Modify: `src/uasset_read/formatters/__init__.py`
- Modify: `src/uasset_read/__init__.py`

- [ ] **Step 1: 清空 formatters/__init__.py**

替换 `src/uasset_read/formatters/__init__.py` 为：
```python
"""输出格式化模块。

注：JSON/Text/Markdown/Blueprint 格式化函数已移除（deprecated 0.4.5），
推荐使用 parse_single(format=...) 统一入口 + renderers 系统。
"""
```

- [ ] **Step 2: 删除 helpers.py**

```bash
rm src/uasset_read/formatters/helpers.py
```

- [ ] **Step 3: 更新 __init__.py — 移除 formatters 导入**

在 `src/uasset_read/__init__.py` 中：

删除 L262-269 区块：
```python
# ============================================================================
# 辅助 API
# ============================================================================

# 格式化辅助函数
from .formatters import (
    build_status_info, build_schema_info, resolve_fpackage_index,
)
```

- [ ] **Step 4: 更新 __init__.py — 修正文档注释**

将 L10：
```python
- 遗留 API: format_* 函数, objects, bulk（已弃用）
```
改为：
```python
- 遗留 API: objects, bulk（已弃用，已移除）
```

注意：实际上 objects/ 和 bulk/ 在 Task 2-3 已删除，所以改为：
```python
- renderers: JSON, text, markdown, C++ skeleton 输出
```

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -5`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/formatters/ src/uasset_read/__init__.py
git commit -m "refactor: 移除零调用的 formatters/helpers.py 及相关导出"
```

---

### Task 6: 最终验证

- [ ] **Step 1: 运行全量测试矩阵**

Run: `python scripts/test_matrix.py unit`
Expected: 全部 PASS

- [ ] **Step 2: 运行质量门禁**

Run: `python scripts/test_matrix.py quality`
Expected: 全部 PASS

- [ ] **Step 3: 确认无残留引用**

Run: `python -c "import uasset_read; print(uasset_read.__version__)"`
Expected: `0.4.5`

Run: `python -c "from uasset_read.objects import UObject" 2>&1`
Expected: ModuleNotFoundError（确认已清理）

Run: `python -c "from uasset_read.bulk import FBulkDataHeader" 2>&1`
Expected: ModuleNotFoundError（确认已清理）

- [ ] **Step 4: 确认 formatters/ 目录状态**

`src/uasset_read/formatters/` 目录应仅包含 `__init__.py`（无其他 .py 文件）。

- [ ] **Step 5: 最终 Commit（如有遗漏修复）**

```bash
git add -A
git status --short
# 如有未提交的修复
git commit -m "fix: 清理残留引用"
```
