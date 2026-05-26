# Phase 69: 节点处理器架构 — Processor 模式替代 switch/case - Research

**Researched:** 2026-05-21
**Domain:** Python 设计模式 — 策略模式/注册表分发/K2Node 节点处理
**Confidence:** HIGH

## Summary

Phase 69 的目标是将代码库中散落在 5+ 个文件中的 `if/elif` 节点类型分派链，重构为基于 Processor 类的统一分发架构。当前代码库中存在 30+ 个独立的 `node.class_name` 或 `node_type` 分支判断，分布在 `flow_builder.py`（~15 处）、`serializers/graph.py`（6 处）、`cpp_function_body_extractor.py`（6 处）、`extract_cpp_skeleton.py`（3 处）、`markdown_formatter.py`（字符串操作）以及 `kismet/translator.py`（~20 处 isinstance 检查）中。

这些分派链的核心问题是：（1）字符串匹配脆弱且无法被 IDE 静态分析；（2）逻辑分散导致修改一个节点类型的行为需要跨文件搜索；（3）无法单元测试单个分支；（4）随着 Phase 68 引入 100+ 语义类型，线性 if/elif 链将不可维护。

Phase 68 的 `N2CNodeTypeRegistry` 将提供语义类型枚举（如 `N2CNodeType.CallFunction`）和类名到语义类型的映射。Phase 69 以此为基础，构建 `N2CNodeProcessor` 抽象基类 + 注册表分发机制，使得每个语义类型有独立的 Processor 类负责提取其特有属性。

**Primary recommendation:** 采用"策略模式 + 类装饰器自动注册"方案，建立 `N2CProcessorRegistry` 单例，每个 Processor 类通过 `@N2CProcessorRegistry.register(N2CNodeType.X)` 装饰器注册自身，工厂方法通过类型查找对应 Processor。先在 `graph/flow_builder.py` 的核心分派链上试点，逐步替换其他文件的分支。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 节点类型分发 | API/Backend (解析层) | — | 属于图解析管道的核心逻辑，在内存中处理已反序列化的节点 |
| 处理器注册表 | API/Backend (解析层) | — | 单例注册中心，管理 Processor 生命周期 |
| 属性提取逻辑 | API/Backend (解析层) | — | 每个 Processor 从 K2Node 提取语义信息到 N2CStruct |
| 序列化写入 | API/Backend (解析层) | — | Phase 70 负责，Phase 69 仅负责填充 N2CNodeDefinition |
| C++ 代码生成 | API/Backend (生成层) | — | Phase 70+ 负责，Phase 69 不触及 cpp_gen/ |

## Phase 68 Dependency

Phase 69 假设 Phase 68 已提供以下接口（作为输入依赖）：

```python
# N2CNodeType 枚举（Phase 68 产出）
class N2CNodeType(Enum):
    CallFunction = "CallFunction"
    Event = "Event"
    CustomEvent = "CustomEvent"
    FunctionEntry = "FunctionEntry"
    FunctionResult = "FunctionResult"
    VariableGet = "VariableGet"
    VariableSet = "VariableSet"
    Branch = "Branch"          # K2Node_IfThenElse
    Sequence = "Sequence"      # K2Node_ExecutionSequence
    SwitchInt = "SwitchInt"    # K2Node_SwitchInteger
    SwitchString = "SwitchString"
    SwitchEnum = "SwitchEnum"
    MakeStruct = "MakeStruct"
    BreakStruct = "BreakStruct"
    MakeArray = "MakeArray"
    DynamicCast = "DynamicCast"
    # ... 100+ 种
```

```python
# N2CNodeTypeRegistry（Phase 68 产出）
class N2CNodeTypeRegistry:
    def resolve(self, class_name: str) -> N2CNodeType:
        """UE class_name (如 'K2Node_CallFunction') → N2CNodeType"""

    def resolve_from_node(self, node: UEdGraphNode) -> N2CNodeType:
        """从 node.class_name 解析语义类型"""
```

Phase 69 **不实现**上述类，仅消费其接口。

## Current Dispatch Patterns

