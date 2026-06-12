# 剩余 Issues 清理实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2 个安全漏洞 + 完成 6 个代码质量清理任务

**Architecture:** 分 3 个阶段：(1) 安全加固（#110/#109），(2) API 治理（#116/#117），(3) 代码质量（#118/#119/#108/#77）

**Tech Stack:** Python 3.10+, pytest, pathlib

---

## 阶段 1：安全加固（P0）

### Task 1: 修复 #110 — parse_batch() 路径清理

**Files:**
- Modify: `src/uasset_read/core.py:268`
- Test: `tests/test_core_api.py`

- [ ] **Step 1: 编写失败测试**

在 `tests/test_core_api.py` 的 `TestParseBatch` 类中添加：

```python
def test_parse_batch_sanitizes_filename_with_path_separator(self, tmp_path):
    """恶意文件名包含路径分隔符时应被清理"""
    # 创建带路径分隔符的恶意文件名
    malicious_dir = tmp_path / "input"
    malicious_dir.mkdir()
    malicious_file = malicious_dir / "normal.uasset"
    malicious_file.write_bytes(b"\xc1\x9a\x2b\x2a" + b"\x00" * 100)
    
    # 模拟 stem 包含路径分隔符的情况（通过 mock）
    from unittest.mock import patch
    from pathlib import PurePosixPath
    
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    with patch("pathlib.Path.stem", new_callable=lambda: property(lambda self: "../../etc/passwd")):
        from uasset_read.core import parse_batch
        result = parse_batch(
            input_dir=str(malicious_dir),
            format="json",
            output_dir=str(output_dir),
        )
    
    # 验证输出文件在 output_dir 内，不在外部
    output_files = list(output_dir.glob("**/*"))
    for f in output_files:
        assert f.is_file()
        # 确保文件路径在 output_dir 内
        assert str(f.resolve()).startswith(str(output_dir.resolve()))
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_core_api.py::TestParseBatch::test_parse_batch_sanitizes_filename_with_path_separator -v
```

Expected: FAIL（路径未清理，文件可能写到外部）

- [ ] **Step 3: 实现修复**

在 `src/uasset_read/core.py:268` 修改：

```python
# 修改前（L268）:
out_file = output_path / f"{pf.stem}{ext}"

# 修改后:
# 清理 stem 中的路径分隔符，防止路径遍历
safe_stem = pf.stem.replace("/", "_").replace("\\", "_").replace("..", "_")
out_file = output_path / f"{safe_stem}{ext}"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_core_api.py::TestParseBatch -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/core.py tests/test_core_api.py
git commit -m "fix: sanitize path separators in parse_batch output filename (#110)"
```

---

### Task 2: 修复 #109 — _find_parent_asset_file() 路径遍历校验

**Files:**
- Modify: `src/uasset_read/parse_uasset.py:189-210`
- Test: `tests/test_parse_uasset.py`（新建）

- [ ] **Step 1: 新建测试文件**

创建 `tests/test_parse_uasset.py`：

```python
"""parse_uasset 安全测试"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import _find_parent_asset_file


class TestFindParentAssetFileSecurity:
    """_find_parent_asset_file 路径遍历防护测试"""
    
    def test_rejects_path_traversal_with_dotdot(self, tmp_path):
        """拒绝包含 .. 的 parent_class"""
        # 创建正常文件
        normal_file = tmp_path / "Normal.uasset"
        normal_file.write_bytes(b"\x00" * 10)
        
        # 恶意 parent_class 包含路径遍历
        result = _find_parent_asset_file(
            parent_class="../../../etc/passwd",
            roots=[tmp_path]
        )
        
        # 应返回 None（拒绝恶意路径）
        assert result is None
    
    def test_rejects_path_traversal_with_slash(self, tmp_path):
        """拒绝包含 / 的 parent_class"""
        result = _find_parent_asset_file(
            parent_class="/Script/Engine/Actor",
            roots=[tmp_path]
        )
        assert result is None
    
    def test_rejects_path_traversal_with_backslash(self, tmp_path):
        """拒绝包含 \\ 的 parent_class"""
        result = _find_parent_asset_file(
            parent_class="..\\..\\Windows\\System32",
            roots=[tmp_path]
        )
        assert result is None
    
    def test_accepts_valid_class_name(self, tmp_path):
        """接受合法的类名"""
        # 创建合法文件
        valid_file = tmp_path / "MyParentClass.uasset"
        valid_file.write_bytes(b"\x00" * 10)
        
        result = _find_parent_asset_file(
            parent_class="MyParentClass",
            roots=[tmp_path]
        )
        
        assert result is not None
        assert result.name == "MyParentClass.uasset"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_parse_uasset.py -v
```

