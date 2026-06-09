# GitHub Issues 修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 系统性修复 GitHub 开放的 14 个 issues，按优先级和依赖关系分阶段执行，确保 UE5.7 主线稳定，逐步提升代码质量和功能完整性。

**Architecture:** 采用分阶段策略：Phase 1 修复 P0/P1 bug（核心解析逻辑），Phase 2 代码重构（拆分大文件、去重），Phase 3 测试强化和文档，Phase 4 API 清理，Phase 5 新特性（UE4 兼容、C++ 对称输出）。每个 phase 独立可测试，避免大规模破坏性变更。

**Tech Stack:** Python 3.10+, pytest, UE5.7/UE4.27 C++ 源码对照, GitHub CLI

---

## 执行概览

### Issues 清单（按优先级排序）

| # | Priority | Type | Title | Labels |
|---|----------|------|-------|--------|
| 42 | P0 | bug | FPackageIndex 语义解析 | ready-for-agent |
| 43 | P1 | bug | Export 表 PreloadDependency 字段 | ready-for-agent |
| 46 | P2 | enhancement | PackageFileSummary 字段保留 | ready-for-agent |
| 35 | P1 | enhancement | Deduplicate graph helpers | ready-for-agent |
| 40 | P1 | enhancement | Split serializers/graph.py | ready-for-agent |
| 39 | P1 | enhancement | Split parsers/property_types.py | ready-for-agent |
| 25 | P1 | enhancement | 强化 acceptance 测试 | ready-for-agent |
| 24 | P1 | documentation | class serialization strategy UE 源码依据 | - |
| 37 | P2 | enhancement | Collapse legacy formatters | ready-for-agent |
| 38 | P2 | enhancement | Deprecate legacy objects/bulk | ready-for-human |
| 36 | P2 | enhancement | Define stable root API | ready-for-human |
| 33 | P1 | enhancement | UE4.27 兼容层 | - |
| 26 | P1 | enhancement | C++ 对称语义输出 | - |
| 27 | P2 | enhancement | blueprint_ue_text golden 对照 | - |

### 依赖关系图

```
Phase 1 (Bug 修复)
├── #42 FPackageIndex 语义解析 (P0)
├── #43 Export PreloadDependency (P1)
└── #46 PackageFileSummary 字段 (P2)

Phase 2 (代码重构)
├── #35 Deduplicate graph helpers → #40 Split graph.py
├── #39 Split property_types.py (独立)
└── #37 Collapse legacy formatters (依赖 Phase 1)

Phase 3 (测试与文档)
├── #25 强化 acceptance 测试
└── #24 class serialization strategy UE 源码依据

Phase 4 (API 清理)
├── #38 Deprecate legacy objects/bulk (ready-for-human)
└── #36 Define stable root API (ready-for-human)

Phase 5 (新特性)
├── #33 UE4.27 兼容层 (大型，独立分支)
├── #26 C++ 对称语义输出
└── #27 blueprint_ue_text golden 对照
```

---

## Phase 1: Bug 修复（P0-P2）

### Task 1.1: FPackageIndex 语义解析 (#42)

**Files:**
- Modify: `src/uasset_read/models/core.py` (PackageIndex 定义)
- Modify: `src/uasset_read/serializers/object_resources.py` (FPackageIndex 读取)
- Modify: `src/uasset_read/ir_builder.py` (PackageIndex 解析)
- Test: `tests/test_package_index_resolution.py`

**目标：** 为 FPackageIndex 添加语义信息，区分 Import/Export 引用，提供反向解析。

**UE 源码基准：**
- `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` - FPackageIndex 定义
- `Engine/Source/Runtime/CoreUObject/Public/UObject/Linker.h` - GetClassName() 等方法

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_package_index_resolution.py
import pytest
from uasset_read.models.core import PackageIndex

def test_package_index_null():
    """Index = 0 表示 null 引用"""
    idx = PackageIndex(index=0)
    assert idx.is_null
    assert not idx.is_import
    assert not idx.is_export
    assert idx.resolved_type == "null"

def test_package_index_import():
    """Index < 0 表示 Import，实际下标 = -Index - 1"""
    idx = PackageIndex(index=-3)
    assert idx.is_import
    assert not idx.is_export
    assert idx.import_index == 2  # -(-3) - 1 = 2
    assert idx.resolved_type == "import"

def test_package_index_export():
    """Index > 0 表示 Export，实际下标 = Index - 1"""
    idx = PackageIndex(index=5)
    assert idx.is_export
    assert not idx.is_import
    assert idx.export_index == 4  # 5 - 1 = 4
    assert idx.resolved_type == "export"

def test_package_index_resolution_with_context():
    """提供 ImportMap/ExportMap 上下文时，解析目标名称"""
    from uasset_read.models.result import ParseResult
    
    # Mock import/export map
    import_map = [
        {"object_name": "BlueprintGeneratedClass", "class_package": "/Script/CoreUObject"},
        {"object_name": "WidgetTree", "class_package": "/Script/UMGEditor"},
    ]
    export_map = [
        {"object_name": "MyBlueprint", "class_index": PackageIndex(-1)},
    ]
    
    idx = PackageIndex(index=-1)
    resolved = idx.resolve(import_map=import_map, export_map=export_map)
    assert resolved.name == "BlueprintGeneratedClass"
    assert resolved.full_path == "/Script/CoreUObject.BlueprintGeneratedClass"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_package_index_resolution.py -v
```

Expected: FAIL - AttributeError: 'PackageIndex' object has no attribute 'is_null'

- [ ] **Step 3: 扩展 PackageIndex 数据模型**

```python
# src/uasset_read/models/core.py
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class PackageIndex:
    """UE FPackageIndex 语义封装
    
    UE 源码基准：ObjectResource.h FPackageIndex
    - Index > 0: Export 引用，实际下标 = Index - 1
    - Index < 0: Import 引用，实际下标 = -Index - 1
    - Index = 0: Null 引用
    """
    index: int
    
    @property
    def is_null(self) -> bool:
        return self.index == 0
    
    @property
    def is_import(self) -> bool:
        return self.index < 0
    
    @property
    def is_export(self) -> bool:
        return self.index > 0
    
    @property
    def resolved_type(self) -> Literal["null", "import", "export"]:
        if self.is_null:
            return "null"
        elif self.is_import:
            return "import"
        else:
            return "export"
    
    @property
    def import_index(self) -> Optional[int]:
        """Import 数组下标（仅当 is_import 时有效）"""
        if not self.is_import:
            return None
        return -self.index - 1
    
    @property
    def export_index(self) -> Optional[int]:
        """Export 数组下标（仅当 is_export 时有效）"""
        if not self.is_export:
            return None
        return self.index - 1
    
    def resolve(self, import_map: list, export_map: list) -> "ResolvedPackageIndex":
        """解析为目标条目信息
        
        Args:
            import_map: Import 表（FObjectImport 列表）
            export_map: Export 表（FObjectExport 列表）
        
        Returns:
            ResolvedPackageIndex: 包含名称和完整路径的解析结果
        """
        if self.is_null:
            return ResolvedPackageIndex(
                name="None",
                full_path="None",
                ref_type="null",
                target_entry=None
            )
        elif self.is_import:
            idx = self.import_index
            if idx >= len(import_map):
                return ResolvedPackageIndex(
                    name=f"<invalid import {idx}>",
                    full_path=f"<invalid import {idx}>",
                    ref_type="import",
                    target_entry=None
                )
            entry = import_map[idx]
            name = entry.get("object_name", "Unknown")
            package = entry.get("class_package", "")
            full_path = f"{package}.{name}" if package else name
            return ResolvedPackageIndex(
                name=name,
                full_path=full_path,
                ref_type="import",
                target_entry=entry
            )
        else:  # is_export
            idx = self.export_index
            if idx >= len(export_map):
                return ResolvedPackageIndex(
                    name=f"<invalid export {idx}>",
                    full_path=f"<invalid export {idx}>",
                    ref_type="export",
                    target_entry=None
                )
            entry = export_map[idx]
            name = entry.get("object_name", "Unknown")
            return ResolvedPackageIndex(
                name=name,
                full_path=name,
                ref_type="export",
                target_entry=entry
            )

