# Phase 43: PackageIndex 增强 — RESEARCH.md

**Date:** 2026-05-14
**Phase:** 043-packageindex-enhance

## 目标

将 `object_resources.py` 中所有旧 PackageIndex 解析函数替换为通过 `PackageLinker` 返回 `UObjectInstance` 的版本，消除 dict 返回路径。

## 上游依赖（Phase 41 已提供）

| 符号 | 文件 | 签名 |
|------|------|------|
| `PackageLinker` | `link/linker.py` | 构造函数接受 archive, summary, name_map, import_map, export_map |
| `PackageLinker.resolve_package_index(pkg_idx)` | `link/linker.py:119-138` | → `Optional[UObjectInstance]` |
| `PackageLinker.build_outer_tree()` | `link/linker.py:109-117` | 自动设置 `inst.outer` |
| `UObjectInstance` | `link/object_instance.py` | `.object_name`, `.object_class`, `.get_full_name()`, `.get_class_object()` |
| `UObjectInstance.get_full_name()` | `object_instance.py:88-104` | → `str` 完整 UE 对象路径 |
| `UObjectInstance.get_class_object()` | `object_instance.py:106-114` | → `Optional[UObjectInstance]` |

**注意**: `UObjectInstance.get_full_name()` 引用了 `self.linker.summary` 和 `self.linker.name_map`，但 `PackageLinker` 中存储的是 `_summary` 和 `_name_map`（私有）。需要给 `PackageLinker` 添加 `summary` 和 `name_map` 的 public property。

## 待替换函数及调用方分析

### 1. `resolve_class_name(class_index, import_map, export_map)` → linker 版

**当前行为**: 返回 `Optional[str]`（从 import/export map 直接查 object_name）

| 调用方 | 文件:行 | 用法 |
|--------|---------|------|
| `linker.py` | `link/linker.py:92` | `_create_export_instances()` 中解析 `exp.class_index` |
| `graph.py` | `serializers/graph.py:559` | `read_fmember_reference()` 解析 `member_parent_index` |
| `graph.py` | `serializers/graph.py:763,798` | script_serial 内部解析 FunctionReference/EventReference 的 MemberParent |
| `graph.py` | `serializers/graph.py:859` | `read_ue_graph_node()` 解析节点 class_name |
| `graph.py` | `serializers/graph.py:897` | `read_ue_graph()` 解析 schema_index |

**新签名**: `resolve_class_name_with_linker(class_index: PackageIndex, linker: PackageLinker) → Optional[str]`
- 内部调用 `linker.resolve_package_index(class_index)` 获取 `UObjectInstance`，然后取 `.object_name`

### 2. `get_asset_class(export, import_map, export_map)` → linker 版

**当前行为**: 返回 `Optional[str]`（从导出条目的 class_index 解析）

| 调用方 | 文件:行 | 用法 |
|--------|---------|------|
| `formatters/json_formatter.py` | `:116, :264` | JSON 输出中获取 export 的 class |
| `formatters/text_formatter.py` | `:56, :147` | 文本输出中获取 export 的 class |
| `formatters/markdown_formatter.py` | `:101` | Markdown 表格中获取 export 的 class |
| `graph/parser.py` | `graph/parser.py:55` | 遍历 export_map 寻找 EdGraph/UberEdGraph |
| `serializers/graph.py` | `serializers/graph.py:705,923` | `read_ue_graph_node()` 和 nodes_count==0 回退中获取节点 class |
| `object_resources.py` | `object_resources.py:360` | `detect_blueprint()` 内部调用 |

**新签名**: `get_asset_class_with_linker(export: ObjectExport, linker: PackageLinker) → Optional[str]`
- 内部调用 `linker.resolve_package_index(export.class_index)` 获取 `UObjectInstance`，然后取 `.object_name`

### 3. `detect_blueprint(export, import_map, export_map)` → linker 版

**当前行为**: 返回 `bool`（检查 class_name 是否包含 "Blueprint"）

| 调用方 | 文件:行 | 用法 |
|--------|---------|------|
| `parse_uasset.py` | `parse_uasset.py:70` | UBlueprint 回退检测 |

**新签名**: `detect_blueprint_with_linker(export: ObjectExport, linker: PackageLinker) → bool`
- 内部调用 `get_asset_class_with_linker()` 然后检查 "Blueprint"

