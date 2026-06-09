# P1 Issues Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 P1 issues (Phase A + B) via branch-per-issue strategy, each branch isolated and merged back to develop after verification.

**Architecture:** Each issue gets its own feature branch from `develop`. After task completion and test verification, merge back to `develop`. This ensures atomic fixes and clean git history.

**Tech Stack:** Python 3.10+, pytest, UE5.7 C++ source reference

---

## Branch Strategy

```
develop
├── fix/p1-status-unification          → #49 (status bug)
├── fix/p1-sentinel-preservation       → #54 (sentinel bug)
├── verify/p1-export-fields            → #43 (verify existing code)
├── feat/p1-unversioned-parser         → #50 (new module)
├── docs/p1-class-serialization-ue     → #24 (documentation)
└── test/p1-acceptance-strengthening   → #25 (test quality)
```

**Merge rule:** Each branch merges to `develop` via `git merge --no-ff` after all tasks in the branch pass tests.

---

## Branch 1: fix/p1-status-unification (#49)

### Task 1.1: Fix ParseResult.status partial set

**Files:**
- Modify: `src/uasset_read/models/result.py:73-77`

**Step 1: Write failing test**

```python
# tests/test_status_unification.py
"""验证 ParseResult.status 对所有 partial 状态的正确处理。"""
import pytest
from unittest.mock import MagicMock
from uasset_read.models.result import ParseResult


def _make_result(parse_status: str) -> ParseResult:
    """构造含指定 parse_status 导出的 ParseResult。"""
    result = ParseResult()
    result.summary = MagicMock()
    mock_export = MagicMock()
    mock_export.parse_status = parse_status
    result.export_map = [mock_export]
    return result


def test_status_partial_metadata():
    """含 partial_metadata 导出 → partial"""
    assert _make_result("partial_metadata").status == "partial"


def test_status_opaque_unversioned():
    """含 opaque_unversioned 导出 → partial"""
    assert _make_result("opaque_unversioned").status == "partial"


def test_status_fallback():
    """含 fallback 导出 → partial"""
    assert _make_result("fallback").status == "partial"


def test_status_mixed_success_and_partial():
    """混合 success + partial_metadata → partial"""
    result = ParseResult()
    result.summary = MagicMock()
    s1 = MagicMock(); s1.parse_status = "success"
    s2 = MagicMock(); s2.parse_status = "partial_metadata"
    result.export_map = [s1, s2]
    assert result.status == "partial"


def test_status_all_success():
    """所有 success → success"""
    assert _make_result("success").status == "success"


def test_status_opaque():
    """含 opaque 导出 → partial（已有逻辑，回归）"""
    assert _make_result("opaque").status == "partial"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_status_unification.py -v
```

Expected: 3 FAIL (partial_metadata, opaque_unversioned, fallback 通过; mixed 可能通过取决于 mock)

**Step 3: Fix result.py status property**

修改 `src/uasset_read/models/result.py:76`:

```python
        # Partial if any export is not success
        for export in self.export_map:
            export_status = getattr(export, 'parse_status', 'success')
            if export_status in (
                'opaque', 'partial', 'partial_metadata', 'opaque_unversioned',
                'skipped', 'metadata', 'fallback', 'failed',
            ):
                return "partial"
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_status_unification.py -v
```

Expected: All 6 PASS

**Step 5: Fix link/result.py status property (same change)**

修改 `src/uasset_read/link/result.py:74`，与 result.py 保持一致：

```python
            if export_status in (
                'opaque', 'partial', 'partial_metadata', 'opaque_unversioned',
                'skipped', 'metadata', 'fallback', 'failed',
            ):
                return "partial"
```

**Step 6: Run regression**

```bash
python -m pytest tests/test_ir_builder.py tests/test_status_unification.py -v
```

**Step 7: Commit**

