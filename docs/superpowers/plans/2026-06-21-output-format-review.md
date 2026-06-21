# 输出格式精简实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精简 JSON 输出为 C++ 翻译参考，去掉冗余信息；同步优化 Markdown 输出

**Architecture:** 修改 `json_renderer.py` 和 `markdown_renderer.py`，去掉 `name_map`、`imports`、`linker`、`resolved_depends_map` 等冗余字段，只保留蓝图相关的 exports、blueprint、execution_chains、variables、decompiled_functions

**Tech Stack:** Python 3.10+, dataclasses, pytest

## Global Constraints

- Python 3.10+
- 零运行时依赖
- 测试 100% 通过率
- 样本路径: `E:\Develop\lib\Samples`

---

## File Structure

| 文件 | 职责 |
|------|------|
| `src/uasset_read/renderers/json_renderer.py` | 修改：去掉冗余字段，删除 JsonSummaryRenderer |
| `src/uasset_read/renderers/markdown_renderer.py` | 修改：去掉重复 Linker 小节 |
| `src/uasset_read/renderers/text_renderer.py` | 删除 |
| `src/uasset_read/renderers/blueprint_text_renderer.py` | 删除 |
| `src/uasset_read/renderers/blueprint_ue_renderer.py` | 删除 |
| `src/uasset_read/renderers/cpp_skeleton_renderer.py` | 删除 |
| `src/uasset_read/renderers/__init__.py` | 修改：移除不需要的 import |
| `src/uasset_read/cli.py` | 修改：移除不需要的 CLI 选项 |
| `tests/test_renderers.py` | 修改：更新测试断言 |
| `tests/renderers/test_json_macro_output.py` | 修改：更新宏输出测试 |

---

### Task 1: 精简 JSON Renderer — 去掉顶层冗余字段

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py:41-97`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `PackageIR` (from ir_builder)
- Produces: 精简后的 JSON 字符串

- [ ] **Step 1: 编写测试 — 验证 JSON 不包含冗余字段**

```python
# tests/test_renderers.py 添加测试
def test_json_excludes_redundant_fields():
    """JSON 输出不应包含 name_map, imports, linker 等冗余字段"""
    import json
    from uasset_read.renderers.json_renderer import JSONRenderer
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.models.ir import PackageIR, PackageHeaderIR

    # 创建最小 IR
    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=["test"],
        imports=[],
        exports=[],
    )
    ir.status = "success"

    renderer = JSONRenderer()
    options = RenderOptions()
    result = renderer.render(ir, options)
    data = json.loads(result)

    # 验证不包含冗余字段
    assert "name_map" not in data, "name_map 应被移除"
    assert "imports" not in data, "imports 应被移除"
    assert "linker" not in data, "linker 应被移除"
    assert "resolved_depends_map" not in data, "resolved_depends_map 应被移除"
    assert "depends_map" not in data, "depends_map 应被移除"
    assert "soft_package_references" not in data, "soft_package_references 应被移除"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_json_excludes_redundant_fields -v`
Expected: FAIL (字段仍然存在)

- [ ] **Step 3: 修改 JSONRenderer.render() — 去掉冗余字段**

```python
# src/uasset_read/renderers/json_renderer.py
def render(self, ir: PackageIR, options: RenderOptions) -> str:
    data = {
        "status": {
            "status": ir.status,
            "message": ir.status_message,
            "code": ir.status_code,
        },
        "output_version": _OUTPUT_VERSION_FULL,
        "summary": {
            "package_name": ir.header.package_name,
            "package_class": ir.header.package_class,
            "package_flags": ir.header.package_flags,
            "total_export_count": ir.header.total_export_count,
            "total_import_count": ir.header.total_import_count,
            "ue_version": ir.header.ue_version,
        },
        # name_map 已移除
        # imports 已移除
        "exports": [self._export_to_dict(e, options) for e in ir.exports],
    }
    # linker 已移除
    if ir.blueprint is not None:
        data["blueprint"] = self._blueprint_to_dict(ir.blueprint)
    if ir.decompiled_functions:
        data["decompiled_functions"] = [self._decompiled_function_to_dict(f) for f in ir.decompiled_functions]
    if ir.execution_chains:
        data["execution_chains"] = [{"event": c.event, "chain": c.chain} for c in ir.execution_chains]
    if ir.variables:
        data["variables"] = [self._variable_to_dict(v) for v in ir.variables]
    # diagnostics 已移除
    # resolved_parent_assets 已移除
    # logic_sources 已移除
    # inherited_blueprint_graphs 已移除
    # soft_object_paths 已移除
    # soft_package_references 已移除
    # depends_map 已移除
    # resolved_depends_map 已移除
    # asset_registry_data_offset 已移除
    if ir.errors:
        data["errors"] = ir.errors
    if options.include_function_graphs:
        data["function_graphs"] = self._build_function_graphs(ir)
    return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_json_excludes_redundant_fields -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/json_renderer.py tests/test_renderers.py
