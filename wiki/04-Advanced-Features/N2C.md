---
title: N2C 中间格式
section: n2c
---

# N2C 中间格式

`n2c/` 模块定义了标准化的蓝图图结构中间格式（Node-to-Code），支持语义化节点表示、验证和双向序列化转换。

## 概述

N2C（Node-to-Code）中间格式将 `UEdGraphNode` 转换为语义化的数据结构，通过处理器注册表模式分发到具体处理器，提取节点的语义信息。核心目标：

- **语义化**：将 UE 内部类名（如 `K2Node_CallFunction`）映射为语义类型（如 `CallFunction`）
- **紧凑化**：通过 `N2CIdMapper` 将 GUID 压缩为短 ID（`N1`, `N2`...），节省约 60% token
- **可验证**：内置 JSON Schema 验证器，零外部依赖
- **可扩展**：57 种节点处理器，覆盖 UE5.8 全部 K2Node 类型

## 核心类

| 类 | 路径 | 说明 |
|----|------|------|
| `N2CStruct` | `schema.py` | 顶层输出容器（version, metadata, graphs, blueprint, properties, decompiled_functions） |
| `N2CGraph` | `schema.py` | 单图表示（name, graph_type, nodes, flows） |
| `N2CNode` | `schema.py` | 紧凑节点表示（id, type, name, pins, extra_data） |
| `N2CPin` | `schema.py` | 引脚信息（pin_name, pin_category, direction, default_value） |
| `N2CNodeDefinition` | `definitions.py` | 语义化节点定义（处理器使用的中间结构） |
| `N2CIdMapper` | `id_mapper.py` | GUID ↔ 短 ID 双向映射器 |
| `N2CNodeType` | `node_types.py` | 126 种 K2Node 语义类型枚举 |
| `N2CNodeTypeRegistry` | `type_registry.py` | 类型注册表（类名 → 语义类型映射） |
| `N2CNodeProcessor` | `processor_base.py` | 节点处理器抽象基类 |
| `N2CProcessorRegistry` | `processor_registry.py` | 处理器注册表与调度 |

## 数据模型

### 四层结构

```
N2CStruct                    ← 顶层容器
├── version: "2.0.0"
├── metadata: {Name, BlueprintType, BlueprintClass}
├── graphs: [N2CGraph, ...]
│   ├── name
│   ├── graph_type            ← "event", "uber", "function", "macro"
│   ├── nodes: [N2CNode, ...]
│   │   ├── id                ← 短 ID "N1", "N2"...
│   │   ├── type              ← 语义类型 "CallFunction", "Event"...
│   │   ├── name              ← 用户友好名称
│   │   ├── comment
│   │   ├── pure / latent
│   │   ├── input_pins: [N2CPin, ...]
│   │   ├── output_pins: [N2CPin, ...]
│   │   └── extra_data: {}    ← 处理器填充的语义数据
│   └── flows
│       ├── execution: [...]   ← 执行流链
│       └── data: {}           ← 数据流映射
├── structs: []                ← 结构体定义占位
├── enums: []                  ← 枚举定义占位
├── blueprint: {}              ← v2.0.0 蓝图元数据（变量/函数/事件）
├── properties: []             ← v2.0.0 属性列表
└── decompiled_functions: []   ← v2.0.0 Kismet 反编译函数列表
```

### Schema 版本

| 版本 | 说明 |
|------|------|
| `1.0.0` | 仅 graphs（向后兼容） |
| `2.0.0` | 增加 blueprint / properties / decompiled_functions |

## 节点类型系统

### N2CNodeType 枚举（126 种）

覆盖 UE5.8 Engine/Source/Editor/ 全模块扫描的 K2Node 类型，主要分类：

