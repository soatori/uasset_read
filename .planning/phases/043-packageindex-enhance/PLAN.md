# Phase 43: PackageIndex 增强 — PLAN.md

**Date:** 2026-05-14
**Phase:** 043-packageindex-enhance
**Goal:** 实现 `resolve_with_linker()` — 将 PackageIndex 解析从字符串/dict 引用全面升级为通过 linker 返回 `UObjectInstance` 实际引用。

**依赖:** Phase 41 (link/ 模块已完成)
**工作量:** ~0.5h

---

## Task 1: 前置修复 — PackageLinker 公开属性

**文件:** `src/uasset_read/link/linker.py`

`UObjectInstance.get_full_name()` 引用 `self.linker.summary` 和 `self.linker.name_map`，但 linker 中存储的是 `_summary` 和 `_name_map`。

**变更:** `__init__` 中新增：
```python
self.summary = summary
self.name_map = name_map
```

---

## Task 2: 新增 4 个 linker 版函数 + 移除旧函数

**文件:** `src/uasset_read/serializers/object_resources.py`

### 新增函数

```python
def resolve_class_name_with_linker(
    class_index: PackageIndex, linker: "PackageLinker",
) -> Optional[str]:
    if class_index.is_null: return None
    inst = linker.resolve_package_index(class_index)
    return inst.object_name if inst else None

def get_asset_class_with_linker(
    export: ObjectExport, linker: "PackageLinker",
) -> Optional[str]:
    inst = linker.resolve_package_index(export.class_index)
    return inst.object_name if inst else None

def detect_blueprint_with_linker(
    export: ObjectExport, linker: "PackageLinker",
) -> bool:
    cls = get_asset_class_with_linker(export, linker)
    return cls is not None and "Blueprint" in cls

def resolve_parent_class_with_linker(
    super_index: PackageIndex, linker: "PackageLinker",
) -> Tuple[Optional[str], Optional[str]]:
    if super_index.is_null: return None, None
    inst = linker.resolve_package_index(super_index)
    if inst is not None: return inst.object_name, None
    return None, f"Parent resolution failed for index {super_index.index}"
```

### 移除函数

- 删除 `resolve_package_index_to_reference()` (line 396-447, ~52行)
- 删除 `_resolve_class_name()` (line 450-463, ~14行)

---

## Task 3: graph.py 全面替换为 linker 版函数

**文件:** `src/uasset_read/serializers/graph.py`

**决策:** 用户选择"全面替换"，graph.py 中 7 处 `resolve_class_name` 和 2 处 `get_asset_class` 必须更新。

**策略:** 所有 graph.py 函数已有 `import_map` 和 `export_map` 参数。改为新增可选 `linker` 参数，优先使用 linker 版函数。

### 3a. 修改 import 行 (line 30)

```python
# 旧:
from uasset_read.serializers.object_resources import resolve_class_name, get_asset_class, PackageIndex
# 新:
from uasset_read.serializers.object_resources import (
    resolve_class_name, resolve_class_name_with_linker,
    get_asset_class, get_asset_class_with_linker,
    PackageIndex,
)
```

### 3b. 修改函数签名 — 所有接受 import_map/export_map 的函数新增 `linker=None`

涉及的函数（均需加 `linker: Optional["PackageLinker"] = None` 参数）:
- `read_fmember_reference` (line 549)
- `read_k2node_call_function` (line 581)
- `read_k2node_event` (line 596)
- `read_ue_graph_node` (line 693)
- `read_ue_graph` (line 880)
- `read_pin_reference` (line 310) — 不需要 linker，不改
- `read_pin_array` (line 339) — 不需要 linker，不改
- `read_ue_graph_pin` (line 367) — 不需要 linker，不改
- `create_node_from_archive` (line 651)

### 3c. 修改调用点

