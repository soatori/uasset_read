---
title: 格式化器
section: formatters
---

# 格式化器 (Formatters)

格式化器模块负责将 `ParseResult` 对象转换为多种人类可读和机器可读的输出格式。所有格式化器定义在 `src/uasset_read/formatters/` 目录下，通过统一的函数接口接收解析结果并返回对应格式的数据。

## 模块结构

| 子模块 | 文件 | 职责 |
|--------|------|------|
| JSON | `json_formatter.py` | 完整/摘要 JSON 输出、属性序列化 |
| Text | `text_formatter.py` | YAML 风格全文/摘要文本 |
| Markdown | `markdown_formatter.py` | Markdown + Mermaid 流程图 |
| Blueprint Text | `blueprint_text_formatter.py` | 蓝图节点翻译参考文本 |
| Blueprint UE Text | `blueprint_ue_text_formatter.py` | UE 编辑器格式文本 |
| Helpers | `helpers.py` | 状态构建、Schema 信息、PackageIndex 解析 |

## 输出格式

| 格式 | 函数 | 说明 |
|------|------|------|
| JSON (full) | `format_json_full` | 完整 JSON 输出，包含 status、summary、exports、blueprint、components、decompiled_functions 等 |
| JSON (summary) | `format_json_summary` | 精简 JSON 摘要，token 减少 70%+ |
| Text (full) | `format_text_full` | YAML 风格全文，含 Graphs 和执行流链 |
| Text (summary) | `format_text_summary` | 精简 YAML 风格摘要 |
| Markdown | `format_markdown` | Markdown + Mermaid 执行流流程图 |
| Blueprint Text | `format_blueprint_translation_text` | 蓝图节点翻译参考文本 |
| UE Text | `format_blueprint_ue_text` | UE 编辑器格式文本 |

## JSON 格式化

### `format_json_full(result, include_schema=False, include_function_graphs=False)`

完整 JSON 输出，遵循以下设计原则：

- **D-01**: 分层输出（完整详情）
- **D-02**: Package → Exports → Properties 层级结构
- **D-03**: 顶层 `errors` 字段
- **D-04**: 单一 `blueprint` 对象结构（`graphs` 移入 blueprint 内部）
- **D-05**: 未解析的 FPackageIndex 原值保留
- **D-06**: `name_map` 不输出（已解析为对象名）
- **D-20-05**: `output_version` 升级到 "4.0"
- **D-20-06**: `blueprint_name` 从 `package_name` 提取
- **Phase 55**: `output_version` 升级到 "5.0" 当 `include_function_graphs=True`

返回结构：

```json
{
  "status": { "status": "success" | "fail" | "error", "message": "...", "code": "..." },
  "output_version": "4.0" | "5.0",
  "summary": { "version_ue5": ..., "legacy_version": ..., "package_flags": ..., "package_name": "..." },
  "exports": [ { "index": 0, "name": "...", "class": "...", "serial_size": ..., "properties": [...], "outer_index": {...}, "super_index": {...}, "parent_class": "..." } ],
  "blueprint": { "PackageName": "...", "BlueprintClass": "...", "Graphs": [...], "NodeCount": ..., "Nodes": [...], "Warnings": [...], "Extensions": { "Metadata": {...} } },
  "components": [...],
  "decompiled_functions": [...],
  "resolved_parent_assets": [...],
  "inherited_blueprint_graphs": [...],
  "logic_sources": [...],
  "errors": [...],
  "function_graphs": [...],
  "_schema": { ... }
}
```

### `format_json_summary(result, include_schema=False)`

精简 JSON 摘要，策略如下：

- **移除**: imports, soft_references, circular_deps, errors
- **精简 exports**: 仅 name, class, parent_class
- **移除 properties 数组**
- **保留**: status, output_version

### `serialize_property_value(value, depth=0, max_depth=10)`

将高级属性值 dataclass 转换为 JSON 兼容 dict。支持类型：