### 1. `graph/flow_builder.py` — 核心图流构建（~15 处分派点）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L191-247 | `_get_start_event_name()` | `node.class_name` | 5 (Event, EnhancedInputAction, VariableSet, CustomEvent, FunctionEntry) | 提取起点节点的用户友好事件名 |
| L120-175 | `format_node_dict()` | `node.class_name` | 3+ (CallFunction parameters, various node_data patterns) | 格式化节点为 OUT-01 JSON 结构 |
| L371-443 | `_trace_data_source()` | `terminal_node.class_name` | 3 (FunctionEntry, CallFunction, boundary) | 反向数据流追踪，判断数据来源类型 |
| L520-578 | `_trace_execution_from_event()` | `current_node.class_name` | 4 (CallFunction, Event, FunctionEntry, CONTROL_FLOW_NODES) | 执行流追踪，为不同节点类型提取特有信息 |
| L690-704 | `build_execution_flows()` | `start_node.class_name` | 2 (EnhancedInputAction vs others) | 多触发时机节点的特殊处理 |
| L945 | `build_function_graphs()` | `node.class_name == "K2Node_FunctionEntry"` | 1 (filter) | 过滤函数入口节点 |

**复杂度评估:** 这是最需要重构的文件。`_trace_execution_from_event()` 中的 4 个 if 块各自提取不同字段（function_name, event_name, branch_type 等），这正是 Processor 模式的最佳应用场景。

### 2. `serializers/graph.py` — 节点反序列化分派（6 处分派点）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L751-780 | `dispatch_node_class()` | `class_name` | 6 (CallFunction, Event, Knot, Comment, EnhancedInputAction, FunctionEntry) | 根据 class_name 调用对应的 `read_k2node_*` 函数 |

**复杂度评估:** 这是工厂模式，每个分支调用不同的反序列化函数。与 Processor 模式有重叠但关注点不同——这里负责二进制反序列化，Processor 负责已反序列化后的语义提取。**Out of scope for Phase 69**（见下方范围界定）。

### 3. `cpp_gen/extractors/cpp_function_body_extractor.py` — C++ 函数体提取（6 处分派点）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L99-127 | `extract_function_body()` | `node_type` string | 6 (FunctionEntry, CallFunction, Switch*, MacroInstance, FunctionResult, else) | 遍历节点序列，分派到翻译函数 |
| L260-267 | `_translate_control_flow()` | `node_type` string | 1 (MacroInstance skip) + implicit if/switch chain | 控制流节点翻译 |

**复杂度评估:** 这是 Node-to-C++ 翻译层的分派，与 graph/ 层的分派是不同关注点。Phase 69 应先在 graph/ 层统一，cpp_gen/ 层可后续消费统一的 Processor 输出。

### 4. `cpp_gen/extract_cpp_skeleton.py` — C++ 骨架提取（3 处分派点）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L629-638 | `extract_cpp_functions()` | `node.class_name` | 2 (FunctionEntry, Event) | 遍历图节点，提取函数声明 |
| L675 | `extract_cpp_call_statements()` | `node.class_name != "K2Node_CallFunction"` | 1 (filter) | 过滤函数调用节点 |

**复杂度评估:** 轻量分派，主要为过滤操作。可后续消费 Processor 输出。

### 5. `formatters/markdown_formatter.py` — Markdown 格式化（字符串操作）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L136-152 | `_build_mermaid_flowchart()` | `node.get("node_type", "")` | String manipulation (remove "K2Node_" prefix) | Mermaid 图生成中的节点名处理 |

**复杂度评估:** 不是真正的分派链，仅为字符串处理。Phase 69 不直接修改。

### 6. `kismet/translator.py` — Kismet 表达式翻译（~20 处 isinstance 检查）

| Location | Function | Dispatch On | Branches | What It Does |
|----------|----------|-------------|----------|-------------|
| L576-700+ | `line_cpp()` | `isinstance(expr, EX_*)` | ~20+ (各 EExprToken 类型) | 将 KismetExpression 翻译为 C++ 伪代码 |

**复杂度评估:** 已使用 `isinstance()` 而非字符串匹配，是比 class_name 分派更好的模式。但仍然是单体函数，**可作为后续重构目标**，但不在 Phase 69 范围内（Kismet 属于字节码反编译层，与 K2Node 处理器不同层）。

