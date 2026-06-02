---
title: 解析管线
section: parse-pipeline
---

# 解析管线

`parse_uasset.py` 提供三个入口函数：

## 核心 API

<!-- data-api="parse_package" -->
```python
parse_package(path: str, tolerant: bool = True, include_parent_assets: bool = False, provider, mappings_path, game) -> ParseResult
```

<!-- data-api="parse_uasset" -->
```python
parse_uasset(...) -> ParseResult  # 委托给 parse_package
```

<!-- data-api="parse_uasset_with_linker" -->
```python
parse_uasset_with_linker(path: str, tolerant: bool = True, preload_all: bool = False, ...) -> LinkerParseResult
```

## 解析流程

```
1. open_package_bundle() → PackageBundle
2. bundle.open_archive() → PackageArchive
3. read_package_summary() → PackageFileSummary
4. build_version_container() → VersionContainer
5. read_name_table() → List[str]
6. read_import_map() → List[ObjectImport]
7. read_export_map() → List[ObjectExport]
8. parse_properties_from_export() (每个 export)
9. [linker only] PackageLinker.link() + post_load()
10. _post_process() → 蓝图/图/Kismet/组件
```

## 关键设计

- **双入口**：parse_package（标准）和 parse_uasset_with_linker（带链接器）
- **容错优先**：可选功能失败不影响主管线，错误收集到 result.errors
- **Provider 抽象**：filesystem/pak/iostore 三种来源

> [!TIP]
> 相关章节: [[FArchive]] · [[序列化模块]]