| 行 | 旧调用 | 新调用 |
|----|--------|--------|
| 559 | `resolve_class_name(PackageIndex(mp_idx), import_map, export_map)` | `(resolve_class_name_with_linker(PackageIndex(mp_idx), linker) if linker else resolve_class_name(PackageIndex(mp_idx), import_map, export_map))` |
| 705 | `get_asset_class(node_export, import_map, export_map)` | `(get_asset_class_with_linker(node_export, linker) if linker else get_asset_class(node_export, import_map, export_map))` |
| 763 | `resolve_class_name(PackageIndex(mp_idx), import_map, export_map)` | 同上 |
| 798 | `resolve_class_name(PackageIndex(mp_idx), import_map, export_map)` | 同上 |
| 859 | `resolve_class_name(node_export.class_index, import_map, export_map)` | 同上 |
| 897 | `resolve_class_name(PackageIndex(schema_index), import_map, export_map)` | 同上 |
| 923 | `get_asset_class(node_export, import_map, export_map)` | 同上 |

> 为减少代码重复，可提取辅助函数：
> ```python
> def _rcn(idx, im, em, lk):
>     return (resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em))
> def _gac(exp, im, em, lk):
>     return (get_asset_class_with_linker(exp, lk) if lk else get_asset_class(exp, im, em))
> ```

---

## Task 4: 修改 `property_parser.py`

**文件:** `src/uasset_read/parsers/property_parser.py`

### 4a. 移除旧 import (line 22-24)

```python
# 移除:
from uasset_read.serializers.object_resources import (
    ObjectExport, PackageIndex, resolve_package_index_to_reference,
)
# 改为:
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
```

### 4b. `parse_properties_from_export()` 签名新增参数 (line 99)

```python
def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: Any,
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None,
    linker: Optional[Any] = None,  # 新增
) -> List[PropertyValue]:
```

### 4c. ObjectProperty 增强逻辑替换 (line 204-209)

```python
# 旧:
if import_map is not None and tag.type == "ObjectProperty" and isinstance(value, int):
    pkg_idx = PackageIndex(value)
    ref = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
    if ref and ref.get("source") == "import_map":
        properties[-1].value = ref

# 新:
if linker is not None and tag.type == "ObjectProperty" and isinstance(value, int):
    pkg_idx = PackageIndex(value)
    inst = linker.resolve_package_index(pkg_idx)
    if inst is not None:
        properties[-1].value = {
            "type": "import" if inst.is_import else "export",
            "object_name": inst.object_name,
            "object_class": inst.object_class,
            "full_name": inst.get_full_name(),
        }
```

---

## Task 5: 修改 `variable_extractor.py`

**文件:** `src/uasset_read/blueprint/variable_extractor.py`

### 5a. `extract_blueprint_metadata()` 签名新增参数 (line 332)

```python
def extract_blueprint_metadata(
    export, archive, import_map, export_map, name_map, summary,
    linker=None,  # 新增
) -> tuple:
```

### 5b. resolve_parent_class 调用替换 (line 389-390)

```python
# 旧:
from uasset_read.serializers.object_resources import resolve_parent_class as _rpc
parent_name, warn = _rpc(export.super_index, import_map, export_map)

# 新:
if linker is not None:
    from uasset_read.serializers.object_resources import resolve_parent_class_with_linker as _rpc
    parent_name, warn = _rpc(export.super_index, linker)
else:
    from uasset_read.serializers.object_resources import resolve_parent_class as _rpc
    parent_name, warn = _rpc(export.super_index, import_map, export_map)
```

---

## Task 6: 修改 `parse_uasset.py` — linker 传播

**文件:** `src/uasset_read/parse_uasset.py`

### 6a. `_post_process()` 签名新增参数 (line 27)

```python
def _post_process(
    path, archive, summary, name_map, import_map, export_map, result,
    tolerant=True, linker=None,  # 新增
) -> None:
```

### 6b. `_post_process()` 内 detect_blueprint 调用 (line 70)

```python
# 旧:
if detect_blueprint(export, import_map, export_map):

# 新:
if linker is not None:
    from uasset_read.serializers.object_resources import detect_blueprint_with_linker
    is_bp = detect_blueprint_with_linker(export, linker)
else:
    from uasset_read.serializers.object_resources import detect_blueprint
    is_bp = detect_blueprint(export, import_map, export_map)
if is_bp:
```

