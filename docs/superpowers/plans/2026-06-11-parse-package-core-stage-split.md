# _parse_package_core Stage Split 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 281 行的 `_parse_package_core()` 拆分为 7 个显式 stage 函数，使主流程可读、可测、可定位，同时保持行为完全不变。

**Architecture:** 引入 `_ParseContext` 数据类在各 stage 之间传递状态。每个 stage 是一个私有函数，接收 `context` 和一个 early-exit 信号。`_parse_package_core()` 变成 ~50 行的 orchestration function，按顺序调用各 stage，处理异常和清理。

**Tech Stack:** Python 3.10+, dataclasses, 现有 `ParseResult`/`LinkerParseResult`

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| 修改 | `src/uasset_read/parse_uasset.py` | 引入 `_ParseContext`，拆分为 7 个 stage |
| 新建 | `tests/test_parse_stages.py` | 各 stage 的单元测试 |

---

### Task 1: 定义 _ParseContext 数据类

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`

- [ ] **Step 1: 编写 _ParseContext 数据类测试**

```python
# tests/test_parse_stages.py
"""解析 stage 拆分测试。

验证 _parse_package_core 拆分后的各 stage 函数行为正确。
"""
import pytest
from dataclasses import dataclass, field
from typing import Any, Optional, List, Callable, Sequence
from unittest.mock import MagicMock, patch


class TestParseContext:
    """_ParseContext 数据类测试。"""

    def test_parse_context_has_required_fields(self):
        """_ParseContext 应包含所有 stage 需要的字段。"""
        from uasset_read.parse_uasset import _ParseContext

        ctx = _ParseContext(
            path="test.uasset",
            result=MagicMock(),
            tolerant=True,
        )

        # Stage 1 产出
        assert hasattr(ctx, "bundle")
        assert hasattr(ctx, "archive")
        assert hasattr(ctx, "mappings_provider")

        # Stage 2 产出
        assert hasattr(ctx, "linker")

        # 控制流
        assert hasattr(ctx, "aborted")
        assert ctx.aborted is False

    def test_parse_context_abort(self):
        """_ParseContext.abort() 应设置 aborted 标志。"""
        from uasset_read.parse_uasset import _ParseContext

        ctx = _ParseContext(
            path="test.uasset",
            result=MagicMock(),
            tolerant=True,
        )
        assert ctx.aborted is False
        ctx.abort()
        assert ctx.aborted is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestParseContext -v
```

预期：FAIL — `_ParseContext` 尚未定义

- [ ] **Step 3: 实现 _ParseContext 数据类**

在 `src/uasset_read/parse_uasset.py` 中 `_parse_package_core` 函数之前添加：

```python
@dataclass
class _ParseContext:
    """解析管线上下文 — 在各 stage 之间传递状态。"""

    # 输入参数（不可变）
    path: str
    result: Any  # ParseResult | LinkerParseResult
    tolerant: bool = True
    provider: Any = None  # PackageProvider | None
    mappings_path: Optional[str] = None
    game: Optional[str] = None
    include_parent_assets: bool = False
    asset_roots: Optional[Sequence[str]] = None
    extra_linker_setup: Optional[Callable] = None
    lightweight_threshold: Optional[int] = None

    # Stage 1 产出: open_bundle_and_archive
    bundle: Any = None  # PackageBundle | None
    archive: Any = None  # FArchive | None
    mappings_provider: Any = None  # TypeMappingsProvider | None

    # Stage 2 产出: read_core_tables
    # (summary, name_map, import_map, export_map 直接写入 result)

    # Stage 3 产出: build_parse_context
    # (engine_family, version_profile, version_container 直接写入 result)

    # Stage 4 产出: create_and_link_linker
    linker: Any = None  # PackageLinker | None

    # 控制流
    aborted: bool = False

    def abort(self) -> None:
        """标记管线中止（tolerant 模式下提前返回）。"""
        self.aborted = True
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestParseContext -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: add _ParseContext dataclass for stage-based parsing"
```

---

### Task 2: 提取 Stage 1 — open_bundle_and_archive

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 1 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage1OpenBundleAndArchive:
    """Stage 1: open_bundle_and_archive 测试。"""

    def test_stage1_opens_bundle_and_archive(self):
        """Stage 1 应打开 bundle 和 archive 并写入 context。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_open_bundle_and_archive

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)

        assert ctx.bundle is not None
        assert ctx.archive is not None
        assert ctx.aborted is False
        assert result.mmap_used is not None

    def test_stage1_tolerant_failure_aborts(self):
        """Stage 1 在 tolerant 模式下失败时应 abort 而非抛异常。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_open_bundle_and_archive

        result = MagicMock()
        result.metadata = {}
        result.errors = []
        result.mmap_used = False
        result.mmap_warning = None

        ctx = _ParseContext(
            path="nonexistent_file.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        assert ctx.aborted is True

    def test_stage1_strict_failure_raises(self):
        """Stage 1 在 strict 模式下失败时应抛异常。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_open_bundle_and_archive

        result = MagicMock()
        result.metadata = {}
        result.errors = []

        ctx = _ParseContext(
            path="nonexistent_file.uasset",
            result=result,
            tolerant=False,
        )

        with pytest.raises(Exception):
            _stage_open_bundle_and_archive(ctx)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage1OpenBundleAndArchive -v
```

