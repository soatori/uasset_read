---
title: 导出系统（已废弃）
section: exporter
---

# 导出系统（已废弃）

> [!WARNING] 已废弃
>
> **Exporter 系统在 0.4.1 中已被 Renderers 系统替代。**
> 
> - `exporter/` 模块已从代码库中删除
> - 新架构：`ParseResult → IR → Renderers → Output`
> - 请查看 [[渲染器系统]] 和 [[IR 中间表示]] 获取最新文档

## 历史参考

以下为 0.3.x 版本的导出系统架构，仅供代码迁移参考：

### 旧架构概览

```
.uasset → Parser → ParseResult → Exporter → Output (JSON/Text/Markdown/N2C/C++/...)
```

采用 **IExporter 接口 + 注册表分发** 模式。

### 旧导出器列表

| 格式名 | 导出器类 | 状态 |
|--------|----------|------|
| `json` | `JsonExporter` | → JsonRenderer |
| `json_summary` | `JsonExporter` | → JsonRenderer |
| `text` | `TextExporter` | → TextRenderer |
| `text_summary` | `TextExporter` | → TextRenderer |
| `markdown` | `MarkdownExporter` | → MarkdownRenderer |
| `blueprint_text` | `BlueprintTextExporter` | → BlueprintTextRenderer |
| `blueprint_ue_text` | `BlueprintUETextExporter` | → BlueprintUERenderer |
| `n2c` | `N2CExporter` | 已移除（N2C 模块整体删除） |
| `cpp_skeleton` | `CppSkeletonExporter` | → CppSkeletonRenderer |
| `cpp_json_ir` | `CppJsonIrExporter` | 合并到 cpp_skeleton |

### 迁移路径

| 旧 API | 新 API |
|--------|--------|
| `export(result, format="json")` | `parse_single(path, format="json")` |
| `ExporterRegistry.get(format)` | `get_renderer(format)` |
| `BatchExporter.export_files(paths)` | `parse_batch(input_dir, format=...)` |
| `ExportOptions` | `RenderOptions` |

## 架构概览

```
.uasset → Parser → ParseResult → Exporter → Output (JSON/Text/Markdown/N2C/C++/...)
```

采用 **IExporter 接口 + 注册表分发** 模式：
- 每个导出器实现 `IExporter` 抽象基类
- 导出器在模块导入时自动注册到 `ExporterRegistry`
- 通过 `export()` 便捷函数或 `ExporterRegistry.get()` 获取导出器

## 核心类

<!-- data-api="IExporter" -->
```python
IExporter            # 导出器接口（抽象基类）
ExporterRegistry     # 导出器注册表（类方法单例）
BatchExporter        # 批量导出器
ExportOptions        # 统一导出配置（dataclass）
ExportValidationError  # 输出验证失败异常
BatchExportResult    # 批量导出结果
```

## 核心 API

<!-- data-api="export" -->
```python
export(result, format: str = "json", **kwargs) -> str
```

便捷函数：一步完成格式分发和导出。

```python
# 便捷方式
output = export(result, format="json")

# 完整方式
from uasset_read.exporter import ExportOptions, ExporterRegistry

options = ExportOptions(format="json", include_schema=True)
exporter = ExporterRegistry.get("json")
output = exporter.export(result, options)

# 导出到文件
exporter.export_to_file(result, options)  # options.output_path 必须设置
```

## ExportOptions

<!-- data-api="ExportOptions" -->
```python
@dataclass
class ExportOptions:
    # 输出格式
    format: str = "json"  # json / json_summary / text / text_summary / markdown /
                          # blueprint_text / blueprint_ue_text / n2c / cpp_skeleton / cpp_json_ir

    # 通用选项
    include_schema: bool = False           # 是否包含 schema 信息
    include_function_graphs: bool = False  # 是否包含函数图
    verbose: bool = False                  # 详细模式

    # 输出目标
    output_path: str | None = None         # None = stdout，文件路径 = 写入文件
    output_dir: str | None = None          # 批量模式：输出目录

    # 验证
    validate_output: bool = False          # 是否验证输出（N2C 支持）

    # 解析选项（批量导出时传递给解析器）
    tolerant: bool = True                  # 容错解析
    include_parent_assets: bool = False    # 包含父级资产
    asset_roots: list[str] | None = None   # 资产根目录
    mappings_path: str | None = None       # 类型映射路径
    game: str | None = None                # 游戏标识
```