### 6c. `_post_process()` 内 extract_blueprint_metadata 调用 (line 53)

```python
# 旧:
meta, warn = extract_blueprint_metadata(
    main_bpgc, temp_archive, import_map, export_map, name_map, summary,
)

# 新: 增加 linker=linker 参数
meta, warn = extract_blueprint_metadata(
    main_bpgc, temp_archive, import_map, export_map, name_map, summary,
    linker=linker,
)
```

### 6d. `parse_uasset()` 中两处调用更新

- `parse_properties_from_export()` (line 161) — 不传 linker（保持兼容）
- `_post_process()` (line 174) — 不传 linker

```python
_post_process(
    path, archive, result.summary, result.name_map,
    result.import_map, result.export_map, result, tolerant,
)
```

### 6e. `parse_uasset_with_linker()` 中两处调用更新

- `parse_properties_from_export()` (line 240) — **传入 linker**

```python
export.properties = parse_properties_from_export(
    export, archive, result.summary, result.name_map,
    result.export_map, result.import_map,
    linker=result.linker,  # 新增
)
```

- `_post_process()` (line 268) — **传入 linker**

```python
_post_process(
    path, archive, result.summary, result.name_map,
    result.import_map, result.export_map, result, tolerant,
    linker=result.linker,  # 新增
)
```

---

## Task 7: 修改格式化层

**文件:** `src/uasset_read/formatters/json_formatter.py`, `text_formatter.py`, `markdown_formatter.py`

格式化层接收 `ParseResult`（无 linker）或 `LinkerParseResult`（有 linker）。使用 `hasattr(result, 'linker') and result.linker is not None` 判断。

### json_formatter.py

在 `format_json()` 函数开头提取 linker：
```python
linker = getattr(result, 'linker', None)
```

- line 116: `"class": get_asset_class(exp, result.import_map, result.export_map)` → `(get_asset_class_with_linker(exp, linker) if linker else get_asset_class(exp, result.import_map, result.export_map))`
- line 264: 同上

### text_formatter.py

- line 56: `get_asset_class(...)` → 同上模式
- line 147: `get_asset_class(...)` → 同上模式

### markdown_formatter.py

- line 101: `get_asset_class(...)` → 同上模式

> 三个 formatter 文件各需在函数开头提取 `linker = getattr(result, 'linker', None)`

---

## Task 8: 更新导出表

**文件:** `src/uasset_read/serializers/__init__.py`
- 新增: `resolve_class_name_with_linker`, `get_asset_class_with_linker`, `detect_blueprint_with_linker`, `resolve_parent_class_with_linker`
- 移除: `resolve_package_index_to_reference`

**文件:** `src/uasset_read/__init__.py`
- 新增: 上述 4 个新函数
- 移除: `resolve_package_index_to_reference`

---

## Task 9: 回归测试

```bash
python -m pytest tests/ -v --tb=short
```

目标: 373 passed, 0 failed

---

## 任务依赖图

```
Task 1 (linker 公开属性)
  ↓
Task 2 (新增 linker 函数 + 移除旧函数)
  ↓
Task 3 (graph.py 适配)    Task 4 (property_parser)    Task 5 (variable_extractor)    Task 6 (parse_uasset)    Task 7 (formatter)
  ↓                       ↓                         ↓                          ↓                       ↓
Task 8 (导出表) ←────────────────────────────────────────────────────────────────┘
  ↓
Task 9 (回归测试)
```

## 验证标准

- [ ] 373 测试 0 回归
- [ ] `resolve_package_index_to_reference` 不再被任何源文件引用
- [ ] `parse_uasset()` 行为不变（向后兼容 — 不传 linker 路径）
- [ ] `parse_uasset_with_linker()` 中 ObjectProperty 通过 linker 解析为 UObjectInstance
- [ ] `parse_uasset_with_linker()` 中 blueprint 检测通过 linker 版函数
- [ ] graph.py 中所有 resolve_class_name/get_asset_class 调用在有 linker 时使用 linker 版
- [ ] `UObjectInstance.get_full_name()` 正常工作（summary/name_map 公开属性）
- [ ] 无旧 dict 返回路径残留