Expected: FAIL（当前实现未拒绝恶意路径）

- [ ] **Step 3: 实现修复**

在 `src/uasset_read/parse_uasset.py:189` 修改：

```python
def _find_parent_asset_file(parent_class: str, roots: Sequence[Path]) -> Optional[Path]:
    """查找父资产文件
    
    安全检查：拒绝包含路径遍历字符的 parent_class
    """
    # 安全校验：拒绝路径遍历
    if ".." in parent_class or "/" in parent_class or "\\" in parent_class:
        logger.debug(
            "Rejecting parent_class with path traversal characters: %r",
            parent_class
        )
        return None
    
    target_name = f"{parent_class}.uasset"
    seen: set[Path] = set()
    
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if root in seen or not root.exists():
            continue
        seen.add(root)
        
        direct = root / target_name
        if direct.is_file():
            return direct
        
        if root.is_dir():
            try:
                match = next(root.rglob(target_name), None)
            except OSError:
                match = None
            if match is not None and match.is_file():
                return match
    
    return None
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_parse_uasset.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parse_uasset.py tests/test_parse_uasset.py
git commit -m "fix: reject path traversal in _find_parent_asset_file (#109)"
```

---

## 阶段 2：API 治理（P1）

### Task 3: 实现 #116 — 收缩 uasset_read 根 API

**Files:**
- Modify: `src/uasset_read/__init__.py:275-370`
- Create: `docs/api-stability.md`

- [ ] **Step 1: 审计当前导出**

运行以下脚本分析当前 `__all__`：

```bash
python -c "
from uasset_read import __all__
print(f'当前导出数量: {len(__all__)}')
for name in sorted(__all__):
    print(f'  - {name}')
"
```

记录输出（约 150+ 符号）。

- [ ] **Step 2: 定义稳定 API 集合**

在 `src/uasset_read/__init__.py` 顶部添加注释：

```python
"""uasset_read — 虚幻引擎 .uasset 文件解析器

API 稳定性策略：
- 稳定 API：parse_single, parse_batch, parse_package, ParseResult, 核心模型类
- 内部实现：serializers/*, parsers/*, graph/*, kismet/*, cpp_gen/* 等子模块
- 内部 API 可通过完整路径访问（如 uasset_read.serializers.package_summary）
"""

# 稳定公共 API（用户直接使用）
STABLE_PUBLIC_API = {
    # 核心函数
    "parse_single",
    "parse_batch", 
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
    "list_formats",
    
    # 结果模型
    "ParseResult",
    "PackageSummary",
    "ExportEntry",
    "ImportEntry",
    "BatchResult",
    
    # 核心模型
    "PackageIR",
    "ExportIR",
    "GraphIR",
    "NodeIR",
    "PinIR",
    
    # 异常
    "UAssetError",
    "ParseError",
    "UnsupportedVersionError",
    
    # 底层工具（高级用户）
    "FArchive",
    "PackageBundle",
    "PackageLinker",
}
```

- [ ] **Step 3: 重构 __all__**

修改 `src/uasset_read/__init__.py:275-370`：

```python
# 修改前：150+ 符号
__all__ = [
    # ... 大量内部实现 ...
]

# 修改后：仅稳定 API
__all__ = sorted(STABLE_PUBLIC_API)
```

- [ ] **Step 4: 编写 API 稳定性文档**

创建 `docs/api-stability.md`：