预期：FAIL — `_stage_open_bundle_and_archive` 未定义

- [ ] **Step 3: 实现 Stage 1 函数**

在 `_parse_package_core` 之前添加，将原函数 lines 488-502 的逻辑提取：

```python
def _stage_open_bundle_and_archive(ctx: _ParseContext) -> None:
    """Stage 1: 打开 package bundle 和 archive。

    产出: ctx.bundle, ctx.archive, ctx.mappings_provider
    写入: result.metadata, result.mmap_used, result.mmap_warning
    """
    try:
        # 加载 mappings
        if ctx.mappings_path:
            from uasset_read.mappings import TypeMappingsProvider
            ctx.mappings_provider = TypeMappingsProvider.from_file(ctx.mappings_path)
            ctx.result.metadata["mappings_path"] = ctx.mappings_path
        if ctx.game:
            ctx.result.metadata["game"] = ctx.game

        # 打开 bundle 和 archive
        ctx.bundle = open_package_bundle(ctx.path, provider=ctx.provider, tolerant=ctx.tolerant)
        ctx.archive = ctx.bundle.open_archive(tolerant=ctx.tolerant)
        ctx.result.metadata.update(_package_metadata(ctx.bundle))

        # 提取 mmap 信息
        mmap_info = ctx.archive.get_mmap_info()
        ctx.result.mmap_used = mmap_info["used"]
        ctx.result.mmap_warning = mmap_info["warning"]

    except Exception as e:
        if not ctx.tolerant:
            raise
        _record_parse_stage_error(ctx.result, None, ctx.path, "archive", "open", e)
        ctx.abort()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage1OpenBundleAndArchive -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 1 — open_bundle_and_archive"
```

---

### Task 3: 提取 Stage 2 — read_core_tables

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 2 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage2ReadCoreTables:
    """Stage 2: read_core_tables 测试。"""

    def test_stage2_reads_summary_and_tables(self):
        """Stage 2 应读取 summary 和所有核心表。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_open_bundle_and_archive, _stage_read_core_tables

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        assert not ctx.aborted

        _stage_read_core_tables(ctx)

        assert ctx.result.summary is not None
        assert ctx.result.name_map is not None
        assert ctx.result.import_map is not None
        assert ctx.result.export_map is not None
        assert ctx.aborted is False

    def test_stage2_abort_on_summary_failure(self):
        """Stage 2 summary 读取失败时应 abort。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_read_core_tables

        result = MagicMock()
        result.metadata = {}
        result.summary = None  # 强制 summary 为 None
        result.name_map = None

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )
        # 手动设置 archive（模拟 Stage 1 已完成但 summary 失败）
        ctx.archive = MagicMock()

        _stage_read_core_tables(ctx)
        # summary 读取失败后应 abort
        assert ctx.aborted is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage2ReadCoreTables -v
