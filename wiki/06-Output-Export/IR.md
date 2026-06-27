---
title: IR 中间表示
section: ir
---

# IR 中间表示

IR（Intermediate Representation，中间表示）是 0.4.1 引入的统一数据层，位于 `ParseResult` 和渲染器之间。渲染器只接收 `PackageIR`，不访问 `ParseResult`。

## 设计目标

1. **解耦**：解析逻辑和输出格式完全独立
2. **精简**：IR 只保留渲染器需要的数据，去除冗余
3. **统一**：所有渲染器共享同一数据结构
4. **GUID 标准化**：所有 Node/Pin GUID 统一为 32 位小写 hex

## 数据类型

所有 IR 类型定义在 `src/uasset_read/models/ir.py`。

### PackageHeaderIR

```python
@dataclass
class PackageHeaderIR:
    package_name: str          # 包名
    package_class: str         # 包类
    package_flags: int         # 包标志
    total_export_count: int    # 导出数量
    total_import_count: int    # 导入数量
    ue_version: str            # UE 版本
```

### PinIR

```python
@dataclass
class PinIR:
    pin_name: str              # Pin 名称
    pin_type: str              # Pin 类型
    pin_type_value: str | None # Pin 类型值
    linked_to: list[str]       # 连接目标
    direction: str             # 方向（输入/输出）
    default_value: str | None  # 默认值
```

### NodeIR

```python
@dataclass
class NodeIR:
    node_guid: str             # 节点 GUID（32 位小写 hex）
    node_class: str            # 节点类
    node_comment: str | None   # 注释
    pins: list[PinIR]          # Pins
    execution_flow: list[dict] # 执行流
```

### GraphIR

```python
@dataclass
class GraphIR:
    graph_guid: str            # 图 GUID
    graph_name: str            # 图名称
    graph_class: str           # 图类
    nodes: list[NodeIR]        # 节点列表
    execution_chains: list[list[str]]  # 执行链
```

### PropertyIR

```python
@dataclass
class PropertyIR:
    name: str                  # 属性名
    type: str                  # 属性类型
    value: Any                 # 属性值
    array_index: int           # 数组索引
    guid: str | None           # 属性 GUID
```

### ExportIR

```python
@dataclass
class ExportIR:
    index: int                 # 导出索引
    object_name: str           # 对象名
    object_class: str          # 对象类
    serial_size: int           # 序列化大小
    outer_index_resolved: str | None    # 外部索引解析
    super_index_resolved: str | None    # 父级索引解析
    parent_class: str | None   # 父类
    properties: list[PropertyIR]  # 属性列表
    graphs: list[GraphIR]      # 图列表
    bulk_data: dict | None     # Bulk 数据
```

### BlueprintIR

```python
@dataclass
class BlueprintIR:
    parent_class: str | None           # 父类
    functions: list[BlueprintFunctionIR]  # 函数列表
    events: list[BlueprintEventIR]     # 事件列表
    components: list[dict]             # 组件列表
```

### BlueprintFunctionIR / BlueprintEventIR

```python
@dataclass
class BlueprintFunctionIR:
    name: str                  # 函数名
    return_type: str           # 返回类型
    parameters: list[dict]     # 参数列表

@dataclass
class BlueprintEventIR:
    name: str                  # 事件名
    event_type: str            # 事件类型
    parameters: list[dict]     # 参数列表
```

### DecompiledFunctionIR

```python
@dataclass
class DecompiledFunctionIR:
    name: str                  # 函数名
    signature: str             # 签名
    cpp_code: str              # C++ 代码
    parameters: list[dict]     # 参数列表
    return_type: str           # 返回类型
```

### ExecutionChainIR

```python
@dataclass
class ExecutionChainIR:
    event: str                 # 起始事件
    chain: list[str]           # 执行链
```

### LinkerSummaryIR

```python
@dataclass
class LinkerSummaryIR:
    has_linker: bool           # 是否有 linker
    import_paths: list[str]    # 导入路径
    export_paths: list[str]    # 导出路径
```

### VariableIR

```python
@dataclass
class VariableIR:
    name: str                  # 变量名
    type: str                  # 变量类型
    default_value: str | None  # 默认值
```

### PackageIR（顶层结构）

```python
@dataclass
class PackageIR:
    header: PackageHeaderIR                    # 包头部
    name_map: list[str]                        # 名称表
    imports: list[dict]                        # 导入表
    exports: list[ExportIR]                    # 导出表
    linker: LinkerSummaryIR | None             # 链接摘要
    blueprint: BlueprintIR | None = None       # 蓝图元数据
    decompiled_functions: list[DecompiledFunctionIR] = field(default_factory=list)
    execution_chains: list[ExecutionChainIR] = field(default_factory=list)
    variables: list[VariableIR] = field(default_factory=list)
```

## IR 构建器

`ir_builder.py` 中的 `build_package_ir(result)` 函数负责从 `ParseResult` 构建 `PackageIR`。

```python
from uasset_read.ir_builder import build_package_ir

ir = build_package_ir(result)
```

## 数据流

```
ParseResult（原始解析结果）
    ↓ build_package_ir()
PackageIR（统一中间表示）
    ↓ renderer.render()
Output String（最终输出）
```

**相关章节**: [[渲染器系统]] · [[解析管线]]