```bash
git checkout -b fix/p1-status-unification develop
git add src/uasset_read/models/result.py src/uasset_read/link/result.py tests/test_status_unification.py
git commit -m "fix: unify partial status set in ParseResult/LinkerParseResult (#49)

Add opaque_unversioned, partial_metadata, and fallback to the partial
status check, consistent with ir_builder._PARTIAL_STATUSES.

Closes #49"
```

**Step 8: Merge to develop**

```bash
git checkout develop
git merge --no-ff fix/p1-status-unification -m "Merge fix/p1-status-unification into develop"
git branch -d fix/p1-status-unification
```

---

## Branch 2: fix/p1-sentinel-preservation (#54)

### Task 2.1: Fix PackageFileSummary sentinel defaults

**Files:**
- Modify: `src/uasset_read/serializers/package_summary.py:109-113` (defaults)
- Modify: `src/uasset_read/serializers/package_summary.py:437` (UE4 reader)
- Modify: `src/uasset_read/serializers/package_summary.py:757-762` (UE5 coercion)
- Modify: `src/uasset_read/serializers/package_summary.py:783` (data_resource_offset)
- Add: `tests/test_package_summary_sentinel.py`

**Step 1: Write failing test**

```python
# tests/test_package_summary_sentinel.py
"""验证 PackageFileSummary 在版本缺失时保留 UE sentinel 值。"""
import pytest
from uasset_read.serializers.package_summary import PackageFileSummary


def test_sentinel_preload_dependency_default():
    """PreloadDependency 默认值应为 UE sentinel（absent = -1/0）"""
    s = PackageFileSummary()
    assert s.preload_dependency_count == -1
    assert s.preload_dependency_offset == 0


def test_sentinel_payload_toc_default():
    """PayloadTocOffset 默认值应为 -1（INDEX_NONE）"""
    s = PackageFileSummary()
    assert s.payload_toc_offset == -1


def test_sentinel_data_resource_default():
    """DataResourceOffset 默认值应为 -1（absent）"""
    s = PackageFileSummary()
    assert s.data_resource_offset == -1


def test_sentinel_present_but_empty_not_confused():
    """已存在的空表保持 0，不与 absent 混淆"""
    s = PackageFileSummary()
    s.preload_dependency_count = 0
    assert s.preload_dependency_count == 0
    assert s.preload_dependency_count != -1  # 区分 absent 和 empty


def test_has_preload_dependencies_property():
    """has_preload_dependencies predicate"""
    s = PackageFileSummary()
    assert not s.has_preload_dependencies  # -1 = absent
    s.preload_dependency_count = 0
    assert s.has_preload_dependencies  # 0 = present but empty


def test_has_payload_toc_property():
    """has_payload_toc predicate"""
    s = PackageFileSummary()
    assert not s.has_payload_toc  # -1 = absent
    s.payload_toc_offset = 100
    assert s.has_payload_toc  # >0 = present


def test_has_data_resources_property():
    """has_data_resources predicate"""
    s = PackageFileSummary()
    assert not s.has_data_resources  # -1 = absent
    s.data_resource_offset = 100
    assert s.has_data_resources  # >0 = present
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_package_summary_sentinel.py -v
```

Expected: FAIL — 默认值为 0 不是 -1

**Step 3: Fix PackageFileSummary defaults**

修改 `src/uasset_read/serializers/package_summary.py:109-113`:

```python
    preload_dependency_count: int = -1   # UE sentinel: -1 = absent
    preload_dependency_offset: int = 0   # UE: 0 = absent (与 -1 配合)
    names_referenced_from_export_data_count: int = 0
    payload_toc_offset: int = -1         # UE: INDEX_NONE = -1
    data_resource_offset: int = -1       # UE: -1 = absent
```

**Step 4: Add helper predicates**

在 `PackageFileSummary` 类中（`get_custom_version` 方法之前）添加：