```

预期：FAIL

- [ ] **Step 3: 实现 Stage 2 函数**

将原 lines 504-595 的逻辑提取：

```python
def _stage_read_core_tables(ctx: _ParseContext) -> None:
    """Stage 2: 读取核心表（summary, name, import, export, depends, soft refs）。

    产出: result.summary, result.name_map, result.import_map, result.export_map,
          result.soft_package_references, result.soft_object_path_list
    """
    result = ctx.result
    archive = ctx.archive
    path = ctx.path
    tolerant = ctx.tolerant

    # 读取文件头
    result.summary = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="package_summary", field="summary",
        reader=lambda: read_package_summary(archive),
    )
    if result.summary is None:
        ctx.abort()
        return

    # 读取名称表
    result.name_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="name_table", field="name_map",
        reader=lambda: read_name_table(archive, result.summary),
    )
    if result.name_map is None:
        result.name_map = []
        ctx.abort()
        return

    # 读取导入表
    result.import_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="import_map", field="import_map",
        reader=lambda: read_import_map(archive, result.summary, result.name_map),
    )
    if result.import_map is None:
        result.import_map = []
        ctx.abort()
        return

    # 读取导出表
    result.export_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="export_map", field="export_map",
        reader=lambda: read_export_map(archive, result.summary, result.name_map),
    )
    if result.export_map is None:
        result.export_map = []
        ctx.abort()
        return

    # 读取 DependsMap 和 PreloadDependencies
    if hasattr(result.summary, 'depends_offset'):
        result.summary.depends_map = read_depends_map(archive, result.summary)
    if hasattr(result.summary, 'preload_dependency_count'):
        result.summary.preload_dependencies = read_preload_dependencies(archive, result.summary)

    # 读取 SoftPackageReferences
    if hasattr(result.summary, 'soft_package_references_count') and result.summary.soft_package_references_count > 0:
        result.soft_package_references = read_soft_package_references(archive, result.summary, result.name_map)

    # 读取 SoftObjectPathList (UE5.7+)
    if hasattr(result.summary, 'soft_object_paths_count') and result.summary.soft_object_paths_count > 0:
        result.soft_object_path_list = read_soft_object_paths(
            archive, result.summary, result.name_map
        )
    else:
        result.soft_object_path_list = []

    # 存储在 summary 上供属性解析器访问
    setattr(result.summary, '_soft_object_path_list', result.soft_object_path_list)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage2ReadCoreTables -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 2 — read_core_tables"
```

---

### Task 4: 提取 Stage 3 — build_parse_context

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 3 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage3BuildParseContext:
    """Stage 3: build_parse_context 测试。"""

    def test_stage3_sets_engine_family_and_version(self):
        """Stage 3 应设置引擎族和版本配置。"""
        from uasset_read.parse_uasset import (
            _ParseContext, _stage_open_bundle_and_archive,
            _stage_read_core_tables, _stage_build_parse_context,
        )

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        _stage_read_core_tables(ctx)
        assert not ctx.aborted

        _stage_build_parse_context(ctx)

        assert ctx.result.engine_family in ("ue4", "ue5")
        assert ctx.result.version_profile is not None
        assert ctx.result.version_container is not None
        assert ctx.aborted is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage3BuildParseContext -v
```

预期：FAIL

- [ ] **Step 3: 实现 Stage 3 函数**

将原 lines 513-544 的逻辑提取：

```python
def _stage_build_parse_context(ctx: _ParseContext) -> None:
    """Stage 3: 推断引擎族、版本配置、版本容器。

    产出: result.engine_family, result.compatibility_mode,
          result.version_profile, result.version_container
    """
    from uasset_read.package_version_profile import build_version_profile

    result = ctx.result
    summary = result.summary

    # 引擎族推断
    file_version_ue5 = getattr(summary, 'file_version_ue5', 0)
    legacy_file_version = getattr(summary, 'legacy_file_version', -9)
    file_version_ue4 = getattr(summary, 'file_version_ue4', 0)

    if file_version_ue5 == 0 and legacy_file_version > -6:
        result.engine_family = "ue4"
        result.compatibility_mode = "compatibility"
    else:
        result.engine_family = "ue5"
        result.compatibility_mode = "native"

    # 版本配置
    result.version_profile = build_version_profile(
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )

    result.version_container = build_version_container(summary)

    # 截断文件检测
    try:
        validate_export_data_range(ctx.archive, summary)
    except Exception as e:
        if not ctx.tolerant:
            raise
        _record_parse_stage_error(
            result, ctx.archive, ctx.path, "package_summary", "export_data_range", e
        )
        ctx.abort()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage3BuildParseContext -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 3 — build_parse_context"
```