### 汇总统计

| File | Dispatch Points | Individual Branches | Pattern |
|------|----------------|---------------------|---------|
| flow_builder.py | 6 | ~15 | `if node.class_name == "..."` |
| serializers/graph.py | 1 | 6 | `elif class_name == "..."` |
| cpp_function_body_extractor.py | 2 | 7 | `if/elif node_type == "..."` |
| extract_cpp_skeleton.py | 2 | 3 | `if node.class_name == "..."` |
| markdown_formatter.py | 1 | 1 | string `.replace()` |
| kismet/translator.py | 1 | ~20 | `isinstance(expr, EX_*)` |
| **Total** | **13** | **~52** | |

## Processor Pattern Design Options

### Option A: 策略模式 + 类装饰器自动注册（推荐）

```python
class N2CNodeProcessor(ABC):
    """节点处理器基类"""

    @abstractmethod
    def process(self, node: UEdGraphNode, definition: "N2CNodeDefinition") -> None:
        """提取节点特有属性到输出定义"""

    @abstractmethod
    def supported_types(self) -> list[N2CNodeType]:
        """此处理器支持的语义类型列表"""


class N2CProcessorRegistry:
    """处理器注册表（单例）"""
    _instance: Optional["N2CProcessorRegistry"] = None
    _processors: dict[N2CNodeType, N2CNodeProcessor]

    @classmethod
    def get_instance(cls) -> "N2CProcessorRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, processor: N2CNodeProcessor) -> None:
        for node_type in processor.supported_types():
            self._processors[node_type] = processor

    def get_processor(self, node_type: N2CNodeType) -> Optional[N2CNodeProcessor]:
        return self._processors.get(node_type)

    def process(self, node: UEdGraphNode, node_type: N2CNodeType,
                definition: "N2CNodeDefinition") -> bool:
        processor = self.get_processor(node_type)
        if processor:
            processor.process(node, definition)
            return True
        return False


# 使用类装饰器注册（可选便捷方式）
def register_processor(*types: N2CNodeType):
    def decorator(cls):
        processor = cls()
        N2CProcessorRegistry.get_instance().register(processor)
        return cls
    return decorator

@register_processor(N2CNodeType.CallFunction)
class CallFunctionProcessor(N2CNodeProcessor):
    def supported_types(self):
        return [N2CNodeType.CallFunction]

    def process(self, node, definition):
        fr = node.node_data.function_reference if node.node_data else None
        if fr:
            definition.member_name = fr.member_name
            definition.member_parent = fr.member_parent
            definition.b_self_context = fr.b_self_context
        definition.pure = not any(p.pin_type.pin_category == "exec" for p in node.pins)
```

**优点:**
- O(1) 查找（字典查找），不随类型数量增长
- 每个 Processor 独立可测试
- 类装饰器注册让新类型只需添加一个文件
- 与 Phase 68 的 N2CNodeTypeRegistry 自然衔接
- 符合 Open-Closed Principle（开闭原则）

**缺点:**
- 需要额外定义 N2CNodeDefinition 数据结构
- 小项目可能显得过度设计

### Option B: 字典映射函数（轻量级）

```python
# processors/call_function.py
def process_call_function(node: UEdGraphNode, definition: "N2CNodeDefinition") -> None:
    fr = node.node_data.function_reference if node.node_data else None
    if fr:
        definition.member_name = fr.member_name
        definition.member_parent = fr.member_parent

# processors/registry.py
PROCESSOR_MAP: dict[N2CNodeType, Callable] = {
    N2CNodeType.CallFunction: process_call_function,
    N2CNodeType.Event: process_event,
    ...
}

def process_node(node: UEdGraphNode, node_type: N2CNodeType,
                 definition: "N2CNodeDefinition") -> None:
    handler = PROCESSOR_MAP.get(node_type, fallback_process)
    handler(node, definition)
```

**优点:**
- 最小改动，无需抽象基类
- 函数独立可测试
- 迁移成本低

**缺点:**
- 函数无法携带状态（如有状态需求需闭包或 partial）
- 无法利用继承共享逻辑（如 FlowControl 处理器可继承基类）
- 注册表需要手动维护映射字典

