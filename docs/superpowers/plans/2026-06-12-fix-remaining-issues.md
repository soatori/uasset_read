# 修复剩余 GitHub Issues 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复/关闭全部 6 个 open GitHub issues（#128 #125 #124 #120 + 关闭过时 #130 #131）

**Architecture:** 按优先级分 4 阶段执行：① 关闭过时 issue → ② 移除 cpp_gen/cpp_skeleton（最大代码变更）→ ③ partial 诊断补全 → ④ SerializationControl 语义映射 + 文档清理。每个阶段独立可测试、可提交。

**Tech Stack:** Python 3.10+, pytest, gh CLI

---

## 前置调查结论

| Issue | 优先级 | 结论 | 行动 |
|-------|--------|------|------|
| #130 | P1 | 引用的 4 个测试文件已删除，底层 bug 已在 commit dffc47e/692d99b 修复 | **关闭 issue** |
| #131 | P2 | 引用的 `test_ue_fidelity_integration.py` 已删除，StaticMesh opaque 标记已在 v0.4.5 实现 | **关闭 issue** |
| #128 | P1 | cpp_gen/ 16 个文件 + renderer + CLI + 文档引用需移除 | **实施** |
| #125 | P3 | 4 处代码路径设置 partial/opaque 但无诊断信息 | **实施** |
| #124 | P3 | `parse_ue511_ctrl_flags()` 已定义但未集成，6 个文件处理不一致 | **实施** |
| #120 | P2 | README/wiki 中 20+ 处引用已删除模块（bulk/objects/formatters 等） | **实施** |

---

## 文件结构概览

### 要删除的文件
- `src/uasset_read/cpp_gen/` — 整个目录（16 个文件）
- `src/uasset_read/renderers/cpp_skeleton_renderer.py`

### 要修改的源码文件
- `src/uasset_read/__init__.py` — 移除 cpp_gen 导出（~L218-233）
- `src/uasset_read/core.py` — 移除 cpp_skeleton 格式分支（~L119-134）
- `src/uasset_read/cli.py` — 移除 `--cpp-skeleton` 参数（~L80, L140-141）
- `src/uasset_read/extras/__init__.py` — 移除 cpp_gen 延迟加载
- `src/uasset_read/renderers/__init__.py` — 更新注释
- `src/uasset_read/parsers/property_types/structs.py` — 3 处 opaque 添加诊断
- `src/uasset_read/parsers/property_types/ue5_verse.py` — 1 处 partial 添加诊断
- `src/uasset_read/parsers/_unversioned_parser.py` — 集成 ctrl flags 解析
- `src/uasset_read/parsers/property_parser.py` — 集成 ctrl flags 解析
- `src/uasset_read/constants.py` — 添加 ctrl flags 常量

### 要修改的测试文件
- `tests/test_acceptance.py` — 移除 cpp_skeleton 格式测试
- `tests/test_real_assets.py` — 移除 cpp_skeleton 格式和质量测试
- `tests/test_smoke_core.py` — 新增 partial 诊断测试

### 要修改的文档文件
- `README.md` — 移除 cpp_skeleton 引用 + 更新模块表
- `README.zh-CN.md` — 同上
- `wiki/01-Overview/Architecture.md` — 更新模块结构表
- `wiki/07-Dev-Guide/Contributing.md` — 更新模块表
- `wiki/07-Dev-Guide/Public-API.md` — 移除 cpp_gen API 文档
- `wiki/04-Advanced-Features/CPP-Generator.md` — 删除或标记废弃
- `wiki/06-Output-Export/Formatters.md` — 标记废弃
- `wiki/06-Output-Export/Renderers.md` — 移除 cpp_skeleton 引用
- `wiki/07-Dev-Guide/UE-Reference.md` — 移除 bulk/ 引用
- `wiki/_Sidebar.md` — 移除 Formatters 链接
- `wiki/Home.md` — 移除 Formatters 链接
- `docs/reference/blueprint-to-cpp-guide.md` — 删除或标记废弃

---

## 阶段 1：关闭过时 Issue

### Task 1: 关闭 #130 和 #131

**Files:**
- 无代码变更，仅 GitHub 操作

- [ ] **Step 1: 关闭 #130**