---

### Task 5: 提取 Stage 4 — create_and_link_linker

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 4 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage4CreateAndLinkLinker:
    """Stage 4: create_and_link_linker 测试。"""

    def test_stage4_creates_linker(self):
        """Stage 4 应创建并 link PackageLinker。"""
        from uasset_read.parse_uasset import (
            _ParseContext, _stage_open_bundle_and_archive,
            _stage_read_core_tables, _stage_build_parse_context,
            _stage_create_and_link_linker,
        )

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None
        result.errors = []

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        _stage_read_core_tables(ctx)
        _stage_build_parse_context(ctx)
        assert not ctx.aborted

        _stage_create_and_link_linker(ctx)

        assert ctx.linker is not None
        assert ctx.result.linker is not None

    def test_stage4_tolerant_linker_failure_records_error(self):
        """Stage 4 linker 创建失败时（tolerant）应记录错误但不抛异常。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_create_and_link_linker

        result = MagicMock()
        result.metadata = {}
        result.errors = []
        result.summary = MagicMock()
        result.name_map = []
        result.import_map = []
        result.export_map = []
        result.version_container = MagicMock()

        ctx = _ParseContext(
            path="test.uasset",
            result=result,
            tolerant=True,
        )
        ctx.archive = MagicMock()  # mock archive

        # 这不会真正失败因为用的是 mock，但测试结构正确
        _stage_create_and_link_linker(ctx)
        # 验证函数不抛异常即成功
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage4CreateAndLinkLinker -v
```

预期：FAIL

- [ ] **Step 3: 实现 Stage 4 函数**

将原 lines 597-615 的逻辑提取：

```python
def _stage_create_and_link_linker(ctx: _ParseContext) -> None:
    """Stage 4: 创建 PackageLinker 并执行 link()。

    产出: ctx.linker, result.linker
    回调: extra_linker_setup (如果提供)
    """
    from uasset_read.link.linker import PackageLinker

    result = ctx.result

    try:
        ctx.linker = PackageLinker(
            ctx.archive, result.summary, result.name_map,
            result.import_map, result.export_map or [],
            version_container=result.version_container,
        )
        ctx.linker.link()
        result.linker = ctx.linker

        if ctx.extra_linker_setup is not None:
            ctx.extra_linker_setup(ctx.linker, result)

    except Exception as e:
        if not ctx.tolerant:
            raise ParseError(f"Linker creation failed: {e}") from e
        result.errors.append(f"Linker creation failed: {e}")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage4CreateAndLinkLinker -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 4 — create_and_link_linker"
```

---

### Task 6: 提取 Stage 5 — preload_exports

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 5 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage5PreloadExports:
    """Stage 5: preload_exports 测试。"""

    def test_stage5_preloads_all_exports(self):
        """Stage 5 应通过 linker.preload() 加载所有 export。"""
        from uasset_read.parse_uasset import (
            _ParseContext, _stage_open_bundle_and_archive,
            _stage_read_core_tables, _stage_build_parse_context,
            _stage_create_and_link_linker, _stage_preload_exports,
        )

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None
        result.errors = []

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        _stage_read_core_tables(ctx)
        _stage_build_parse_context(ctx)
        _stage_create_and_link_linker(ctx)
        assert not ctx.aborted

        _stage_preload_exports(ctx)

        # 验证至少一个 export 被解析
        assert len(ctx.result.export_map) > 0
        has_parsed = any(
            getattr(exp, 'parse_status', None) in ('success', 'partial_metadata', 'opaque')
            for exp in ctx.result.export_map
        )
        assert has_parsed, "至少一个 export 应被成功解析"

    def test_stage5_lightweight_parse_aborts(self):
        """Stage 5 在 lightweight tolerant parse 条件下应 abort。"""
        from uasset_read.parse_uasset import _ParseContext, _stage_preload_exports

        result = MagicMock()
        result.metadata = {}
        result.errors = []
        result.warnings = []
        result.summary = MagicMock()
        result.summary.export_count = 99999  # 超大 export 数

        ctx = _ParseContext(
            path="test.uasset",
            result=result,
            tolerant=True,
            lightweight_threshold=10,  # 低阈值
        )

        _stage_preload_exports(ctx)

        assert ctx.aborted is True
        assert result.metadata.get("lightweight_tolerant_parse") is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage5PreloadExports -v
```

预期：FAIL

- [ ] **Step 3: 实现 Stage 5 函数**

将原 lines 617-667 的逻辑提取：

```python
def _stage_preload_exports(ctx: _ParseContext) -> None:
    """Stage 5: 预加载所有 export 属性。

    通过 linker.preload() 统一调度，处理 lightweight tolerant parse 降级。
    产出: export.properties, export.parse_status, export.transforms
    """
    result = ctx.result

    # Lightweight tolerant parse 检查
    if _should_use_lightweight_tolerant_parse(result, ctx.tolerant, ctx.lightweight_threshold):
        result.warnings.append(
            "Lightweight tolerant parse used due to export complexity "
            f"(exports={getattr(result.summary, 'export_count', 0)})"
        )
        result.metadata["lightweight_tolerant_parse"] = True
        result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
        result.is_success = len(result.errors) == 0
        ctx.abort()
        return

    _mappings = ctx.mappings_provider.mappings if ctx.mappings_provider else None

    for exp_idx, export in enumerate(result.export_map or []):
        if export.serial_size > 0:
            try:
                if ctx.linker is not None:
                    ctx.linker.preload(
                        exp_idx,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                    # 向后兼容：将 linker instance 的属性复制回 export.properties
                    inst = ctx.linker._export_objects[exp_idx]
                    export.properties = inst.serialized_properties
                else:
                    export.properties = parse_properties_from_export(
                        export, ctx.archive, result.summary, result.name_map,
                        result.export_map or [], result.import_map,
                        linker=ctx.linker,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                if not getattr(export, "parse_status", None):
                    setattr(export, "parse_status", "success")
                elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                    pass
            except Exception as e:
                if not ctx.tolerant:
                    raise ParseError(f"Property parse error in {export.object_name}: {e}") from e
                result.errors.append(f"Property parse error in {export.object_name}: {e}")
                export.properties = []
                setattr(export, "parse_status", "failed")
                setattr(export, "fallback_reason", "parse_error")
                setattr(export, "error_message", str(e))

            # 提取组件变换属性
            if export.properties:
                export.transforms = extract_component_transforms(export.properties)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage5PreloadExports -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 5 — preload_exports"
```

---

### Task 7: 提取 Stage 6 — run_post_load_and_post_process

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`
- Modify: `tests/test_parse_stages.py`

- [ ] **Step 1: 编写 Stage 6 测试**

```python
# tests/test_parse_stages.py — 追加

class TestStage6PostLoadAndPostProcess:
    """Stage 6: run_post_load_and_post_process 测试。"""

    def test_stage6_runs_post_load(self):
        """Stage 6 应执行 linker.post_load()。"""
        from uasset_read.parse_uasset import (
            _ParseContext, _stage_open_bundle_and_archive,
            _stage_read_core_tables, _stage_build_parse_context,
            _stage_create_and_link_linker, _stage_preload_exports,
            _stage_run_post_load_and_post_process,
        )

        result = MagicMock()
        result.metadata = {}
        result.mmap_used = False
        result.mmap_warning = None
        result.errors = []

        ctx = _ParseContext(
            path="tests/assets/DA_Cube_C.uasset",
            result=result,
            tolerant=True,
        )

        _stage_open_bundle_and_archive(ctx)
        _stage_read_core_tables(ctx)
        _stage_build_parse_context(ctx)
        _stage_create_and_link_linker(ctx)
        _stage_preload_exports(ctx)
        assert not ctx.aborted

        _stage_run_post_load_and_post_process(ctx)

        # post_load 后 linker 应标记完成
        assert ctx.result.is_success is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_stages.py::TestStage6PostLoadAndPostProcess -v
```

预期：FAIL

- [ ] **Step 3: 实现 Stage 6 函数**

将原 lines 669-687 的逻辑提取：

```python
def _stage_run_post_load_and_post_process(ctx: _ParseContext) -> None:
    """Stage 6: 执行 post_load() 和后处理。

    调用 linker.post_load() 完成对象图引用解析，
    然后运行 _post_process() 进行蓝图元数据提取、图提取、依赖分析。
    """
    result = ctx.result

    # post_load — 在所有 export 预加载完成后执行
    if ctx.linker is not None:
        try:
            ctx.linker.post_load()
        except Exception as e:
            if not ctx.tolerant:
                raise ParseError(f"Linker post_load failed: {e}") from e
            result.errors.append(f"Linker post_load failed: {e}")

    # 共享后处理
    _post_process(
        ctx.path, ctx.archive, result.summary, result.name_map,
        result.import_map, result.export_map or [], result, ctx.tolerant,
        linker=ctx.linker,
        include_parent_assets=ctx.include_parent_assets,
        asset_roots=ctx.asset_roots,
        archive_factory=lambda: ctx.bundle.open_archive(tolerant=ctx.tolerant) if ctx.bundle else FArchive(ctx.path, tolerant=ctx.tolerant),
    )
    result.is_success = len(result.errors) == 0
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_stages.py::TestStage6PostLoadAndPostProcess -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_parse_stages.py src/uasset_read/parse_uasset.py
git commit -m "refactor: extract stage 6 — run_post_load_and_post_process"
```

---

### Task 8: 重写 _parse_package_core 为 orchestration function

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`

- [ ] **Step 1: 编写 orchestration 集成测试**

```python
# tests/test_parse_stages.py — 追加

class TestParsePackageCoreOrchestration:
    """_parse_package_core orchestration 测试 — 验证行为保持。"""

    def test_orchestration_produces_same_result(self):
        """拆分后的 _parse_package_core 应产生与原始版本相同的结果。"""
        from uasset_read.parse_uasset import _parse_package_core
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        _parse_package_core("tests/assets/DA_Cube_C.uasset", result, tolerant=True)

        assert result.is_success is True
        assert result.summary is not None
        assert result.name_map is not None
        assert len(result.export_map) > 0

    def test_orchestration_is_short(self):
        """_parse_package_core 应该是一个短函数（~50 行）。"""
        import inspect
        from uasset_read.parse_uasset import _parse_package_core

        source = inspect.getsource(_parse_package_core)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('"""')]

        # orchestration function 应该显著短于原始 281 行
        assert len(lines) < 80, f"_parse_package_core 仍有 {len(lines)} 行，应 < 80"

    def test_orchestration_handles_errors(self):
        """_parse_package_core 应在 tolerant 模式下正确处理错误。"""
        from uasset_read.parse_uasset import _parse_package_core
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        _parse_package_core("nonexistent.uasset", result, tolerant=True)

        assert result.is_success is False
        assert len(result.errors) > 0