```python
    @property
    def has_preload_dependencies(self) -> bool:
        """是否包含预加载依赖表（区分 absent 和 empty）。"""
        return self.preload_dependency_count >= 0

    @property
    def has_payload_toc(self) -> bool:
        """是否包含 PayloadToc（-1 = absent）。"""
        return self.payload_toc_offset >= 0

    @property
    def has_data_resources(self) -> bool:
        """是否包含 DataResource（-1 = absent）。"""
        return self.data_resource_offset >= 0
```

**Step 5: Fix UE5 payload_toc_offset coercion**

修改 `src/uasset_read/serializers/package_summary.py:757-762`，保留 INDEX_NONE sentinel：

```python
    # Tolerant: payload_toc_offset 负值可能是 INDEX_NONE sentinel
    if payload_toc_offset < 0:
        # -1 是 UE INDEX_NONE sentinel，表示 absent，保留
        # 其他负值视为异常
        if payload_toc_offset != -1:
            logger.warning(
                "PayloadTocOffset 异常负值: %d, 设为 INDEX_NONE (-1)",
                payload_toc_offset,
            )
            payload_toc_offset = -1
        # -1 保留为 sentinel，不 coerce 到 0
```

**Step 6: Fix UE4 reader payload_toc_offset**

修改 `src/uasset_read/serializers/package_summary.py:437`:

```python
        payload_toc_offset=-1,  # UE4 没有 PayloadToc，用 INDEX_NONE sentinel
```

**Step 7: Fix UE5 data_resource_offset absent default**

修改 `src/uasset_read/serializers/package_summary.py:783`:

```python
    data_resource_offset = -1  # 默认 absent，UE sentinel
    if file_version_ue5 >= UE5_DATA_RESOURCES:
        data_resource_offset = archive.read_i32()
```

**Step 8: Run test to verify it passes**

```bash
python -m pytest tests/test_package_summary_sentinel.py -v
```

Expected: All 7 PASS

**Step 9: Run regression**

```bash
python scripts/test_matrix.py all
```

**Step 10: Commit**

```bash
git checkout -b fix/p1-sentinel-preservation develop
git add src/uasset_read/serializers/package_summary.py tests/test_package_summary_sentinel.py
git commit -m "fix: preserve UE sentinel values for absent PackageFileSummary fields (#54)

Set preload_dependency_count=-1, payload_toc_offset=-1, data_resource_offset=-1
as defaults (UE absent sentinels). Remove coercion of negative payload_toc_offset
to 0 which destroyed INDEX_NONE. Add has_* predicate properties.

Closes #54"
```

**Step 11: Merge to develop**

```bash
git checkout develop
git merge --no-ff fix/p1-sentinel-preservation -m "Merge fix/p1-sentinel-preservation into develop"
git branch -d fix/p1-sentinel-preservation
```

---

## Branch 3: verify/p1-export-fields (#43)

### Task 3.1: Verify Export PreloadDependency fields exist

**Files:**
- Verify: `src/uasset_read/serializers/object_resources.py` (export fields)
- Verify: `src/uasset_read/models/core.py` (ExportEntry dataclass)
- Add: `tests/test_export_preload_dependency.py`

**Step 1: Write verification test**

```python
# tests/test_export_preload_dependency.py
"""验证 FObjectExport 缺失字段已正确实现。"""
import pytest


def test_export_entry_has_preload_dependency_fields():
    """ExportEntry 包含所有 PreloadDependency 字段"""
    from uasset_read.models.core import ExportEntry
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ExportEntry)}
    expected = {
        'first_export_dependency',
        'serialization_before_serialization_dependencies',
        'create_before_serialization_dependencies',
        'serialization_before_create_dependencies',
        'create_before_create_dependencies',
    }
    missing = expected - field_names
    assert not missing, f"ExportEntry 缺少字段: {missing}"


def test_export_entry_has_script_serialization_fields():
    """ExportEntry 包含 ScriptSerializationOffset 字段"""
    from uasset_read.models.core import ExportEntry
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ExportEntry)}
    assert 'script_serialization_start_offset' in field_names
    assert 'script_serialization_end_offset' in field_names


def test_export_entry_has_inherited_and_hash_flags():
    """ExportEntry 包含 bIsInheritedInstance 和 bGeneratePublicHash"""
    from uasset_read.models.core import ExportEntry
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ExportEntry)}
    assert 'is_inherited_instance' in field_names
    assert 'generate_public_hash' in field_names


def test_export_preload_default_values():
    """PreloadDependency 默认值正确"""
    from uasset_read.models.core import ExportEntry
    e = ExportEntry(
        class_index=None, super_index=None, template_index=None,
        outer_index=None, object_name="Test", object_flags=0,
        serial_size=0, serial_offset=0,
    )
    assert e.first_export_dependency == -1
    assert e.serialization_before_serialization_dependencies == 0
    assert e.script_serialization_start_offset == 0
    assert e.is_inherited_instance is False
    assert e.generate_public_hash is False
```