```bash
gh issue close 130 --reason completed --comment "已修复。引用的测试文件（test_acceptance_field_level.py, test_event_execution_fix.py, test_sample_assets_representative.py）已在 v0.4.4 测试重组中移除。底层问题已在 commit dffc47e（self-referencing parent_class 修复）和 692d99b（graph detection + blueprint_text 修复）中解决。当前测试套件（test_acceptance.py, test_real_assets.py）已覆盖相关功能。"
```

- [ ] **Step 2: 关闭 #131**

```bash
gh issue close 131 --reason completed --comment "已修复。引用的 test_ue_fidelity_integration.py 已在测试重组中移除。StaticMesh opaque/partial_metadata 标记已在 v0.4.5 中实现（class_serialization_strategy.py OPAQUE_CLASS_PAYLOAD 策略）。当前测试套件已覆盖。"
```

- [ ] **Step 3: 验证关闭**

```bash
gh issue list --state open --label bug
```

Expected: #130 和 #131 不再出现在列表中

---

## 阶段 2：移除 C++ 生成能力（#128）

### Task 2: 删除 cpp_gen 目录和 cpp_skeleton renderer

**Files:**
- Delete: `src/uasset_read/cpp_gen/` (整个目录)
- Delete: `src/uasset_read/renderers/cpp_skeleton_renderer.py`

- [ ] **Step 1: 删除 cpp_gen 目录**

```bash
rm -rf src/uasset_read/cpp_gen/
```

- [ ] **Step 2: 删除 cpp_skeleton_renderer.py**

```bash
rm src/uasset_read/renderers/cpp_skeleton_renderer.py
```

- [ ] **Step 3: 验证删除**

```bash
ls src/uasset_read/cpp_gen/ 2>&1
ls src/uasset_read/renderers/cpp_skeleton_renderer.py 2>&1
```

Expected: 两个都报 "No such file or directory"

### Task 3: 清理 __init__.py 中的 cpp_gen 导出

**Files:**
- Modify: `src/uasset_read/__init__.py`

- [ ] **Step 1: 读取当前 __init__.py 中 cpp_gen 相关部分**

读取 `src/uasset_read/__init__.py`，定位 cpp_gen 导入块（约 L218-233）。

- [ ] **Step 2: 移除 cpp_gen 导入块**

删除以下导入块（精确匹配后删除）：

```python
# C++ 代码生成
from .cpp_gen import (
    CppProperty, CppHeaderMeta, CppClassIR,
    format_cpp_class_json, format_cpp_header,
    UE_TO_CPP_TYPE_MAP, ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type, ue_package_path_to_cpp_class,
    infer_class_prefix, resolve_ue_type,
    CPF_TO_UPROPERTY_MAP, cpf_flags_to_uproperty_marks,
    extract_cpp_class_skeleton, extract_cpp_constructor,
    format_cpp_call_statements, CppCallParameter, CppMethodIR, CppCallStatement,
    CppStatement, CppCallStmt, CppAssignmentStmt, CppIfStmt,
    CppInlineExprStmt, CppReturnStmt, CppWhileStmt, CppRawStmt,
    kismet_to_cpp_body, format_cpp_default_value, format_cpp_transform,
    format_cpp_component_init, format_cpp_input_action_load,
    build_constructor_sections, sanitize_identifier,
)
```

同时移除 `CppClassSkeletonRenderer` 的导入（如果存在）。

- [ ] **Step 3: 更新 __all__ 列表**

从 `__all__` 中移除所有 cpp_gen 相关符号。

- [ ] **Step 4: 验证 import 不报错**

```bash
python -c "import uasset_read; print('OK')"
```

Expected: 输出 `OK`，无 ImportError

### Task 4: 清理 core.py 中的 cpp_skeleton 格式分支

**Files:**
- Modify: `src/uasset_read/core.py`

- [ ] **Step 1: 读取 core.py 中 cpp_skeleton 相关部分**

读取 `src/uasset_read/core.py`，定位 cpp_skeleton 特殊处理（约 L119-134）。

- [ ] **Step 2: 移除 cpp_skeleton 格式分支**

删除以下代码块：

```python
# cpp_skeleton 走独立管线（不经过标准渲染器注册表）
if format == "cpp_skeleton":
    from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonRenderer
    result = parse_uasset_with_linker(...)
    pipeline = CppSkeletonRenderer()
    return pipeline.generate(result)
```

- [ ] **Step 3: 验证 core.py 无 cpp_skeleton 引用**

```bash
grep -n "cpp_skeleton\|cpp_gen" src/uasset_read/core.py
```

Expected: 无输出