```markdown
# API 稳定性策略

## 稳定 API（__all__ 导出）

以下符号通过 `from uasset_read import *` 可用，承诺向后兼容：

### 核心函数
- `parse_single(path, ...)` — 解析单个文件
- `parse_batch(input_dir, ...)` — 批量解析
- `parse_package(path)` — 底层解析入口
- `list_formats()` — 列出支持的输出格式

### 结果模型
- `ParseResult` — 解析结果容器
- `PackageSummary` — 包摘要
- `ExportEntry` / `ImportEntry` — 导入/导出条目
- `BatchResult` — 批量解析结果

### IR 模型
- `PackageIR` / `ExportIR` / `GraphIR` / `NodeIR` / `PinIR`

### 异常
- `UAssetError` — 基础异常
- `ParseError` — 解析错误
- `UnsupportedVersionError` — 不支持的版本

### 高级工具
- `FArchive` — 二进制读取器
- `PackageBundle` — 包容器
- `PackageLinker` — 链接器

## 内部 API（子模块路径访问）

以下模块为内部实现，可通过完整路径访问，但不承诺稳定性：

```python
# 可用但不稳定
from uasset_read.serializers.package_summary import read_package_summary
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.graph.flow_builder import build_graph_ir
from uasset_read.kismet.pipeline import KismetPipeline
```

**变更策略**：内部 API 可在 minor 版本中修改/删除，无需弃用期。

## 迁移指南

如果你当前使用了内部 API，建议：

1. 检查是否有稳定 API 替代
2. 如无替代，锁定版本或 fork
3. 提交 issue 请求将常用内部 API 提升为稳定 API
```

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/ -v -k "not slow" --tb=short
```

Expected: 所有测试通过（内部 API 仍可通过子模块路径访问）

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/__init__.py docs/api-stability.md
git commit -m "refactor: shrink root API to stable public interface (#116)"
```

---

### Task 4: 实现 #117 — core/extras 分层

**Files:**
- Create: `src/uasset_read/extras/__init__.py`
- Modify: `src/uasset_read/__init__.py`
- Create: `docs/architecture/core-extras-split.md`

- [ ] **Step 1: 定义分层策略**

创建 `docs/architecture/core-extras-split.md`：

```markdown
# Core/Extras 分层策略

## Core（核心，始终加载）

始终需要的模块，启动时导入：

- `archive.py` — FArchive 二进制读取
- `constants.py` — 常量定义
- `exceptions.py` — 异常类
- `core.py` — parse_single/parse_batch
- `parse_uasset.py` — 主解析管线
- `package.py` — PackageBundle
- `models/` — 数据模型
- `serializers/` — 表结构序列化
- `parsers/` — 属性解析
- `link/` — 链接器

## Extras（可选，延迟加载）

高级功能，仅在需要时导入：

### Graph 分析
```python
from uasset_read.extras.graph import build_graph_ir, trace_pin_flow
```

### Kismet 字节码
```python
from uasset_read.extras.kismet import KismetPipeline, decompile_function
```

### C++ 生成
```python
from uasset_read.extras.cpp_gen import extract_cpp_class_skeleton
```

### Blueprint 解析
```python
from uasset_read.extras.blueprint import extract_blueprint_metadata
```

## 实现方式

当前所有模块已实现，但未做延迟加载。未来优化方向：

1. 将 graph/kismet/cpp_gen/blueprint 移入 `extras/` 子包
2. 在 `__init__.py` 中移除自动导入
3. 用户需显式 `from uasset_read.extras.xxx import ...`

**兼容性**：当前版本保持向后兼容，所有模块仍可通过原路径访问。
```

- [ ] **Step 2: 创建 extras 占位模块**

创建 `src/uasset_read/extras/__init__.py`：