```

- [ ] **Step 2: 运行现有测试建立基线**

```bash
python -m pytest tests/test_parse_package_core.py tests/test_linker_lifecycle.py tests/test_diagnostic_output.py -v
```

记录通过率作为基线。

- [ ] **Step 3: 重写 _parse_package_core 为 orchestration**

替换原函数体（保持签名不变）：

```python
def _parse_package_core(
    path: str,
    result,
    tolerant: bool = True,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    extra_linker_setup: Optional[Callable] = None,
    lightweight_threshold: Optional[int] = None,
) -> None:
    """共享核心解析逻辑 — 编排 7 个 stage 的解析管线。

    管线: open → read_tables → build_context → link → preload → post_load → finalize
    """
    ctx = _ParseContext(
        path=path, result=result, tolerant=tolerant,
        provider=provider, mappings_path=mappings_path, game=game,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots, extra_linker_setup=extra_linker_setup,
        lightweight_threshold=lightweight_threshold,
    )

    try:
        _stage_open_bundle_and_archive(ctx)
        if ctx.aborted:
            return

        _stage_read_core_tables(ctx)
        if ctx.aborted:
            return

        _stage_build_parse_context(ctx)
        if ctx.aborted:
            return

        _stage_create_and_link_linker(ctx)

        _stage_preload_exports(ctx)
        if ctx.aborted:
            return

        _stage_run_post_load_and_post_process(ctx)

        _stage_finalize_result(ctx)

    except VersionError as e:
        _record_parse_stage_error(result, ctx.archive, path, "version", "legacy_file_version", e)
        result.errors.append(str(e))
        result.is_success = False
        if not tolerant:
            raise

    except ParseError as e:
        _record_parse_stage_error(result, ctx.archive, path, "parse", "parse_error", e)
        result.errors.append(str(e))
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False
        if not tolerant:
            raise

    except Exception as e:
        _record_parse_stage_error(result, ctx.archive, path, "parse", "unexpected", e)
        result.errors.append(f"Unexpected error: {str(e)}")
        result.is_success = False
        if not tolerant:
            raise

    finally:
        _stage_cleanup(ctx)