### Option C: match/case 分派（Python 3.10+）

```python
def process_node(node: UEdGraphNode, node_type: N2CNodeType,
                 definition: "N2CNodeDefinition") -> None:
    match node_type:
        case N2CNodeType.CallFunction:
            _process_call_function(node, definition)
        case N2CNodeType.Event:
            _process_event(node, definition)
        case N2CNodeType.Branch:
            _process_branch(node, definition)
        # ...
```

**优点:**
- 最接近现有代码结构，迁移成本最低
- Python 3.14.3 原生支持
- IDE 支持好（可以检查未覆盖的 case）

**缺点:**
- 仍然是单体函数，100+ 种类型后难以维护
- 不符合 Open-Closed Principle（新增类型需修改主函数）
- 本质上是将 `if/elif on string` 改为 `match/case on enum`，架构层面没有进步

### 对比表

| 维度 | Option A (策略+注册) | Option B (字典函数) | Option C (match/case) |
|------|---------------------|---------------------|----------------------|
| 可扩展性 | HIGH（添加文件即可） | MEDIUM（需更新映射） | LOW（需修改主函数） |
| 可测试性 | HIGH（独立类） | HIGH（独立函数） | MEDIUM（需构造 match） |
| 状态携带 | YES（实例属性） | NO（需闭包） | NO |
| 逻辑共享 | YES（继承） | NO | NO |
| 100+ 类型后维护 | GOOD | OKAY | POOR |
| 迁移成本 | HIGH | LOW | LOWEST |

**推荐：Option A。** Phase 68 已引入注册表模式（N2CNodeTypeRegistry），Phase 69 延续这一架构风格是自然的。100+ 类型的规模下，Option C 的单体函数和 Option B 的手动映射都不可持续。

## Existing Patterns to Emulate

### Parser Dispatcher (`parsers/property_parser.py`)

```python
def _get_parse_functions():
    """Lazy import to avoid circular dependency."""
    from uasset_read.parsers.property_types import (...)
    return {
        "BoolProperty": parse_bool_property,
        "IntProperty": parse_int_property,
        ...
    }

def parse_property_value(tag, archive, name_map, export_map, summary=None, depth=0):
    parsers = _get_parse_functions()
    base_type = tag.type.split("(")[0]  # Extract base type
    handler = parsers.get(base_type)
    if handler is None:
        return None  # Unknown type → None
    # Dispatch based on handler signature
    ...
```

**值得借鉴:**
- 字典映射查找（O(1) 分发）
- 惰性导入避免循环依赖
- 未知类型优雅降级（返回 None 而非抛异常）

**需要注意的坑:**
- `_get_parse_functions()` 每次调用都重新构建字典 — 应使用模块级常量或单例缓存
- 参数签名不统一（不同处理器接受不同数量的参数）— 需要统一接口

**Phase 69 改进:** 使用类实例方法统一接口签名，避免函数签名不一致问题。

### Kismet Translator (`kismet/translator.py`)

```python
class KismetTranslator:
    def line_cpp(self, expr: KismetExpression) -> str:
        if isinstance(expr, (EX_LocalVariable, EX_InstanceVariable, ...)):
            ...
        if isinstance(expr, EX_IntConst):
            return str(expr.Value)
        ...
```

**值得借鉴:**
- 使用 `isinstance()` 而非字符串匹配
- TypeRegistry 作为依赖注入

**需要改进:**
- 单体函数 ~20+ 个 if 分支 — 未来可扩展为每个 EX_* 类型一个 Translator 类

### Fallback Pattern (`serializers/graph.py`)

```python
def dispatch_node_class(base_node, archive, name_map, ...):
    if class_name == "K2Node_CallFunction":
        ...
    elif class_name == "K2Node_Event":
        ...
    elif raw_properties:
        # Unknown type: preserve raw metadata for debugging
        base_node.node_data = {"_raw_properties": raw_properties}
    return base_node
```

**值得借鉴:**
- 未知类型的 fallback 策略（保留原始数据用于调试）
- Phase 69 的 Processor 分发也应保留类似的 fallback

## Out of Scope

Phase 69 **不修改**以下代码/领域：