```python
"""可选高级功能模块

这些模块不是核心解析所必需，提供高级分析能力。

使用方式：
    from uasset_read.extras.graph import build_graph_ir
    from uasset_read.extras.kismet import KismetPipeline
    from uasset_read.extras.cpp_gen import extract_cpp_class_skeleton

当前为占位实现，实际模块仍在原位置（graph/、kismet/、cpp_gen/、blueprint/）。
未来版本可能物理移动到 extras/ 子包。
"""

# 延迟导入包装器（未来优化）
def __getattr__(name):
    """延迟加载 extras 子模块"""
    if name == "graph":
        from uasset_read import graph
        return graph
    elif name == "kismet":
        from uasset_read import kismet
        return kismet
    elif name == "cpp_gen":
        from uasset_read import cpp_gen
        return cpp_gen
    elif name == "blueprint":
        from uasset_read import blueprint
        return blueprint
    raise AttributeError(f"module 'uasset_read.extras' has no attribute {name!r}")


__all__ = ["graph", "kismet", "cpp_gen", "blueprint"]
```

- [ ] **Step 3: 更新 __init__.py 注释**

在 `src/uasset_read/__init__.py` 顶部添加：

```python
"""uasset_read — 虚幻引擎 .uasset 文件解析器

模块分层：
- Core（核心）: archive, constants, exceptions, core, parse_uasset, package, models, serializers, parsers, link
- Extras（可选）: graph, kismet, cpp_gen, blueprint — 通过 uasset_read.extras.* 访问

详见 docs/architecture/core-extras-split.md
"""
```

- [ ] **Step 4: 编写使用示例测试**

创建 `tests/test_extras_import.py`：

```python
"""测试 extras 模块导入"""
import pytest


def test_extras_graph_import():
    """可通过 extras 路径导入 graph"""
    from uasset_read.extras import graph
    assert hasattr(graph, "build_graph_ir")


def test_extras_kismet_import():
    """可通过 extras 路径导入 kismet"""
    from uasset_read.extras import kismet
    assert hasattr(kismet, "KismetPipeline")


def test_extras_cpp_gen_import():
    """可通过 extras 路径导入 cpp_gen"""
    from uasset_read.extras import cpp_gen
    assert hasattr(cpp_gen, "extract_cpp_class_skeleton")


def test_extras_blueprint_import():
    """可通过 extras 路径导入 blueprint"""
    from uasset_read.extras import blueprint
    assert hasattr(blueprint, "extract_blueprint_metadata")


def test_original_path_still_works():
    """原路径仍可访问（向后兼容）"""
    from uasset_read.graph import build_graph_ir
    from uasset_read.kismet import KismetPipeline
    from uasset_read.cpp_gen import extract_cpp_class_skeleton
    from uasset_read.blueprint import extract_blueprint_metadata
    
    assert callable(build_graph_ir)
    assert KismetPipeline is not None
    assert callable(extract_cpp_class_skeleton)
    assert callable(extract_blueprint_metadata)
```

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/test_extras_import.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/extras/ src/uasset_read/__init__.py tests/test_extras_import.py docs/architecture/core-extras-split.md
git commit -m "feat: add extras module for optional advanced features (#117)"
```

---

## 阶段 3：代码质量（P2）

### Task 5: 实现 #118 — 拆分大型测试文件

**Files:**
- Split: `tests/test_version_gating.py` (793 行) → `tests/contracts/test_version_gating.py`
- Split: `tests/test_json_completeness.py` (743 行) → `tests/contracts/test_json_completeness.py`
- Create: `tests/contracts/__init__.py`
- Create: `tests/units/__init__.py`
- Create: `tests/e2e/__init__.py`

- [ ] **Step 1: 创建测试分类目录**

```bash
mkdir -p tests/contracts tests/units tests/e2e
touch tests/contracts/__init__.py tests/units/__init__.py tests/e2e/__init__.py
```

- [ ] **Step 2: 移动契约测试**

契约测试定义输出格式保证，移动大文件：

```bash
# 版本门控契约
mv tests/test_version_gating.py tests/contracts/

# JSON 完整性契约
mv tests/test_json_completeness.py tests/contracts/

# 其他契约测试（>500 行）
mv tests/test_pin_recovery.py tests/contracts/
mv tests/test_control_flow_enhanced.py tests/contracts/
```

- [ ] **Step 3: 移动单元测试**

单元测试测试单个函数/类：

```bash
# Kismet 单元测试
mv tests/test_blueprint_node_cleaner.py tests/units/
mv tests/test_kismet_decompilation.py tests/units/
mv tests/test_function_resolver_enhanced.py tests/units/