git commit -m "refactor: JSON 输出去掉 name_map/imports/linker 等冗余字段"
```

---

### Task 2: 精简 JSON Export — 去掉 ue_export_raw 和 diagnostics

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py:99-145`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `ExportIR` (from ir_builder)
- Produces: 精简后的 export 字典

- [ ] **Step 1: 编写测试 — 验证 export 不包含冗余字段**

```python
# tests/test_renderers.py 添加测试
def test_json_export_excludes_raw_fields():
    """JSON export 不应包含 ue_export_raw, diagnostics, outer_index_resolved 等"""
    import json
    from uasset_read.renderers.json_renderer import JSONRenderer
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.models.ir import (
        PackageIR, PackageHeaderIR, ExportIR, PropertyIR, ExportRawIR
    )

    # 创建带 export 的 IR
    export = ExportIR(
        index=0,
        object_name="TestExport",
        object_class="",
        serial_size=100,
        outer_index_resolved="/Game/Test",
        super_index_resolved="/Script/Engine.Actor",
        parent_class="/Script/Engine.Actor",
        properties=[],
        graphs=[],
        bulk_data=None,
        asset_type_data=None,
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        ue_export_raw=ExportRawIR(),
        diagnostics={"test": "data"},
    )

    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=[],
        imports=[],
        exports=[export],
    )
    ir.status = "success"

    renderer = JSONRenderer()
    options = RenderOptions()
    result = renderer.render(ir, options)
    data = json.loads(result)

    export_data = data["exports"][0]

    # 验证保留的字段
    assert "object_name" in export_data
    assert "object_class" in export_data
    assert "serial_size" in export_data
    assert "parent_class" in export_data
    assert "properties" in export_data
    assert "graphs" in export_data

    # 验证移除的字段
    assert "ue_export_raw" not in export_data, "ue_export_raw 应被移除"
    assert "diagnostics" not in export_data, "diagnostics 应被移除"
    assert "outer_index_resolved" not in export_data, "outer_index_resolved 应被移除"
    assert "super_index_resolved" not in export_data, "super_index_resolved 应被移除"
    assert "index" not in export_data, "index 应被移除（无用）"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_json_export_excludes_raw_fields -v`
Expected: FAIL

- [ ] **Step 3: 修改 _export_to_dict() — 去掉冗余字段**

```python
# src/uasset_read/renderers/json_renderer.py
def _export_to_dict(self, export, options: RenderOptions) -> dict[str, Any]:
    d = {
        # index 已移除
        "object_name": export.object_name,
        "object_class": export.object_class,
        "serial_size": export.serial_size,
        # outer_index_resolved 已移除
        # super_index_resolved 已移除
        "parent_class": export.parent_class,
        "properties": [self._property_to_dict(p) for p in export.properties],
        "graphs": [self._graph_to_dict(g, options) for g in export.graphs],
    }
    # bulk_data 已移除
    # asset_type_data 已移除
    if export.parse_status != "success":
        d["parse_status"] = export.parse_status
    if export.fallback_reason:
        d["fallback_reason"] = export.fallback_reason
    if export.error_message:
        d["error_message"] = export.error_message
    # ue_export_raw 已移除
    # diagnostics 已移除
    return d
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_json_export_excludes_raw_fields -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/json_renderer.py tests/test_renderers.py
git commit -m "refactor: JSON export 去掉 ue_export_raw/diagnostics/outer_index_resolved"
```

---

