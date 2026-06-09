# uasset_read → UE 原始加载输出等价性改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前"容错型离线提取器"改造为在 `FLinkerLoad + UObject::Serialize` 关键路径上与 UE 基准等价的反序列化器；对未实现 class-specific `Serialize()` 的类型，必须诚实标记 `parse_status=opaque/partial`，不再伪装成 `GENERIC_UOBJECT` 成功解析。

**Architecture:** 以 UE `FLinkerLoad::SerializePackageFileSummary → NameMap → ImportMap → ExportMap → CreateExport → Preload → Serialize → PostLoad` 为基准，把现有管线按"linker 生命周期 / ScriptSerialization 范围 / class-specific 策略 / SoftObjectPath 索引化 / DependsMap 语义 / 输出状态"六条主线重构。所有改动都通过 linker 单例状态与 `ObjectExport.parse_status` 暴露给下游；对外 API (`parse_package` / `parse_uasset_with_linker`) 签名不变。

**Tech Stack:** Python 3.10+, pytest, 现有 `uasset_read` 包（`link/linker.py`, `parse_uasset.py`, `parsers/property_parser.py`, `parsers/asset_types/__init__.py`, `parsers/class_registry.py`, `serializers/package_summary.py`, `serializers/object_resources.py`, `models/result.py`, `link/result.py`）。

**参考 UE 源码（只读基准，不需要在工程里复现）：**

- `Engine/Source/Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp:1494,1941,2070,2438,4694,6450`
- `Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp:1514`
- `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyTag.cpp:548`

---

## 总体改造顺序（依赖关系，必须按此顺序推进）

| # | 主题 | 关键产物 | 依赖 |
|---|------|---------|------|
| 1 | Linker 生命周期等价 | `PackageLinker.preload` 写入 export + instance；`_parse_package_core` 显式 preload 所有 export 后再 `post_load` | — |
| 2 | `ScriptSerializationStartOffset` 使用条件收窄 | `export.use_script_serialization_range()`；默认走 `SerialOffset → SerialOffset+SerialSize` | 1 |
| 3 | Class-specific 策略表：opaque 取代 `GENERIC_UOBJECT` 伪装 | `FallbackPolicy.OPAQUE`、`parse_status="opaque"` 写入 export | 1, 2 |
| 4 | `FSoftObjectPath` 分层读取 | header list 仍双 FName；属性内 soft path 走 SoftObjectPathList 索引 | 1 |
| 5 | DependsMap / PreloadDependencies 按 `FPackageIndex` 解析 | `read_depends_map` 返回 `List[List[PackageIndex]]`；`_build_dependency_graph` 使用 `resolve_package_index` | 1 |
| 6 | 输出状态不再过于乐观 | 移除无条件 `result.is_success = True`；根据 export `parse_status` 计算最终状态 | 1–5 |

每个 Phase 都是独立可测试、可提交的最小切片。

---

## 文件职责地图（实施前锁定，避免跨文件改动漂移）

| 文件 | 本次职责 | 不做什么 |
|------|----------|----------|
| `src/uasset_read/link/linker.py` | Phase 1/5：preload 回写、依赖图按 `FPackageIndex` resolve | 不新增 asset 类型知识 |
| `src/uasset_read/parse_uasset.py` | Phase 1/6：先 preload 再 post_load；计算 `is_success` | 不直接读属性 |
| `src/uasset_read/parsers/property_parser.py` | Phase 2：`script_serialization_*_offset` 只在允许名单内使用 | 不实现 class-specific 解码 |
| `src/uasset_read/parsers/class_registry.py` | Phase 3：新增 `FallbackPolicy.OPAQUE` | 不新增 asset 类型 |
| `src/uasset_read/parsers/asset_types/__init__.py` | Phase 3：所有未真实实现 `Serialize()` 的 handler 使用 `OPAQUE` | 不假装解析成功 |
| `src/uasset_read/serializers/package_summary.py` | Phase 5：`read_depends_map` 返回 `PackageIndex`；`read_preload_dependencies` 同样 | 不改变文件格式 |
| `src/uasset_read/serializers/object_resources.py` | Phase 4：`read_soft_object_paths` 返回索引化结构；新增 `SoftObjectPathTable` | 不触碰属性解析 |
| `src/uasset_read/models/result.py` / `link/result.py` | Phase 6：新增 `parse_status` 字段、`compute_overall_status()` | 不修改字段类型 |
| `tests/unit/test_linker_lifecycle.py` | Phase 1 | — |
| `tests/unit/test_script_serialization_range.py` | Phase 2 | — |
| `tests/unit/test_opaque_policy.py` | Phase 3 | — |
| `tests/unit/test_soft_object_path_table.py` | Phase 4 | — |
| `tests/unit/test_depends_package_index.py` | Phase 5 | — |
| `tests/unit/test_parse_status_propagation.py` | Phase 6 | — |

---

## Task 1 — Linker 生命周期等价（UE CreateExport → Preload → Serialize → PostLoad）

**Files:**
- Modify: `src/uasset_read/link/linker.py:218-285` (`preload`)
- Modify: `src/uasset_read/parse_uasset.py:554-620`（`_parse_package_core` 中段）
- Modify: `src/uasset_read/link/object_instance.py`（确保 `serialized_properties` 与 `export.properties` 同步）
- Test: `tests/unit/test_linker_lifecycle.py`

### 目标

对齐 UE 顺序：

1. `link()` 创建 `UObjectInstance` 壳（已实现）。
2. 对每个 export **显式** 调 `preload(i)`，并把属性结果 **回写** 到 `export.properties`。
3. 所有 export 都 preloaded 之后，才调 `post_load()`，此时 `_resolve_property_references` 不会跳过任何对象。

### 当前问题

- `parse_uasset.py:568` 在 linker 创建后立刻 `linker.post_load()`，但 export 属性解析发生在 `parse_uasset.py:583` 之后，导致 `_resolve_property_references` 因 `inst._preloaded == False` 跳过所有对象（`linker.py:317-319`）。
- `preload()` 只把结果写到 `instance.serialized_properties`，没写回 `export.properties`，linker 路径和直接解析路径数据不同步。

### Step-by-step

- [ ] **Step 1.1: 写失败测试**

`tests/unit/test_linker_lifecycle.py`:

```python
"""UE 基准等价：link → preload(all) → post_load。"""
import pytest
from pathlib import Path


def _sample_asset():
    assets = list(Path("tests/assets").glob("*.uasset"))
    if not assets:
        pytest.skip("No test assets")
    return str(assets[0])


def test_preload_populates_export_properties_and_instance():
    """preload(i) 必须同时写回 export.properties 和 instance.serialized_properties。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(_sample_asset())
    assert result.linker is not None

    linker = result.linker
    # 选第一个 serial_size > 0 的 export
    target_idx = next(
        (i for i, e in enumerate(result.export_map) if e.serial_size > 0),
        None,
    )
    if target_idx is None:
        pytest.skip("No serializable export in sample")

    linker.preload(target_idx)

    export = result.export_map[target_idx]
    instance = linker._export_objects[target_idx]

    assert instance._preloaded is True
    assert export.properties is not None, "preload must write back to export.properties"
    assert instance.serialized_properties is export.properties, (
        "instance.serialized_properties 与 export.properties 必须是同一对象"
    )


def test_post_load_runs_after_all_exports_preloaded():
    """post_load 运行前，所有 export 必须已经 preloaded。"""
    from uasset_read.link.linker import PackageLinker

    result = parse_uasset_with_linker(_sample_asset())
    linker = result.linker

    # 手动触发：preload 全部 → post_load
    for i in range(len(linker._export_objects)):
        linker.preload(i)

    for inst in linker._export_objects:
        assert inst._preloaded is True, (
            f"{inst.object_name} 在 post_load 之前未被 preload"
        )

    # 运行 post_load 不应再跳过任何对象
    linker.post_load()

    # 验证：任何带有 ObjectProperty 的 export 都应产生 property_references 条目
    # （即使引用无法解析，也应记录 attempt；不会因 _preloaded=False 跳过）


def test_resolve_property_references_sees_all_preloaded_exports():
    """_resolve_property_references 不应因 _preloaded=False 跳过任何 export。"""
    from uasset_read.link.linker import PackageLinker
    from unittest.mock import patch

    result = parse_uasset_with_linker(_sample_asset())
    linker = result.linker
    for i in range(len(linker._export_objects)):
        linker.preload(i)

    skipped: list[str] = []
    original = linker._resolve_property_references

    def spy():
        for inst in linker._export_objects:
            if not inst._preloaded:
                skipped.append(inst.object_name)
        return original()

    with patch.object(linker, "_resolve_property_references", spy):
        linker.post_load()

    assert skipped == [], (
        f"post_load 时有 {len(skipped)} 个 export 因 _preloaded=False 被跳过: {skipped[:5]}"
    )
```

- [ ] **Step 1.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_linker_lifecycle.py -v
```

期望：`test_preload_populates_export_properties_and_instance` 与 `test_resolve_property_references_sees_all_preloaded_exports` FAIL。

- [ ] **Step 1.3: 修改 `PackageLinker.preload()` 回写到 `export.properties`**

`src/uasset_read/link/linker.py:268-285`：

```python
        self._archive.seek(instance.serial_offset)

        # Delayed import to avoid circular dependency at module load time.
        from uasset_read.parsers.property_parser import (
            parse_properties_from_export,
        )

        exp = self._export_map[index]
        parsed = parse_properties_from_export(
            exp,
            self._archive,
            self._summary,
            self._name_map,
            self._export_map,
            self._import_map,
            linker=self,
        )
        # 双写：instance 与 export 共享同一结果（UE 等价：对象属性就是 export 属性）
        instance.serialized_properties = parsed
        exp.properties = parsed
        if not getattr(exp, "parse_status", None):
            setattr(exp, "parse_status", "success")
        instance._preloaded = True
        self._preload_cache[index] = True
```

- [ ] **Step 1.4: 修改 `_parse_package_core` 的生命周期顺序**

`src/uasset_read/parse_uasset.py:554-620`，替换为：

```python
        # 创建 linker（在属性解析之前创建，确保 parse_properties_from_export 可使用 linker）
        linker: Optional["PackageLinker"] = None
        try:
            linker = PackageLinker(
                archive, result.summary, result.name_map,
                result.import_map, result.export_map or [],
                version_container=result.version_container,
            )
            linker.link()
            result.linker = linker

            if extra_linker_setup is not None:
                extra_linker_setup(linker, result)
        except Exception as e:
            if not tolerant:
                raise ParseError(f"Linker creation failed: {e}") from e
            result.errors.append(f"Linker creation failed: {e}")

        if _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold):
            result.warnings.append(
                "Lightweight tolerant parse used due to export complexity "
                f"(exports={getattr(result.summary, 'export_count', 0)})"
            )
            result.metadata["lightweight_tolerant_parse"] = True
            result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
            # 不再无条件 is_success = True（Phase 6 统一计算）
            return

        # ① Preload 全部 export（UE FLinkerLoad::Preload 等价）
        #    结果写入 linker._export_objects[i].serialized_properties
        #    且回写到 result.export_map[i].properties（Step 1.3 已保证）
        if linker is not None:
            for i in range(len(result.export_map or [])):
                try:
                    linker.preload(i)
                except Exception as e:
                    if not tolerant:
                        raise ParseError(
                            f"Preload failed for export #{i} "
                            f"({result.export_map[i].object_name}): {e}"
                        ) from e
                    result.errors.append(
                        f"Preload failed for export #{i} "
                        f"({result.export_map[i].object_name}): {e}"
                    )
                    # 标记 failed，避免后续误认为 success
                    setattr(result.export_map[i], "parse_status", "failed")
                    setattr(result.export_map[i], "fallback_reason", "preload_error")
                    setattr(result.export_map[i], "error_message", str(e))

        # ② 提取组件变换（使用已 preload 的 export.properties）
        for export in result.export_map or []:
            if getattr(export, "properties", None):
                export.transforms = extract_component_transforms(export.properties)

        # ③ PostLoad（此时所有 export 都已 preloaded）
        if linker is not None:
            try:
                linker.post_load()
            except Exception as e:
                if not tolerant:
                    raise ParseError(f"PostLoad failed: {e}") from e
                result.errors.append(f"PostLoad failed: {e}")

        # 共享后处理
        _post_process(
            path, archive, result.summary, result.name_map,
            result.import_map, result.export_map or [], result, tolerant,
            linker=linker,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            archive_factory=lambda: bundle.open_archive(tolerant=tolerant) if bundle else FArchive(path, tolerant=tolerant),
        )
        # Phase 6 统一计算 result.is_success；这里不再无条件赋值
```

- [ ] **Step 1.5: 运行测试，确认 PASS**

```bash
pytest tests/unit/test_linker_lifecycle.py -v
```

- [ ] **Step 1.6: 运行全量单元测试，确认无回归**

```bash
pytest tests/unit -q
```

若有测试依赖"export.properties 不被 preload 填充"的旧假设，更新之（通常是 `assert export.properties == []` 之类的断言，改为 `assert export.properties is not None`）。

- [ ] **Step 1.7: 提交**

```bash
git add src/uasset_read/link/linker.py src/uasset_read/parse_uasset.py tests/unit/test_linker_lifecycle.py
git commit -m "refactor(linker): UE 等价生命周期 link→preload(all)→post_load

- PackageLinker.preload 同时回写到 export.properties 与 instance.serialized_properties
- _parse_package_core 改为显式 preload 所有 export 后再 post_load
- 修复 _resolve_property_references 因 _preloaded=False 跳过全部 export 的问题"
```

---

## Task 2 — `ScriptSerializationStartOffset` 使用条件收窄

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py:314-380`
- Create: `src/uasset_read/parsers/tps_only_registry.py`（TPS-only 类型名单）
- Test: `tests/unit/test_script_serialization_range.py`

