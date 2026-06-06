# API 快速参考

## 核心入口

```python
from uasset_read import parse_package, parse_uasset, parse_uasset_with_linker

# 推荐入口 — 支持 .uasset/.umap/package
result = parse_package("path/to/asset.uasset")

# 兼容入口 — 仅 .uasset
result = parse_uasset("path/to/asset.uasset")

# Linker 模式 — 完整对象图解析
result = parse_uasset_with_linker("path/to/asset.uasset")
```

## ParseResult 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `summary` | PackageFileSummary | 包文件头信息 |
| `name_map` | list[str] | 名称表 |
| `import_map` | list[ObjectImport] | 导入表 |
| `export_map` | list[ObjectExport] | 导出表（含 properties） |
| `linker` | PackageLinker \| None | 对象链接器（parse_uasset_with_linker 模式） |
| `blueprint` | BlueprintMetadata \| None | 蓝图元数据 |
| `graphs` | list \| None | 蓝图图数据 |
| `decompiled_functions` | list[KismetDecompiledResult] | 反编译函数 |
| `errors` | list[str] | 错误列表 |
| `is_success` | bool | 解析是否成功 |

## 配置选项

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `tolerant` | bool | True | 容错模式 |
| `mappings_path` | str \| None | None | .usmap/.jmap 映射文件 |
| `game` | str \| None | None | 游戏标识（用于自定义属性 handler） |
| `include_parent_assets` | bool | False | 是否递归解析父资产 |
| `asset_roots` | list[str] \| None | None | 资产搜索根目录 |
| `provider` | PackageProvider \| None | None | 自定义 provider（PAK/IoStore） |

## 常量

```python
from uasset_read import (
    MAX_PROPERTY_COUNT,      # 属性循环上限 10,000
    MAX_ARRAY_COUNT,         # 数组元素上限 1,000,000
    MMAP_THRESHOLD,          # mmap 阈值 50MB
    MAX_FSTRING_LENGTH,      # FString 上限 10MB
)
```

## 异常类

```python
from uasset_read import ParseError, VersionError, UAssetError, ErrorContext

try:
    result = parse_package(path)
except ParseError as e:
    # e.context 包含 OffsetRangeDiagnostic 上下文
    print(f"解析失败: {e}")
except VersionError as e:
    print(f"不支持的版本: {e}")
```