## IExporter 接口

<!-- data-api="IExporter" -->
```python
class IExporter(ABC):
    @abstractmethod
    def export(self, result, options: ExportOptions) -> str:
        """将解析结果导出为字符串。"""
        ...

    def export_to_file(self, result, options: ExportOptions) -> str:
        """导出并写入文件。返回写入的文件路径。"""
        ...

    def validate(self, result, options: ExportOptions) -> list[str]:
        """验证导出内容。默认返回空列表。"""
        return []

    @property
    @abstractmethod
    def format_name(self) -> str:
        """此导出器处理的格式名称。"""
        ...

    @property
    def validates_against_schema(self) -> bool:
        """此导出器是否支持 schema 验证。"""
        return False
```

## ExporterRegistry

<!-- data-api="ExporterRegistry" -->
```python
class ExporterRegistry:
    @classmethod
    def register(cls, format_name: str, exporter_class) -> None:
        """注册格式名到导出器类的映射。"""

    @classmethod
    def get(cls, format_name: str) -> IExporter:
        """获取指定格式的导出器实例。"""

    @classmethod
    def list_formats(cls) -> list[str]:
        """返回所有已注册的格式名。"""

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）。"""
```

## 已注册的导出器

| 格式名 | 导出器类 | 输出扩展名 | 说明 |
|--------|----------|------------|------|
| `json` | `JsonExporter` | `.json` | 完整 JSON 输出 |
| `json_summary` | `JsonExporter` | `.json` | JSON 摘要输出 |
| `text` | `TextExporter` | `.txt` | YAML 风格完整文本 |
| `text_summary` | `TextExporter` | `.txt` | YAML 风格摘要文本 |
| `markdown` | `MarkdownExporter` | `.md` | Markdown + Mermaid 图表 |
| `blueprint_text` | `BlueprintTextExporter` | `.txt` | 蓝图翻译参考文本（紧凑格式） |
| `blueprint_ue_text` | `BlueprintUETextExporter` | `.txt` | 接近 UE 原样的蓝图节点文本 |
| `n2c` | `N2CExporter` | `.n2c.json` | N2C 中间格式 JSON（支持验证） |
| `cpp_skeleton` | `CppSkeletonExporter` | `.h` | C++ 类骨架头文件（需要 LinkerParseResult） |
| `cpp_json_ir` | `CppJsonIrExporter` | `.cpp.json` | C++ JSON IR 格式 |

### JsonExporter

包装 `format_json_full` / `format_json_summary`。

```python
class JsonExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        if options.format == "json_summary":
            data = format_json_summary(result, include_schema=options.include_schema)
        else:
            data = format_json_full(
                result,
                include_schema=options.include_schema,
                include_function_graphs=options.include_function_graphs,
            )
        return json.dumps(data, indent=2, ensure_ascii=False)
```

### TextExporter

包装 `format_text_full` / `format_text_summary`。

```python
class TextExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        if options.format == "text_summary":
            return format_text_summary(result)
        return format_text_full(result)
```

### MarkdownExporter

包装 `format_markdown`，输出含表格和 Mermaid 流程图的 Markdown。

```python
class MarkdownExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        return format_markdown(result)
```

### BlueprintTextExporter

包装 `format_blueprint_translation_text`，输出紧凑格式的蓝图翻译参考文本。

```python
class BlueprintTextExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        return format_blueprint_translation_text(result)
```

### BlueprintUETextExporter

包装 `format_blueprint_ue_text`，输出接近 UE 文本导出的蓝图节点文本。

```python
class BlueprintUETextExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        return format_blueprint_ue_text(result)
```

### N2CExporter

包装 `to_n2c_json` + `validate_n2c_json`，支持输出验证。