| 分类 | 类型示例 |
|------|----------|
| **函数调用** | `CallFunction`, `CallArrayFunction`, `CallDelegate`, `CallParentFunction`, `CallFunctionOnMember` |
| **事件** | `Event`, `CustomEvent`, `ActorBoundEvent`, `ComponentBoundEvent`, `InputActionEvent` |
| **变量** | `VariableGet`, `VariableSet`, `LocalVariable`, `StructMemberGet`, `StructMemberSet` |
| **流程控制** | `Branch`, `Sequence`, `MultiGate`, `DoOnce`, `Select` |
| **Switch** | `SwitchInt`, `SwitchString`, `SwitchEnum`, `SwitchName` |
| **类型转换** | `DynamicCast`, `ClassDynamicCast`, `CastByteToEnum` |
| **结构体** | `MakeStruct`, `BreakStruct`, `SetFieldsInStruct` |
| **容器** | `MakeArray`, `MakeMap`, `MakeSet`, `MapForEach`, `SetForEach` |
| **委托** | `AddDelegate`, `CreateDelegate`, `ClearDelegate`, `RemoveDelegate`, `DelegateSet` |
| **异步/潜行** | `AsyncAction`, `Timeline`, `PlayMontage`, `LatentGameplayTaskCall` |
| **数学/逻辑** | `MathExpression`, `FormatText`, `BinaryOperator` |
| **枚举** | `EnumLiteral`, `GetEnumeratorName`, `GetNumEnumEntries`, `ForEachEnum` |
| **输入** | `InputAction`, `InputKey`, `InputTouch`, `EnhancedInputAction` |
| **对象创建** | `SpawnActor`, `CreateWidget`, `ConstructObject`, `AddComponent` |
| **宏/隧道** | `MacroInstance`, `Tunnel`, `TunnelBoundary`, `Composite` |
| **其他** | `Comment`, `Knot`, `Literal`, `Self`, `Unknown` |

## 处理器架构

### N2CNodeProcessor 抽象基类

```python
class N2CNodeProcessor(ABC):
    @property
    @abstractmethod
    def node_types(self) -> List[N2CNodeType]:
        """此处理器可处理的节点语义类型列表。"""
        ...

    @abstractmethod
    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        """处理节点，填充 definition 的 extra_data。"""
        ...
```

### 处理器注册表

`N2CProcessorRegistry` 负责注册、查找和调度处理器：

- **register()**：注册处理器到指定节点类型
- **set_fallback()**：设置默认回退处理器
- **get_processor()**：获取处理器（无精确匹配时返回 fallback）
- **process_node()**：统一处理入口，异常安全

### 57 种处理器列表

| 模块 | 处理器 |
|------|--------|
| **核心** | `CallFunctionProcessor`, `EventProcessor`, `FunctionEntryProcessor`, `FlowControlProcessor`, `VariableProcessor`, `CastProcessor`, `CommentProcessor`, `DelegateProcessor`, `WidgetProcessor` |
| **flow_control** | `MultiGateProcessor`, `DoOnceProcessor`, `SelectProcessor`, `EaseFunctionProcessor`, `ForEachEnumProcessor`, `MapForEachProcessor`, `SetForEachProcessor` |
| **struct_ops** | `StructOpsProcessor`, `MakeArrayProcessor`, `MakeMapProcessor`, `MakeSetProcessor` |
| **variable_ops** | `LocalVariableProcessor`, `CreateDelegateProcessor`, `ClearDelegateProcessor`, `RemoveDelegateProcessor`, `DelegateSetProcessor`, `StructMemberGetProcessor`, `StructMemberSetProcessor`, `SetFieldsInStructProcessor` |
| **utilities** | `AsyncActionProcessor`, `TimelineProcessor`, `FormatTextProcessor`, `MathExpressionProcessor`, `GetEnumeratorNameProcessor`, `GetEnumeratorNameAsStringProcessor`, `GetNumEnumEntriesProcessor`, `EnumComparisonProcessor` |
| **input** | `EnhancedInputActionProcessor` |

## 序列化 API

### to_n2c_json()

将图数据转换为 N2CStruct 格式 dict。