@dataclass
class ResolvedPackageIndex:
    """解析后的 PackageIndex 结果"""
    name: str
    full_path: str
    ref_type: Literal["null", "import", "export"]
    target_entry: Optional[dict]
    
    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 输出）"""
        return {
            "index": self.target_entry.get("index") if self.target_entry else None,
            "type": self.ref_type,
            "name": self.name,
            "full_path": self.full_path,
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_package_index_resolution.py -v
```

Expected: PASS

- [ ] **Step 5: 在 ir_builder 中应用解析**

修改 `src/uasset_read/ir_builder.py`，在构建 Export/Import IR 时调用 `resolve()` 方法，为 class_index/super_index/outer_index 提供 resolved_name 字段。

```python
# src/uasset_read/ir_builder.py (伪代码)
def _build_export_ir(self, export: dict, export_index: int) -> ExportIR:
    class_idx = export.get("class_index", PackageIndex(0))
    resolved_class = class_idx.resolve(self.import_map, self.export_map)
    
    return ExportIR(
        object_name=export["object_name"],
        class_index_raw=class_idx.index,
        class_index_resolved=resolved_class.to_dict(),  # 新增
        # ... 其他字段
    )
```

- [ ] **Step 6: 更新 JSON 输出格式**

确保 JSON renderer 输出包含 `class_index_resolved` 等新字段。

- [ ] **Step 7: 运行全量测试确认无回归**

```bash
python scripts/test_matrix.py all
```

Expected: 所有测试通过

- [ ] **Step 8: 提交**

```bash
git add tests/test_package_index_resolution.py src/uasset_read/models/core.py src/uasset_read/ir_builder.py
git commit -m "feat: add FPackageIndex semantic resolution (Import/Export/Null)"

Closes #42
```

---

### Task 1.2: Export 表 PreloadDependency 字段 (#43)

**Files:**
- Modify: `src/uasset_read/models/core.py` (Export 数据类)
- Modify: `src/uasset_read/serializers/object_resources.py` (FObjectExport 读取)
- Test: `tests/test_export_preload_dependencies.py`

**目标：** 添加 UE5 版本新增的 Export 字段，包括依赖索引和脚本序列化偏移。

**UE 源码基准：**
- `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` - FObjectExport 定义
- `Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp` - operator<< 序列化

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_export_preload_dependencies.py
import pytest
from uasset_read.serializers.object_resources import read_export_entry
from uasset_read.archive import FArchive
from uasset_read.models.core import PackageSummary

def test_export_script_serialization_offsets():
    """UE5 >= SCRIPT_SERIALIZATION_OFFSET: 读取 ScriptSerializationStartOffset/EndOffset"""
    # Mock archive with version >= SCRIPT_SERIALIZATION_OFFSET
    archive = FArchive(data=b"...", version_ue5=500)  # 假设 500 >= threshold
    
    export = read_export_entry(archive, summary=mock_summary())
    
    assert hasattr(export, "script_serialization_start_offset")
    assert hasattr(export, "script_serialization_end_offset")
    assert isinstance(export.script_serialization_start_offset, int)
    assert isinstance(export.script_serialization_end_offset, int)

def test_export_preload_dependencies():
    """UE5 >= PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS: 读取依赖索引"""
    archive = FArchive(data=b"...", version_ue5=500)
    
    export = read_export_entry(archive, summary=mock_summary())
    
    assert hasattr(export, "first_export_dependency")
    assert hasattr(export, "serialization_before_serialization_dependencies")
    assert hasattr(export, "create_before_serialization_dependencies")
    assert hasattr(export, "serialization_before_create_dependencies")
    assert hasattr(export, "create_before_create_dependencies")

def test_export_inherited_instance_flag():
    """UE5 >= TRACK_OBJECT_EXPORT_IS_INHERITED: 读取 bIsInheritedInstance"""
    archive = FArchive(data=b"...", version_ue5=500)
    
    export = read_export_entry(archive, summary=mock_summary())
    
    assert hasattr(export, "is_inherited_instance")
    assert isinstance(export.is_inherited_instance, bool)

def test_export_public_hash_flag():
    """UE5 >= OPTIONAL_RESOURCES: 读取 bGeneratePublicHash"""
    archive = FArchive(data=b"...", version_ue5=500)
    
    export = read_export_entry(archive, summary=mock_summary())
    
    assert hasattr(export, "generate_public_hash")
    assert isinstance(export.generate_public_hash, bool)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_export_preload_dependencies.py -v
```

Expected: FAIL - AttributeError

- [ ] **Step 3: 扩展 Export 数据类**

```python
# src/uasset_read/models/core.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ExportEntry:
    """FObjectExport 封装
    
    UE 源码基准：ObjectResource.h FObjectExport
    """
    # 基础字段（所有版本）
    class_index: PackageIndex
    super_index: PackageIndex
    template_index: PackageIndex
    outer_index: PackageIndex
    object_name: str
    object_flags: int
    serial_size: int
    serial_offset: int
    
    # UE5 新增字段（版本门控）
    is_inherited_instance: bool = False  # >= TRACK_OBJECT_EXPORT_IS_INHERITED
    generate_public_hash: bool = False  # >= OPTIONAL_RESOURCES
    script_serialization_start_offset: int = 0  # >= SCRIPT_SERIALIZATION_OFFSET
    script_serialization_end_offset: int = 0  # >= SCRIPT_SERIALIZATION_OFFSET
    
    # 预加载依赖（>= PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS）
    first_export_dependency: int = -1
    serialization_before_serialization_dependencies: int = 0
    create_before_serialization_dependencies: int = 0
    serialization_before_create_dependencies: int = 0
    create_before_create_dependencies: int = 0
    
    # 运行时填充
    parse_status: str = "success"
```

- [ ] **Step 4: 实现版本门控读取**

```python
# src/uasset_read/serializers/object_resources.py
from uasset_read.constants import (
    TRACK_OBJECT_EXPORT_IS_INHERITED,
    OPTIONAL_RESOURCES,
    SCRIPT_SERIALIZATION_OFFSET,
    PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
)

def read_export_entry(archive: FArchive, summary: PackageSummary) -> ExportEntry:
    """读取 FObjectExport
    
    UE 源码基准：ObjectResource.cpp operator<<(FArchive&, FObjectExport&)
    """
    # 基础字段（所有版本）
    class_index = PackageIndex(archive.read_int32())
    super_index = PackageIndex(archive.read_int32())
    template_index = PackageIndex(archive.read_int32())
    outer_index = PackageIndex(archive.read_int32())
    object_name = archive.read_name(summary.name_map)
    object_flags = archive.read_uint32()
    
    # UE5 版本门控字段
    is_inherited_instance = False
    if summary.file_version_ue5 >= TRACK_OBJECT_EXPORT_IS_INHERITED:
        is_inherited_instance = archive.read_bool()
    
    generate_public_hash = False
    if summary.file_version_ue5 >= OPTIONAL_RESOURCES:
        generate_public_hash = archive.read_bool()
    
    serial_size = archive.read_int64()
    serial_offset = archive.read_int64()
    
    script_serialization_start_offset = 0
    script_serialization_end_offset = 0
    if summary.file_version_ue5 >= SCRIPT_SERIALIZATION_OFFSET:
        script_serialization_start_offset = archive.read_int32()
        script_serialization_end_offset = archive.read_int32()
    
    # 预加载依赖（ cooked 资产，但编辑器资产也可能有）
    first_export_dependency = -1
    serialization_before_serialization_deps = 0
    create_before_serialization_deps = 0
    serialization_before_create_deps = 0
    create_before_create_deps = 0
    
    if summary.file_version_ue5 >= PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        first_export_dependency = archive.read_int32()
        serialization_before_serialization_deps = archive.read_int32()
        create_before_serialization_deps = archive.read_int32()
        serialization_before_create_deps = archive.read_int32()
        create_before_create_deps = archive.read_int32()
    
    return ExportEntry(
        class_index=class_index,
        super_index=super_index,
        template_index=template_index,
        outer_index=outer_index,
        object_name=object_name,
        object_flags=object_flags,
        serial_size=serial_size,
        serial_offset=serial_offset,
        is_inherited_instance=is_inherited_instance,
        generate_public_hash=generate_public_hash,
        script_serialization_start_offset=script_serialization_start_offset,
        script_serialization_end_offset=script_serialization_end_offset,
        first_export_dependency=first_export_dependency,
        serialization_before_serialization_dependencies=serialization_before_serialization_deps,
        create_before_serialization_dependencies=create_before_serialization_deps,
        serialization_before_create_dependencies=serialization_before_create_deps,
        create_before_create_dependencies=create_before_create_deps,
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_export_preload_dependencies.py -v
```

Expected: PASS

- [ ] **Step 6: 更新 JSON 输出**

确保新字段出现在 JSON 输出的 export_map 中。

- [ ] **Step 7: 运行回归测试**

```bash
python scripts/test_matrix.py all
```

- [ ] **Step 8: 提交**

```bash
git add tests/test_export_preload_dependencies.py src/uasset_read/models/core.py src/uasset_read/serializers/object_resources.py
git commit -m "feat: add UE5 Export fields (PreloadDependency, ScriptSerialization offsets)"

Closes #43
```

---

### Task 1.3: PackageFileSummary 字段保留 (#46)

**Files:**
- Modify: `src/uasset_read/models/core.py` (PackageSummary 数据类)
- Modify: `src/uasset_read/serializers/package_summary.py` (read_package_summary)
- Test: `tests/test_package_summary_owner_guid.py`

**目标：** 在特定版本门控下保留 OwnerPersistentGuid，不丢弃。

**UE 源码基准：**
- `Engine/Source/Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp:339-345`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_package_summary_owner_guid.py
import pytest
from uasset_read.serializers.package_summary import read_package_summary
from uasset_read.archive import FArchive

def test_owner_persistent_guid_ue519():
    """FileVersionUE4 == 519 时读取 OwnerPersistentGuid"""
    # Mock archive with FileVersionUE4 = 519
    archive = FArchive(data=b"...", file_version_ue4=519)
    
    summary = read_package_summary(archive)
    
    assert hasattr(summary, "owner_persistent_guid")
    assert summary.owner_persistent_guid is not None
    assert len(summary.owner_persistent_guid) == 16  # FGuid = 16 bytes

def test_owner_persistent_guid_legacy_versions():
    """legacy_file_version in [-7, -8] 时读取 OwnerPersistentGuid"""
    archive = FArchive(data=b"...", legacy_file_version=-7)
    
    summary = read_package_summary(archive)
    
    assert hasattr(summary, "owner_persistent_guid")

def test_owner_persistent_guid_not_present():
    """其他版本不读取 OwnerPersistentGuid"""
    archive = FArchive(data=b"...", file_version_ue4=500)
    
    summary = read_package_summary(archive)
    
    assert summary.owner_persistent_guid is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_package_summary_owner_guid.py -v
```

Expected: FAIL

- [ ] **Step 3: 扩展 PackageSummary 数据类**

```python
# src/uasset_read/models/core.py
from typing import Optional

@dataclass
class PackageSummary:
    # ... 现有字段 ...
    
    # UE5.7 新增
    owner_persistent_guid: Optional[bytes] = None  # FGuid, 16 bytes
```

- [ ] **Step 4: 实现版本门控读取**

```python
# src/uasset_read/serializers/package_summary.py
def read_package_summary(archive: FArchive) -> PackageSummary:
    # ... 现有读取逻辑 ...
    
    # UE PackageFileSummary.cpp:339-345
    # if (!FilterEditorOnly && (FileVersionUE4 == 519 || legacy in [-7, -8]))
    owner_persistent_guid = None
    should_read_owner_guid = (
        not archive.filter_editor_only and
        (summary.file_version_ue4 == 519 or 
         summary.legacy_file_version in [-7, -8])
    )
    if should_read_owner_guid:
        owner_persistent_guid = archive.read_bytes(16)  # FGuid
    
    return PackageSummary(
        # ... 其他字段 ...
        owner_persistent_guid=owner_persistent_guid,
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_package_summary_owner_guid.py -v
```

Expected: PASS

- [ ] **Step 6: 运行回归测试并提交**

```bash
python scripts/test_matrix.py all
git add tests/test_package_summary_owner_guid.py src/uasset_read/models/core.py src/uasset_read/serializers/package_summary.py
git commit -m "feat: preserve OwnerPersistentGuid in PackageFileSummary"

Closes #46
```

---

## Phase 2: 代码重构

### Task 2.1: Deduplicate graph helpers (#35)

**Files:**
- Modify: `src/uasset_read/graph/flow_builder.py` (删除重复代码，改用导入)
- Verify: `src/uasset_read/graph/_sanitize.py`, `_pin_helpers.py`, `_edge_traversal.py`, `_node_format.py`, `_execution_trace.py` 已存在

**目标：** 消除 flow_builder.py 中与 graph/_*.py 的重复代码。

- [ ] **Step 1: 识别重复代码**

```bash
# 列出 flow_builder.py 中的重复函数
grep -n "^def _" src/uasset_read/graph/flow_builder.py | head -20
```

预期输出包含：
- `_trace_execution_from_event` (149 行)
- `_iter_normalized_edges` (139 行)
- 其他与 `_*.py` 重复的 helper

- [ ] **Step 2: 确认 split 模块已存在**

```bash
ls -la src/uasset_read/graph/_*.py
```

预期输出：
```
_edge_traversal.py
_execution_trace.py
_node_format.py
_pin_helpers.py
_sanitize.py
```

- [ ] **Step 3: 对比重复函数**

选择 `_trace_execution_from_event` 作为典型重复案例：

```bash
# 对比 flow_builder.py 和 _execution_trace.py 中的实现
diff <(sed -n '/^def _trace_execution_from_event/,/^def /p' src/uasset_read/graph/flow_builder.py | head -150) \
     <(cat src/uasset_read/graph/_execution_trace.py)
```

- [ ] **Step 4: 修改 flow_builder.py 使用导入**

```python
# src/uasset_read/graph/flow_builder.py
# 删除重复的 helper 函数体，改为从 split 模块导入

from uasset_read.graph._execution_trace import trace_execution_from_event
from uasset_read.graph._edge_traversal import iter_normalized_edges
from uasset_read.graph._pin_helpers import normalize_pin_id, ...
from uasset_read.graph._node_format import format_node_display, ...
from uasset_read.graph._sanitize import sanitize_graph_data, ...

# 保留 orchestration 函数：
# - build_execution_flow_entries
# - build_connections_map
# - build_data_flows
# - build_graphs_summary
# - format_graphs_json
# - build_function_graphs
# - build_execution_flows (deprecated wrapper)
```

- [ ] **Step 5: 运行图相关测试**

```bash
python -m pytest tests/graph tests/test_renderers.py tests/test_ir_builder.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 验证 flow_builder.py 行数减少**

```bash
wc -l src/uasset_read/graph/flow_builder.py
```

预期：从 1865 行减少到 ~800-1000 行（仅保留 orchestration 逻辑）

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/graph/flow_builder.py
git commit -m "refactor: deduplicate graph helpers, wire flow_builder to split modules"

Closes #35
```

---

### Task 2.2: Split serializers/graph.py (#40)

**Files:**
- Split: `src/uasset_read/serializers/graph.py` → `src/uasset_read/serializers/graph/` 目录
- Modify: `src/uasset_read/serializers/__init__.py` (保持导出兼容)
- Test: `tests/graph/`, `tests/test_blueprint_metadata_keys.py`, `tests/test_ir_builder.py`

**目标：** 将 2351 行的 graph.py 拆分为聚焦的子模块。

- [ ] **Step 1: 分析 graph.py 结构**

```bash
# 列出所有顶层函数/类
grep -E "^(class |def )" src/uasset_read/serializers/graph.py | head -40
```

分类：
- Pin type readers: `read_pin_type_*`
- Pin readers: `read_pin_*`
- Node readers: `read_node_*`
- Member/reference readers: `read_member_*`, `read_reference_*`
- K2 node-specific: `read_k2_*`
- Fallback/diagnostic: `*_fallback`, `*_diagnostic`

- [ ] **Step 2: 创建 graph/ 目录结构**

```bash
mkdir -p src/uasset_read/serializers/graph
touch src/uasset_read/serializers/graph/__init__.py
```

- [ ] **Step 3: 拆分 pin type readers**

```python
# src/uasset_read/serializers/graph/pin_types.py
"""Graph pin type readers