| 类型 | 输出结构 |
|------|----------|
| `StructValue` | `{ "struct_type": "...", "fields": {...} }` |
| `MapValue` | `{ "key_type": "...", "value_type": "...", "entries": [...] }` |
| `SetValue` | `{ "element_type": "...", "elements": [...] }` |
| `EnumValue` | `{ "enum_type": "...", "value": "..." }` |
| `TextValue` | `{ "namespace": "...", "key": "...", "source_string": "..." }` |
| `DelegateValue` | `{ "object_ref": "...", "function_name": "..." }` |

超过 `max_depth` 时返回 `"[deep nesting truncated]"`。

### `format_properties_list(properties)`

格式化属性列表，每个元素包含 `name`, `type`, `value`, `array_index`。

### `format_blueprint_dict(blueprint, blueprint_name=None)`

格式化 BlueprintMetadata 为字典。Phase 26 增强输出：

- **变量**: 包含类型信息（pin_category, pin_subcategory, container_type）、编辑标志（is_edit_anywhere, is_blueprint_read_only 等）、元数据
- **函数**: 包含参数列表、函数标志（is_pure, is_native, is_static 等）、访问修饰符、元数据
- **事件**: 包含事件类型、多播委托信息、覆盖父类信息、参数列表、元数据

## Text 格式化

### `format_text_full(result)`

YAML 风格完整文本输出，结构：

```yaml
Package: /Game/MyBlueprint
  Version: UE5=27
  Flags: 0x00000001
  Imports: 15
  Exports: 3

Exports:
  - Name: Default__MyBlueprint_C
    Class: BlueprintGeneratedClass
    SerialSize: 1024
    Properties:
      - Name: MyVariable
        Type: IntProperty
        Value: 42

Blueprint:
  ParentClass: Actor
  Variables: 5
  - Name: MyVariable
    Type: Int
    Default: 42
    Category: Default

Graphs:
  - Name: EventGraph
    Class: EdGraph
    Nodes: 12
    Connections: 25
    ExecutionChains: 3
      - EventBeginPlay: N1->N2->N3

ERRORS:
  (none)
```

### `format_text_summary(result)`

精简 YAML 风格摘要，每个 export 一行：

```yaml
Package: /Game/MyBlueprint
Exports: 3

  - Default__MyBlueprint_C (BlueprintGeneratedClass)
  - MyBlueprint (Blueprint)
  - SKEL_MyBlueprint_C (Skeleton)
```

## Markdown 格式化

### `format_markdown(result)`

三节结构 + 表格优先 + Mermaid 流程图：

1. **Asset Overview**: 包名、版本、状态表格
2. **Blueprint Details**: 父类、变量统计（组件/常规）
3. **Graph Summary**: 每个图含 Mermaid `graph LR` 执行流流程图
4. **Exports**: 导出对象表格

Mermaid 流程图从 `execution_chains` 解析生成，链式字符串如 `"N1->N2->N3"` 转换为 `N1 --> N2 --> N3` 连接。

## 辅助函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `build_status_info` | `(result: ParseResult) -> StatusInfo` | 构建状态信息，三元分类：success（无错误）、fail（部分结果可用）、error（严重错误） |
| `build_schema_info` | `() -> Dict[str, str]` | 构建字段语义注释，仅在 `--verbose` 或 `--schema` 时输出 |
| `resolve_fpackage_index` | `(idx: PackageIndex, result: ParseResult) -> Dict` | 解析 FPackageIndex 到对象名称，返回 `{raw, resolved, kind}` 结构 |

### `resolve_fpackage_index` 返回值

```python
{"raw": 0, "resolved": None, "kind": "null"}        # 空索引
{"raw": -3, "resolved": "SomeClass", "kind": "import"}  # Import（负索引）
{"raw": 2, "resolved": "Default__Actor", "kind": "export"}  # Export（正索引）
```

## 公共 API 导出

所有格式化器函数通过 `uasset_read.formatters.__all__` 导出：

```python
from uasset_read.formatters import (
    format_json_full,
    format_json_summary,
    format_text_full,
    format_text_summary,
    format_markdown,
    format_blueprint_translation_text,
    format_blueprint_ue_text,
    format_exports_list,
    format_properties_list,
    format_blueprint_dict,
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
)
```

**相关章节**: [[导出系统]] · [[CLI 接口]]
