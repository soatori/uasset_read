# Core / Extras 分层策略

## 背景

uasset_read 包含从基础 .uasset 解析到蓝图字节码反编译、C++ 骨架生成等
多层次功能。许多使用者只需要核心解析能力，不需要高级分析模块。

将模块划分为 **core** 和 **extras** 两个命名空间，帮助使用者理解依赖关系，
也为未来可选延迟加载 / 拆分提供结构基础。

## 分层定义

### Core（核心模块）

基础解析管线，任何 .uasset 解析都需要：

| 模块 | 职责 |
|---|---|
| `archive` | FArchive 二进制读取 |
| `constants` | 格式常量 |
| `exceptions` | 异常类型 |
| `core` | 高层 API（parse_single / parse_batch） |
| `parse_uasset` | 包解析入口 |
| `package` | PackageBundle / Provider |
| `models` | 数据模型（IR、PropertyTag、结果容器） |
| `serializers` | 表结构序列化（PackageSummary、Import/ExportMap） |
| `parsers` | 属性解析器 |
| `link` | PackageLinker、对象实例化 |

### Extras（可选高级模块）

构建在 core 之上，提供深度分析能力：

| 模块 | 职责 |
|---|---|
| `graph` | 蓝图图解析（执行流、数据流、连接映射） |
| `kismet` | 字节码反编译（表达式 → AST → C++ 伪代码） |
| `cpp_gen` | C++ 类骨架生成 |
| `blueprint` | 蓝图元数据提取（变量、组件、SCS） |

## 导入路径

Extras 模块通过 `uasset_read.extras.*` 命名空间访问：

```python
from uasset_read.extras.graph import extract_blueprint_graphs
from uasset_read.extras.kismet import decompile_uasset
from uasset_read.extras.cpp_gen import extract_cpp_class_skeleton
from uasset_read.extras.blueprint import extract_blueprint_metadata
```

原路径 `uasset_read.graph` 等仍然可用（向后兼容）。

## 实现方式

`uasset_read/extras/__init__.py` 使用 PEP 562 `__getattr__` 延迟加载，
将 `extras.X` 映射到 `uasset_read.X`。实际模块位置不变，仅为命名空间别名。

## 设计原则

- **零运行时开销**：未访问的 extras 子模块不会被导入
- **向后兼容**：原导入路径保持不变
- **渐进增强**：使用者可按需引入高级功能