**Step 2: Run test to verify it passes**

```bash
python -m pytest tests/test_export_preload_dependency.py -v
```

Expected: All 4 PASS（字段已存在）

**Step 3: Verify JSON output includes new fields**

```bash
python run.py "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" --json 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); e=d.get('exports',[]); print(json.dumps({k:v for k,v in e[0].items() if 'dependency' in k or 'serialization_offset' in k or 'inherited' in k or 'public_hash' in k}, indent=2))" 2>&1
```

Expected: Fields present in JSON output

**Step 4: Mark issue as resolved**

```bash
gh issue close 43 --comment "Verified: Export PreloadDependency fields already implemented in object_resources.py with correct version gating. Tests added to confirm field presence and default values."
```

**Step 5: Commit**

```bash
git checkout -b verify/p1-export-fields develop
git add tests/test_export_preload_dependency.py
git commit -m "test: verify Export PreloadDependency fields already implemented (#43)

Fields confirmed present in ExportEntry dataclass and read_export_map.
Tests added to prevent regression.

Closes #43"
```

**Step 6: Merge to develop**

```bash
git checkout develop
git merge --no-ff verify/p1-export-fields -m "Merge verify/p1-export-fields into develop"
git branch -d verify/p1-export-fields
```

---

## Branch 4: feat/p1-unversioned-parser (#50)

### Task 4.1: Create unversioned_parser module

**Files:**
- Create: `src/uasset_read/parsers/unversioned_parser.py`
- Add: `tests/test_unversioned_parser.py`

**Step 1: Write failing tests**

```python
# tests/test_unversioned_parser.py
"""验证 UnversionedProperties 解析模块。"""
import pytest
from io import BytesIO
from uasset_read.parsers.unversioned_parser import (
    read_unversioned_header,
    parse_unversioned_properties,
    UnversionedHeader,
    UnversionedFragment,
    UnversionedPropertyResult,
)


def _make_archive(data: bytes):
    """从字节创建最小 FArchive 替身。"""
    from unittest.mock import MagicMock
    archive = MagicMock()
    buf = BytesIO(data)
    archive.read_uint16 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(2), 'little'))
    archive.read_uint32 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(4), 'little'))
    archive.read_int32 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(4), 'little', signed=True))
    archive.read_int64 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(8), 'little', signed=True))
    return archive


def test_header_single_keep_fragment():
    """单个 keep 片段 + 终止"""
    # Fragment: keep=3, skip=0, zero=False → raw = (0 << 5) | (3 << 1) | 0 = 6
    # Terminator: keep=0, skip=0, zero=False → raw = 0
    # Validity mask: 0
    data = (0).to_bytes(2, 'little') + (6).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert len(header.fragments) == 2  # keep + terminator
    assert header.fragments[0].keep_count == 3
    assert header.fragments[0].skip_count == 0
    assert not header.fragments[0].is_zero


def test_header_skip_keep_sequence():
    """skip=2, keep=1 片段"""
    # skip=2, keep=1, zero=False → raw = (2 << 5) | (1 << 1) | 0 = 66
    # Terminator: 0
    # Validity mask: 0
    data = (0).to_bytes(2, 'little') + (66).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].skip_count == 2
    assert header.fragments[0].keep_count == 1
    assert not header.fragments[0].is_zero


def test_header_zero_mask():
    """zero flag 设置"""
    # keep=1, zero=True → raw = (0 << 5) | (1 << 1) | 1 = 3
    # Terminator: 0
    data = (0).to_bytes(2, 'little') + (3).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].is_zero
    assert header.fragments[0].keep_count == 1


def test_parse_with_schema_order():
    """按 schema 顺序解析属性"""
    result = parse_unversioned_properties(
        archive=None,  # 需要实际 archive
        header=UnversionedHeader(
            fragments=[UnversionedFragment(keep_count=2)],
            zero_mask=0,
            validity_mask=0,
        ),
        mapping={"PropA": 4, "PropB": 8},
        schema_order=["PropA", "PropB"],
    )
    assert result.fidelity in ("schema_backed", "partial_size_inferred")


def test_parse_missing_mapping_produces_partial():
    """缺少 mapping 时产生 partial fidelity"""
    result = parse_unversioned_properties(
        archive=None,
        header=UnversionedHeader(
            fragments=[UnversionedFragment(keep_count=1)],
            zero_mask=0,
            validity_mask=0,
        ),
        mapping={},  # 空 mapping
        schema_order=["UnknownProp"],
    )
    assert result.fidelity == "opaque_missing_mapping"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_unversioned_parser.py -v
```