### Task 3: JSON 只保留蓝图 Export

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py:59`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `PackageIR` (from ir_builder)
- Produces: 仅蓝图 export 的 JSON 数组

- [ ] **Step 1: 编写测试 — 验证 JSON 只包含蓝图 export**

```python
# tests/test_renderers.py 添加测试
def test_json_only_blueprint_exports():
    """JSON 输出应只包含蓝图相关 export（类名以 _C 结尾或有 graphs）"""
    import json
    from uasset_read.renderers.json_renderer import JSONRenderer
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.models.ir import (
        PackageIR, PackageHeaderIR, ExportIR, GraphIR
    )

    # 创建两个 export：一个蓝图，一个非蓝图
    bp_export = ExportIR(
        index=0,
        object_name="BP_Test_C",
        object_class="",
        serial_size=100,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class="/Script/Engine.Actor",
        properties=[],
        graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
        bulk_data=None,
        asset_type_data=None,
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        ue_export_raw=None,
        diagnostics={},
    )

    non_bp_export = ExportIR(
        index=1,
        object_name="BodySetup",
        object_class="",
        serial_size=200,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
        asset_type_data=None,
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        ue_export_raw=None,
        diagnostics={},
    )

    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=2,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=[],
        imports=[],
        exports=[bp_export, non_bp_export],
    )
    ir.status = "success"

    renderer = JSONRenderer()
    options = RenderOptions()
    result = renderer.render(ir, options)
    data = json.loads(result)

    # 验证只包含蓝图 export
    assert len(data["exports"]) == 1, f"应只有 1 个蓝图 export，实际有 {len(data['exports'])}"
    assert data["exports"][0]["object_name"] == "BP_Test_C", "应保留蓝图 export"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_json_only_blueprint_exports -v`
Expected: FAIL

- [ ] **Step 3: 修改 JSONRenderer.render() — 过滤蓝图 export**

```python
# src/uasset_read/renderers/json_renderer.py
def _is_blueprint_export(self, export) -> bool:
    """判断是否为蓝图相关 export"""
    # 类名以 _C 结尾
    if export.object_name.endswith("_C"):
        return True
    # 有 graphs 数据
    if export.graphs:
        return True
    return False

def render(self, ir: PackageIR, options: RenderOptions) -> str:
    # ... 前面的代码不变 ...

    # 过滤只保留蓝图 export
    blueprint_exports = [e for e in ir.exports if self._is_blueprint_export(e)]
    data["exports"] = [self._export_to_dict(e, options) for e in blueprint_exports]

    # ... 后面的代码不变 ...
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_json_only_blueprint_exports -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/json_renderer.py tests/test_renderers.py
git commit -m "refactor: JSON 只保留蓝图相关 export"
```

---

### Task 4: Markdown 只保留蓝图 Export

**Files:**
- Modify: `src/uasset_read/renderers/markdown_renderer.py:170-182`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `PackageIR` (from ir_builder)
- Produces: 仅蓝图 export 的 Markdown 表格

- [ ] **Step 1: 编写测试 — 验证 Markdown 只包含蓝图 export**

```python
# tests/test_renderers.py 添加测试
def test_markdown_only_blueprint_exports():
    """Markdown Export 表格应只包含蓝图相关 export"""
    from uasset_read.renderers.markdown_renderer import MarkdownRenderer
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.models.ir import (
        PackageIR, PackageHeaderIR, ExportIR, GraphIR
    )

    bp_export = ExportIR(
        index=0,
        object_name="BP_Test_C",
        object_class="",
        serial_size=100,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class="/Script/Engine.Actor",
        properties=[],
        graphs=[GraphIR(graph_guid="abc", graph_name="EventGraph", graph_class="EdGraph", nodes=[], execution_chains=[])],
        bulk_data=None,
        asset_type_data=None,
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        ue_export_raw=None,
        diagnostics={},
    )

    non_bp_export = ExportIR(
        index=1,
        object_name="BodySetup",
        object_class="",
        serial_size=200,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
        asset_type_data=None,
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        ue_export_raw=None,
        diagnostics={},
    )

    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=2,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=[],
        imports=[],
        exports=[bp_export, non_bp_export],
    )
    ir.status = "success"

    renderer = MarkdownRenderer()
    options = RenderOptions()
    result = renderer.render(ir, options)

    # 验证只包含蓝图 export
    assert "BP_Test_C" in result, "应包含蓝图 export"
    assert "BodySetup" not in result, "不应包含非蓝图 export"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_markdown_only_blueprint_exports -v`
Expected: FAIL

- [ ] **Step 3: 修改 MarkdownRenderer.render() — 过滤蓝图 export**

```python
# src/uasset_read/renderers/markdown_renderer.py
def _is_blueprint_export(self, export) -> bool:
    """判断是否为蓝图相关 export"""
    if export.object_name.endswith("_C"):
        return True
    if export.graphs:
        return True
    return False