### 目标

默认从 `SerialOffset` 开始读属性；只有"保存类和实际类不匹配 / PropertyBag placeholder / BlueprintGeneratedClass 等"的明确 TPS-only 情况才使用 `[serial_offset + script_serialization_start_offset, serial_offset + script_serialization_end_offset)`。

### 当前问题

`property_parser.py:315-316` 对 UE5.10+ **所有** export 一律使用 `script_serialization_start_offset` 作为起点，会把 `StaticMesh` / `Texture2D` / `Material` 的 class-specific payload 当作 PropertyTag 流，结果全部错位。

### Step-by-step

- [ ] **Step 2.1: 写失败测试**

`tests/unit/test_script_serialization_range.py`:

```python
"""ScriptSerializationStartOffset 只能在允许名单内使用。"""
import pytest
from dataclasses import dataclass
from uasset_read.serializers.object_resources import PackageIndex


@dataclass
class FakeExport:
    serial_offset: int = 1000
    serial_size: int = 200
    script_serialization_start_offset: int = 50
    script_serialization_end_offset: int = 180
    class_index: PackageIndex = None
    object_name: str = "Fake"


@dataclass
class FakeSummary:
    file_version_ue5: int = 1010  # >= UE5_SCRIPT_SERIALIZATION_OFFSET


def test_default_uses_serial_offset_for_unknown_class():
    """对未知 class，起点必须是 serial_offset，终点是 serial_offset+serial_size。"""
    from uasset_read.parsers.property_parser import compute_property_range
    from uasset_read.parsers.tps_only_registry import is_tps_only_class

    export = FakeExport()
    summary = FakeSummary()

    # 模拟一个未注册的 class name（通过 class name 查找返回 False）
    start, end = compute_property_range(export, summary, class_name="StaticMesh")

    assert start == export.serial_offset, (
        "非 TPS-only 类型必须从 SerialOffset 开始读取"
    )
    assert end == export.serial_offset + export.serial_size, (
        "非 TPS-only 类型必须以 SerialOffset+SerialSize 为终点"
    )


def test_tps_only_class_uses_script_range():
    """已注册为 TPS-only 的类型，使用 script_serialization_*_offset。"""
    from uasset_read.parsers.property_parser import compute_property_range

    export = FakeExport()
    summary = FakeSummary()

    start, end = compute_property_range(
        export, summary, class_name="BlueprintGeneratedClass",
    )

    assert start == export.serial_offset + export.script_serialization_start_offset
    assert end == export.serial_offset + export.script_serialization_end_offset


def test_old_ue_version_ignores_script_offsets():
    """UE 版本 < UE5_SCRIPT_SERIALIZATION_OFFSET 时永远不使用 script_*。"""
    from uasset_read.parsers.property_parser import compute_property_range

    export = FakeExport()
    summary = FakeSummary(file_version_ue5=500)  # 老版本

    start, end = compute_property_range(
        export, summary, class_name="BlueprintGeneratedClass",
    )

    assert start == export.serial_offset
    assert end == export.serial_offset + export.serial_size
```

- [ ] **Step 2.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_script_serialization_range.py -v
```

- [ ] **Step 2.3: 创建 TPS-only 注册表**

`src/uasset_read/parsers/tps_only_registry.py`:

```python
"""TPS-only 类型名单 — 仅这些类型使用 script_serialization_*_offset。

UE 基准：FLinkerLoad::Preload 调用 Object->Serialize()，但以下情况
         缩窄到 SerializeScriptProperties()：
  - 保存类与运行时类不匹配（编辑器回退）
  - PropertyBag placeholder
  - BlueprintGeneratedClass（只读脚本属性）
  - 部分 CDO（在特定条件下）

本模块列出已知的 TPS-only class name；未列出的类型一律按
SerialOffset → SerialOffset+SerialSize 处理。
"""
from __future__ import annotations

# 已知 TPS-only 类型白名单
TPS_ONLY_CLASSES: frozenset[str] = frozenset({
    "BlueprintGeneratedClass",
    # 后续按需追加，例如：
    # "PropertyBag",  # 待 UE 基准确认
})


def is_tps_only_class(class_name: str | None) -> bool:
    """判断给定 class_name 是否属于 TPS-only 范围。"""
    if not class_name:
        return False
    return class_name in TPS_ONLY_CLASSES
```

- [ ] **Step 2.4: 在 `property_parser.py` 中抽出 `compute_property_range`**

`src/uasset_read/parsers/property_parser.py`：在文件顶部导入区添加：

```python
from uasset_read.parsers.tps_only_registry import is_tps_only_class
```

并新增函数（放在 `parse_properties_from_export` 之前）：

```python
def compute_property_range(
    export,
    summary,
    *,
    class_name: str | None = None,
) -> tuple[int, int]:
    """计算属性读取的 [start, end) 字节区间。

    只在 is_tps_only_class(class_name) 为 True 且 UE 版本满足条件时使用
    script_serialization_*_offset；否则一律使用 [SerialOffset, SerialOffset+SerialSize)。
    """
    serial_offset = export.serial_offset
    serial_size = export.serial_size

    use_script_range = (
        summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET
        and is_tps_only_class(class_name)
    )

    if use_script_range:
        start = serial_offset + export.script_serialization_start_offset
        end = serial_offset + export.script_serialization_end_offset
    else:
        start = serial_offset
        end = serial_offset + serial_size

    return start, end
```

- [ ] **Step 2.5: 改写 `parse_properties_from_export` 使用 `compute_property_range`**

`src/uasset_read/parsers/property_parser.py:314-380`：

```python
    # 解析 class name（提前，供 compute_property_range 使用）
    _class_name = None
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name
            _class_name = resolve_class_name(export.class_index, import_map, export_map)
        except Exception as e:
            logger.debug("Failed to resolve class name: %s", e)

    # 计算属性读取区间
    property_start, property_end = compute_property_range(
        export, summary, class_name=_class_name,
    )
    archive.seek(property_start)

    # Tolerant skip: 对已知不兼容的 class-specific payload 直接跳过
    from uasset_read.parsers.class_specific_skip import (
        should_skip_export_for_tolerant_parsing,
        skip_export_payload,
    )
    if should_skip_export_for_tolerant_parsing(export, class_name=_class_name):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            export.object_name,
        )
        try:
            skip_export_payload(archive, export, summary)
        except Exception as e:
            logger.warning("Failed to skip export '%s' payload: %s", export.object_name, e)
        setattr(export, "parse_status", "skipped")
        setattr(export, "fallback_reason", "unsupported_type")
        setattr(export, "class_name", _class_name or "")
        return []

    # ... (SerializationControlExtensions 段保持不变)

    # 移除原先的 property_end 重算块（已统一由 compute_property_range 提供）
    # 原代码：
    #   if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    #       property_end = export.serial_offset + export.script_serialization_end_offset
    #   else:
    #       property_end = export.serial_offset + export.serial_size
    # → 整段删除