1. **Binary serialization readers** — `serializers/graph.py` 中的 `read_k2node_*` 函数。这些是从二进制流反序列化节点的函数，属于数据读取层，不是后处理分派。Phase 69 消费它们的输出，不替换它们。

2. **Kismet bytecode translator** — `kismet/translator.py` 中的 `line_cpp()`。这是 EExprToken 层面的分派（字节码表达式），与 K2Node 层面的分派属于不同抽象层次。可以作为后续重构目标。

3. **C++ code generation** — `cpp_gen/` 中的格式化逻辑。Phase 69 的 Processor 输出 N2CNodeDefinition 中间格式，cpp_gen/ 后续消费这个格式。Phase 69 不直接修改 cpp_gen/。

4. **Property parsing** — `parsers/property_parser.py` 中的属性类型分派。已经是字典映射模式，无需重构为 Processor 模式。

5. **Phase 68 的 N2CNodeTypeRegistry 实现** — Phase 69 假设它已存在，不实现它。

6. **N2CStruct JSON Schema** — Phase 70 负责，Phase 69 仅确保 Processor 输出与其兼容。

## Recommended Approach

### Architecture

```
N2CNodeTypeRegistry (Phase 68)
        │
        ▼ resolves class_name → N2CNodeType
N2CProcessorRegistry (Phase 69)
        │
        ▼ lookup N2CNodeType → N2CNodeProcessor
N2CNodeProcessor.process()
        │
        ▼ fills
N2CNodeDefinition (Phase 69/70 shared)
        │
        ▼ serialized by
N2CStruct JSON (Phase 70)
```

### Implementation Plan

1. **Define `N2CNodeDefinition`** — 统一的节点语义输出结构，包含所有 K2Node 类型的公共字段（node_id, node_type, position, comment, pins）和扩展槽（extra_data: dict 用于类型特有字段）。

2. **Define `N2CNodeProcessor` ABC** — 抽象基类，`process(node, definition)` + `supported_types()`.

3. **Define `N2CProcessorRegistry`** — 单例注册中心，`register()`, `get_processor()`, `process_node()`.

4. **Implement core processors:**
   - `CallFunctionProcessor` — member_name, member_parent, pure, latent
   - `EventProcessor` — event_reference, b_override_function
   - `FunctionEntryProcessor` — function_reference, parameters
   - `FlowControlProcessor` — branch_type, pin_names (True/False pins)
   - `VariableProcessor` — variable_name, direction (get/set)
   - `CastProcessor` — target_type, b_is_safe_cast

5. **Replace dispatch in `flow_builder.py`** — `_trace_execution_from_event()` 中的 4 个 if 块改为 Registry 调用。

6. **Update `format_node_dict()`** — 调用 Processor 而非手动提取。

7. **Backward compatibility** — 保留现有 JSON 输出格式，Processor 内部填充 `N2CNodeDefinition` 后再转换为现有 dict 格式。

### N2CNodeDefinition Structure

```python
@dataclass
class N2CNodeDefinition:
    """统一的节点语义输出（Phase 69/70 共享）"""
    # Common fields (all node types)
    node_id: str              # Short ID ("N1") or GUID
    node_type: N2CNodeType    # Semantic type
    position: tuple[int, int] # (x, y)
    comment: str              # Node comment

    # Common pin info
    input_pins: list[dict]
    output_pins: list[dict]

    # Type-specific extra data (filled by specific Processor)
    extra_data: dict = field(default_factory=dict)
    # Examples:
    # CallFunction: {"member_name": "...", "member_parent": "...", "pure": True}
    # Event: {"event_name": "...", "b_override": False}
    # Branch: {"condition_pin": "Condition"}
```

### Pitfall Prevention

| Pitfall | Prevention |
|---------|-----------|
| Circular imports (processors importing from graph/ which imports from processors/) | 使用惰性导入或字符串类型注解；Registry 在 `__init__.py` 中初始化 |
| Processor returns None for unknown type | 实现 `FallbackProcessor` 作为默认处理器，记录 warning |
| N2CNodeDefinition incompatible with existing JSON output | 提供 `to_dict()` 方法向后兼容现有 OUT-01 格式 |
| Registry not initialized before first use | 模块级 `get_instance()` 自动初始化；或在 `__init__.py` 中预加载 |
| Multiple processors claiming same type | Registry `register()` 检测重复并 raise ValueError |