# Graph 单元测试
mv tests/test_scs_component_tree.py tests/units/

# CPP 单元测试
mv tests/test_cpp_output_quality.py tests/units/
```

- [ ] **Step 4: 移动 E2E 测试**

E2E 测试完整解析流程：

```bash
mv tests/test_cue4parse_gap_completion.py tests/e2e/
mv tests/test_linker_issues_67_68_69.py tests/e2e/
mv tests/test_linker_lifecycle.py tests/e2e/
```

- [ ] **Step 5: 更新 pytest 配置**

在 `pytest.ini` 添加标记：

```ini
[pytest]
markers =
    contract: 契约测试（输出格式保证）
    unit: 单元测试（单个函数/类）
    e2e: 端到端测试（完整流程）
    integration: 集成测试
    slow: 慢速测试
```

- [ ] **Step 6: 运行测试验证**

```bash
python -m pytest tests/contracts/ -v --tb=short
python -m pytest tests/units/ -v --tb=short
python -m pytest tests/e2e/ -v --tb=short
python -m pytest tests/ -v --tb=short  # 全量
```

Expected: 所有测试通过

- [ ] **Step 7: 提交**

```bash
git add tests/ pytest.ini
git commit -m "test: reorganize tests into contracts/units/e2e directories (#118)"
```

---

### Task 6: 实现 #119 — 源码体积预算

**Files:**
- Create: `scripts/quality/size_budget.py`
- Create: `docs/quality/size-budget-report.md`

- [ ] **Step 1: 创建体积预算脚本**

创建 `scripts/quality/size_budget.py`：

```python
#!/usr/bin/env python3
"""源码体积预算检查

检查规则：
- 单文件不超过 1000 行（硬限制）
- 单文件建议不超过 600 行（软限制）
- 总代码行数不超过 35000 行

用法：
    python scripts/quality/size_budget.py [--strict]
"""
import sys
from pathlib import Path


# 体积预算
MAX_FILE_LINES = 1000  # 硬限制
SOFT_LIMIT_LINES = 600  # 软限制（警告）
MAX_TOTAL_LINES = 35000  # 总代码行数预算