### Task 5: 清理 cli.py 中的 --cpp-skeleton 参数

**Files:**
- Modify: `src/uasset_read/cli.py`

- [ ] **Step 1: 读取 cli.py 中 cpp_skeleton 相关部分**

读取 `src/uasset_read/cli.py`，定位 `--cpp-skeleton` 参数定义（~L80）和格式解析（~L140-141）。

- [ ] **Step 2: 移除 CLI 参数定义**

删除：
```python
group.add_argument('--cpp-skeleton', action='store_true', help='Output C++ class skeleton')
```

- [ ] **Step 3: 移除格式解析逻辑**

删除：
```python
if args.cpp_skeleton:
    return "cpp_skeleton"
```

- [ ] **Step 4: 验证 CLI 帮助无 cpp-skeleton**

```bash
python run.py --help 2>&1 | grep -i "cpp"
```

Expected: 无输出

### Task 6: 清理 extras/__init__.py 中的 cpp_gen 引用

**Files:**
- Modify: `src/uasset_read/extras/__init__.py`

- [ ] **Step 1: 读取 extras/__init__.py**

读取文件，定位 cpp_gen 延迟加载逻辑。

- [ ] **Step 2: 移除 cpp_gen 从 extras 模块**

删除 `cpp_gen` 相关的 `__getattr__` 分支和 `_EXTRA_MODULES` 中的条目。

- [ ] **Step 3: 验证 extras 模块不报错**

```bash
python -c "from uasset_read.extras import *; print('OK')"
```

Expected: 输出 `OK`

### Task 7: 更新 renderers/__init__.py 注释

**Files:**
- Modify: `src/uasset_read/renderers/__init__.py`

- [ ] **Step 1: 更新注释**

将注释 `# 注意：cpp_skeleton 已拆分为独立管线，不再通过渲染器注册表分发` 修改为 `# cpp_skeleton 已移除（v0.4.5+），项目聚焦 uasset 解析`。

### Task 8: 更新测试文件移除 cpp_skeleton 引用

**Files:**
- Modify: `tests/test_acceptance.py`
- Modify: `tests/test_real_assets.py`

- [ ] **Step 1: 更新 test_acceptance.py**

在 `test_acceptance.py` 中，找到格式遍历列表（约 L34-37）：
```python
for format_name in ["text", "markdown", "blueprint_text", "blueprint_ue_text", "cpp_skeleton"]:
```

移除 `"cpp_skeleton"`：
```python
for format_name in ["text", "markdown", "blueprint_text", "blueprint_ue_text"]:
```

- [ ] **Step 2: 更新 test_real_assets.py**

在 `test_real_assets.py` 中：

1. 从 `FORMATS` 列表中移除 `"cpp_skeleton"`（约 L13-21）
2. 删除 `test_cpp_skeleton_quality_has_no_obvious_fallback_flood()` 测试函数（约 L40-47）

- [ ] **Step 3: 运行测试验证**

```bash
$env:PYTHONPATH='.'; python -m pytest tests/ -q --tb=short
```

Expected: 全部通过，无 cpp_skeleton 相关失败

### Task 9: 提交阶段 2 变更

- [ ] **Step 1: 提交**

```bash
git add -A
git commit -m "refactor: 移除 cpp_gen/cpp_skeleton C++ 代码生成能力 (#128)"
```

---

## 阶段 3：partial 状态诊断补全（#125）

### Task 10: 为 structs.py 中 3 处 opaque 添加诊断

**Files:**
- Modify: `src/uasset_read/parsers/property_types/structs.py`

- [ ] **Step 1: 读取 structs.py 中 3 处 opaque 设置点**

定位以下 3 处（约 L403, L640, L690）：

```python
# L403: 负数 struct size
return StructValue(struct_type=..., fields={}, raw_size=tag.size, parse_status="opaque")

# L640: 零/negative struct size
return StructValue(struct_type=..., fields={}, raw_size=tag.size, parse_status="opaque")

# L690: struct parse exception
return StructValue(struct_type=..., fields={}, raw_size=tag.size, parse_status="opaque")
```

- [ ] **Step 2: 为每处添加 unsupported_reason**

L403 修改为：
```python
return StructValue(
    struct_type=declared_struct_type or "UnknownStruct",
    fields={},
    raw_size=tag.size,
    parse_status="opaque",
    unsupported_reason=f"negative_struct_size:{tag.size}",
)
```

