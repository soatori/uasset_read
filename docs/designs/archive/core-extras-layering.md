# Core/Extras 分层设计

status: historical

> **状态：历史分层方案。** 可用于理解现有 lazy import 决策，但新的 core/extension 边界由 [`../2026-08-26-package-first-uasset-parser-refactor.md`](../2026-08-26-package-first-uasset-parser-refactor.md) 定义。

> Issue #117 — 定义 core/extras 分层，extras 模块延迟导入

## 目标

将 `uasset_read` 包按功能域分为 **Core**（默认加载）和 **Extras**（按需加载），确保基本解析流程不会触发重量级模块的导入开销。

## 分层定义

### Core 模块（始终加载）

基础解析管线所需的所有模块，`from uasset_read.parse_uasset import parse_package` 时自动加载：

| 模块 | 路径 | 职责 |
| --- | --- | --- |
| `archive` | `archive.py` | FArchive 二进制读取层 |
| `parse_uasset` | `parse_uasset.py` | 主解析管线入口 |
| `models` | `models/` | 数据模型（ParseResult、PropertyTag 等） |
| `serializers` | `serializers/` | 二进制序列化器 |
| `parsers` | `parsers/` | 属性解析器 |
| `ir_builder` | `ir_builder.py` | ParseResult → PackageIR |
| `renderers` | `renderers/` | 基础输出格式化（JSON/Markdown） |
| `constants` | `constants.py` | 常量定义 |
| `exceptions` | `exceptions.py` | 异常类 |
| `versioning` | `versioning.py` | UE 版本容器 |
| `package` | `package.py` | PackageBundle/Provider |
| `memory_safety` | `memory_safety.py` | 内存限制/监控 |
| `project_logging` | `project_logging.py` | 日志配置 |

### Extras 模块（按需加载）

可选功能域，仅在实际使用时通过函数内 import 加载：

| 模块 | 路径 | 职责 | 使用场景 |
| --- | --- | --- | --- |
| `graph` | `graph/` | 蓝图图解析 | `--markdown` 输出蓝图图 |
| `kismet` | `kismet/` | Kismet 字节码反编译 | 蓝图函数体提取 |
| `blueprint` | `blueprint/` | 蓝图变量/组件提取 | 蓝图元数据解析 |
| `cpp_gen` | `cpp_gen/` | C++ 代码生成 | `--format cpp` 输出 |
| `pak` | `pak/` | .pak 文件读取 | PAK 包解析 |
| `iostore` | `iostore/` | IoStore 容器读取 | UE5.3+ IoStore |
| `link` | `link/` | PackageLinker 链接 | `parse_uasset_with_linker()` |
| `objects` | `objects/` | UObject 类型系统 | 链接模式 |
| `debug` | `debug/` | HexView 等调试工具 | `--hex-view` 选项 |
| `mappings` | `mappings.py` | 类型映射（usmap/jmap） | `--mappings` 参数 |

## 延迟导入策略

### 规则

1. **Core 模块之间**：允许顶层 import
2. **Extras 模块被 Core 引用**：必须使用函数内 import（延迟导入）
3. **Extras 模块之间**：允许顶层 import（extras 内部的依赖关系不受限）
4. **`TYPE_CHECKING` 守卫**：类型注解使用 `from __future__ import annotations` + `TYPE_CHECKING` 块

### 实现模式

```python
# 错误 — extras 模块在顶层导入
from uasset_read.kismet.pipeline import decompile_single_function

# 正确 — extras 模块在函数内延迟导入
def _extract_kismet(...):
    from uasset_read.kismet.pipeline import decompile_single_function
    ...
```

## 验证

`tests/test_core_extras_import.py` 通过监控 `sys.modules` 确保 `parse_package` 的导入不会触发任何 kismet 模块加载。

## 影响范围

- 不改变功能行为，仅改变 import 时机
- 零运行时依赖不变
- 所有现有测试通过