```python
class N2CExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        data = to_n2c_json(result=result)
        if options.validate_output:
            errors = validate_n2c_json(data)
            if errors:
                raise ExportValidationError(f"N2C validation failed: {'; '.join(errors)}")
        return json.dumps(data, indent=2, ensure_ascii=False)

    def validate(self, result, options: ExportOptions) -> list[str]:
        data = to_n2c_json(result=result)
        return validate_n2c_json(data)

    @property
    def validates_against_schema(self) -> bool:
        return True
```

### CppSkeletonExporter

包装 `extract_cpp_class_skeleton` + `format_cpp_header`。

需要 `parse_uasset_with_linker` 返回的 `LinkerParseResult`。
对普通 `ParseResult` 会尝试提取但可能结果有限。

```python
class CppSkeletonExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        from uasset_read.cpp_gen import extract_cpp_class_skeleton, format_cpp_header
        ir = extract_cpp_class_skeleton(result)
        return format_cpp_header(ir)
```

### CppJsonIrExporter

包装 `format_cpp_class_json`，将 `CppClassIR` 序列化为 JSON。

```python
class CppJsonIrExporter(IExporter):
    def export(self, result, options: ExportOptions) -> str:
        from uasset_read.cpp_gen import extract_cpp_class_skeleton
        ir = extract_cpp_class_skeleton(result)
        data = format_cpp_class_json(ir)
        return json.dumps(data, indent=2, ensure_ascii=False)
```

## 批量导出

<!-- data-api="BatchExporter" -->
```python
class BatchExporter:
    def __init__(self, output_dir: str, options: ExportOptions):
        ...

    def export_files(self, file_paths: list[str]) -> BatchExportResult:
        """导出多个 .uasset/.umap 文件。"""
        ...
```

### BatchExportResult

```python
@dataclass
class BatchExportResult:
    success: list[str]           # 成功导出的文件路径
    failed: list[tuple[str, str]]  # (file_path, error_message)
    skipped: list[tuple[str, str]] # (file_path, reason)

    @property
    def total(self) -> int: ...
    @property
    def has_failures(self) -> bool: ...
```

### 批量导出目录结构

```
output_dir/
  BP_MyBlueprint/
    blueprint.json
  BP_Another/
    blueprint.json
```

### 批量导出示例

```python
from uasset_read.exporter import BatchExporter, ExportOptions

options = ExportOptions(format="json", tolerant=True)
exporter = BatchExporter(output_dir="./output", options=options)
result = exporter.export_files([
    "path/to/BP_A.uasset",
    "path/to/BP_B.uasset",
])

print(f"成功: {len(result.success)}, 失败: {len(result.failed)}, 跳过: {len(result.skipped)}")
```

## 自动注册机制

导出器在模块导入时自动注册：

```python
# src/uasset_read/exporter/__init__.py
from . import json_exporter      # 导入时自动注册 "json" 和 "json_summary"
from . import text_exporter      # 自动注册 "text" 和 "text_summary"
from . import markdown_exporter  # 自动注册 "markdown"
from . import blueprint_text_exporter   # 自动注册 "blueprint_text"
from . import blueprint_ue_text_exporter  # 自动注册 "blueprint_ue_text"
from . import n2c_exporter       # 自动注册 "n2c"
from . import cpp_skeleton_exporter  # 自动注册 "cpp_skeleton"
from . import cpp_json_ir_exporter   # 自动注册 "cpp_json_ir"
```

每个导出器模块末尾调用：

```python
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("format_name", ExporterClass)
```

## 文件位置

| 文件 | 路径 |
|------|------|
| 模块根目录 | `src/uasset_read/exporter/` |
| 基类与接口 | `exporter/base.py` |
| 注册表 | `exporter/registry.py` |
| 批量导出 | `exporter/batch.py` |
| JSON 导出器 | `exporter/json_exporter.py` |
| 文本导出器 | `exporter/text_exporter.py` |
| Markdown 导出器 | `exporter/markdown_exporter.py` |
| 蓝图文本导出器 | `exporter/blueprint_text_exporter.py` |
| 蓝图 UE 文本导出器 | `exporter/blueprint_ue_text_exporter.py` |
| N2C 导出器 | `exporter/n2c_exporter.py` |
| C++ 骨架导出器 | `exporter/cpp_skeleton_exporter.py` |
| C++ JSON IR 导出器 | `exporter/cpp_json_ir_exporter.py` |