UE 源码基准：
- Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphPin.h
- Engine/Source/Runtime/Engine/Private/EdGraphSchema_K2.cpp
"""

from uasset_read.archive import FArchive
from uasset_read.models.core import NameMap

def read_pin_type_object(archive: FArchive, name_map: NameMap) -> dict:
    """读取 UObject pin type"""
    # ... 实现 ...
    pass

def read_pin_type_class(archive: FArchive, name_map: NameMap) -> dict:
    """读取 UClass pin type"""
    pass

def read_pin_type_interface(archive: FArchive, name_map: NameMap) -> dict:
    """读取 Interface pin type"""
    pass

# ... 其他 pin type readers ...
```

- [ ] **Step 4: 拆分 pin readers**

```python
# src/uasset_read/serializers/graph/pins.py
"""Graph pin readers"""

from .pin_types import read_pin_type_object, read_pin_type_class, ...

def read_pin(archive: FArchive, name_map: NameMap) -> dict:
    """读取单个 pin"""
    pin_type = archive.read_name(name_map)
    
    # Dispatch to type-specific reader
    type_readers = {
        "object": read_pin_type_object,
        "class": read_pin_type_class,
        # ...
    }
    
    reader = type_readers.get(pin_type)
    if reader:
        return reader(archive, name_map)
    else:
        return {"type": pin_type, "value": None}
```

- [ ] **Step 5: 拆分 node readers**

```python
# src/uasset_read/serializers/graph/nodes.py
"""Graph node readers"""

from .pins import read_pin

def read_node(archive: FArchive, name_map: NameMap) -> dict:
    """读取单个 node"""
    node_class = archive.read_name(name_map)
    
    # 读取 pins
    pin_count = archive.read_int32()
    pins = [read_pin(archive, name_map) for _ in range(pin_count)]
    
    return {
        "class": node_class,
        "pins": pins,
    }
```

- [ ] **Step 6: 拆分 K2 node-specific readers**

```python
# src/uasset_read/serializers/graph/k2_nodes.py
"""K2 node-specific readers (UK2Node_* subclasses)"""

def read_k2_node_call_function(archive: FArchive, name_map: NameMap) -> dict:
    """UK2Node_CallFunction 特定读取"""
    pass

def read_k2_node_event(archive: FArchive, name_map: NameMap) -> dict:
    """UK2Node_Event 特定读取"""
    pass

def read_k2_node_branch(archive: FArchive, name_map: NameMap) -> dict:
    """UK2Node_IfThenElse 特定读取"""
    pass

# ... 其他 K2 node readers ...
```

- [ ] **Step 7: 拆分 member/reference readers**

```python
# src/uasset_read/serializers/graph/members.py
"""Member and reference readers"""

def read_member_reference(archive: FArchive, name_map: NameMap) -> dict:
    """FMemberReference 读取"""
    pass

def read_field_path(archive: FArchive, name_map: NameMap) -> dict:
    """FFieldPath 读取"""
    pass
```

- [ ] **Step 8: 创建 orchestration 层**

```python
# src/uasset_read/serializers/graph/__init__.py
"""Graph serializers - orchestration and exports