```python
to_n2c_json(
    graphs: list | None = None,
    result: Any | None = None,
    *,
    execution_flows: list[dict] | None = None,
    data_flows: list[dict] | None = None,
) → dict
```

**参数**：`graphs` 传 `UEdGraph` 列表，或 `result` 传 `ParseResult` 对象。可选传入预计算的执行流和数据流。

**流程**：
1. 初始化处理器注册表（幂等）
2. 构建 `N2CIdMapper`，注册非 Knot 节点
3. 遍历节点：派生名称 → 解析语义类型 → 构建引脚 → 调用处理器填充 extra_data
4. 构建执行流链和数据流映射
5. 提取元数据（Name, BlueprintType, BlueprintClass）
6. 提取 v2.0.0 字段（blueprint, properties, decompiled_functions）
7. 返回 `N2CStruct.to_dict()`

### from_n2c_json()

从 N2CStruct dict 重建 dataclass 实例。

```python
from_n2c_json(data: dict) → N2CStruct
```

验证必需字段（`graphs`、节点 `id/type/name`），重建所有 dataclass 层级。

### validate_n2c_json()

纯 Python JSON Schema 验证器，零外部依赖。

```python
validate_n2c_json(data: dict) → List[str]
```

返回错误消息列表，空列表表示验证通过。检查类型、枚举值、正则模式、必需字段。

## N2CIdMapper

GUID ↔ 短 ID 双向映射器，按注册顺序分配 `N1`, `N2`, `N3`...

```python
mapper = N2CIdMapper()
short_id = mapper.to_short("4A3B2C1D-...")  # → "N1"
guid = mapper.to_guid("N1")                   # → "4A3B2C1D-..."
```

- 重复注册同一 GUID 返回相同短 ID（幂等）
- Token 压缩率约 60%（GUID 36 字符 → 短 ID 2-4 字符）

## JSON Schema

内置 `N2C_JSON_SCHEMA`（Draft-07 兼容），关键约束：

| 字段 | 约束 |
|------|------|
| `version` | 正则 `^\d+\.\d+\.\d+$` |
| `metadata.Name` | 必需 string |
| `graphs[*].graph_type` | 枚举 `["EventGraph", "Function", "Macro", "Animation"]` |
| `graphs[*].nodes[*].id` | 正则 `^N\d+$` |
| `graphs[*].nodes[*].pins[*].direction` | 枚举 `["input", "output"]` |

## 数据流提取

`extract_data_flow_map()` 将数据流转换为紧凑映射格式，通过 `N2CIdMapper` 和引脚位置索引优化输出大小。

## Token 估算

`_estimate_token_count()` 粗略估算 JSON 的 token 用量，基于 JSON 字符串长度 / 4 的经验公式，与 OpenAI tokenizer 近似。

## CLI 使用

```bash
uasset-read path/to/file.uasset --n2c    # 输出 N2C 中间格式 JSON
```

## 相关文件

| 文件 | 路径 |
|------|------|
| 模块入口 | `src/uasset_read/n2c/__init__.py` |
| 数据模型 | `src/uasset_read/n2c/schema.py` |
| 节点定义 | `src/uasset_read/n2c/definitions.py` |
| 序列化器 | `src/uasset_read/n2c/serializer.py` |
| 类型枚举 | `src/uasset_read/n2c/node_types.py` |
| 类型注册表 | `src/uasset_read/n2c/type_registry.py` |
| ID 映射器 | `src/uasset_read/n2c/id_mapper.py` |
| 处理器基类 | `src/uasset_read/n2c/processor_base.py` |
| 处理器注册表 | `src/uasset_read/n2c/processor_registry.py` |
| Schema 验证 | `src/uasset_read/n2c/validation.py` |
| 数据流提取 | `src/uasset_read/n2c/flow_extractor.py` |
| 兼容性层 | `src/uasset_read/n2c/compat.py` |
| 处理器目录 | `src/uasset_read/n2c/processors/` |