Expected: FAIL — module does not exist

**Step 3: Create unversioned_parser.py**

```python
"""UnversionedProperties 解析模块

按 UE FUnversionedHeader/Schema 语义解析 unversioned 属性。
UE 源码基准：UnversionedPropertySerialization.cpp
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Literal

logger = logging.getLogger(__name__)


@dataclass
class UnversionedFragment:
    """FUnversionedHeader 片段

    UE 源码：UnversionedPropertySerialization.cpp:610
    每个片段描述一段 skip/keep 序列。
    """
    skip_count: int = 0
    keep_count: int = 0
    is_zero: bool = False


@dataclass
class UnversionedHeader:
    """FUnversionedHeader 完整结构

    UE 源码：UnversionedPropertySerialization.cpp:978-1009
    """
    fragments: List[UnversionedFragment] = field(default_factory=list)
    zero_mask: int = 0  # bitfield: 1 = skip (zero), 0 = keep
    validity_mask: int = 0


@dataclass
class UnversionedPropertyResult:
    """Unversioned 解析结果"""
    properties: List[dict] = field(default_factory=list)
    fidelity: Literal["schema_backed", "opaque_missing_mapping", "partial_size_inferred"] = "schema_backed"
    unparsed_bytes: int = 0
    diagnostics: List[str] = field(default_factory=list)


def read_unversioned_header(archive) -> UnversionedHeader:
    """读取 FUnversionedHeader

    UE 源码：UnversionedPropertySerialization.cpp:978-1009

    Header 结构：
    - validity_mask: uint16 (bitfield)
    - fragments: 以终止片段结束的 fragment 列表
      - 每个 fragment: uint16
        - bit 0: is_zero (1 = skip/zero)
        - bits 1-4: keep_count (4-bit)
        - bits 5-15: skip_count (12-bit)
    - 终止条件: keep_count == 0 && skip_count == 0
    """
    validity_mask = archive.read_uint16()
    fragments: List[UnversionedFragment] = []

    while True:
        raw = archive.read_uint16()
        is_zero = bool(raw & 1)
        keep_count = (raw >> 1) & 0xF
        skip_count = (raw >> 5) & 0xFFF

        fragments.append(UnversionedFragment(
            skip_count=skip_count,
            keep_count=keep_count,
            is_zero=is_zero,
        ))

        # 终止条件
        if keep_count == 0 and skip_count == 0:
            break

    return UnversionedHeader(
        fragments=fragments,
        zero_mask=validity_mask,
        validity_mask=validity_mask,
    )


def parse_unversioned_properties(
    archive,
    header: UnversionedHeader,
    mapping: dict,
    schema_order: list,
) -> UnversionedPropertyResult:
    """按 schema 顺序解析 unversioned 属性

    UE 源码：UnversionedPropertySerialization.cpp:978-1009

    Args:
        archive: FArchive 实例
        header: 解析后的 header
        mapping: property name → size 映射
        schema_order: schema 定义的属性顺序（属性索引映射）

    Returns:
        UnversionedPropertyResult: 解析结果，含 fidelity 诊断
    """
    properties = []
    diagnostics = []
    fidelity = "schema_backed"
    schema_idx = 0  # 在 schema_order 中的当前位置

    for fragment in header.fragments:
        # Skip 片段：跳过 skip_count 个属性
        schema_idx += fragment.skip_count

        # Zero 片段：标记为零值
        if fragment.is_zero:
            for i in range(fragment.keep_count):
                if schema_idx < len(schema_order):
                    prop_name = schema_order[schema_idx]
                    properties.append({
                        "name": prop_name,
                        "value": None,
                        "is_zero": True,
                    })
                    schema_idx += 1
            continue

        # Keep 片段：需要从 archive 读取
        for i in range(fragment.keep_count):
            if schema_idx >= len(schema_order):
                fidelity = "opaque_missing_mapping"
                diagnostics.append(
                    f"Schema index {schema_idx} >= schema_order length {len(schema_order)}"
                )
                break

            prop_name = schema_order[schema_idx]
            prop_size = mapping.get(prop_name)

            if prop_size is None:
                fidelity = "opaque_missing_mapping"
                diagnostics.append(f"Missing mapping for property '{prop_name}'")
                properties.append({
                    "name": prop_name,
                    "value": None,
                    "missing_mapping": True,
                })
            elif archive is not None:
                # 读取属性数据
                raw_bytes = archive.read_bytes(prop_size)
                properties.append({
                    "name": prop_name,
                    "raw_bytes": raw_bytes.hex(),
                    "size": prop_size,
                })
            else:
                fidelity = "partial_size_inferred"
                properties.append({
                    "name": prop_name,
                    "size": prop_size,
                    "no_archive": True,
                })

            schema_idx += 1

    return UnversionedPropertyResult(
        properties=properties,
        fidelity=fidelity,
        diagnostics=diagnostics,
    )
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_unversioned_parser.py -v
```

