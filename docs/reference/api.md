> **status:** historical — Documents the retired v0.5.x API surface. The v1 pipeline (`parse_uasset`, `parse_uasset_with_linker`, `--legacy-json`) is gone. For the current surface, see [Wiki Public API](../../wiki/07-Dev-Guide/Public-API.md) and `src/uasset_read/package.py`.

# API 快速参考（historical — v0.5.x）

> **Do not use the snippets below.** They describe APIs that no longer exist. Current public surface:

```python
from uasset_read import parse_package_document, ParseError, FArchive, __version__

doc = parse_package_document(
    "path/to/asset.uasset",
    *,
    tolerant=True,
    mappings_path=None,   # .usmap
    game=None,
    depth="asset",        # package | object | asset | decode
    object_ids=None,
)
```

CLI: `python -m uasset_read file.uasset` (see Wiki Quick-Start). Agent tools live in `src/uasset_read/agent_tools.py`.

---

## Retired v0.5.x surface (do not use)

### 核心入口

```python
from uasset_read import parse_package, parse_uasset, parse_uasset_with_linker

result = parse_package("path/to/asset.uasset")
result = parse_uasset("path/to/asset.uasset")
result = parse_uasset_with_linker("path/to/asset.uasset")
```

### ParseResult 字段（已删除）

| 字段 | 类型 | 说明 |
|------|------|------|
| `summary` | PackageFileSummary | 包文件头信息 |
| `name_map` | list[str] | 名称表 |
| `import_map` | list[ObjectImport] | 导入表 |
| `export_map` | list[ObjectExport] | 导出表（含 properties） |
| `linker` | PackageLinker \| None | 对象链接器 |
| `blueprint` | BlueprintMetadata \| None | 蓝图元数据 |
| `graphs` | list \| None | 蓝图图数据 |
| `decompiled_functions` | list[KismetDecompiledResult] | 反编译函数 |
| `errors` | list[str] | 错误列表 |
| `is_success` | bool | 解析是否成功 |

### 配置选项（v0.5.x）

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `tolerant` | bool | True | 容错模式 |
| `mappings_path` | str \| None | None | .usmap 映射文件 |
| `game` | str \| None | None | 游戏标识 |
| `provider` | PackageProvider \| None | None | 自定义 provider（PAK/IoStore） |

> 2026-09-10：`resolve_parents` / `parent_root`（及 CLI `--include-parent-assets` / `--asset-root`）已随 parent-asset 解析产品决策退役（D1 §7）。

### 异常类（部分仍存在）

`ParseError` / `FArchive` remain public. `parse_uasset` and related helpers were removed with the v1 pipeline.