```

- [ ] **Step 2.6: 运行测试，确认 PASS**

```bash
pytest tests/unit/test_script_serialization_range.py -v
```

- [ ] **Step 2.7: 回归测试**

```bash
pytest tests/unit -q
```

重点检查 `test_property_parser_error_handling.py`、`test_tolerant_class_specific.py` 是否依赖旧行为；若它们对 `StaticMesh` 等类型期望属性非空，需要改为 `parse_status in ("skipped","opaque")` 的判断。

- [ ] **Step 2.8: 提交**

```bash
git add src/uasset_read/parsers/property_parser.py src/uasset_read/parsers/tps_only_registry.py tests/unit/test_script_serialization_range.py
git commit -m "refactor(parser): 收窄 ScriptSerializationStartOffset 的使用范围

- 默认从 SerialOffset 读起，终点 SerialOffset+SerialSize
- 仅 TPS-only 白名单 (BlueprintGeneratedClass 等) 使用 script_serialization_*_offset
- 防止 StaticMesh/Texture/Material 等 class-specific payload 被错误当 PropertyTag 流"
```

---

## Task 3 — Class-specific 策略表：opaque 取代 `GENERIC_UOBJECT` 伪装

**Files:**
- Modify: `src/uasset_read/parsers/class_registry.py:30-45`
- Modify: `src/uasset_read/parsers/asset_types/__init__.py:45-92`
- Test: `tests/unit/test_opaque_policy.py`

### 目标

对未真正实施 `Serialize()` 的 asset 类型（`StaticMesh`、`Texture2D`、`Material`、`AnimSequence`、`SkeletalMesh`、`SoundWave`、`TextureCube`），把 `fallback_policy` 改为 `OPAQUE`；handler 返回的数据只视为 `partial_metadata`，`export.parse_status` 必须为 `"opaque"`，不能再是 `"success"`。

### 当前问题

- `AssetTypeHandler.fallback_policy` 返回 `GENERIC_UOBJECT`，让下游以为这些类型已被"泛型成功解析"。
- 实际 handler 只是读了 256 字节样本，与 UE 的 `UStaticMesh::Serialize` 完全不是同一层级。

### Step-by-step

- [ ] **Step 3.1: 写失败测试**

`tests/unit/test_opaque_policy.py`:

```python
"""未实现真实 Serialize() 的资产类型必须标记 OPAQUE。"""
import pytest
from uasset_read.parsers.class_registry import FallbackPolicy, get_class_registry


@pytest.mark.parametrize(
    "class_name",
    [
        "StaticMesh", "SkeletalMesh", "Material", "MaterialInstance",
        "MaterialInstanceConstant", "Texture2D", "TextureCube",
        "AnimSequence", "SoundWave",
    ],
)
def test_asset_type_handler_fallback_is_opaque(class_name):
    """所有未实现真实 Serialize() 的 handler 必须声明 OPAQUE。"""
    registry = get_class_registry()
    handler = registry.get_handler(class_name)
    assert handler is not None, f"{class_name} 应当已注册"
    assert handler.fallback_policy is FallbackPolicy.OPAQUE, (
        f"{class_name} 的 fallback_policy 应为 OPAQUE, "
        f"实际为 {handler.fallback_policy}"
    )


def test_opaque_handler_result_marks_export_parse_status():
    """handler 的 parse 结果必须把 export.parse_status 设置为 opaque。"""
    from unittest.mock import MagicMock
    from uasset_read.parsers.asset_types import AssetTypeHandler
    from uasset_read.parsers.asset_types.static_mesh import parse_static_mesh

    handler = AssetTypeHandler(
        class_names=["StaticMesh"],
        parse_func=parse_static_mesh,
        handler_name="StaticMeshHandler",
    )
    export = MagicMock()
    export.object_name = "SM_Test"
    archive = MagicMock()

    result = handler.parse(export, archive, context=[])
    # parse_status 由 parse 调用方（property_parser）根据 fallback_policy 设置；
    # 这里只验证 policy 本身
    assert handler.fallback_policy is FallbackPolicy.OPAQUE
```

- [ ] **Step 3.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_opaque_policy.py -v
```

- [ ] **Step 3.3: 在 `FallbackPolicy` 中增加 `OPAQUE`**

`src/uasset_read/parsers/class_registry.py:30-36`:

```python
class FallbackPolicy(str, Enum):
    """当 handler 无法处理时的 fallback 策略。"""
    GENERIC_UOBJECT = "generic_uobject"
    SKIP = "skip"
    RAISE = "raise"
    PROPERTY_FALLBACK = "property_fallback"
    # 新增：handler 没有实现真实 Serialize()，只能给出原始字节样本
    OPAQUE = "opaque"
```

- [ ] **Step 3.4: 把 `AssetTypeHandler` 的 `fallback_policy` 改为 `OPAQUE`**

`src/uasset_read/parsers/asset_types/__init__.py:45-92`:

```python
class AssetTypeHandler(ClassHandler):
    """将 parse_*() 函数包装为 ClassHandler。

    所有已注册 parse 函数都只产出 partial_metadata，不实现真正的 Serialize()，
    因此 fallback_policy 一律为 OPAQUE。
    """

    def __init__(
        self,
        class_names: List[str],
        parse_func: Callable[["FArchive", List[str]], Dict[str, Any]],
        handler_name: str,
    ) -> None:
        self._class_names = set(class_names)
        self._parse_func = parse_func
        self._handler_name = handler_name

    def can_handle(self, class_name: str) -> bool:
        return class_name in self._class_names

    @property
    def handler_name(self) -> str:
        return self._handler_name

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.OPAQUE

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            name_map = context if isinstance(context, list) else []
            data = self._parse_func(archive, name_map)
            return HandlerResult(
                success=True,
                data=data,
                # 即便 parse 成功，数据也只是 partial_metadata
                fallback_policy=FallbackPolicy.OPAQUE,
            )
        except Exception as e:
            logger.debug(
                "AssetTypeHandler '%s' failed for '%s': %s",
                self._handler_name, export.object_name, e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.OPAQUE,
            )
```

- [ ] **Step 3.5: 在 `property_parser.py` 根据 `fallback_policy == OPAQUE` 设置 `parse_status`**

在 `property_parser.py` 调用 class handler 的分支（搜索 `registry.get_handler` / `handler.parse`），在成功后：

```python
if handler.fallback_policy is FallbackPolicy.OPAQUE:
    setattr(export, "parse_status", "opaque")
    setattr(export, "partial_metadata", result.data)
    setattr(export, "fallback_reason", "class_specific_serialize_not_implemented")
    setattr(export, "class_name", class_name)
    return []  # 不把这些字节当成 PropertyTag 流
```

- [ ] **Step 3.6: 运行测试，确认 PASS**

```bash
pytest tests/unit/test_opaque_policy.py -v
```

- [ ] **Step 3.7: 回归测试 + 更新既有断言**