## Common Pitfalls

### Pitfall 1: 字符串匹配的脆弱性
**What goes wrong:** `node.class_name == "K2Node_CallFunction"` 在 UE 更新类名后静默失败。
**Why it happens:** 字符串无类型检查，拼写错误或类名变更都不会被 IDE 捕获。
**How to avoid:** 使用 `N2CNodeType` 枚举 + Registry 解析，解析失败显式报错而非静默跳过。
**Warning signs:** 测试中出现 "Unhandled node type" 日志但无失败。

### Pitfall 2: 分派逻辑分散导致的遗漏
**What goes wrong:** 新增一种 K2Node 类型时，只更新了 `flow_builder.py` 的分派但遗漏了 `extract_cpp_skeleton.py` 的。
**Why it happens:** 分派逻辑分散在 5+ 个文件中，没有单一注册点。
**How to avoid:** Processor 注册表作为单一注册点，所有模块通过 Registry 获取处理器。
**Warning signs:** 不同模块对同一节点类型产生不一致的输出。

### Pitfall 3: Processor 间共享逻辑的重复
**What goes wrong:** `SwitchInteger`、`SwitchString`、`SwitchEnum` 处理器都复制了相同的 "提取输入引脚" 逻辑。
**Why it happens:** 每个 Processor 独立实现，没有继承或组合机制。
**How to avoid:** 使用 `BaseSwitchProcessor` 抽象基类，Switch* 子类继承并仅覆盖类型特有行为。
**Warning signs:** `grep -r "pin_name.*Index"` 在多个 Processor 文件中出现相同代码。

### Pitfall 4: 循环导入
**What goes wrong:** `processors/__init__.py` 导入所有 Processor，而 Processor 导入 `N2CNodeTypeRegistry`，Registry 又导入 `N2CNodeDefinition`，后者又导入 processors...
**Why it happens:** Python 的模块加载顺序问题。
**How to avoid:** 
- 将 `N2CNodeDefinition` 放在独立模块 `n2c/definitions.py`（不依赖 processors 或 registry）
- Registry 使用 `TYPE_CHECKING` 块 + 字符串类型注解
- Processor 注册在模块级 `__init__.py` 中批量执行

## Code Examples

### Processor Base Class

```python
# src/uasset_read/n2c/processor_base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.node_type import N2CNodeType
    from uasset_read.n2c.definitions import N2CNodeDefinition


class N2CNodeProcessor(ABC):
    """节点处理器基类。

    每个具体 Processor 子类实现 process() 方法，
    从 UEdGraphNode 提取语义信息填充 N2CNodeDefinition。
    """

    @property
    @abstractmethod
    def node_types(self) -> list["N2CNodeType"]:
        """此处理器支持的语义类型列表。"""
        ...

    @abstractmethod
    def process(self, node: "UEdGraphNode", definition: "N2CNodeDefinition") -> None:
        """提取节点特有属性到输出定义。

        Args:
            node: 已反序列化的 UEdGraphNode
            definition: 输出定义对象（由调用方创建，处理器填充 extra_data）
        """
        ...
```

### Registry with Auto-Registration

```python
# src/uasset_read/n2c/processor_registry.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.node_type import N2CNodeType
    from uasset_read.n2c.definitions import N2CNodeDefinition
    from uasset_read.n2c.processor_base import N2CNodeProcessor

logger = logging.getLogger(__name__)


class N2CProcessorRegistry:
    """处理器注册表。

    使用:
        registry = N2CProcessorRegistry.get_instance()
        registry.register(CallFunctionProcessor())
        processor = registry.get_processor(N2CNodeType.CallFunction)
    """
    _instance: Optional["N2CProcessorRegistry"] = None

    def __init__(self) -> None:
        self._processors: dict["N2CNodeType", "N2CNodeProcessor"] = {}
        self._fallback: Optional["N2CNodeProcessor"] = None

    @classmethod
    def get_instance(cls) -> "N2CProcessorRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """测试用：重置单例。"""
        cls._instance = None

    def register(self, processor: "N2CNodeProcessor") -> None:
        for node_type in processor.node_types:
            if node_type in self._processors:
                existing = self._processors[node_type].__class__.__name__
                raise ValueError(
                    f"Processor already registered for {node_type}: {existing}"
                )
            self._processors[node_type] = processor

    def set_fallback(self, processor: "N2CNodeProcessor") -> None:
        self._fallback = processor

    def get_processor(self, node_type: "N2CNodeType") -> Optional["N2CNodeProcessor"]:
        return self._processors.get(node_type, self._fallback)

    def process_node(
        self,
        node: "UEdGraphNode",
        node_type: "N2CNodeType",
        definition: "N2CNodeDefinition",
    ) -> bool:
        processor = self.get_processor(node_type)
        if processor is None:
            logger.warning(f"No processor for node type: {node_type}")
            return False
        processor.process(node, definition)
        return True
```