### 4. `resolve_parent_class(super_index, import_map, export_map)` → linker 版

**当前行为**: 返回 `Tuple[Optional[str], Optional[str]]` — (resolved_name, warning)

| 调用方 | 文件:行 | 用法 |
|--------|---------|------|
| `blueprint/variable_extractor.py` | `blueprint/variable_extractor.py:389-390` | 从 export 的 super_index 推断父类 |

**新签名**: `resolve_parent_class_with_linker(super_index: PackageIndex, linker: PackageLinker) → Tuple[Optional[str], Optional[str]]`
- 内部调用 `linker.resolve_package_index(super_index)` 获取 `UObjectInstance`，然后取 `.object_name`

### 5. `resolve_package_index_to_reference(pkg_idx, ...)` → **完全移除**

**当前行为**: 返回 `Optional[Dict[str, Any]]`（dict 格式的对象引用）

| 调用方 | 文件:行 | 用法 |
|--------|---------|------|
| `parsers/property_parser.py` | `parsers/property_parser.py:207` | ObjectProperty 增强：将 int 值转换为 dict 引用 |
| `__init__.py` | `__init__.py` | 仅 re-export，无实际调用 |

**处理方式**:
- 移除函数定义
- 修改 `property_parser.py:204-209` 的 ObjectProperty 增强逻辑：改为通过 linker 解析为 `UObjectInstance`，然后直接取属性
- 但 property_parser.py 的 `parse_properties_from_export()` 目前不接受 linker 参数，需要新增参数

## 调用方适配策略

### 格式化层（json/text/markdown formatter）

格式化层当前使用 `get_asset_class()` 获取 export 的 class 字符串。由于返回类型不变（仍是 `Optional[str]`），只需要修改参数：

- **方案**: 格式化层如果处理的是 LinkerParseResult，则通过 `result.linker` 调用 linker 版函数
- **兼容**: `parse_uasset()` 返回的 ParseResult 没有 linker，需要保持旧路径或要求通过 linker 入口调用

### 图序列化层（graph.py）

graph.py 中大量使用 `resolve_class_name` 和 `get_asset_class`，但这些函数目前只接受 import_map/export_map。

- **方案**: 在 graph.py 中新增 `*_with_linker` 版本，旧版本保留（因为 graph.py 被 `extract_blueprint_graphs()` 调用，而该函数不接受 linker）

### 属性解析层（property_parser.py）

`parse_properties_from_export()` 中的 ObjectProperty 增强需要 linker 来解析引用。

- **方案**: 新增可选参数 `linker: Optional[PackageLinker] = None`，如果传入 linker 则使用 linker 解析，否则保留旧行为
- 因为 `parse_uasset()` 不使用 linker，需要保持向后兼容

### 蓝图提取层（variable_extractor.py）

`extract_blueprint_metadata()` 中调用 `resolve_parent_class`。

- **方案**: 新增可选参数 `linker: Optional[PackageLinker] = None`，如果传入则使用 linker 版本

## 风险点

1. **循环依赖**: `object_resources.py` 已经导入 `link/linker.py` 中的类型（TYPE_CHECKING），实际函数不能直接 import PackageLinker（会导致循环）。需要在调用方注入 linker 参数，而非在 object_resources.py 中创建依赖。

2. **linker.py 自身的 resolve_class_name 调用**: `link/linker.py:92` 中 `_create_export_instances()` 调用 `resolve_class_name`。这个调用在 linker 内部，此时 linker 还没完全建立，不能调用 `self.resolve_package_index`。**保持不变**，因为此时 import/export objects 还未创建。

3. **get_full_name() 的 linker 属性访问**: `UObjectInstance.get_full_name()` 使用 `self.linker.summary` 和 `self.linker.name_map`，但 `PackageLinker` 中存储的是 `_summary` 和 `_name_map`。**需要添加 public property**。

4. **ParseResult vs LinkerParseResult**: `parse_uasset()` 返回 ParseResult（无 linker），`parse_uasset_with_linker()` 返回 LinkerParseResult（有 linker）。格式化层和图解析需要判断哪种结果。

## 结论

Phase 43 的核心工作是在调用方注入 linker，通过 `UObjectInstance` 获取对象信息，而不是直接查 import/export map。由于需要保持 `parse_uasset()` 的向后兼容，采用**可选 linker 参数**模式。