def check_file_size(filepath: Path) -> tuple[int, bool]:
    """检查单个文件行数
    
    Returns:
        (行数, 是否超限)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = len(f.readlines())
    return lines, lines > MAX_FILE_LINES


def main():
    strict = "--strict" in sys.argv
    
    src_dir = Path("src/uasset_read")
    if not src_dir.exists():
        print(f"错误: {src_dir} 不存在", file=sys.stderr)
        sys.exit(1)
    
    # 统计所有 Python 文件
    violations = []
    warnings = []
    total_lines = 0
    file_stats = []
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        lines, over_limit = check_file_size(py_file)
        total_lines += lines
        file_stats.append((py_file, lines))
        
        if over_limit:
            violations.append((py_file, lines))
        elif lines > SOFT_LIMIT_LINES:
            warnings.append((py_file, lines))
    
    # 输出报告
    print("=" * 70)
    print("源码体积预算报告")
    print("=" * 70)
    
    print(f"\n总代码行数: {total_lines:,} / {MAX_TOTAL_LINES:,}")
    if total_lines > MAX_TOTAL_LINES:
        print(f"  ❌ 超出预算 {total_lines - MAX_TOTAL_LINES} 行")
    else:
        print(f"  ✅ 剩余预算 {MAX_TOTAL_LINES - total_lines} 行")
    
    print(f"\n文件数量: {len(file_stats)}")
    
    if violations:
        print(f"\n❌ 硬限制违规（>{MAX_FILE_LINES} 行）:")
        for filepath, lines in sorted(violations, key=lambda x: -x[1]):
            print(f"  {filepath}: {lines} 行")
    
    if warnings:
        print(f"\n⚠️  软限制警告（>{SOFT_LIMIT_LINES} 行）:")
        for filepath, lines in sorted(warnings, key=lambda x: -x[1])[:10]:
            print(f"  {filepath}: {lines} 行")
    
    print("\n" + "=" * 70)
    
    # 退出码
    if strict and (violations or total_lines > MAX_TOTAL_LINES):
        print("❌ 严格模式：体积预算超标")
        sys.exit(1)
    else:
        print("✅ 体积预算检查通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行体积检查**

```bash
python scripts/quality/size_budget.py
```

记录输出（当前状态）。

- [ ] **Step 3: 生成详细报告**

创建 `docs/quality/size-budget-report.md`：

```markdown
# 源码体积预算报告

**生成日期**: 2026-06-11  
**检查工具**: `scripts/quality/size_budget.py`

## 总体统计

- **总代码行数**: ~32,000 行
- **文件数量**: ~80 个
- **预算上限**: 35,000 行
- **状态**: ✅ 在预算内

## 大文件清单（>600 行）

| 文件 | 行数 | 状态 |
|------|------|------|
| `cpp_gen/extract_cpp_skeleton.py` | 1353 | ❌ 超限 |
| `kismet/translator.py` | 1158 | ❌ 超限 |
| `serializers/package_summary.py` | 1070 | ❌ 超限 |
| `blueprint/variable_extractor.py` | 1048 | ❌ 超限 |
| `parsers/property_parser.py` | 1010 | ❌ 超限 |
| `ir_builder.py` | 1000 | ⚠️ 临界 |
| `iostore/reader.py` | 863 | ⚠️ 大文件 |
| `serializers/object_resources.py` | 769 | ⚠️ 大文件 |
| `parse_uasset.py` | 764 | ⚠️ 大文件 |
| `graph/flow_builder.py` | 761 | ⚠️ 大文件 |
| `link/linker.py` | 711 | ⚠️ 大文件 |

## 改进计划

### 短期（v0.4.6）
- [ ] 拆分 `extract_cpp_skeleton.py`（1353 行）→ 按职责拆为 3 个文件
- [ ] 拆分 `translator.py`（1158 行）→ 按字节码类型分组

### 中期（v0.5.0）
- [ ] 拆分 `package_summary.py`（1070 行）→ UE4/UE5 分离
- [ ] 拆分 `variable_extractor.py`（1048 行）→ 按变量类型分组
- [ ] 拆分 `property_parser.py`（1010 行）→ 策略模式重构

### 长期
- 所有文件控制在 600 行以内
- 总代码行数控制在 35,000 行以内

## CI 集成

在 GitHub Actions 中添加体积检查：

```yaml
- name: Check size budget
  run: python scripts/quality/size_budget.py --strict
```
```

- [ ] **Step 4: 提交**

```bash
git add scripts/quality/size_budget.py docs/quality/size-budget-report.md
git commit -m "chore: add source code size budget check and report (#119)"
```

---

### Task 7: 实现 #108 — 内存安全审计

**Files:**
- Modify: `src/uasset_read/archive.py:37`
- Modify: `src/uasset_read/pak/reader.py:55`
- Modify: `src/uasset_read/iostore/reader.py:179,825,839`
- Create: `tests/test_memory_safety_file_handles.py`

- [ ] **Step 1: 编写文件句柄泄漏测试**

创建 `tests/test_memory_safety_file_handles.py`：

```python
"""文件句柄安全测试"""
import pytest
import gc
from pathlib import Path


class TestFileHandleCleanup:
    """文件句柄清理测试"""
    
    def test_farchive_closes_on_exception(self, tmp_path):
        """FArchive 在异常时应关闭文件句柄"""
        from uasset_read.archive import FArchive
        
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)
        
        # 打开后触发异常
        with pytest.raises(Exception):
            archive = FArchive(str(test_file))
            archive.read_u32()
            raise RuntimeError("模拟异常")
        
        # 强制 GC
        del archive
        gc.collect()
        
        # 验证文件可被删除（Windows 上未关闭的文件无法删除）
        try:
            test_file.unlink()
        except PermissionError:
            pytest.fail("文件句柄未关闭（Windows PermissionError）")
    
    def test_farchive_context_manager(self, tmp_path):
        """FArchive 支持 context manager"""
        from uasset_read.archive import FArchive
        
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\xc1\x9a\x2b\x2a" + b"\x00" * 100)
        
        with FArchive(str(test_file)) as archive:
            archive.read_u32()
        
        # 退出 context 后应可删除
        try:
            test_file.unlink()
        except PermissionError:
            pytest.fail("文件句柄未关闭")
    
    def test_pak_reader_closes_on_exception(self, tmp_path):
        """PakFileReader 在异常时应关闭文件句柄"""
        from uasset_read.pak.reader import PakFileReader
        
        # 创建假 pak 文件
        pak_file = tmp_path / "test.pak"
        pak_file.write_bytes(b"\x00" * 1000)
        
        with pytest.raises(Exception):
            reader = PakFileReader(str(pak_file))
            reader.read_header()
            raise RuntimeError("模拟异常")
        
        del reader
        gc.collect()
        
        try:
            pak_file.unlink()
        except PermissionError:
            pytest.fail("PakFileReader 文件句柄未关闭")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_memory_safety_file_handles.py -v
```

Expected: FAIL（当前未实现 context manager）

- [ ] **Step 3: 为 FArchive 添加 context manager**

在 `src/uasset_read/archive.py` 添加：

```python
class FArchive:
    """二进制文件读取器"""
    
    def __init__(self, path: str):
        self._path = path
        self._file = open(path, 'rb')
        self._diagnostics: list = []
        self._name_map: Optional[list] = None
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭"""
        self.close()
        return False  # 不抑制异常
    
    def close(self):
        """关闭文件句柄"""
        if hasattr(self, '_file') and self._file and not self._file.closed:
            self._file.close()
    
    def __del__(self):
        """析构时确保关闭（安全网）"""
        try:
            self.close()
        except Exception:
            pass
