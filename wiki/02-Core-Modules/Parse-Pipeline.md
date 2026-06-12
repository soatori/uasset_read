---
title: 解析管线
section: parse-pipeline
---

# 解析管线

`parse_uasset.py` 提供三个入口函数，`core.py` 提供新的高级 API。

## 新 Core API（0.4.1+ 推荐）

<!-- data-api="parse_single" -->
```python
parse_single(file_path, format="json", tolerant=True, verbose=False, include_schema=False, ...) -> str
```

纯函数入口，无 argparse/sys.exit/print。内部自动完成：解析 → IR 构建 → 渲染。

<!-- data-api="parse_batch" -->
```python
parse_batch(input_dir, format="json", output_dir=None, ...) -> BatchResult
```

批量解析目录下所有 `.uasset`/`.umap` 文件。

<!-- data-api="list_formats" -->
```python
list_formats() -> list[str]
```

返回所有已注册的渲染格式名。

## 旧 API（向后兼容）

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

## 完整解析流程（0.4.5+）

```
1. open_package_bundle() → PackageBundle
2. bundle.open_archive() → PackageArchive
3. read_package_summary() → PackageFileSummary
4. build_version_container() → VersionContainer
5. read_name_table() → List[str]
6. read_import_map() → List[ObjectImport]
7. read_export_map() → List[ObjectExport]
8. [linker only] PackageLinker.link() — Phase 1: 创建对象实例
9. [linker only] PackageLinker.preload(idx) × N — Phase 2: 序列化属性
10. [linker only] PackageLinker.post_load() — Phase 3: 解析引用
11. parse_properties_from_export() (每个 export)
12. _post_process() → 蓝图/图/Kismet/组件
13. build_package_ir() → PackageIR
14. renderer.render(ir, options) → str
```

> **v0.4.5 变更**: 加载生命周期现在遵循 UE 风格：`link() → preload(idx) × N → post_load()`。
> 这确保 ObjectProperty 引用在 `post_load()` 阶段能正确解析为已预加载的 UObjectInstance。

## cpp_skeleton 独立路径

```
parse_single(format="cpp_skeleton")
  → parse_uasset_with_linker() → LinkerParseResult
  → CppSkeletonRenderer.generate(result) → C++ 骨架字符串
```

注意：`cpp_skeleton` 不通过 `RENDERER_REGISTRY`，也不使用 `RenderOptions.linker_result`。

## 关键设计

- **三层架构**：ParseResult → PackageIR → Renderers（解析、数据、输出完全分离）
- **Core API**：parse_single/parse_batch 是纯函数，CLI/脚本/Skill 共享
- **容错优先**：可选功能失败不影响主管线，错误收集到 result.errors
- **Provider 抽象**：filesystem/pak/iostore 三种来源
- **Linker 自动选择**：parse_single 对 cpp_skeleton 等需要 linker 的格式自动使用 parse_uasset_with_linker

## 模块位置

| 模块 | 路径 | 说明 |
|------|------|------|
| 旧解析入口 | `parse_uasset.py` | parse_package / parse_uasset / parse_uasset_with_linker |
| 新 Core API | `core.py` | parse_single / parse_batch / list_formats / BatchResult |
| IR 构建器 | `ir_builder.py` | build_package_ir：ParseResult → PackageIR |
| IR 模型 | `models/ir.py` | PackageIR / ExportIR / GraphIR / NodeIR / PinIR 等 |

> [!TIP]
> 相关章节: [[FArchive]] · [[序列化模块]] · [[渲染器系统]] · [[IR 中间表示]]