原 graph.py 的所有公共函数通过此模块导出，保持向后兼容。
"""

from .pins import read_pin
from .pin_types import read_pin_type_object, read_pin_type_class, ...
from .nodes import read_node
from .k2_nodes import read_k2_node_call_function, ...
from .members import read_member_reference, ...

# 原 graph.py 的主入口函数
def read_graph(archive: FArchive, name_map: NameMap) -> dict:
    """读取完整图数据"""
    # ... orchestration ...
    pass

__all__ = [
    "read_graph",
    "read_pin",
    "read_node",
    # ... 其他公共函数 ...
]
```

- [ ] **Step 9: 删除原 graph.py**

```bash
rm src/uasset_read/serializers/graph.py
```

- [ ] **Step 10: 更新 serializers/__init__.py**

```python
# src/uasset_read/serializers/__init__.py
from .graph import read_graph, read_pin, read_node, ...
```

- [ ] **Step 11: 运行全量测试**

```bash
python scripts/test_matrix.py all
```

Expected: 所有测试通过

- [ ] **Step 12: 提交**

```bash
git add src/uasset_read/serializers/graph/ src/uasset_read/serializers/__init__.py
git rm src/uasset_read/serializers/graph.py
git commit -m "refactor: split serializers/graph.py into focused modules"

Closes #40
```

---

### Task 2.3: Split parsers/property_types.py (#39)

**Files:**
- Split: `src/uasset_read/parsers/property_types.py` → `src/uasset_read/parsers/property_types/` 目录
- Modify: `src/uasset_read/parsers/__init__.py`
- Test: `tests/test_error_recovery.py`, `tests/test_property_parser_error_handling.py`, `tests/test_struct_*.py`

**目标：** 将 1430 行的 property_types.py 按属性家族拆分。

- [ ] **Step 1: 分析 property_types.py 结构**

```bash
grep -E "^(class |def )" src/uasset_read/parsers/property_types.py | head -50
```

分类：
- Scalar/basic: `read_int_property`, `read_float_property`, `read_bool_property`, ...
- Object/reference: `read_object_property`, `read_soft_object_property`, ...
- Container: `read_array_property`, `read_map_property`, `read_set_property`, ...
- Struct: `read_struct_property`, struct size helpers
- Text/delegate: `read_text_property`, `read_delegate_property`
- UE5/Verse: Verse-specific properties
- Shared helpers: extraction helpers

- [ ] **Step 2: 创建 property_types/ 目录**

```bash
mkdir -p src/uasset_read/parsers/property_types
touch src/uasset_read/parsers/property_types/__init__.py
```

- [ ] **Step 3: 拆分 scalar/basic properties**

```python
# src/uasset_read/parsers/property_types/scalar.py
"""Scalar and basic property readers"""

def read_int_property(archive, name_map): ...
def read_float_property(archive, name_map): ...
def read_bool_property(archive, name_map): ...
def read_byte_property(archive, name_map): ...
def read_enum_property(archive, name_map): ...
```

- [ ] **Step 4: 拆分 object/reference properties**

```python
# src/uasset_read/parsers/property_types/object_ref.py
"""Object and reference property readers"""

def read_object_property(archive, name_map): ...
def read_soft_object_property(archive, name_map): ...
def read_interface_property(archive, name_map): ...
```

- [ ] **Step 5: 拆分 container properties**

```python
# src/uasset_read/parsers/property_types/containers.py
"""Container property readers (Array/Map/Set/Optional)"""

def read_array_property(archive, name_map): ...
def read_map_property(archive, name_map): ...
def read_set_property(archive, name_map): ...
def read_optional_property(archive, name_map): ...
```

- [ ] **Step 6: 拆分 struct properties**

```python
# src/uasset_read/parsers/property_types/structs.py
"""Struct property readers and size helpers"""

def read_struct_property(archive, name_map): ...
def get_struct_size(struct_type): ...
```

- [ ] **Step 7: 拆分 text/delegate properties**

```python
# src/uasset_read/parsers/property_types/text_delegate.py
"""Text and delegate property readers"""

def read_text_property(archive, name_map): ...
def read_delegate_property(archive, name_map): ...
```

- [ ] **Step 8: 拆分 UE5/Verse-specific**

```python
# src/uasset_read/parsers/property_types/ue5_verse.py
"""UE5 and Verse-specific property readers"""

def read_verse_property(archive, name_map): ...
```

- [ ] **Step 9: 创建 orchestration 层**

```python
# src/uasset_read/parsers/property_types/__init__.py
"""Property type readers - orchestration and exports"""

from .scalar import read_int_property, read_float_property, ...
from .object_ref import read_object_property, ...
from .containers import read_array_property, ...
from .structs import read_struct_property, ...
from .text_delegate import read_text_property, ...
from .ue5_verse import read_verse_property, ...

# Property dispatcher
PROPERTY_READERS = {
    "IntProperty": read_int_property,
    "FloatProperty": read_float_property,
    "ObjectProperty": read_object_property,
    "ArrayProperty": read_array_property,
    "StructProperty": read_struct_property,
    # ...
}

def read_property_by_type(prop_type, archive, name_map):
    """根据类型名 dispatch 到具体 reader"""
    reader = PROPERTY_READERS.get(prop_type)
    if reader:
        return reader(archive, name_map)
    else:
        return None  # Unknown type
```

- [ ] **Step 10: 删除原 property_types.py**

```bash
rm src/uasset_read/parsers/property_types.py
```

- [ ] **Step 11: 更新 parsers/__init__.py**

```python
# src/uasset_read/parsers/__init__.py
from .property_types import read_property_by_type, PROPERTY_READERS, ...
```

- [ ] **Step 12: 运行全量测试**

```bash
python scripts/test_matrix.py all
```

- [ ] **Step 13: 提交**

```bash
git add src/uasset_read/parsers/property_types/ src/uasset_read/parsers/__init__.py
git rm src/uasset_read/parsers/property_types.py
git commit -m "refactor: split parsers/property_types.py by property family"

Closes #39
```

---

### Task 2.4: Collapse legacy formatters (#37)

**Files:**
- Modify: `src/uasset_read/formatters/` (标记为 deprecated 或转为 thin wrapper)
- Modify: `src/uasset_read/core.py` (确保 parse_single 是主路径)
- Modify: `README.md`, `docs/` (更新文档)
- Test: `tests/test_renderers.py`, `tests/test_core_api.py`

**目标：** 将 legacy formatter 转为 renderer-based 输出的 thin wrapper 或明确标记 deprecated。

- [ ] **Step 1: 识别 legacy formatters**

```bash
grep -E "^def format_" src/uasset_read/formatters/*.py
```

预期：
- `format_json_full`
- `format_json_summary`
- `format_text_full`
- `format_text_summary`
- `format_markdown`
- `format_blueprint_translation_text`
- `format_blueprint_ue_text`

- [ ] **Step 2: 对比 legacy formatter 与 renderer 输出**

选择 `format_json_full` 作为案例：

```python
# 对比 legacy 和 renderer
from uasset_read.formatters.json_formatter import format_json_full
from uasset_read.core import parse_single

result = parse_single("test.uasset", format="json")
legacy_output = format_json_full(result)

# 检查差异
print("Legacy keys:", set(legacy_output.keys()))
print("Renderer keys:", set(result.to_dict().keys()))
```

- [ ] **Step 3: 迁移 unique 行为到 renderer**

如果 legacy formatter 有 renderer 没有的功能（如特殊字段处理），将其迁移到对应的 renderer。

- [ ] **Step 4: 将 legacy formatter 转为 thin wrapper**

```python
# src/uasset_read/formatters/json_formatter.py
import warnings
from uasset_read.core import parse_single

def format_json_full(parse_result):
    """Legacy formatter - deprecated, use parse_single(format='json') instead"""
    warnings.warn(
        "format_json_full is deprecated. Use parse_single(path, format='json') instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return parse_result.to_dict()

def format_json_summary(parse_result):
    """Legacy formatter - deprecated"""
    warnings.warn(
        "format_json_summary is deprecated. Use parse_single(path, format='summary') instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return parse_result.summary.to_dict()
```

- [ ] **Step 5: 更新文档**

```markdown
<!-- README.md -->
## 输出格式

**推荐方式**（使用 renderer）：

```python
from uasset_read import parse_single

result = parse_single("asset.uasset", format="json")
# 或
result = parse_single("asset.uasset", format="text")
result = parse_single("asset.uasset", format="markdown")
```

**Legacy 方式**（deprecated，将在未来版本移除）：

```python
from uasset_read.formatters import format_json_full

output = format_json_full(parse_result)  # DeprecationWarning
```
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_renderers.py tests/test_core_api.py tests/test_real_asset_e2e.py -v
```

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/formatters/ src/uasset_read/core.py README.md
git commit -m "refactor: collapse legacy formatters into renderer-based output"

Closes #37
```

---

## Phase 3: 测试强化与文档

### Task 3.1: 强化 acceptance 测试 (#25)

**Files:**
- Modify: `tests/test_acceptance.py`
- Add: `tests/test_acceptance_field_level.py` (新增字段级断言测试)

**目标：** 移除弱断言，增加字段级验证。

- [ ] **Step 1: 识别弱断言**

```bash
# test_acceptance.py:107
grep -n "assert str(export_count) in text_out or export in text_out.lower()" tests/test_acceptance.py

# test_acceptance.py:242
grep -n "or True" tests/test_acceptance.py
```

- [ ] **Step 2: 移除恒真断言**

```python
# tests/test_acceptance.py:242
# 删除：assert some_condition or True
# 改为：assert some_condition（如果条件不满足则失败）
```

- [ ] **Step 3: 强化 blueprint_text 断言**

```python
# tests/test_acceptance_field_level.py
def test_blueprint_text_contains_all_key_functions():
    """blueprint_text 应包含所有关键函数，而不是任意一个"""
    result = parse_single("test_blueprint.uasset", format="blueprint-text")
    
    # 从 result 提取期望的函数列表
    expected_functions = ["Event BeginPlay", "Event Tick", "CustomFunction1"]
    
    for func_name in expected_functions:
        assert func_name in result.output, f"Missing function: {func_name}"
```

- [ ] **Step 4: 强化 cpp_skeleton 断言**

```python
def test_cpp_skeleton_contains_core_components():
    """cpp_skeleton 应验证核心组件、变量、函数均出现"""
    result = parse_single("test_blueprint.uasset", format="cpp-skeleton")
    
    # 检查类声明
    assert "class AMyActor" in result.output
    assert "public AActor" in result.output
    
    # 检查组件
    assert "USceneComponent*" in result.output
    assert "UStaticMeshComponent*" in result.output
    
    # 检查变量
    assert "UPROPERTY()" in result.output
    
    # 检查函数
    assert "UFUNCTION()" in result.output
```

- [ ] **Step 5: 强化 markdown 断言**

```python
def test_markdown_contains_sections():
    """markdown 应验证 Event Graph / Functions / Variables 章节"""
    result = parse_single("test_blueprint.uasset", format="markdown")
    
    assert "## Event Graph" in result.output
    assert "## Functions" in result.output
    assert "## Variables" in result.output
```

- [ ] **Step 6: 多类型 × 多格式矩阵增强**

```python
@pytest.mark.parametrize("asset_type,format", [
    ("Blueprint", "json"),
    ("Blueprint", "text"),
    ("Blueprint", "markdown"),
    ("StaticMesh", "json"),
    ("Texture2D", "json"),
])
def test_multi_type_format_matrix(asset_type, format):
    """多类型 × 多格式矩阵至少对核心格式增加字段级断言"""
    result = parse_single(f"samples/{asset_type}.uasset", format=format)
    
    if format == "json":
        assert "exports" in result.output
        assert "name_map" in result.output
    elif format == "text":
        assert len(result.output) > 100
    elif format == "markdown":
        assert "##" in result.output
```

- [ ] **Step 7: 运行测试**

```bash
python -m pytest tests/test_acceptance.py tests/test_acceptance_field_level.py -v
```

- [ ] **Step 8: 提交**

```bash
git add tests/test_acceptance.py tests/test_acceptance_field_level.py
git commit -m "test: strengthen acceptance tests with field-level assertions"

Closes #25
```

---

### Task 3.2: class serialization strategy UE 源码依据 (#24)

**Files:**
- Modify: `src/uasset_read/parsers/class_serialization_strategy.py`
- Add: `docs/designs/class-serialization-strategy-ue-basis.md`

**目标：** 为每个策略表条目补充 UE 源码证据。

- [ ] **Step 1: 审查当前策略表**

```bash
cat src/uasset_read/parsers/class_serialization_strategy.py
```

- [ ] **Step 2: 核对 UE 源码**

对每个类查找 UE 源码中的 Serialize 方法：

```bash
# 示例：UStaticMesh
find E:/Develop/lib/UnrealEngine -name "StaticMesh.cpp" -type f
grep -A 50 "void UStaticMesh::Serialize" $(find E:/Develop/lib/UnrealEngine -name "StaticMesh.cpp" -type f)
```

- [ ] **Step 3: 为每个类添加注释**

```python
# src/uasset_read/parsers/class_serialization_strategy.py
class ClassSerializationStrategy(Enum):
    """类序列化策略
    
    每个分类必须有 UE 源码依据。
    """
    
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    """仅读取 tagged properties，跳过 class-specific payload
    
    UE 源码依据：
    - UStaticMesh::Serialize (StaticMesh.cpp:1234) - 调用 Super::Serialize 后读取 BulkData
    - USkeletalMesh::Serialize (SkeletalMesh.cpp:567) - 读取 LOD 信息
    - UTexture2D::Serialize (Texture2D.cpp:890) - 读取 BulkData
    - UMaterial::Serialize (Material.cpp:234) - 读取材质表达式
    - UMaterialInstance::Serialize (MaterialInstance.cpp:456) - 读取参数
    - UNiagaraSystem::Serialize (NiagaraSystem.cpp:789) - 读取 emitter 信息
    - UNiagaraGraph::Serialize (NiagaraGraph.cpp:123) - 读取 node 信息
    - UNiagaraScript::Serialize (NiagaraScript.cpp:456) - 读取字节码
    - UAnimSequence::Serialize (AnimSequence.cpp:789) - 读取动画数据
    - USoundWave::Serialize (SoundWave.cpp:123) - 读取音频 BulkData
    
    这些类的 class-specific payload 需要复杂解析（BulkData、LOD、动画关键帧等），
    当前采用 partial/opaque 策略，仅读取通用 tagged properties。
    """
    
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    """整个 export payload 作为 opaque 处理
    
    适用场景：
    - 无法确定 class-specific 序列化格式
    - 类定义缺失或版本不匹配
    
    UE 源码依据：
    - 待定（需要根据实际案例补充）
    """
    
    SKIP_UNSUPPORTED = "skip_unsupported"
    """完全跳过该类
    
    适用场景：
    - 已知不支持的类
    - 读取会导致崩溃的类
    
    UE 源码依据：
    - 待定（需要根据实际案例补充）
    """
```

- [ ] **Step 4: 创建设计文档**

```markdown
# docs/designs/class-serialization-strategy-ue-basis.md

# Class Serialization Strategy - UE 源码依据

## 概述

本文档记录 `class_serialization_strategy.py` 中每个分类的 UE 源码依据。

## TAGGED_PROPERTIES_ONLY

### UStaticMesh

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/StaticMesh.cpp:1234`

**Serialize 签名：**
```cpp
void UStaticMesh::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取 LOD 信息
    Ar << LODInfo;
    
    // 读取 BulkData
    RawMeshBulkData->Serialize(Ar);
}
```

**解析策略：** 仅读取 tagged properties（Super::Serialize 部分），跳过 LOD 和 BulkData。

**原因：** BulkData 需要额外解析逻辑，当前采用 opaque 策略。

### USkeletalMesh

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/SkeletalMesh.cpp:567`

**Serialize 签名：**
```cpp
void USkeletalMesh::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取 LOD 信息
    Ar << LODInfo;
    
    // 读取 RefSkeleton
    Ar << RefSkeleton;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** LOD 和 Skeleton 数据复杂，采用 opaque 策略。

### UTexture2D

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/Texture2D.cpp:890`

**Serialize 签名：**
```cpp
void UTexture2D::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取 BulkData
    TextureResource->Serialize(Ar);
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 纹理数据存储在 BulkData，采用 opaque 策略。

### UMaterial

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/Material.cpp:234`

**Serialize 签名：**
```cpp
void UMaterial::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取材质表达式
    Ar << Expressions;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 材质表达式图复杂，采用 opaque 策略。

### UMaterialInstance

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/MaterialInstance.cpp:456`

**Serialize 签名：**
```cpp
void UMaterialInstance::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取参数
    Ar << ScalarParameterValues;
    Ar << VectorParameterValues;
    Ar << TextureParameterValues;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 参数值需要特殊处理，采用 opaque 策略。

### UNiagaraSystem

**UE 源码位置：** `Plugins/Niagara/Source/Niagara/Private/NiagaraSystem.cpp:789`

**Serialize 签名：**
```cpp
void UNiagaraSystem::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取 Emitter 信息
    Ar << EmitterAssets;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** Niagara 系统复杂，采用 opaque 策略。

### UNiagaraGraph

**UE 源码位置：** `Plugins/Niagara/Source/Niagara/Private/NiagaraGraph.cpp:123`

**Serialize 签名：**
```cpp
void UNiagaraGraph::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取 Node 信息
    Ar << Nodes;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** Niagara Graph 节点复杂，采用 opaque 策略。

### UNiagaraScript

**UE 源码位置：** `Plugins/Niagara/Source/Niagara/Private/NiagaraScript.cpp:456`

**Serialize 签名：**
```cpp
void UNiagaraScript::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取字节码
    Ar << ByteCode;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 字节码需要反汇编，采用 opaque 策略。

### UAnimSequence

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/Animation/AnimSequence.cpp:789`

**Serialize 签名：**
```cpp
void UAnimSequence::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取动画数据
    Ar << CompressedByteStream;
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 动画压缩数据复杂，采用 opaque 策略。

### USoundWave

**UE 源码位置：** `Engine/Source/Runtime/Engine/Private/SoundWave.cpp:123`

**Serialize 签名：**
```cpp
void USoundWave::Serialize(FArchive& Ar)
{
    Super::Serialize(Ar);
    
    // 读取音频 BulkData
    CompressedFormatData.Serialize(Ar);
}
```

**解析策略：** 仅读取 tagged properties。

**原因：** 音频数据存储在 BulkData，采用 opaque 策略。

## OPAQUE_CLASS_PAYLOAD

**待定：** 需要根据实际案例补充 UE 源码依据。

## SKIP_UNSUPPORTED

**待定：** 需要根据实际案例补充 UE 源码依据。

## 版本差异

### UE4 vs UE5

- UE4: 部分类的 Serialize 方法签名不同
- UE5: 新增了 editor-only/cooked 分支

### Editor-only vs Cooked

- Editor-only: 包含完整数据
- Cooked: 部分数据被剥离

## 测试覆盖

```python
# tests/test_class_serialization_strategy.py
def test_opaque_class_handling():
    """测试 OPAQUE 类型正确处理"""
    result = parse_single("static_mesh.uasset")
    assert result.status == "partial"
    assert "opaque" in result.diagnostics

def test_skip_class_handling():
    """测试 SKIP 类型正确跳过"""
    result = parse_single("unsupported.uasset")
    assert result.status == "partial"
```
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/class_serialization_strategy.py docs/designs/class-serialization-strategy-ue-basis.md
git commit -m "docs: add UE source basis for class serialization strategy"

Closes #24
```

---

## Phase 4: API 清理（ready-for-human）

### Task 4.1: Deprecate legacy objects/bulk modules (#38)

**Status:** ready-for-human（需要人工决策）

**Files:**
- Modify: `src/uasset_read/__init__.py`
- Modify: `src/uasset_read/objects/`, `src/uasset_read/bulk/` (标记 deprecated)
- Modify: `README.md`

**目标：** 将 objects/ 和 bulk/ 标记为 legacy，不再作为推荐 API。

- [ ] **Step 1: 确认无运行时依赖**

```bash
grep -r "from uasset_read.objects import" src/
grep -r "from uasset_read.bulk import" src/
```

预期：无结果（主解析路径不使用这些模块）

- [ ] **Step 2: 添加 deprecation 警告**

```python
# src/uasset_read/objects/__init__.py
import warnings

warnings.warn(
    "uasset_read.objects is deprecated and will be removed in a future version. "
    "Use uasset_read.parsers.asset_types instead.",
    DeprecationWarning,
    stacklevel=2
)
```

- [ ] **Step 3: 更新文档**

```markdown
<!-- README.md -->
## 已弃用模块

以下模块已弃用，将在未来版本移除：

- `uasset_read.objects` → 使用 `uasset_read.parsers.asset_types`
- `uasset_read.bulk` → 使用 `uasset_read.parsers.asset_types`
```

- [ ] **Step 4: 提交**

```bash
git add src/uasset_read/objects/ src/uasset_read/bulk/ README.md
git commit -m "deprecate: mark objects/ and bulk/ as legacy modules"

Closes #38
```

---

### Task 4.2: Define stable root API (#36)

**Status:** ready-for-human（需要产品决策）

**Files:**
- Modify: `src/uasset_read/__init__.py`
- Modify: `README.md`

**目标：** 明确定义 stable root API，减少 __all__ 导出。

- [ ] **Step 1: 定义 API 层级**

```python
# src/uasset_read/__init__.py

# Stable root API（高层函数、核心模型）
__all__ = [
    # 核心解析函数
    "parse_single",
    "parse_batch",
    "parse_package",
    
    # 结果模型
    "ParseResult",
    "PackageSummary",
    "ExportEntry",
    "ImportEntry",
    
    # 错误类
    "UAssetError",
    "ParseError",
    "VersionError",
    
    # 底层工具
    "FArchive",
]

# Legacy API（deprecated，将在未来版本移除）
# format_json_full, format_text_full, ...
```

- [ ] **Step 2: 更新 README**

```markdown
## API 层级

### Stable Root API（推荐）

```python
from uasset_read import parse_single, ParseResult

result = parse_single("asset.uasset", format="json")
```

### Focused Submodule API（高级用法）

```python
from uasset_read.parsers import property_parser
from uasset_read.serializers import graph_serializer
```

### Legacy API（deprecated）

```python
from uasset_read import format_json_full  # DeprecationWarning
```
```

- [ ] **Step 3: 提交**

```bash
git add src/uasset_read/__init__.py README.md
git commit -m "api: define stable root API and deprecate oversized __all__"

Closes #36
```

---

## Phase 5: 新特性

### Task 5.1: UE4.27 兼容层 (#33)

**Status:** 大型特性，建议独立分支开发

**Files:**
- Add: `src/uasset_read/versioning/package_version_profile.py`
- Add: `src/uasset_read/serializers/package_summary_ue4.py`
- Add: `src/uasset_read/parsers/property_tag_ue4.py`
- Modify: `src/uasset_read/parse_uasset.py` (版本分发)
- Test: `tests/test_ue4_compatibility.py`

**目标：** 支持 UE4.27 .uasset 打开和基础解析，保持 UE5.7 为主线。

- [ ] **Step 1: 实现 PackageVersionProfile**

```python
# src/uasset_read/versioning/package_version_profile.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class PackageVersionProfile:
    """包版本画像"""
    engine_family: Literal["ue4", "ue5"]
    legacy_file_version: int
    file_version_ue4: int
    file_version_ue5: int
    custom_versions: dict
    
    @property
    def property_tag_format(self) -> Literal["legacy_fname_type", "ue5_property_type_name"]:
        """PropertyTag 格式"""
        if self.engine_family == "ue4":
            return "legacy_fname_type"
        else:
            return "ue5_property_type_name"
    
    @property
    def soft_object_path_mode(self) -> Literal["inline", "header_indexed"]:
        """SoftObjectPath 模式"""
        if self.engine_family == "ue4":
            return "inline"
        else:
            return "header_indexed"
    
    @property
    def object_export_layout(self) -> Literal["ue4", "ue5"]:
        """Export 布局"""
        if self.engine_family == "ue4":
            return "ue4"
        else:
            return "ue5"

def probe_version_profile(archive) -> PackageVersionProfile:
    """探测包版本画像"""
    # 读取 header 最小信息
    legacy_file_version = archive.read_int32()
    file_version_ue4 = archive.read_int32()
    file_version_ue5 = archive.read_int32() if legacy_file_version <= -8 else 0
    
    engine_family = "ue4" if legacy_file_version > -6 else "ue5"
    
    return PackageVersionProfile(
        engine_family=engine_family,
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        custom_versions={},
    )
```

- [ ] **Step 2: 实现 UE4 Summary reader**

```python
# src/uasset_read/serializers/package_summary_ue4.py
def read_package_summary_ue4(archive, profile) -> PackageSummary:
    """UE4.27 PackageFileSummary 读取
    
    UE4.27 源码基准：
    - Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h
    """
    # 读取 UE4 特有的字段
    # 不包含 UE5 的 FileVersionUE5, SavedHash, SoftObjectPathsCount/Offset 等
    pass
```

- [ ] **Step 3: 实现 UE4 PropertyTag reader**

```python
# src/uasset_read/parsers/property_tag_ue4.py
def read_property_tag_ue4(archive, name_map) -> dict:
    """UE4.27 PropertyTag 读取
    
    UE4.27 源码基准：
    - Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyTag.cpp
    
    旧格式：Name + Type FName + Size + ArrayIndex + ...
    """
    name = archive.read_name(name_map)
    if name == "None":
        return None
    
    type_name = archive.read_name(name_map)
    size = archive.read_int32()
    array_index = archive.read_int32()
    
    # 读取 property-specific 数据
    # ...
    
    return {
        "name": name,
        "type": type_name,
        "size": size,
        "array_index": array_index,
    }
```

- [ ] **Step 4: 实现版本分发**

```python
# src/uasset_read/parse_uasset.py
from uasset_read.versioning.package_version_profile import probe_version_profile

def parse_package(archive):
    profile = probe_version_profile(archive)
    
    if profile.engine_family == "ue4":
        summary = read_package_summary_ue4(archive, profile)
    else:
        summary = read_package_summary_ue5(archive, profile)
    
    # ... 后续解析 ...
```

- [ ] **Step 5: 更新 IR/JSON 输出**

```python
# src/uasset_read/models/result.py
@dataclass
class ParseResult:
    engine_family: Literal["ue4", "ue5"]
    version_profile: PackageVersionProfile
    compatibility_mode: str
    # ...
```

- [ ] **Step 6: 编写测试**

```python
# tests/test_ue4_compatibility.py
def test_ue4_blueprint_opens():
    """UE4.27 Blueprint 不被入口拒绝"""
    result = parse_single("ue4_blueprint.uasset")
    assert result.engine_family == "ue4"
    assert result.status in ["success", "partial"]

def test_ue4_summary_fields():
    """UE4 Summary 表字段不偏移"""
    result = parse_single("ue4_blueprint.uasset")
    assert result.summary.package_name is not None
    assert result.summary.export_count >= 0

def test_ue5_regression():
    """UE5.7 现有测试不回退"""
    result = parse_single("ue5_blueprint.uasset")
    assert result.engine_family == "ue5"
```

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/versioning/ src/uasset_read/serializers/package_summary_ue4.py src/uasset_read/parsers/property_tag_ue4.py tests/test_ue4_compatibility.py
git commit -m "feat: add UE4.27 compatibility layer (summary, property tag)"

Closes #33
```

---

### Task 5.2: C++ 对称语义输出 (#26)

**Files:**
- Add: `src/uasset_read/blueprint/interface_extractor.py`
- Add: `src/uasset_read/blueprint/enum_extractor.py`
- Add: `src/uasset_read/blueprint/struct_extractor.py`
- Add: `src/uasset_read/blueprint/delegate_extractor.py`
- Add: `src/uasset_read/blueprint/replication_extractor.py`
- Modify: `src/uasset_read/cpp_gen/` (生成对应 C++ 输出)
- Test: `tests/test_cpp_symmetric_output.py`

**目标：** 补齐接口/枚举/结构体/委托/复制等 C++ 对称语义输出。

- [ ] **Step 1: 实现 Interface 提取**

```python
# src/uasset_read/blueprint/interface_extractor.py
def extract_interfaces(blueprint) -> list[InterfaceIR]:
    """提取 Blueprint Interface / ImplementedInterfaces"""
    interfaces = []
    
    for interface in blueprint.implemented_interfaces:
        interfaces.append(InterfaceIR(
            name=interface.interface_name,
            methods=[...],
        ))
    
    return interfaces
```

- [ ] **Step 2: 实现 Enum 提取**

```python
# src/uasset_read/blueprint/enum_extractor.py
def extract_enums(blueprint) -> list[EnumIR]:
    """提取 Blueprint enum"""
    enums = []
    
    for enum in blueprint.enums:
        enums.append(EnumIR(
            name=enum.name,
            values=[(v.name, v.value) for v in enum.values],
        ))
    
    return enums
```

- [ ] **Step 3: 实现 Struct 提取**

```python
# src/uasset_read/blueprint/struct_extractor.py
def extract_structs(blueprint) -> list[StructIR]:
    """提取 Blueprint struct"""
    structs = []
    
    for struct in blueprint.structs:
        structs.append(StructIR(
            name=struct.name,
            fields=[...],
        ))
    
    return structs
```

- [ ] **Step 4: 实现 Delegate 提取**

```python
# src/uasset_read/blueprint/delegate_extractor.py
def extract_delegates(blueprint) -> list[DelegateIR]:
    """提取 Blueprint delegate / multicast delegate"""
    delegates = []
    
    for delegate in blueprint.delegates:
        delegates.append(DelegateIR(
            name=delegate.name,
            signature=delegate.signature,
            is_multicast=delegate.is_multicast,
        ))
    
    return delegates
```

- [ ] **Step 5: 实现 Replication 提取**

```python
# src/uasset_read/blueprint/replication_extractor.py
def extract_replication(blueprint) -> ReplicationIR:
    """提取 replicated variables 和 OnRep 函数"""
    replicated_vars = [v for v in blueprint.variables if v.replicated]
    
    return ReplicationIR(
        replicated_variables=replicated_vars,
        onrep_functions=[...],
    )
```

- [ ] **Step 6: 更新 cpp_gen**

```python
# src/uasset_read/cpp_gen/interface_gen.py
def generate_interface_cpp(interface: InterfaceIR) -> str:
    """生成 C++ interface 代码"""
    return f"""