def render(self, ir: PackageIR, options: RenderOptions) -> str:
    # ... 前面的代码不变 ...

    # 导出 — 只显示蓝图 export
    blueprint_exports = [e for e in ir.exports if self._is_blueprint_export(e)]
    if blueprint_exports:
        lines.append("## Exports")
        lines.append("| Name | Class | Size | Properties |")
        lines.append("|------|-------|------|------------|")
        for export in blueprint_exports:
            prop_count = len(export.properties) if export.properties else 0
            lines.append(
                f"| {_escape_md_cell(export.object_name)} "
                f"| {_escape_md_cell(export.object_class)} "
                f"| {export.serial_size} "
                f"| {prop_count} |"
            )
        lines.append("")

    # ... 后面的代码不变 ...
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_markdown_only_blueprint_exports -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/markdown_renderer.py tests/test_renderers.py
git commit -m "refactor: Markdown Export 表格只显示蓝图 export"
```

---

### Task 5: Markdown 去掉重复 Linker 小节

**Files:**
- Modify: `src/uasset_read/renderers/markdown_renderer.py:220-227`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `PackageIR` (from ir_builder)
- Produces: 精简后的 Markdown 字符串

- [ ] **Step 1: 编写测试 — 验证 Markdown 不包含 Linker 小节**

```python
# tests/test_renderers.py 添加测试
def test_markdown_excludes_linker_section():
    """Markdown 输出不应包含 Linker 小节"""
    from uasset_read.renderers.markdown_renderer import MarkdownRenderer
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.models.ir import PackageIR, PackageHeaderIR, LinkerIR

    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=[],
        imports=[],
        exports=[],
        linker=LinkerIR(
            has_linker=True,
            import_paths=["/Script/Engine"],
            export_paths=["/Game/Test"],
        ),
    )
    ir.status = "success"

    renderer = MarkdownRenderer()
    options = RenderOptions()
    result = renderer.render(ir, options)

    # 验证不包含 Linker 小节
    assert "## Linker" not in result, "Linker 小节应被移除"
    assert "Has Linker" not in result, "Has Linker 应被移除"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_markdown_excludes_linker_section -v`
Expected: FAIL

- [ ] **Step 3: 修改 MarkdownRenderer.render() — 去掉 Linker 小节**

```python
# src/uasset_read/renderers/markdown_renderer.py
# 在 render() 方法中，删除以下代码块（约 220-227 行）：

# 删除：
if ir.linker is not None:
    lines.append("## Linker")
    lines.append(f"- **Has Linker**: {ir.linker.has_linker}")
    if ir.linker.import_paths:
        lines.append(f"- **Imports**: {len(ir.linker.import_paths)}")
    if ir.linker.export_paths:
        lines.append(f"- **Exports**: {len(ir.linker.export_paths)}")
    lines.append("")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_markdown_excludes_linker_section -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/markdown_renderer.py tests/test_renderers.py
git commit -m "refactor: Markdown 去掉重复的 Linker 小节"
```

---

### Task 6: 运行全量测试验证

**Files:**
- 无新文件

**Interfaces:**
- 无

- [ ] **Step 1: 运行渲染器测试**

Run: `python -m pytest tests/test_renderers.py -v`
Expected: 全部通过

- [ ] **Step 2: 运行集成测试**

Run: `python -m pytest tests/ -v -m integration`
Expected: 全部通过

- [ ] **Step 3: 用样本文件验证输出**

```bash
# 验证 JSON 输出
python run.py "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset" --json 2>/dev/null | python -c "
import sys, json
d = json.load(sys.stdin)
print('=== 验证 JSON 结构 ===')
print(f'顶层键: {list(d.keys())}')
assert 'name_map' not in d, 'name_map 应被移除'
assert 'imports' not in d, 'imports 应被移除'
assert 'linker' not in d, 'linker 应被移除'
print('✓ JSON 结构正确')
"