```bash
pytest tests/unit -q
```

如果既有测试对 `StaticMesh` 等 export 期望 `parse_status == "success"`，需改为 `parse_status == "opaque"` 或 `parse_status in ("opaque","skipped")`。

- [ ] **Step 3.8: 提交**

```bash
git add src/uasset_read/parsers/class_registry.py src/uasset_read/parsers/asset_types/__init__.py src/uasset_read/parsers/property_parser.py tests/unit/test_opaque_policy.py
git commit -m "refactor(parser): 未实现 Serialize() 的资产类型使用 OPAQUE fallback

- 新增 FallbackPolicy.OPAQUE
- AssetTypeHandler 的 fallback_policy 改为 OPAQUE
- property_parser 在 OPAQUE 分支设置 export.parse_status='opaque'
- 不再伪装为 GENERIC_UOBJECT 成功解析"
```

---

## Task 4 — `FSoftObjectPath` 分层读取（header list vs 属性内索引）

**Files:**
- Modify: `src/uasset_read/serializers/object_resources.py:163-181`
- Create: `src/uasset_read/serializers/soft_object_path_table.py`
- Modify: `src/uasset_read/parsers/property_parser.py`（在 `SoftObjectProperty` 处理分支）
- Test: `tests/unit/test_soft_object_path_table.py`

### 目标

区分两个层面：

1. **Package-level `SoftObjectPaths`**（header）：UE5.7 用 double FName + FString；UE5.7+ 在 `FPackageFileSummary` 里记录 `bSoftObjectPathsInCookedExports` / `SoftObjectPathsOffset` 等，作为全局表。
2. **属性中的 `SoftObjectProperty`**：当包级别 soft path list 存在时，属性里只存一个 `int32` 索引（回表解析）；否则才存 inline `FSoftObjectPath`。

### 当前问题

`object_resources.py:174-181` 始终按 double FName + FString 读；属性端也一律按 inline 读。这会让 UE5 cooked 包里的 `SoftObjectProperty` 偏移错位。

### Step-by-step

- [ ] **Step 4.1: 写失败测试**

`tests/unit/test_soft_object_path_table.py`:

```python
"""SoftObjectPath 必须按 header/property 两层处理。"""
import io
import struct
import pytest


def _make_archive(data: bytes):
    from uasset_read.archive import FArchive
    a = FArchive.__new__(FArchive)
    a._fp = io.BytesIO(data)
    a._file_size = len(data)
    a._byte_swapping = False
    a._diagnostics = []
    return a


def test_header_table_double_fname_plus_fstring():
    """UE5.7 header table：double FName + FString。"""
    from uasset_read.serializers.soft_object_path_table import read_header_soft_paths

    # 构造：1 个 soft path entry
    # package_name name_idx=1, asset_name name_idx=2, sub_path="sub"
    buf = bytearray()
    buf += struct.pack("<i", 1)      # name_idx for package
    buf += struct.pack("<i", 2)      # name_idx for asset
    sub = b"sub\x00"
    buf += struct.pack("<i", len(sub)) + sub

    archive = _make_archive(bytes(buf))
    name_map = ["unused", "/Game/Foo", "Foo"]

    paths = read_header_soft_paths(archive, count=1, name_map=name_map)

    assert len(paths) == 1
    assert paths[0]["asset_path"] == "/Game/Foo.Foo"
    assert paths[0]["sub_path"] == "sub"


def test_property_index_resolution_against_table():
    """属性里读到 int32 索引时，必须回表解析为 asset path。"""
    from uasset_read.serializers.soft_object_path_table import SoftObjectPathTable

    table = SoftObjectPathTable([
        {"asset_path": "/Game/A.A", "sub_path": ""},
        {"asset_path": "/Game/B.B", "sub_path": "child"},
    ])

    assert table.resolve(0) == {"asset_path": "/Game/A.A", "sub_path": ""}
    assert table.resolve(1) == {"asset_path": "/Game/B.B", "sub_path": "child"}
    with pytest.raises(IndexError):
        table.resolve(99)


def test_empty_table_means_inline_encoding():
    """如果 header 没有 soft path table，属性端必须按 inline 读取。"""
    from uasset_read.serializers.soft_object_path_table import SoftObjectPathTable

    table = SoftObjectPathTable([])
    assert table.is_empty is True
    # 调用方在 is_empty 时走 inline 路径，而非读索引
```