### CallFunctionProcessor Example

```python
# src/uasset_read/n2c/processors/call_function.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode

from uasset_read.n2c.processor_base import N2CNodeProcessor
from uasset_read.n2c.node_type import N2CNodeType
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.processor_registry import N2CProcessorRegistry


class CallFunctionProcessor(N2CNodeProcessor):
    """处理 K2Node_CallFunction 节点。

    提取：
    - function_reference (member_name, member_parent, b_self_context)
    - pure 标志（无 exec pin）
    - latent 标志（如有）
    """

    @property
    def node_types(self) -> list[N2CNodeType]:
        return [N2CNodeType.CallFunction]

    def process(self, node: "UEdGraphNode", definition: "N2CNodeDefinition") -> None:
        nd = node.node_data
        if nd:
            fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, "function_reference", None)
            if fr:
                definition.extra_data["member_name"] = getattr(fr, "member_name", None)
                definition.extra_data["member_parent"] = getattr(fr, "member_parent", None)
                definition.extra_data["b_self_context"] = getattr(fr, "b_self_context", True)

        # Pure 函数检测（无 exec pin）
        has_exec_pin = any(
            p.pin_type and p.pin_type.pin_category == "exec"
            for p in node.pins
        )
        definition.extra_data["pure"] = not has_exec_pin
```

### Usage in flow_builder.py (after migration)

```python
# Before (current):
if current_node.class_name == "K2Node_CallFunction":
    nd = current_node.node_data
    if nd:
        fr = nd.get("function_reference") if isinstance(nd, dict) else ...
        if fr:
            node_info["function_name"] = getattr(fr, "member_name", None)
    # ... pure detection, data_providers, etc.

# After (with Processor):
from uasset_read.n2c.processor_registry import N2CProcessorRegistry
from uasset_read.n2c.definitions import N2CNodeDefinition

node_type = type_registry.resolve(current_node.class_name)
definition = N2CNodeDefinition(
    node_id=current_node.node_guid,
    node_type=node_type,
    position=(current_node.node_pos_x, current_node.node_pos_y),
    comment=current_node.node_comment,
)
N2CProcessorRegistry.get_instance().process_node(current_node, node_type, definition)
# definition.extra_data now contains type-specific fields
node_info["function_name"] = definition.extra_data.get("member_name")
node_info["pure"] = definition.extra_data.get("pure", False)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `if node.class_name == "K2Node_X"` | `Registry.get_processor(N2CNodeType.X).process()` | Phase 69 | O(1) 分发，独立可测试 |
| String-based type matching | Enum-based type resolution | Phase 68 | 类型安全，IDE 支持 |
| Single 50+ line dispatch function | One file per processor | Phase 69 | 每个文件 < 50 行 |
| Manual fallback handling | FallbackProcessor pattern | Phase 69 | 统一的未知类型处理 |

**Deprecated/outdated:**
- `if/elif node.class_name == "..."` chains: Phase 69 replaces with Registry dispatch
- `isinstance(expr, EX_*)` in translator: Not deprecated, but similar pattern should be applied in a future phase

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 68 的 N2CNodeTypeRegistry 将提供 `resolve(class_name) → N2CNodeType` 接口 | Phase 68 Dependency | MEDIUM — 如果接口不同，Phase 69 需适配 |
| A2 | `N2CNodeType` 枚举值采用简短语义名（如 `CallFunction` 而非 `K2Node_CallFunction`） | Phase 68 Dependency | LOW — 仅影响 Processor 注册时的枚举引用 |
| A3 | Python 3.14.3 的 match/case 行为与 Python 3.10+ 一致 | Design Options | LOW — 已验证 Python 3.14 可用 |
| A4 | K2Node 的 `node_data` 字段格式保持不变（dict 或 dataclass） | Code Examples | LOW — 仅影响 Processor 内部读取方式 |

## Open Questions

1. **N2CNodeDefinition 的 exact field set** — 需要与 Phase 70 (N2CStruct JSON Schema) 协调，确保 extra_data 的字段名与 Schema 一致。建议 Phase 70 先定义 Schema，Phase 69 的 extra_data 键名对齐 Schema。

2. **是否立即替换所有分派点** — 建议采用渐进式迁移：先替换 `flow_builder.py` 的核心分派（~15 处），验证后再替换其他文件。cpp_gen/ 和 markdown_formatter/ 可延后，它们消费 Processor 输出而非替代分派。

3. **serializers/graph.py 是否纳入** — `dispatch_node_class()` 负责二进制反序列化分派，与 Processor 的语义提取分派是不同关注点。建议保留现有的 if/elif 链（或单独重构为反序列化工厂），不纳入 Phase 69。

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified — this is a refactoring phase using existing project code and Python standard library only).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none — see Wave 0 |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v --cov=uasset_read` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROCESSOR-01 | Registry dispatches correct Processor for each N2CNodeType | unit | `python -m pytest tests/n2c/ -x` | ❌ Wave 0 |
| PROCESSOR-02 | Each Processor produces correct N2CNodeDefinition.extra_data | unit | `python -m pytest tests/n2c/test_processors.py -x` | ❌ Wave 0 |
| PROCESSOR-03 | Backward compatibility: existing JSON output unchanged | integration | `python -m pytest tests/ -k "format" -x` | ✅ existing |