```

- [ ] **Step 4: 为 PakFileReader 添加 context manager**

在 `src/uasset_read/pak/reader.py` 添加相同模式：

```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False

def close(self):
    if hasattr(self, '_file') and self._file and not self._file.closed:
        self._file.close()

def __del__(self):
    try:
        self.close()
    except Exception:
        pass
```

- [ ] **Step 5: 为 IoStoreReader 添加 context manager**

在 `src/uasset_read/iostore/reader.py` 添加相同模式，并关闭多个文件句柄：

```python
def close(self):
    """关闭所有文件句柄"""
    if hasattr(self, '_utoc_file') and self._utoc_file and not self._utoc_file.closed:
        self._utoc_file.close()
    if hasattr(self, '_ucas_file') and self._ucas_file and not self._ucas_file.closed:
        self._ucas_file.close()
```

- [ ] **Step 6: 运行测试验证通过**

```bash
python -m pytest tests/test_memory_safety_file_handles.py -v
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/archive.py src/uasset_read/pak/reader.py src/uasset_read/iostore/reader.py tests/test_memory_safety_file_handles.py
git commit -m "fix: add context manager support to file handle classes (#108)"
```

---

### Task 8: 实现 #77 — Kismet fallback scan 标记

**Files:**
- Modify: `src/uasset_read/kismet/result.py:41`
- Modify: `src/uasset_read/kismet/pipeline.py:83-90`
- Test: `tests/kismet/test_fallback_scan_marking.py`

- [ ] **Step 1: 编写 fallback 标记测试**

创建 `tests/kismet/test_fallback_scan_marking.py`：

```python
"""Kismet fallback scan 标记测试"""
import pytest


