# API 稳定性策略

## 概述

`uasset_read` 是一个纯输出脚本项目，**不提供向后兼容保证**。但为了清晰起见，我们明确区分：
- **稳定根 API**：推荐外部使用的符号，通过 `from uasset_read import ...` 访问
- **子模块 API**：内部实现细节，通过 `from uasset_read.xxx import ...` 访问，不保证稳定

## 稳定根 API（`__all__`）

以下符号通过 `from uasset_read import ...` 访问，是推荐的外部使用接口：

### 核心入口函数
- `parse_single(file_path, ...)` — 解析单个 .uasset 文件
- `parse_batch(file_paths, ...)` — 批量解析多个文件
- `parse_package(archive, ...)` — 底层包解析
- `parse_uasset(file_path, ...)` — `parse_package` 的别名
- `parse_uasset_with_linker(file_path, ...)` — 带 Linker 的解析
- `list_formats()` — 列出所有可用的渲染器格式

### 结果模型
- `ParseResult` — 解析结果容器（summary、linker、graphs、blueprint）
- `PackageSummary` — 包摘要信息
- `ExportEntry` — 导出条目
- `ImportEntry` — 导入条目
- `BatchResult` — 批量解析结果

### IR 模型
- `PackageIR` — 包中间表示
- `ExportIR` — 导出中间表示
- `GraphIR` — 图中间表示
- `NodeIR` — 节点中间表示
- `PinIR` — 引脚中间表示

### 异常
- `UAssetError` — 所有 uasset_read 异常的基类
- `ParseError` — 解析错误
- `VersionError` — 版本不支持错误

### 高级工具
- `FArchive` — 底层归档读取器
- `PackageBundle` — 包 bundle（支持 PAK/IoStore）
- `PackageLinker` — 包链接器

## 子模块 API（不稳定）

以下模块通过 `from uasset_read.xxx import ...` 访问，是内部实现细节：

### 序列化模块
- `uasset_read.serializers` — 底层序列化器（PackageFileSummary、ObjectImport/Export 等）
- `uasset_read.serializers.property_tags` — 属性标签解析
- `uasset_read.serializers.object_resources` — 对象资源读取

### 解析器模块
- `uasset_read.parsers` — 属性值解析器
- `uasset_read.parsers.class_registry` — 类处理器注册表

### 蓝图模块
- `uasset_read.blueprint` — 蓝图变量、组件、SCS 树提取
- `uasset_read.blueprint.variable_extractor` — 变量提取器
- `uasset_read.blueprint.transform_parser` — 变换数据解析

### 图解析模块
- `uasset_read.graph` — 蓝图图解析（执行流、数据流、连接图）
- `uasset_read.graph.flow_builder` — 执行流构建器
- `uasset_read.graph.data_tracker` — 数据流追踪器

### Kismet 字节码模块
- `uasset_read.kismet` — 字节码解析、反编译
- `uasset_read.kismet.expression` — Kismet 表达式
- `uasset_read.kismet.translator` — 字节码到 AST 转换

### C++ 代码生成
- `uasset_read.cpp_gen` — C++ 类骨架生成
- `uasset_read.cpp_gen.skeleton` — 骨架提取
- `uasset_read.cpp_gen.call_graph` — 调用图生成

### 渲染器模块
- `uasset_read.renderers` — 输出格式渲染器（JSON、text、markdown、cpp-skeleton）
- `uasset_read.renderers.json_renderer` — JSON 渲染
- `uasset_read.renderers.text_renderer` — 文本渲染
- `uasset_read.renderers.markdown_renderer` — Markdown 渲染

### 其他模块
- `uasset_read.memory` — 内存监控
- `uasset_read.versioning` — 版本管理
- `uasset_read.link` — 链接器
- `uasset_read.pak` — PAK 文件读取
- `uasset_read.iostore` — IoStore 容器
- `uasset_read.package` — 包管理
- `uasset_read.raw` — 原始文件解析（JSON、INI、locres）
- `uasset_read.mappings` — 类型映射（usmap/jmap）
- `uasset_read.models` — 数据模型（UEdGraph、PropertyTag 等）

## 根模块的其他符号

根模块 `uasset_read` 仍然导入了大量内部符号（常量、辅助函数等），这是为了向后兼容。但这些符号**不在 `__all__` 中**，使用者不应直接依赖：

```python
# ❌ 不推荐：依赖内部常量
from uasset_read import PACKAGE_FILE_TAG

# ✅ 推荐：从子模块访问
from uasset_read.constants import PACKAGE_FILE_TAG
```

## 迁移指南

如果你之前使用了根模块的内部符号，建议迁移到子模块路径：

```python
# 旧代码（可能在未来的版本中失效）
from uasset_read import read_package_summary, ObjectExport

# 新代码（稳定）
from uasset_read.serializers import read_package_summary, ObjectExport
```

## 设计原则

1. **最小稳定 API**：`__all__` 只包含最高层、最常用的符号
2. **子模块即内部**：所有实现细节通过子模块访问，不保证稳定
3. **稳定 API 也会演进**：稳定 API 是当前推荐的使用方式，但项目整体遵循"无向后兼容"原则。重大变更会在 changelog 中说明，并提供迁移路径
4. **清晰性优先**：明确区分"推荐使用"和"内部实现"，避免误导

## 参见

- [Issue #116](https://github.com/soatori/uasset_read/issues/116) — 收缩根 API 的讨论
- [项目约束](../.claude/rules/constraints.md) — "无向后兼容"原则