# 验证 Markdown 输出
python run.py "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset" --markdown 2>/dev/null | grep -c "## Linker"
# 预期: 0
```

- [ ] **Step 4: 提交最终验证**

```bash
git add -A
git commit -m "test: 验证输出格式精简效果"
```

---

### Task 7: 删除非 JSON/Markdown 的输出格式

**Files:**
- Delete: `src/uasset_read/renderers/text_renderer.py`
- Delete: `src/uasset_read/renderers/blueprint_text_renderer.py`
- Delete: `src/uasset_read/renderers/blueprint_ue_renderer.py`
- Delete: `src/uasset_read/renderers/cpp_skeleton_renderer.py`
- Modify: `src/uasset_read/renderers/__init__.py:37-42`
- Modify: `src/uasset_read/cli.py:71-80, 106-124`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: 无
- Produces: 仅保留 json 和 markdown 格式

- [ ] **Step 1: 编写测试 — 验证只支持 json 和 markdown**

```python
# tests/test_renderers.py 添加测试
def test_only_json_and_markdown_formats():
    """应只支持 json 和 markdown 两种格式"""
    from uasset_read.renderers import list_formats

    formats = list_formats()
    assert "json" in formats, "json 格式应存在"
    assert "markdown" in formats, "markdown 格式应存在"
    assert "text" not in formats, "text 格式应被移除"
    assert "text_summary" not in formats, "text_summary 格式应被移除"
    assert "blueprint_text" not in formats, "blueprint_text 格式应被移除"
    assert "blueprint_ue_text" not in formats, "blueprint_ue_text 格式应被移除"
    assert "cpp_skeleton" not in formats, "cpp_skeleton 格式应被移除"
    assert "json_summary" not in formats, "json_summary 格式应被移除"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py::test_only_json_and_markdown_formats -v`
Expected: FAIL

- [ ] **Step 3: 删除不需要的渲染器文件**

```bash
rm src/uasset_read/renderers/text_renderer.py
rm src/uasset_read/renderers/blueprint_text_renderer.py
rm src/uasset_read/renderers/blueprint_ue_renderer.py
rm src/uasset_read/renderers/cpp_skeleton_renderer.py
```

- [ ] **Step 4: 更新 __init__.py — 移除不需要的 import**

```python
# src/uasset_read/renderers/__init__.py
# 删除以下行：
# from uasset_read.renderers import text_renderer  # noqa: F401, E402
# from uasset_read.renderers import blueprint_text_renderer  # noqa: F401, E402
# from uasset_read.renderers import blueprint_ue_renderer  # noqa: F401, E402
# from uasset_read.renderers import cpp_skeleton_renderer  # noqa: F401, E402
```

- [ ] **Step 5: 更新 cli.py — 移除不需要的 CLI 选项**

```python
# src/uasset_read/cli.py
# 在 create_parser() 中，删除以下参数：
# group.add_argument('--text', ...)
# group.add_argument('--text-summary', ...)
# group.add_argument('--summary', ...)
# group.add_argument('--blueprint-text', ...)
# group.add_argument('--blueprint-ue-text', ...)
# group.add_argument('--cpp-skeleton', ...)

# 在 resolve_format() 中，删除以下分支：
# if args.blueprint_text:
#     return "blueprint_text"
# if args.blueprint_ue_text:
#     return "blueprint_ue_text"
# if args.cpp_skeleton:
#     return "cpp_skeleton"
# if args.summary or args.json_summary:
#     return "json_summary"
# if args.text_summary:
#     return "text_summary"
# if args.text:
#     return "text"
# return "text"  # 改为 return "json"
```

- [ ] **Step 6: 更新 json_renderer.py — 移除 JsonSummaryRenderer**

```python
# src/uasset_read/renderers/json_renderer.py
# 删除 JsonSummaryRenderer 类（约 284-343 行）
# 删除 register_renderer("json_summary", JsonSummaryRenderer)
```

- [ ] **Step 7: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::test_only_json_and_markdown_formats -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "refactor: 删除非 JSON/Markdown 的输出格式"
```

---

### Task 8: 更新文档

**Files:**
- Modify: `docs/superpowers/specs/2026-06-21-output-format-review-design.md`

**Interfaces:**
- 无

- [ ] **Step 1: 更新设计文档为完成状态**

```markdown
# 输出格式精简设计

**日期**: 2026-06-21  
**目标**: JSON 输出精简为 C++ 翻译参考，去掉冗余信息  
**影响范围**: 仅 `json` 和 `markdown` 格式  
**状态**: ✅ 已完成

## 完成内容

- [x] JSON 去掉 name_map, imports, linker, resolved_depends_map 等冗余字段
- [x] JSON export 去掉 ue_export_raw, diagnostics, outer_index_resolved, super_index_resolved
- [x] Markdown 去掉重复的 Linker 小节
- [x] 测试 100% 通过
```

- [ ] **Step 2: 提交**

```bash
git add docs/superpowers/specs/2026-06-21-output-format-review-design.md
git commit -m "docs: 更新设计文档状态为已完成"
```