L640 修改为：
```python
return StructValue(
    struct_type=declared_struct_type or "UnknownStruct",
    fields={},
    raw_size=tag.size,
    parse_status="opaque",
    unsupported_reason=f"zero_struct_size",
)
```

L690 修改为：
```python
return StructValue(
    struct_type=declared_struct_type or "UnknownStruct",
    fields={},
    raw_size=tag.size,
    parse_status="opaque",
    unsupported_reason=f"struct_parse_exception:{type(e).__name__}:{e}",
)
```

- [ ] **Step 3: 确认 StructValue 支持 unsupported_reason 字段**

检查 `models/properties.py` 中 `StructValue` 定义。如果 `unsupported_reason` 不是已有字段，需要添加。

```bash
grep -n "class StructValue" src/uasset_read/models/properties.py
```

如果 StructValue 没有 `unsupported_reason`，在其 dataclass 定义中添加：
```python
unsupported_reason: str = ""
```

### Task 11: 为 ue5_verse.py 中 partial 添加诊断

**Files:**
- Modify: `src/uasset_read/parsers/property_types/ue5_verse.py`

- [ ] **Step 1: 读取 ue5_verse.py 中 partial 设置点**

定位约 L105：
```python
parse_status = "partial"
result["path"] = path
```

- [ ] **Step 2: 添加诊断信息**

修改为：
```python
parse_status = "partial"
result["path"] = path
# ...
if parse_status != "parsed":
    result["parse_status"] = parse_status
    result["unsupported_reason"] = "fieldpath_missing_name_map"
```

### Task 12: 确保 compute_result_status 传播诊断

**Files:**
- Modify: `src/uasset_read/status.py`

- [ ] **Step 1: 读取 status.py**

理解 `compute_result_status()` 逻辑。确认当 export 级别有 `fallback_reason` 或 struct 级别有 `unsupported_reason` 时，package 级别的 warnings/diagnostics 能收集到这些信息。

- [ ] **Step 2: 添加诊断收集逻辑**

在 `compute_result_status()` 或 post_process 中，遍历所有 export 的 struct 值，收集 `unsupported_reason` 到 warnings 列表：

```python
# 在 status 计算后，收集所有 partial/opaque 的原因
for export in result.exports:
    if hasattr(export, 'fallback_reason') and export.fallback_reason:
        if f"fallback: {export.fallback_reason}" not in result.warnings:
            result.warnings.append(f"fallback: {export.fallback_reason}")
```

### Task 13: 添加 partial 诊断测试

**Files:**
- Modify: `tests/test_smoke_core.py`

- [ ] **Step 1: 编写测试**

在 `tests/test_smoke_core.py` 中添加：

```python
def test_partial_status_has_diagnostic_reason():
    """partial/opaque 状态必须附带可追踪原因"""
    from uasset_read.models.properties import StructValue

    # 构造一个 opaque struct
    sv = StructValue(
        struct_type="TestStruct",
        fields={},
        raw_size=-1,
        parse_status="opaque",
        unsupported_reason="negative_struct_size:-1",
    )
    assert sv.parse_status == "opaque"
    assert sv.unsupported_reason != ""
    assert "negative_struct_size" in sv.unsupported_reason
```

- [ ] **Step 2: 运行测试**

```bash
$env:PYTHONPATH='.'; python -m pytest tests/test_smoke_core.py::test_partial_status_has_diagnostic_reason -v
```

Expected: PASS

- [ ] **Step 3: 运行全量测试**

```bash
$env:PYTHONPATH='.'; python -m pytest tests/ -q --tb=short
```

Expected: 全部通过

### Task 14: 提交阶段 3 变更

- [ ] **Step 1: 提交**

```bash
git add -A
git commit -m "fix: partial/opaque 状态必须附带可追踪诊断原因 (#125)"
```

---

## 阶段 4：SerializationControl 语义映射 + 文档清理（#124 + #120）

### Task 15: 集成 parse_ue511_ctrl_flags() 到所有读取点

**Files:**
- Modify: `src/uasset_read/parsers/_unversioned_parser.py`
- Modify: `src/uasset_read/parsers/property_parser.py`

- [ ] **Step 1: 读取 _unversioned_parser.py 中 ctrl 处理逻辑**

定位约 L135-159，找到 unknown_bits 计算和 warning 输出。

- [ ] **Step 2: 替换为结构化诊断**

将当前的：
```python
unknown_bits = serialization_control & ~0x02
if unknown_bits:
    logger.warning("Export '%s' SerializationControlExtensions 未知位: 0x%02X (offset %d)", ...)
```