Expected: All 5 PASS

**Step 5: Run regression**

```bash
python -m pytest tests/ -v --timeout=60
```

**Step 6: Commit**

```bash
git checkout -b feat/p1-unversioned-parser develop
git add src/uasset_read/parsers/unversioned_parser.py tests/test_unversioned_parser.py
git commit -m "feat: add UnversionedProperties parser with UE fidelity diagnostics (#50)

New module implementing FUnversionedHeader/Schema parsing per UE
UnversionedPropertySerialization.cpp. Includes fragment parsing,
schema-order binding, and fidelity diagnostics (schema_backed,
opaque_missing_mapping, partial_size_inferred).

Closes #50"
```

**Step 7: Merge to develop**

```bash
git checkout develop
git merge --no-ff feat/p1-unversioned-parser -m "Merge feat/p1-unversioned-parser into develop"
git branch -d feat/p1-unversioned-parser
```

---

## Branch 5: docs/p1-class-serialization-ue (#24)

### Task 5.1: Create UE source basis document

**Files:**
- Add: `docs/designs/class-serialization-strategy-ue-basis.md`
- Verify: `src/uasset_read/parsers/class_serialization_strategy.py` (already has refs)

**Step 1: Verify existing source references**

```bash
grep -n "UE 源码" src/uasset_read/parsers/class_serialization_strategy.py | head -20
```

Expected: Each class has UE source file:line reference

**Step 2: Create design document**

```bash
mkdir -p docs/designs
```