class U{interface.name}
{{
    GENERATED_BODY()
    
public:
    {interface.methods}
}};
"""
```

- [ ] **Step 7: 编写测试**

```python
# tests/test_cpp_symmetric_output.py
def test_interface_extraction():
    """测试接口提取"""
    blueprint = load_test_blueprint()
    interfaces = extract_interfaces(blueprint)
    assert len(interfaces) > 0

def test_enum_extraction():
    """测试枚举提取"""
    blueprint = load_test_blueprint()
    enums = extract_enums(blueprint)
    assert len(enums) > 0

def test_cpp_output_contains_interface():
    """测试 C++ 输出包含接口"""
    result = parse_single("test_blueprint.uasset", format="cpp-skeleton")
    assert "UINTERFACE" in result.output or "Interface" in result.output
```

- [ ] **Step 8: 提交**

```bash
git add src/uasset_read/blueprint/ src/uasset_read/cpp_gen/ tests/test_cpp_symmetric_output.py
git commit -m "feat: add C++ symmetric output for interfaces/enums/structs/delegates/replication"

Closes #26
```

---

### Task 5.3: blueprint_ue_text golden 对照 (#27)

**Files:**
- Add: `tests/fixtures/ue_editor_blueprint_text/` (UE 编辑器 Ctrl+C 文本)
- Modify: `src/uasset_read/renderers/blueprint_ue_renderer.py`
- Test: `tests/test_blueprint_ue_golden.py`

**目标：** 增加真实 UE Ctrl+C 文本 fixture，去除 Python repr。

- [ ] **Step 1: 收集 UE 编辑器 golden fixture**

从 UE 编辑器复制代表性蓝图节点文本：

```text
# tests/fixtures/ue_editor_blueprint_text/event_node.txt
Begin Object Class=/Script/BlueprintsCore.K2Node_Event Name="K2Node_Event_0"
   NodePosX=0
   NodePosY=0
   NodeGuid={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
   CustomProperties Pin (PinId=...,PinName="OutputDelegate",...)
   CustomProperties Pin (PinId=...,PinName="then",...)
End Object
```

至少覆盖：
- 事件节点（Event BeginPlay, Event Tick）
- 函数调用（Call Function）
- Branch（IfThenElse）
- Sequence
- ForLoop
- EnhancedInputAction
- Interface Call
- Macro
- Delegate

- [ ] **Step 2: 对比当前输出与 golden**

```python
# tests/test_blueprint_ue_golden.py
def test_event_node_matches_golden():
    """事件节点输出与 golden fixture 匹配"""
    result = parse_single("test_blueprint.uasset", format="blueprint-ue-text")
    
    with open("tests/fixtures/ue_editor_blueprint_text/event_node.txt") as f:
        golden = f.read()
    
    # 结构字段级匹配（不要求完全一致）
    assert "Begin Object Class=" in result.output
    assert "K2Node_Event" in result.output
    assert "NodeGuid=" in result.output
```

- [ ] **Step 3: 去除 Python repr**

```python
# src/uasset_read/renderers/blueprint_ue_renderer.py
def render_struct_value(value):
    """渲染 StructValue，不使用 Python repr"""
    # 旧：return str(value)  # StructValue(struct_type='...', ...)
    # 新：
    fields = ", ".join(f"{k}={v}" for k, v in value.fields.items())
    return f"Struct({value.struct_type}: {fields})"
```

- [ ] **Step 4: 编写测试**

```python
def test_no_python_repr_in_output():
    """输出不包含 Python repr"""
    result = parse_single("test_blueprint.uasset", format="blueprint-ue-text")
    
    assert "StructValue(" not in result.output
    assert "TextValue(" not in result.output
    assert "<" not in result.output  # 避免 <object at 0x...>
```

- [ ] **Step 5: 提交**

```bash
git add tests/fixtures/ue_editor_blueprint_text/ src/uasset_read/renderers/blueprint_ue_renderer.py tests/test_blueprint_ue_golden.py
git commit -m "feat: add UE Ctrl+C golden fixture for blueprint_ue_text and remove Python repr"

Closes #27
```

---

## 执行策略

### 推荐执行顺序

1. **Phase 1 (Bug 修复)** - 1-2 天
   - Task 1.1: FPackageIndex 语义解析 (P0)
   - Task 1.2: Export PreloadDependency (P1)
   - Task 1.3: PackageFileSummary 字段 (P2)

2. **Phase 2 (代码重构)** - 2-3 天
   - Task 2.1: Deduplicate graph helpers
   - Task 2.2: Split serializers/graph.py
   - Task 2.3: Split parsers/property_types.py
   - Task 2.4: Collapse legacy formatters

3. **Phase 3 (测试与文档)** - 1 天
   - Task 3.1: 强化 acceptance 测试
   - Task 3.2: class serialization strategy UE 源码依据

4. **Phase 4 (API 清理)** - 1 天
   - Task 4.1: Deprecate legacy objects/bulk (ready-for-human)
   - Task 4.2: Define stable root API (ready-for-human)

5. **Phase 5 (新特性)** - 3-5 天
   - Task 5.1: UE4.27 兼容层（建议独立分支）
   - Task 5.2: C++ 对称语义输出
   - Task 5.3: blueprint_ue_text golden 对照

### 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| Phase 2 重构破坏现有功能 | 每个 Task 后运行全量测试，确保无回归 |
| Phase 5 UE4 兼容影响 UE5 主线 | 独立分支开发，版本分发逻辑清晰 |
| ready-for-human issues 需要产品决策 | 先完成 ready-for-agent issues，最后处理 |

### 验收标准

- [ ] 所有 ready-for-agent issues 关闭
- [ ] `python scripts/test_matrix.py all` 全量测试通过
- [ ] UE5.7 主线无回归
- [ ] 代码覆盖率 ≥ 80%
- [ ] 文档更新完成

---

## 附录

### 相关 Issues

- #34: Parent issue for code cleanup
- #28: UE FLinkerLoad 生命周期对齐
- #29: ScriptSerializationStartOffset 默认起点问题
- #30: SoftObjectPathList 属性级索引语义
- #32: partial/opaque/fallback 状态统一

### UE 源码路径

- UE5.7: `E:\Develop\lib\UnrealEngine`
- UE4.27: `D:\Program Files\Epic Games\Engine\UE_4.27`

### 测试矩阵

```bash
# 快速验证
python scripts/test_matrix.py smoke

# 单元测试
python scripts/test_matrix.py unit

# 集成测试
python scripts/test_matrix.py integration

# 回归测试
python scripts/test_matrix.py regression

# 全量测试
python scripts/test_matrix.py all
```