### Wave 0 Gaps
- [ ] `tests/n2c/` — new test directory for Processor tests
- [ ] `tests/n2c/test_registry.py` — Registry registration/dispatch tests
- [ ] `tests/n2c/test_call_function_processor.py` — CallFunctionProcessor specific tests
- [ ] `tests/n2c/conftest.py` — shared fixtures (mock UEdGraphNode instances)
- [ ] Framework install: `pip install -e ".[dev]"` — already configured

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Registry validates node_type before dispatch (ValueError for unregistered types) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unregistered node type causes None dispatch | Tampering | FallbackProcessor + warning logging |
| Processor raises exception during process() | Availability | try/except in Registry.process_node() with error annotation |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/uasset_read/graph/flow_builder.py` — all 15 dispatch points read and analyzed
- Codebase inspection: `src/uasset_read/serializers/graph.py` L740-780 — dispatch_node_class factory pattern
- Codebase inspection: `src/uasset_read/parsers/property_parser.py` — existing dict-based dispatcher pattern
- Codebase inspection: `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py` — node_type dispatch chain
- Codebase inspection: `src/uasset_read/models/node_types.py` — K2Node dataclass hierarchy
- `.planning/ROADMAP.md` — v12.0 Phase 69 goal and Processor pattern description
- `.planning/STATE.md` — v12.0 dependency chain (P67 → P68 → P69)

### Secondary (MEDIUM confidence)
- Python 3.10+ match/case documentation — PEP 634/635/636
- Strategy pattern (GoF) — standard reference for polymorphic dispatch
- Registry pattern — standard reference for plugin/dispatch architecture

### Tertiary (LOW confidence)
- NodeToCode C++ reference patterns (`N2CNodeProcessor.cpp`, `N2CFunctionCallProcessor.cpp`) — referenced in ROADMAP but not directly inspected (external `E:\Develop\lib\UnrealEngine\` path not available as project directory)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — patterns from existing codebase, no external dependencies
- Architecture: HIGH — derived from actual dispatch chains in codebase
- Pitfalls: HIGH — based on observed code patterns and known Python import issues
- Design options: HIGH — standard patterns evaluated against actual codebase complexity

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (30 days — stable domain, no fast-moving dependencies)