创建 `docs/designs/class-serialization-strategy-ue-basis.md`，内容包含：

```markdown
# Class Serialization Strategy — UE 源码依据

## 概述

本文档记录 `src/uasset_read/parsers/class_serialization_strategy.py` 中每个分类的 UE C++ 源码证据。

源码根目录：`E:\Develop\lib\UnrealEngine`

## TAGGED_PROPERTIES_ONLY

仅依赖 `UStruct::SerializeTaggedProperties()` 的通用属性解析。

| 类 | UE 源码 | Serialize 策略 | 说明 |
|----|---------|---------------|------|
| UBlueprintGeneratedClass | BlueprintGeneratedClass.cpp:2595 | Super::Serialize + 自定义字段 | 当前仅读 tagged properties，自定义字段未解析 |
| UWidgetBlueprintGeneratedClass | 同上变体 | Super::Serialize | 同上 |
| UFunction | Field.cpp | 标准 tagged properties | 函数签名数据通过 tagged properties |
| UUserDefinedStruct | UserDefinedStruct.cpp | 标准 tagged properties | 用户定义结构体 |
| UEdGraph | EdGraph.cpp | 标准 tagged properties | 编辑器图数据 |

## OPAQUE_CLASS_PAYLOAD

有自定义 `Serialize()` 方法，当前未实现完整反序列化。

| 类 | UE 源码 | 自定义 Serialize 内容 | 当前状态 |
|----|---------|---------------------|---------|
| UStaticMesh | StaticMesh.cpp:7195 | BulkData, LODInfo | partial_metadata |
| USkeletalMesh | SkeletalMesh.cpp:567 | LOD, RefSkeleton | partial_metadata |
| UTexture2D | Texture2D.cpp:462 | Strip flags, cooked data | partial_metadata |
| UMaterial | Material.cpp:234 | Expressions | partial_metadata |
| UMaterialInstanceConstant | MaterialInstance.cpp:456 | Scalar/Vector/Texture params | partial_metadata |
| UAnimSequence | AnimSequence.cpp:609 | CompressedByteStream | partial_metadata |
| USoundWave | SoundWave.cpp:1199 | CompressedFormatData | partial_metadata |

## SKIP_UNSUPPORTED

已知不支持或读取会导致问题。

| 类 | UE 源码 | 跳过原因 |
|----|---------|---------|
| UNiagaraGraph | NiagaraGraph.cpp | 节点格式复杂 |
| UNiagaraScript | NiagaraScript.cpp | 字节码格式未解析 |
| UNiagaraDataInterface | NiagaraDataInterface.cpp | 接口数据格式未定义 |

## 版本差异

### Editor-only vs Cooked

- Editor-only 资产包含完整 tagged properties
- Cooked 资产的 class-specific payload 已被烘焙，但 tagged properties 仍可读

### UE4 vs UE5

- 部分类的 `Serialize()` 方法签名在 UE4/UE5 间有差异
- UE5 新增了 `bIsInheritedInstance` 等字段
```

**Step 3: Commit**

```bash
git checkout -b docs/p1-class-serialization-ue develop
git add docs/designs/class-serialization-strategy-ue-basis.md
git commit -m "docs: add UE source basis for class serialization strategy (#24)

Document UE C++ source references for each class serialization strategy
classification (TAGGED_PROPERTIES_ONLY, OPAQUE_CLASS_PAYLOAD,
SKIP_UNSUPPORTED).

Closes #24"
```

**Step 4: Merge to develop**

```bash
git checkout develop
git merge --no-ff docs/p1-class-serialization-ue -m "Merge docs/p1-class-serialization-ue into develop"
git branch -d docs/p1-class-serialization-ue
```

---

## Branch 6: test/p1-acceptance-strengthening (#25)

### Task 6.1: Strengthen acceptance test assertions

**Files:**
- Modify: `tests/test_acceptance.py`
- Add: `tests/test_acceptance_field_level.py`