替换为：
```python
from uasset_read.serializers.property_tags import parse_ue511_ctrl_flags
ctrl_info = parse_ue511_ctrl_flags(serialization_control)
unknown_bits = serialization_control & ~0x3F  # 已知位掩码 0x01|0x02|0x04|0x08|0x10|0x20
if unknown_bits:
    logger.warning(
        "Export '%s' SerializationControlExtensions 未知位: 0x%02X "
        "(已知位: has_array_index=%s, serialize_control=%s, has_extensions=%s, "
        "has_binary_or_native=%s, bool_true=%s, skipped_serialize=%s; offset %d)",
        export_name, serialization_control,
        ctrl_info["has_array_index"], ctrl_info["serialize_control"],
        ctrl_info["has_extensions"], ctrl_info["has_binary_or_native"],
        ctrl_info["bool_true"], ctrl_info["skipped_serialize"],
        offset,
    )
```

- [ ] **Step 3: 对 property_parser.py 做同样修改**

定位 `_apply_serialization_control_header()` 方法（约 L406-429），做同样的结构化诊断替换。

### Task 16: 更新 constants.py 添加完整 ctrl flags 常量

**Files:**
- Modify: `src/uasset_read/constants.py`

- [ ] **Step 1: 添加 SerializationControl 位掩码常量**

在 constants.py 中添加：

```python
# SerializationControlExtensions 完整位定义
CTRL_HAS_ARRAY_INDEX = 0x01
CTRL_HAS_PROPERTY_GUID = 0x02       # = PROP_TAG_HAS_PROPERTY_GUID
CTRL_HAS_EXTENSIONS = 0x04
CTRL_HAS_BINARY_OR_NATIVE = 0x08
CTRL_BOOL_TRUE = 0x10
CTRL_SKIPPED_SERIALIZE = 0x20
CTRL_KNOWN_MASK = 0x3F              # 所有已知位的掩码
```

### Task 17: 添加 ctrl flags 诊断测试

**Files:**
- Modify: `tests/test_smoke_core.py`

- [ ] **Step 1: 编写测试**

```python
def test_serialization_control_flags_parsed():
    """SerializationControlExtensions 已知位应被结构化解析"""
    from uasset_read.serializers.property_tags import parse_ue511_ctrl_flags

    # 0x03 = has_array_index + serialize_control
    result = parse_ue511_ctrl_flags(0x03)
    assert result["has_array_index"] is True
    assert result["serialize_control"] is True
    assert result["has_extensions"] is False

    # 0x00 = 无扩展
    result = parse_ue511_ctrl_flags(0x00)
    assert all(v is False for v in result.values())
```

- [ ] **Step 2: 运行测试**

```bash
$env:PYTHONPATH='.'; python -m pytest tests/test_smoke_core.py::test_serialization_control_flags_parsed -v
```

Expected: PASS

### Task 18: 清理文档中的陈旧模块引用（#120）

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `wiki/01-Overview/Architecture.md`
- Modify: `wiki/07-Dev-Guide/Contributing.md`
- Modify: `wiki/07-Dev-Guide/Public-API.md`
- Modify: `wiki/06-Output-Export/Renderers.md`
- Modify: `wiki/07-Dev-Guide/UE-Reference.md`
- Modify: `wiki/_Sidebar.md`
- Modify: `wiki/Home.md`
- Delete: `wiki/04-Advanced-Features/CPP-Generator.md`
- Delete: `docs/reference/blueprint-to-cpp-guide.md`

- [ ] **Step 1: 更新 README.md**

1. 移除所有 `cpp_skeleton` / `cpp_gen` 引用（约 L3, L103, L135, L145, L173, L203, L322）
2. 移除 `uasset_read.objects`, `uasset_read.bulk` 遗留 API 表引用（~L146）
3. 移除迁移指南中的 `from uasset_read.objects import *` / `from uasset_read.bulk import *`（~L185-186）
4. 更新模块结构表，确保只列出当前存在的目录

- [ ] **Step 2: 更新 README.zh-CN.md**

1. 移除 `cpp_skeleton` 引用（约 L3, L101, L136, L150, L272）
2. 移除模块结构表中的 `bulk/`, `objects/`, `formatters/`（~L277-280）

- [ ] **Step 3: 更新 wiki/01-Overview/Architecture.md**