- [ ] **Step 4.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_soft_object_path_table.py -v
```

- [ ] **Step 4.3: 新建 `SoftObjectPathTable`**

`src/uasset_read/serializers/soft_object_path_table.py`:

```python
"""Package-level SoftObjectPath table（UE5 cooked package）。

两个使用场景：
1. `read_header_soft_paths()` — 从 summary.soft_object_paths_offset 读取
   全局表（UE5.7 是 double FName + FString）。
2. `SoftObjectPathTable` — 属性端读到 int32 索引时回表解析。
   当包不含全局表时（is_empty=True），属性端按 inline FSoftObjectPath 读。

参考 UE FLinkerLoad::operator<<(FSoftObjectPath&)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


@dataclass
class SoftObjectPathTable:
    """Package 级别的 soft path 查找表。"""

    entries: List[Dict[str, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def resolve(self, index: int) -> Dict[str, str]:
        """按索引解析为 {asset_path, sub_path} 字典。"""
        if not (0 <= index < len(self.entries)):
            raise IndexError(
                f"SoftObjectPath index {index} 越界 "
                f"(table size={len(self.entries)})"
            )
        return self.entries[index]


def read_header_soft_paths(
    archive: "FArchive",
    *,
    count: int,
    name_map: List[str],
) -> List[Dict[str, str]]:
    """读取 package header 的 soft path table。

    当前实现覆盖 UE5.7 cooked 包的 double FName + FString 格式。
    未来如需支持 UE5.7+ 的移除 FName 版本（bSoftObjectPathsInCookedExports），
    由调用方根据 summary 字段选择 reader。
    """
    if count <= 0:
        return []

    paths: List[Dict[str, str]] = []
    for _ in range(count):
        package_name_idx = archive.read_i32()
        asset_name_idx = archive.read_i32()
        sub_path = archive.read_fstring()

        package_name = (
            name_map[package_name_idx]
            if 0 <= package_name_idx < len(name_map)
            else ""
        )
        asset_name = (
            name_map[asset_name_idx]
            if 0 <= asset_name_idx < len(name_map)
            else ""
        )
        asset_path = (
            f"{package_name}.{asset_name}" if asset_name else package_name
        )
        paths.append({"asset_path": asset_path, "sub_path": sub_path})
    return paths
```

- [ ] **Step 4.4: 改造 `object_resources.read_soft_object_paths` 复用新模块**

`src/uasset_read/serializers/object_resources.py:163-181`：

```python
def read_soft_object_paths(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[Dict]:
    """读取 SoftObjectPaths 数组（UE5.7+ header 全局表）。"""
    if summary.soft_object_paths_count <= 0 or summary.soft_object_paths_offset <= 0:
        return []

    from uasset_read.serializers.soft_object_path_table import read_header_soft_paths

    archive.seek(summary.soft_object_paths_offset)
    return read_header_soft_paths(
        archive,
        count=summary.soft_object_paths_count,
        name_map=name_map,
    )
```

- [ ] **Step 4.5: 在 `property_parser.py` 的 `SoftObjectProperty` 分支加入索引化读取**

找到 `SoftObjectProperty` 处理分支（搜索 `SoftObjectProperty`），在读取值时：

```python
# 调用方在 parse_properties_from_export 入口已构建：
#   summary._soft_path_table: SoftObjectPathTable  （没有则为 empty）
soft_table = getattr(summary, "_soft_path_table", None)

if soft_table is not None and not soft_table.is_empty:
    # cooked 包：属性里是 int32 索引
    idx = archive.read_i32()
    try:
        value = soft_table.resolve(idx)
    except IndexError as e:
        logger.warning("SoftObjectProperty index 越界: %s", e)
        value = None
else:
    # 旧格式或未 cooked：inline FSoftObjectPath
    package_name = archive.read_name(name_map)
    asset_name = archive.read_name(name_map)
    sub_path = archive.read_fstring()
    asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
    value = {"asset_path": asset_path, "sub_path": sub_path}
```

并在 `parse_properties_from_export` 开头（archive.seek 之前）构造 table：

```python
# 构造 package-level soft path table（属性端 SoftObjectProperty 使用）
if not hasattr(summary, "_soft_path_table"):
    from uasset_read.serializers.soft_object_path_table import (
        SoftObjectPathTable, read_header_soft_paths,
    )
    if (
        getattr(summary, "soft_object_paths_count", 0) > 0
        and getattr(summary, "soft_object_paths_offset", 0) > 0
    ):
        saved = archive.tell()
        archive.seek(summary.soft_object_paths_offset)
        entries = read_header_soft_paths(
            archive,
            count=summary.soft_object_paths_count,
            name_map=name_map,
        )
        archive.seek(saved)
        summary._soft_path_table = SoftObjectPathTable(entries)
    else:
        summary._soft_path_table = SoftObjectPathTable([])
```

- [ ] **Step 4.6: 运行测试**

```bash
pytest tests/unit/test_soft_object_path_table.py -v
```

- [ ] **Step 4.7: 回归测试**

```bash
pytest tests/unit -q
```

- [ ] **Step 4.8: 提交**

```bash
git add src/uasset_read/serializers/soft_object_path_table.py src/uasset_read/serializers/object_resources.py src/uasset_read/parsers/property_parser.py tests/unit/test_soft_object_path_table.py
git commit -m "feat(softpath): 分层读取 FSoftObjectPath

- 新增 SoftObjectPathTable + read_header_soft_paths
- header 全局表 double FName + FString 读取集中到新模块
- 属性端在 table 存在时按 int32 索引回表解析；否则 inline 读取
- 修复 cooked 包里 SoftObjectProperty 偏移错位"
```

---

## Task 5 — DependsMap / PreloadDependencies 按 `FPackageIndex` 解析

**Files:**
- Modify: `src/uasset_read/serializers/package_summary.py:605-678`
- Modify: `src/uasset_read/link/linker.py:398-413`
- Test: `tests/unit/test_depends_package_index.py`

### 目标

`read_depends_map` 返回 `List[List[PackageIndex]]`，不再返回裸 `int`；`_build_dependency_graph` 必须通过 `linker.resolve_package_index(dep)` 解析，而不是 `self._export_objects[dep_idx]`。

### 当前问题

- `package_summary.py:629` 只 `read_i32()` 当作裸 export 下标。
- `linker.py:412` 直接 `self._export_objects[dep_idx]`，会把 import 依赖或负数下标错误处理。

### Step-by-step

- [ ] **Step 5.1: 写失败测试**

`tests/unit/test_depends_package_index.py`:

```python
"""DependsMap 必须按 FPackageIndex 语义解析。"""
import io
import struct
import pytest


def _make_archive(data: bytes):
    from uasset_read.archive import FArchive
    a = FArchive.__new__(FArchive)
    a._fp = io.BytesIO(data)
    a._file_size = len(data)
    a._byte_swapping = False
    a._diagnostics = []
    return a


def test_read_depends_map_returns_package_index():
    """返回类型应为 List[List[PackageIndex]]，不是 List[List[int]]。"""
    from uasset_read.serializers.package_summary import read_depends_map
    from uasset_read.serializers.object_resources import PackageIndex

    # 构造：2 个 export，第 1 个依赖 export #0 (index=1) 和 import #0 (index=-1)
    buf = bytearray()
    # export 0 deps: count=2
    buf += struct.pack("<i", 2)
    buf += struct.pack("<i", 1)   # PackageIndex → export 0
    buf += struct.pack("<i", -1)  # PackageIndex → import 0
    # export 1 deps: count=0
    buf += struct.pack("<i", 0)

    archive = _make_archive(bytes(buf))
    summary = type("S", (), {"depends_offset": 0, "export_count": 2})()

    depends_map = read_depends_map(archive, summary)

    assert len(depends_map) == 2
    assert all(isinstance(dep, PackageIndex) for dep in depends_map[0])
    assert depends_map[0][0].to_export_index() == 0
    assert depends_map[0][1].to_import_index() == 0
    assert depends_map[1] == []


def test_build_dependency_graph_uses_resolve_package_index():
    """_build_dependency_graph 必须用 resolve_package_index，不能按数组下标。"""
    from unittest.mock import patch
    from uasset_read.parse_uasset import parse_uasset_with_linker
    from pathlib import Path

    assets = list(Path("tests/assets").glob("*.uasset"))
    if not assets:
        pytest.skip("No test assets")

    result = parse_uasset_with_linker(str(assets[0]))
    linker = result.linker
    if not getattr(result.summary, "depends_map", None):
        pytest.skip("Sample has no depends_map")

    # 监视 resolve_package_index 调用
    calls: list = []
    original = linker.resolve_package_index

    def spy(pkg_idx):
        calls.append(pkg_idx)
        return original(pkg_idx)

    with patch.object(linker, "resolve_package_index", side_effect=spy):
        linker._build_dependency_graph()

    assert len(calls) > 0, (
        "_build_dependency_graph 必须对每个依赖调用 resolve_package_index"
    )


def test_negative_dep_index_resolved_as_import():
    """负值 dep 应被解析为 import，而不是当作大正数 export 下标。"""
    from uasset_read.serializers.object_resources import PackageIndex
    from uasset_read.link.linker import PackageLinker

    pkg = PackageIndex(-3)  # import index 2
    assert pkg.is_import is True
    assert pkg.to_import_index() == 2
    # 如果 linker 用裸 int 解释 -3，会越界或误指 export
```

- [ ] **Step 5.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_depends_package_index.py -v
```

- [ ] **Step 5.3: 修改 `read_depends_map` 返回 `PackageIndex`**

`src/uasset_read/serializers/package_summary.py:605-632`:

```python
def read_depends_map(
    archive: FArchive, summary: "PackageFileSummary",
) -> "List[List[PackageIndex]]":
    """读取 DependsMap（依赖表）。

    UE 格式：TArray<TArray<FPackageIndex>>
    每个 Export 对应一个依赖列表，依赖值为 FPackageIndex（有符号 int32）。

    Returns:
        二维列表，第一维是 Export 索引，第二维是 PackageIndex 实例。
    """
    from uasset_read.serializers.object_resources import PackageIndex

    if summary.depends_offset <= 0 or summary.export_count <= 0:
        return []

    archive.seek(summary.depends_offset)

    depends_map: List[List[PackageIndex]] = []
    for _ in range(summary.export_count):
        dep_count = archive.read_i32()
        if dep_count < 0 or dep_count > 10000:
            logger.warning("DependsMap: 异常的依赖数量 %d, 跳过", dep_count)
            depends_map.append([])
            continue
        deps: List[PackageIndex] = []
        for _ in range(dep_count):
            raw = archive.read_i32()
            deps.append(PackageIndex(raw))
        depends_map.append(deps)

    return depends_map
```

- [ ] **Step 5.4: 同样让 `read_preload_dependencies` 返回 `PackageIndex`**

`src/uasset_read/serializers/package_summary.py:660-678`:

```python
def read_preload_dependencies(
    archive: FArchive, summary: "PackageFileSummary",
) -> "List[PackageIndex]":
    """读取 PreloadDependencies（预加载依赖）。

    UE 格式：TArray<FPackageIndex>。

    Returns:
        PackageIndex 实例列表。
    """
    from uasset_read.serializers.object_resources import PackageIndex

    if summary.preload_dependency_offset <= 0 or summary.preload_dependency_count <= 0:
        return []

    archive.seek(summary.preload_dependency_offset)

    dependencies: List[PackageIndex] = []
    for _ in range(summary.preload_dependency_count):
        raw = archive.read_i32()
        dependencies.append(PackageIndex(raw))

    return dependencies
```

- [ ] **Step 5.5: 修改 `_build_dependency_graph` 使用 `resolve_package_index`**

`src/uasset_read/link/linker.py:398-413`:

```python
    def _build_dependency_graph(self) -> None:
        """将 DependsMap 转换为 UObjectInstance 之间的依赖链接。

        DependsMap[export_index] = List[PackageIndex]
        依赖值按 FPackageIndex 语义解析（可能是 export 也可能是 import）。
        """
        if not hasattr(self._summary, "depends_map") or not self._summary.depends_map:
            return

        depends_map = self._summary.depends_map
        for exp_idx, dep_pkg_indices in enumerate(depends_map):
            if exp_idx >= len(self._export_objects):
                continue
            inst = self._export_objects[exp_idx]
            resolved_deps: List[UObjectInstance] = []
            for pkg_idx in dep_pkg_indices:
                target = self.resolve_package_index(pkg_idx)
                if target is not None:
                    resolved_deps.append(target)
                else:
                    # 诊断：依赖无法解析（越界或 null）
                    self._diagnostics.append(OffsetRangeDiagnostic(
                        module="linker",
                        field="DependsMap",
                        export_index=exp_idx,
                        source="_build_dependency_graph",
                        error=(
                            f"Export #{exp_idx} ({inst.object_name}) "
                            f"依赖 PackageIndex({pkg_idx.index}) 无法解析"
                        ),
                        file_size=self._file_size,
                    ))
            inst.dependencies = resolved_deps
```

- [ ] **Step 5.6: 运行测试**

```bash
pytest tests/unit/test_depends_package_index.py -v
```

- [ ] **Step 5.7: 回归测试**

```bash
pytest tests/unit -q
```

特别注意 `test_linker_offset_check.py` 等既有依赖图测试；如有 `isinstance(dep, int)` 的断言需改为 `PackageIndex`。

- [ ] **Step 5.8: 提交**

```bash
git add src/uasset_read/serializers/package_summary.py src/uasset_read/link/linker.py tests/unit/test_depends_package_index.py
git commit -m "fix(depends): DependsMap 按 FPackageIndex 语义解析

- read_depends_map/read_preload_dependencies 返回 PackageIndex 实例
- _build_dependency_graph 通过 resolve_package_index 解析，支持 import 引用
- 无法解析的依赖记入 linker diagnostics，不再按数组下标静默丢弃"
```

---

## Task 6 — 输出状态不再过于乐观

**Files:**
- Modify: `src/uasset_read/models/result.py`
- Modify: `src/uasset_read/link/result.py`
- Modify: `src/uasset_read/parse_uasset.py:242, 576, 615`
- Test: `tests/unit/test_parse_status_propagation.py`

### 目标

`result.is_success` 必须真实反映：

- `success`：所有 export 都 `parse_status == "success"` 且无 errors/warnings。
- `partial`：存在 `parse_status in ("opaque","skipped","partial")` 的 export，或 warnings 不为空，或发生了 fallback。
- `fail`：`errors` 不为空，或所有 export 都 `failed`。

### 当前问题

- `_post_process` 末尾用 `result.is_success = len(result.errors) == 0` 算一次，但 `_parse_package_core` 后面又无条件 `result.is_success = True`（`parse_uasset.py:581, 620`），把错误掩盖。

### Step-by-step

- [ ] **Step 6.1: 写失败测试**

`tests/unit/test_parse_status_propagation.py`:

```python
"""输出状态必须反映 export 的真实 parse_status。"""
import pytest
from pathlib import Path


def _sample_asset():
    assets = list(Path("tests/assets").glob("*.uasset"))
    if not assets:
        pytest.skip("No test assets")
    return str(assets[0])


def test_compute_overall_status_with_opaque_exports():
    """只要存在 opaque export，结果就不能是 pure success。"""
    from uasset_read.models.result import compute_overall_status

    class FakeResult:
        errors = []
        warnings = []
        export_map = []

    r = FakeResult()
    # 造一个 opaque export
    class E:
        parse_status = "opaque"
    r.export_map = [E()]

    status = compute_overall_status(r)
    assert status != "success", (
        "存在 opaque export 时整体状态不能为 success"
    )


def test_compute_overall_status_with_errors():
    """errors 非空 → fail。"""
    from uasset_read.models.result import compute_overall_status

    class FakeResult:
        errors = ["something broke"]
        warnings = []
        export_map = []

    assert compute_overall_status(FakeResult()) == "fail"


def test_compute_overall_status_all_success():
    """全部 success 且无错误 → success。"""
    from uasset_read.models.result import compute_overall_status

    class E:
        parse_status = "success"

    class FakeResult:
        errors = []
        warnings = []
        export_map = [E(), E()]

    assert compute_overall_status(FakeResult()) == "success"


def test_parse_package_core_does_not_overwrite_is_success():
    """_parse_package_core 结尾不得无条件 is_success=True。"""
    import inspect
    from uasset_read.parse_uasset import _parse_package_core

    src = inspect.getsource(_parse_package_core)
    # 查找任何 "result.is_success = True" 的无条件赋值
    lines = src.splitlines()
    bad = [
        ln.strip() for ln in lines
        if "result.is_success" in ln and ln.strip().endswith("= True")
    ]
    assert bad == [], (
        "_parse_package_core 不应无条件设置 is_success=True，"
        f"发现: {bad}"
    )
```

- [ ] **Step 6.2: 运行测试，确认 FAIL**

```bash
pytest tests/unit/test_parse_status_propagation.py -v
```

- [ ] **Step 6.3: 在 `models/result.py` 增加 `compute_overall_status`**

`src/uasset_read/models/result.py`：追加

```python
def compute_overall_status(result) -> str:
    """根据 errors/warnings 与每个 export 的 parse_status 计算整体状态。

    Returns:
        "success" / "partial" / "fail"
    """
    if getattr(result, "errors", None):
        return "fail"

    statuses = []
    for export in getattr(result, "export_map", None) or []:
        s = getattr(export, "parse_status", None)
        if s:
            statuses.append(s)

    if not statuses:
        # 没有 export（或都没有 parse_status）且无错误
        return "success" if not getattr(result, "warnings", None) else "partial"

    if all(s == "success" for s in statuses):
        return "success" if not getattr(result, "warnings", None) else "partial"

    if all(s == "failed" for s in statuses):
        return "fail"

    return "partial"
```

- [ ] **Step 6.4: 修改 `_post_process` 与 `_parse_package_core` 使用新函数**

`src/uasset_read/parse_uasset.py:242`：

```python
    # 设置成功标志（不再只看 errors）
    from uasset_read.models.result import compute_overall_status
    status = compute_overall_status(result)
    result.is_success = status != "fail"
    result.parse_status = status  # 新增字段
```

`src/uasset_read/parse_uasset.py:581`（轻量模式）：

```python
        if _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold):
            result.warnings.append(
                "Lightweight tolerant parse used due to export complexity "
                f"(exports={getattr(result.summary, 'export_count', 0)})"
            )
            result.metadata["lightweight_tolerant_parse"] = True
            result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
            result.parse_status = "partial"
            result.is_success = False  # 不再把 partial 视为 success
            return
```

`src/uasset_read/parse_uasset.py:620`：

```python
        # 共享后处理
        _post_process(...)
        # 不再无条件 result.is_success = True；由 _post_process 统一计算
```

- [ ] **Step 6.5: 在 `ParseResult` 与 `LinkerParseResult` 增加 `parse_status` 字段**

`src/uasset_read/models/result.py`：

```python
@dataclass
class ParseResult:
    ...
    parse_status: str = "pending"  # "pending" | "success" | "partial" | "fail"
```

`src/uasset_read/link/result.py`：

```python
@dataclass
class LinkerParseResult:
    ...
    parse_status: str = "pending"
```

- [ ] **Step 6.6: 运行测试**

```bash
pytest tests/unit/test_parse_status_propagation.py -v
```

- [ ] **Step 6.7: 回归测试 + 既有断言更新**

```bash
pytest tests/unit -q
```

重点检查所有 `assert result.is_success is True` 的测试，确认样本是否真的全 success；若含 opaque/skipped export，改为 `assert result.parse_status in ("success","partial")` 或 `assert result.is_success`（按新语义：partial 不算 success）。

- [ ] **Step 6.8: 提交**

```bash
git add src/uasset_read/models/result.py src/uasset_read/link/result.py src/uasset_read/parse_uasset.py tests/unit/test_parse_status_propagation.py
git commit -m "fix(status): 输出状态由 compute_overall_status 计算，不再无条件 success

- 新增 ParseResult.parse_status / LinkerParseResult.parse_status
- 移除 _parse_package_core 末尾的无条件 is_success=True
- lightweight tolerant 模式不再标记 is_success=True
- 存在 opaque/skipped export 时整体状态为 partial"
```

---

## 验收清单（所有 Phase 完成后）

### 功能验收

- [ ] `pytest tests/unit -q` 全绿。
- [ ] 选取一个 `StaticMesh` / `Texture2D` / `Material` / `AnimSequence` 样本，确认其 `export.parse_status` 为 `"opaque"` 或 `"skipped"`，**不再** 是 `"success"`。
- [ ] 选取一个 BlueprintGeneratedClass 样本，确认仍走 TPS 子区间，`parse_status == "success"`。
- [ ] 运行 `parse_uasset_with_linker()` 后，所有 export 的 `instance._preloaded == True`，且 `instance.serialized_properties is export.properties`。
- [ ] 含 `DependsMap` 的样本：`linker._build_dependency_graph` 之后，`inst.dependencies` 里的实例是通过 `resolve_package_index` 解析来的，支持 import 引用。
- [ ] cooked 包里若有 `SoftObjectPaths`，属性里 `SoftObjectProperty` 读到的 `value["asset_path"]` 与 header 表一致，偏移无错位。
- [ ] 整体 `result.parse_status` 反映真实情况：全 success → `"success"`；含 opaque/skipped → `"partial"`；有 errors 或全 failed → `"fail"`。

### 兼容性验收

- [ ] 既有 `parse_package()` / `parse_uasset()` / `parse_uasset_with_linker()` 公开 API 签名不变。
- [ ] 既有 `is_success` 字段仍存在；新字段 `parse_status` 为可选（default `"pending"`）。
- [ ] 旧测试若假设 `is_success == True` 即"完全解析"，需要按 `parse_status` 重新断言。

### 提交记录（按此顺序 rebase 成线性历史）

1. `refactor(linker): UE 等价生命周期 link→preload(all)→post_load`
2. `refactor(parser): 收窄 ScriptSerializationStartOffset 的使用范围`
3. `refactor(parser): 未实现 Serialize() 的资产类型使用 OPAQUE fallback`
4. `feat(softpath): 分层读取 FSoftObjectPath`
5. `fix(depends): DependsMap 按 FPackageIndex 语义解析`
6. `fix(status): 输出状态由 compute_overall_status 计算，不再无条件 success`

---

## 不在本计划范围内（明确排除）

- **真正为每种资产类型实现 `UStaticMesh::Serialize` 等级的解码器** — 这是另一个专项（每个类型单独成 plan），本计划只建立"未实现即 OPAQUE"的策略与状态传播。
- **UE4 旧版 `FLazyObjectPtr` / `FUniqueObjectGuid` 表** — 当前项目无此需求。
- **BulkData / 外部资源加载** — 本次不扩展。
- **Kismet / Blueprint Graph 重构** — 已有独立管线，本次不动。

后续专项（每个单独一份 plan）：
- `uasset-read-class-serialize-static-mesh`
- `uasset-read-class-serialize-texture`
- `uasset-read-class-serialize-material`
- `uasset-read-class-serialize-anim-sequence`
- `uasset-read-unversioned-properties-with-mappings`
