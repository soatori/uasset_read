# CLI 核心与入口分离设计

**日期**: 2026-06-03 | **版本**: 0.4.0-dev | **状态**: 已批准

## 1. 问题与目标

**现状**: `cli.py`（400+ 行）承担三个职责：argparse 参数解析、核心解析路由、batch/graph 特殊模式。脚本无法复用核心逻辑，因为一切绑定在 argparse 流程中。

**目标**: 核心逻辑与入口分离，使 CLI、独立脚本、未来 Skill 都共享同一套 API。

**原则**:
- 核心函数纯 Python，无 argparse 依赖
- CLI 瘦身为参数解析 + 委托
- 脚本 5 行即可调用
- 不考虑向后兼容，直接重建

---

## 2. 架构设计

### 分层

```
uasset_read/
├── core.py              # 新增：核心解析 API（纯函数）
├── cli.py               # 瘦身：argparse + 委托 core.py
├── __main__.py          # 不变：python -m uasset_read 入口
└── simple.py            # 新增：快速诊断脚本

项目根目录/
└── diag.py              # 新增：快捷诊断入口（调用 simple.py 或 core API）
```

### 文件职责

| 文件 | 职责 | 依赖 |
|------|------|------|
| `core.py` | 纯解析函数：parse_single, parse_batch, list_formats | 无 argparse |
| `cli.py` | argparse 定义 + 参数转 options + 委托 core.py | core.py |
| `simple.py` | 单文件快速诊断入口 | core.py |
| `diag.py` | 项目根快捷脚本 | core.py |

---

## 3. core.py API 设计

### parse_single

```python
def parse_single(
    file_path: str,
    format: str = "text",
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
) -> str:
    """解析单个 .uasset/.umap 文件，返回格式化字符串。
    
    纯函数，无 argparse、无 sys.exit、无 print。
    格式通过 format 参数路由（与 resolve_format 等价）。
    需要 linker 的格式（cpp_skeleton、blueprint_ue_text 等）内部自动选择 parse_uasset_with_linker。
    
    Raises:
        FileNotFoundError: 文件不存在
        IsADirectoryError: 路径是目录
        UAssetError: 解析失败（strict 模式）
    """
```

### parse_batch

```python
@dataclass
class BatchResult:
    total: int
    success: list[str]      # 成功文件路径
    skipped: list[tuple]    # (path, reason)
    failed: list[tuple]     # (path, error)

def parse_batch(
    input_dir: str,
    format: str = "text",
    output_dir: str | None = None,
    tolerant: bool = True,
    **format_options,
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap 文件。"""
```

### list_formats

```python
def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
```

---

## 4. CLI 瘦身方案

### 保留

- `create_parser()` — argparse 定义不变
- `_write_output()` — 写入逻辑不变
- `_build_export_options()` — 构建 options

### 简化

`main()` 中原有的解析 + 导出逻辑替换为：

```python
# 旧：直接调用 parse_package + ExporterRegistry
# 新：委托 core.parse_single(file_path, format, **options)
output_str = core.parse_single(str(file_path), fmt, **opts_dict)
```

`_handle_graph_mode` 和 `_handle_batch` 同样委托 `core.parse_single` / `core.parse_batch`。

---

## 5. 快速诊断脚本

### diag.py（项目根目录）

```python
#!/usr/bin/env python
"""快速诊断：python diag.py <path.uasset> [--format text|json|markdown|...]"""
import sys
from uasset_read.core import parse_single

if len(sys.argv) < 2:
    print("用法: python diag.py <path.uasset> [--format FORMAT]")
    sys.exit(1)

path = sys.argv[1]
fmt = "text"
if len(sys.argv) >= 4 and sys.argv[2] == "--format":
    fmt = sys.argv[3]

print(parse_single(path, format=fmt))
```

### simple.py（src/uasset_read/simple.py）

同上，作为模块内标准入口，支持 `python -m uasset_read.simple <path>`。

---

## 6. 迁移顺序

1. 定义 `core.py` API（parse_single, parse_batch, list_formats）
2. 实现 `parse_single` 内部逻辑（复用现有 parse_package + ExporterRegistry）
3. 实现 `parse_batch` 内部逻辑（复用现有 BatchExporter）
4. CLI 瘦身：main() 委托 core.py
5. 创建 `diag.py` 和 `simple.py`
6. 测试：CLI 回归 + 脚本基本功能

---

## 7. 测试矩阵

| 测试类型 | 用例 | 验证 |
|----------|------|------|
| core.parse_single | 每种格式 | 输出与现有 CLI 等价 |
| CLI 回归 | `--json/--text/--markdown` 等 | 输出不变 |
| 脚本基本功能 | `python diag.py <path>` | 正确输出 |
| 错误处理 | 文件不存在、目录传入 | 正确抛出异常 |