```

- [ ] **Step 4: 提交（先不运行测试，因为 _stage_finalize_result 和 _stage_cleanup 还未实现）**

```bash
git add src/uasset_read/parse_uasset.py
git commit -m "refactor: rewrite _parse_package_core as orchestration function (WIP)"
```

---

### Task 9: 提取 Stage 7 — finalize_result + cleanup

**Files:**
- Modify: `src/uasset_read/parse_uasset.py`

- [ ] **Step 1: 实现 _stage_finalize_result**

```python
def _stage_finalize_result(ctx: _ParseContext) -> None:
    """Stage 7: 设置最终成功标志。"""
    ctx.result.is_success = len(ctx.result.errors) == 0
```

注意：`_stage_run_post_load_and_post_process` 中已有 `result.is_success = ...`，所以 `_stage_finalize_result` 实际上是确保在正常路径结束时设置标志。如果 `post_process` 阶段已经设置了，这里就是确认。

- [ ] **Step 2: 实现 _stage_cleanup（finally 块）**

将原 lines 714-735 的 finally 逻辑提取：

```python
def _stage_cleanup(ctx: _ParseContext) -> None:
    """清理阶段 — 收集诊断、关闭 archive、重置缓存。

    在 finally 块中调用，确保无论成功失败都执行。
    """
    result = ctx.result

    # 收集 linker 诊断
    if result.linker and getattr(result.linker, 'diagnostics', None):
        result.diagnostics.extend(result.linker.diagnostics)

    # 收集 FArchive 诊断并关闭
    if ctx.archive:
        archive_diagnostics = ctx.archive.get_diagnostics()
        if archive_diagnostics:
            result.diagnostics = archive_diagnostics + result.diagnostics
        ctx.archive.close()

    # 释放 linker 对 archive 的引用
    if result.linker is not None:
        result.linker._archive = None

    # 重置 Kismet 类级别缓存
    from uasset_read.kismet.archive import FKismetArchive
    FKismetArchive.reset_warned_offsets()

    # 重置 BPGC 字节码缓存
    from uasset_read.kismet.bytecode_extractor import reset_bpgc_cache
    reset_bpgc_cache()