class TestFallbackScanMarking:
    """fallback scan 结果应正确标记"""
    
    def test_fallback_scan_sets_logic_source(self):
        """fallback scan 应设置 logic_source 为 fallback"""
        from uasset_read.kismet.result import KismetDecompiledResult
        
        result = KismetDecompiledResult(
            function_name="TestFunc",
            cpp_code="// fallback code",
            bytecode_status="fallback",
            logic_source="serial_scan_recovery",  # 应标记来源
        )
        
        assert result.logic_source == "serial_scan_recovery"
        assert result.bytecode_status == "fallback"
    
    def test_normal_bytecode_has_current_asset_source(self):
        """正常字节码 logic_source 应为 current_asset"""
        from uasset_read.kismet.result import KismetDecompiledResult
        
        result = KismetDecompiledResult(
            function_name="TestFunc",
            cpp_code="// normal code",
            bytecode_status="parsed",
            logic_source="current_asset",
        )
        
        assert result.logic_source == "current_asset"
        assert result.bytecode_status == "parsed"
    
    def test_json_output_includes_fallback_warning(self):
        """JSON 输出应包含 fallback 警告"""
        from uasset_read.kismet.result import KismetDecompiledResult
        import json
        
        result = KismetDecompiledResult(
            function_name="TestFunc",
            cpp_code="// fallback code",
            bytecode_status="fallback",
            logic_source="serial_scan_recovery",
            fallback_reasons=["serial_scan_recovery"],
        )
        
        # 转为 dict（模拟 JSON 输出）
        result_dict = {
            "function_name": result.function_name,
            "cpp_code": result.cpp_code,
            "bytecode_status": result.bytecode_status,
            "logic_source": result.logic_source,
            "fallback_reasons": result.fallback_reasons,
        }
        
        # 验证包含警告信息
        assert result_dict["bytecode_status"] == "fallback"
        assert "serial_scan_recovery" in result_dict["fallback_reasons"]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/kismet/test_fallback_scan_marking.py -v
```

Expected: FAIL（当前 logic_source 始终为 "current_asset"）

- [ ] **Step 3: 修改 KismetDecompiledResult**

在 `src/uasset_read/kismet/result.py:41` 修改：

```python
@dataclass
class KismetDecompiledResult:
    """Kismet 反编译结果"""
    function_name: str
    cpp_code: str
    bytecode_status: str = "parsed"  # parsed | fallback | failed
    logic_source: str = "current_asset"  # current_asset | serial_scan_recovery | bpgc_fallback
    fallback_reasons: list[str] = field(default_factory=list)
    # ... 其他字段
```

- [ ] **Step 4: 修改 pipeline.py 设置 logic_source**

在 `src/uasset_read/kismet/pipeline.py:127` 修改：

```python
# 修改前:
bytecode_source=("function_export" if extraction_reason == "function_export" else "fallback_or_serial_scan"),

# 修改后:
logic_source=extraction_reason,  # 直接使用 extraction_reason 作为来源标记
bytecode_status="parsed" if extraction_reason == "function_export" else "fallback",
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/kismet/test_fallback_scan_marking.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/kismet/result.py src/uasset_read/kismet/pipeline.py tests/kismet/test_fallback_scan_marking.py
git commit -m "fix: properly mark kismet fallback scan results (#77)"
```

---

## 完成验证

- [ ] **运行全量测试**

```bash
python scripts/test_matrix.py all
```

Expected: 100% 通过

- [ ] **运行质量检查**

```bash
python scripts/quality/size_budget.py
python scripts/test_matrix.py quality
```

Expected: 通过

- [ ] **创建 PR**

```bash
git push origin feat/remaining-issues-cleanup
gh pr create --title "fix: 剩余 issues 清理（安全加固 + API 治理 + 代码质量）" --body "修复 #110 #109 安全漏洞，完成 #116 #117 #118 #119 #108 #77 代码质量任务"
```

---

## 总结

| Issue | 标题 | 优先级 | 状态 |
|-------|------|--------|------|
| #110 | parse_batch() 路径清理 | P0 | 📋 待实现 |
| #109 | _find_parent_asset_file() 路径遍历 | P0 | 📋 待实现 |
| #116 | 收缩根 API | P1 | 📋 待实现 |
| #117 | core/extras 分层 | P1 | 📋 待实现 |
| #118 | 拆分大型测试文件 | P2 | 📋 待实现 |
| #119 | 源码体积预算 | P2 | 📋 待实现 |
| #108 | 内存安全审计 | P2 | 📋 待实现 |
| #77 | Kismet fallback scan 标记 | P2 | 📋 待实现 |

**预计工作量**: 8 个 tasks × 30 分钟 = 4 小时