1. 更新模块结构表，移除 `bulk/`, `objects/`, `formatters/`（~L65-67）
2. 移除 cpp_skeleton 相关描述（~L62, L70-88）

- [ ] **Step 4: 更新 wiki/07-Dev-Guide/Contributing.md**

移除模块表中的 `formatters/`（~L49）

- [ ] **Step 5: 更新 wiki/07-Dev-Guide/Public-API.md**

1. 移除 cpp_gen API 文档部分
2. 将 `formatters` 部分标记为已废弃（添加 `> ⚠️ 已废弃，使用 renderers/ 替代`）
3. 将 `bulk/` 和 `objects/` 部分标记为已废弃

- [ ] **Step 6: 更新 wiki/06-Output-Export/Renderers.md**

移除 cpp_skeleton renderer 引用（~L78, L125）

- [ ] **Step 7: 更新 wiki/07-Dev-Guide/UE-Reference.md**

移除 `bulk/` 映射引用（~L41）

- [ ] **Step 8: 更新 wiki/_Sidebar.md 和 wiki/Home.md**

移除 `[[格式化器|Formatters]]` 链接

- [ ] **Step 9: 删除废弃的 CPP-Generator wiki 页面**

```bash
rm wiki/04-Advanced-Features/CPP-Generator.md
```

- [ ] **Step 10: 删除废弃的 blueprint-to-cpp guide**

```bash
rm docs/reference/blueprint-to-cpp-guide.md
```

### Task 19: 运行全量测试验证

- [ ] **Step 1: 运行全量测试**

```bash
$env:PYTHONPATH='.'; python -m pytest tests/ -q --tb=short
```

Expected: 全部通过，无 cpp_skeleton 相关失败

- [ ] **Step 2: 验证 CLI 帮助**

```bash
python run.py --help
```

Expected: 无 `--cpp-skeleton` 选项

- [ ] **Step 3: 验证 import**

```bash
python -c "import uasset_read; print([x for x in dir(uasset_read) if 'cpp' in x.lower()])"
```

Expected: `[]`（无 cpp 相关导出）

### Task 20: 提交阶段 4 变更

- [ ] **Step 1: 提交**

```bash
git add -A
git commit -m "feat: SerializationControl 语义映射 + 文档清理 (#124, #120)"
```

---

## 阶段 5：关闭已修复 Issue

### Task 21: 关闭 #128, #125, #124, #120

- [ ] **Step 1: 关闭 #128**

```bash
gh issue close 128 --reason completed --comment "已移除 cpp_gen/ 目录（16 文件）+ cpp_skeleton_renderer.py + CLI 参数 + 文档引用。项目聚焦 uasset 解析目标。"
```

- [ ] **Step 2: 关闭 #125**

```bash
gh issue close 125 --reason completed --comment "已为 4 处 partial/opaque 设置点添加 unsupported_reason 诊断字段（structs.py ×3, ue5_verse.py ×1）。status 计算逻辑收集 fallback_reason 到 warnings。"
```

- [ ] **Step 3: 关闭 #124**

```bash
gh issue close 124 --reason completed --comment "已集成 parse_ue511_ctrl_flags() 到 _unversioned_parser.py 和 property_parser.py。未知位 warning 现在包含已知位结构化解析结果。添加 CTRL_KNOWN_MASK 常量。"
```

- [ ] **Step 4: 关闭 #120**

```bash
gh issue close 120 --reason completed --comment "已清理 README/README.zh-CN/wiki 中对 bulk/objects/formatters/cpp_gen 的陈旧引用。删除 CPP-Generator.md 和 blueprint-to-cpp-guide.md。"
```

- [ ] **Step 5: 验证所有 issue 已关闭**

```bash
gh issue list --state open
```

Expected: 无 open issue（或仅剩非本次范围的 issue）

---

## 完成标准

- [ ] 所有 6 个 issue 已关闭（#130 #131 直接关闭，#128 #125 #124 #120 修复后关闭）
- [ ] `cpp_gen/` 目录和 `cpp_skeleton_renderer.py` 已删除
- [ ] CLI 无 `--cpp-skeleton` 选项
- [ ] `import uasset_read` 无 cpp 相关导出
- [ ] partial/opaque 状态均有 `unsupported_reason` 或 `fallback_reason`
- [ ] SerializationControlExtensions warning 包含结构化位解析
- [ ] 文档中无已删除模块的陈旧引用
- [ ] 全量测试通过