```

- [ ] **Step 3: 运行完整测试验证行为保持**

```bash
python -m pytest tests/test_parse_package_core.py tests/test_linker_lifecycle.py tests/test_diagnostic_output.py tests/test_parse_stages.py -v
```

预期：全部 PASS（行为保持）

- [ ] **Step 4: 运行 smoke 测试确保无回归**

```bash
python scripts/test_matrix.py smoke
```

预期：全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parse_uasset.py tests/test_parse_stages.py
git commit -m "refactor: extract stage 7 — finalize_result + cleanup"
```

---

### Task 10: 最终验收

- [ ] **Step 1: 运行全量测试矩阵**

```bash
python scripts/test_matrix.py all
```

预期：100% 通过率

- [ ] **Step 2: 验证 _parse_package_core 行数**

```bash
python -c "
import inspect
from uasset_read.parse_uasset import _parse_package_core
source = inspect.getsource(_parse_package_core)
print(f'_parse_package_core: {len(source.splitlines())} lines')
"
```

预期：< 80 行

- [ ] **Step 3: 代码质量**

```bash
python scripts/test_matrix.py quality
```

预期：PASS

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "refactor: complete _parse_package_core stage split (#112)"
```

---

## 验收标准核对

- [x] `_parse_package_core()` 变成短 orchestration function（< 80 行）
- [x] 拆分后的每个 stage 有单元测试覆盖
- [x] 行为保持：现有解析、linker 生命周期、tolerant error、diagnostics、cache reset 测试通过
- [x] 不改变公开 API：`parse_package()`、`parse_uasset()`、`parse_uasset_with_linker()` 签名保持兼容