**Step 1: Audit current test quality**

```bash
grep -n "or True\|assert True\|== True" tests/test_acceptance.py
```

Expected: 无结果（无恒真断言）

```bash
grep -n "assert.*in.*or.*in" tests/test_acceptance.py
```

Expected: 检查弱断言模式

**Step 2: Create field-level acceptance tests**

```python
# tests/test_acceptance_field_level.py
"""字段级 acceptance 测试 — 验证输出内容正确性。"""
import json
import os
import pytest
from uasset_read.core import parse_single

SAMPLES = os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples")
FIRST_PERSON_BP = os.path.join(
    SAMPLES, "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)
_has_bp = os.path.isfile(FIRST_PERSON_BP)


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestJsonFieldLevel:
    """JSON 输出字段级断言"""

    def test_json_has_required_sections(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        assert "summary" in data
        assert "exports" in data
        assert "name_map" in data

    def test_json_summary_has_key_fields(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        summary = data["summary"]
        assert summary.get("package_name") is not None
        assert summary.get("export_count", 0) >= 1
        assert summary.get("import_count", 0) >= 1

    def test_json_exports_have_required_fields(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        for export in data["exports"]:
            assert "object_name" in export
            assert "class_name" in export
            assert "serial_size" in export


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestBlueprintTextFieldLevel:
    """blueprint-text 输出字段级断言"""

    def test_contains_event_graph_nodes(self):
        output = parse_single(FIRST_PERSON_BP, format="blueprint-text", tolerant=True)
        # 至少包含事件节点标记
        assert "Event" in output or "K2Node" in output

    def test_output_not_empty_and_reasonable(self):
        output = parse_single(FIRST_PERSON_BP, format="blueprint-text", tolerant=True)
        assert len(output) > 200  # 不是空/极短输出


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestCppSkeletonFieldLevel:
    """cpp-skeleton 输出字段级断言"""

    def test_contains_class_declaration(self):
        output = parse_single(FIRST_PERSON_BP, format="cpp-skeleton", tolerant=True)
        assert "class" in output.lower()

    def test_contains_function_definitions(self):
        output = parse_single(FIRST_PERSON_BP, format="cpp-skeleton", tolerant=True)
        assert "void" in output  # 至少有 void 函数


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestStatusConsistency:
    """状态一致性"""

    def test_json_status_field_present(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data
        status = data["status"]
        assert isinstance(status, dict)
        assert status.get("status") in ("success", "partial", "failed")
```

**Step 3: Run new tests**

```bash
python -m pytest tests/test_acceptance_field_level.py -v
```

Expected: All PASS

**Step 4: Run original acceptance tests**

```bash
python -m pytest tests/test_acceptance.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git checkout -b test/p1-acceptance-strengthening develop
git add tests/test_acceptance_field_level.py
git commit -m "test: add field-level acceptance assertions (#25)

Add tests verifying JSON structure, blueprint-text content,
cpp-skeleton structure, and status consistency.

Closes #25"
```

**Step 6: Merge to develop**

```bash
git checkout develop
git merge --no-ff test/p1-acceptance-strengthening -m "Merge test/p1-acceptance-strengthening into develop"
git branch -d test/p1-acceptance-strengthening
```

---

## 执行顺序

```
1. fix/p1-status-unification    (#49) — 最小改动，立即生效
2. fix/p1-sentinel-preservation (#54) — 依赖 #49 的状态定义
3. verify/p1-export-fields      (#43) — 验证已有代码
4. feat/p1-unversioned-parser   (#50) — 新模块，最大 task
5. docs/p1-class-serialization-ue (#24) — 文档，可并行
6. test/p1-acceptance-strengthening (#25) — 最后执行
```

## 验收标准

- [ ] 每个分支的测试全部通过
- [ ] `python scripts/test_matrix.py all` 在 develop 上全量通过
- [ ] 6 个 branches 全部合并到 develop
- [ ] 6 个 GitHub issues 全部关闭
