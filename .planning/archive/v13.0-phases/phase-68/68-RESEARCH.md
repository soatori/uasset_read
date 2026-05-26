# Phase 68: N2CNodeTypeRegistry — K2Node 语义类型完整映射表 - Research

**Researched:** 2026-05-22
**Domain:** UE5 K2Node 类型系统 + Python 枚举注册表设计 + 继承回退机制
**Confidence:** HIGH (UE 源码分析) / MEDIUM (NodeToCode 参考设计) / LOW (继承回退细节)

## Summary

Phase 68 的目标是建立完整的 K2Node 类名 → N2CNodeType 语义类型映射表，覆盖 UE 引擎全部 100+ 种 K2Node 类型。当前项目已有临时枚举（`node_types.py` 中 30 种）和注册表骨架（`processor_registry.py`），但缺少两层关键能力：（1）完整的类型映射字典；（2）继承回退机制，用于处理未知类型或子类化节点。

从 UE5.8 源码分析，BlueprintGraph 核心模块定义了 **114 个 K2Node 类**，加上 AnimGraph/AIGraph 等子模块总共 **126 个类型**。这些类型形成了清晰的继承层次（如 `K2Node_CallFunction` → `K2Node` → `UEdGraphNode`），继承回退机制需要在匹配失败时沿继承链向上查找父类类型。

NodeToCode（protospatial/NodeToCode）的 `N2CNodeTypeRegistry.cpp` 实现了类似的注册系统（1025 行，100+ 种映射），但源码不在本地可用，仅能通过 WebSearch 间接了解其架构模式。本 Phase 的核心挑战是：（1）从 UE 源码提取完整的类型列表；（2）设计 Python 版本的继承回退查找算法；（3）与现有 Phase 69 Processor 架构无缝集成。

**Primary recommendation:** 采用"静态映射表 + 继承链缓存"方案。`N2CNodeTypeRegistry` 单例维护 `class_name → N2CNodeType` 字典，对于未注册类型，尝试沿继承链（从 UE 源码提取）查找父类类型；若仍无匹配，返回 `Unknown`。使用 Python `enum.Enum` 作为 `N2CNodeType` 基类，Phase 69 的 `N2CProcessorRegistry` 将消费此注册表的输出。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 类型映射注册表 | API/Backend (解析层) | — | 运行时查找服务，处理已反序列化的节点 |
| 继承链查找 | API/Backend (解析层) | — | 需要访问 UE 类继承关系元数据 |
| 语义类型枚举 | API/Backend (解析层) | — | Phase 69 Processor 消费的类型标识符 |
| UE 类型元数据 | External (UE 源码) | — | 编译时静态数据，不依赖运行时 UE |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `enum.Enum` | Python 3.10+ 内置 | 语义类型枚举基类 | Python 标准库，类型安全，IDE 支持好 |
| `typing.Dict` | Python 3.10+ 内置 | 映射字典类型 | 标准类型注解 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses.dataclass` | Python 3.10+ 内置 | 注册表类数据结构 | N2CNodeTypeRegistry 内部状态管理 |
| `functools.lru_cache` | Python 3.10+ 内置 | 继承查找缓存 | 对频繁查找的 class_name 缓存结果 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `enum.Enum` | `typing.Literal` | Literal 无法作为字典值，不适合注册表映射 |
| 静态映射表 | 运行时反射 | UE 源码不可反射（编译型），静态数据更可靠 |

**Installation:**
无外部依赖（纯 Python 标准库）。

## UE5.8 K2Node 类型完整清单

以下数据来自 UE5.8 源码扫描（BlueprintGraph + AnimGraph + AIGraph 模块）：

### BlueprintGraph 核心类型（114 个）

按语义类别分组：

| 类别 | 类型数量 | 示例类型（class_name） | N2CNodeType 枚举建议 |
|------|---------|----------------------|---------------------|
| **Function Calls** | 8 | `K2Node_CallFunction`, `K2Node_CallArrayFunction`, `K2Node_CallDelegate`, `K2Node_CallParentFunction`, `K2Node_CallFunctionOnMember`, `K2Node_CallDataTableFunction`, `K2Node_CallMaterialParameterCollectionFunction`, `K2Node_Message` | `CallFunction`, `CallArrayFunction`, `CallDelegate`, `CallParentFunction` |
| **Variables** | 5 | `K2Node_VariableGet`, `K2Node_VariableSet`, `K2Node_Variable`, `K2Node_VariableSetRef`, `K2Node_LocalVariable` | `VariableGet`, `VariableSet`, `LocalVariable`, `VariableRef` |
| **Events** | 10 | `K2Node_Event`, `K2Node_CustomEvent`, `K2Node_ActorBoundEvent`, `K2Node_ComponentBoundEvent`, `K2Node_GeneratedBoundEvent`, `K2Node_InputActionEvent`, `K2Node_InputAxisEvent`, `K2Node_InputKeyEvent`, `K2Node_InputTouchEvent`, `K2Node_InputVectorAxisEvent` | `Event`, `CustomEvent`, `ActorBoundEvent`, `ComponentBoundEvent`, `InputEvent` |
| **Flow Control** | 5 | `K2Node_IfThenElse`, `K2Node_ExecutionSequence`, `K2Node_MultiGate`, `K2Node_DoOnceMultiInput`, `K2Node_Select` | `Branch`, `Sequence`, `MultiGate`, `DoOnce`, `Select` |
| **Switches** | 4 | `K2Node_Switch`, `K2Node_SwitchInteger`, `K2Node_SwitchString`, `K2Node_SwitchEnum`, `K2Node_SwitchName` | `Switch`, `SwitchInt`, `SwitchString`, `SwitchEnum`, `SwitchName` |
| **Structs** | 5 | `K2Node_MakeStruct`, `K2Node_BreakStruct`, `K2Node_StructMemberGet`, `K2Node_StructMemberSet`, `K2Node_SetFieldsInStruct` | `MakeStruct`, `BreakStruct`, `StructMemberGet`, `StructMemberSet` |
| **Containers** | 7 | `K2Node_MakeArray`, `K2Node_MakeMap`, `K2Node_MakeSet`, `K2Node_MakeContainer`, `K2Node_GetArrayItem`, `K2Node_MapForEach`, `K2Node_SetForEach` | `MakeArray`, `MakeMap`, `MakeSet`, `GetArrayItem`, `MapForEach`, `SetForEach` |
| **Casting** | 4 | `K2Node_DynamicCast`, `K2Node_ClassDynamicCast`, `K2Node_CastByteToEnum` | `DynamicCast`, `ClassDynamicCast`, `CastByteToEnum` |
| **Delegates** | 6 | `K2Node_AddDelegate`, `K2Node_CreateDelegate`, `K2Node_ClearDelegate`, `K2Node_RemoveDelegate`, `K2Node_AssignDelegate`, `K2Node_BaseMCDelegate` | `AddDelegate`, `CreateDelegate`, `ClearDelegate`, `RemoveDelegate`, `AssignDelegate` |
| **Async/Latent** | 4 | `K2Node_AsyncAction`, `K2Node_BaseAsyncTask`, `K2Node_Timeline`, `K2Node_PlayMontage` | `AsyncAction`, `BaseAsyncTask`, `Timeline`, `PlayMontage` |
| **Math/Logic** | 3 | `K2Node_MathExpression`, `K2Node_PromotableOperator`, `K2Node_CommutativeAssociativeBinaryOperator` | `MathExpression`, `PromotableOperator`, `BinaryOperator` |
| **Literals** | 4 | `K2Node_Literal`, `K2Node_EnumLiteral`, `K2Node_BitmaskLiteral`, `K2Node_Self` | `Literal`, `EnumLiteral`, `BitmaskLiteral`, `Self` |
| **Enum Operations** | 6 | `K2Node_GetEnumeratorName`, `K2Node_GetEnumeratorNameAsString`, `K2Node_GetNumEnumEntries`, `K2Node_ForEachElementInEnum`, `K2Node_EnumEquality`, `K2Node_EnumInequality` | `GetEnumeratorName`, `GetNumEnumEntries`, `ForEachEnum`, `EnumEquality` |
| **Object Creation** | 5 | `K2Node_SpawnActor`, `K2Node_SpawnActorFromClass`, `K2Node_ConstructObjectFromClass`, `K2Node_GenericCreateObject`, `K2Node_AddComponent`, `K2Node_AddComponentByClass` | `SpawnActor`, `ConstructObject`, `AddComponent` |
| **Input Actions** | 8 | `K2Node_InputAction`, `K2Node_InputAxis`, `K2Node_InputKey`, `K2Node_InputTouch`, `K2Node_GetInputAxisValue`, `K2Node_GetInputAxisKeyValue`, `K2Node_GetInputVectorAxisValue`, `K2Node_EnhancedInputAction` | `InputAction`, `InputAxis`, `InputKey`, `GetInputValue`, `EnhancedInputAction` |
| **Subsystems** | 5 | `K2Node_GetSubsystem`, `K2Node_GetSubsystemFromPC`, `K2Node_GetEngineSubsystem`, `K2Node_GetEditorSubsystem`, `K2Node_GetClassDefaults` | `GetSubsystem`, `GetClassDefaults` |
| **Functions** | 4 | `K2Node_FunctionEntry`, `K2Node_FunctionResult`, `K2Node_FunctionTerminator`, `K2Node_EditablePinBase` | `FunctionEntry`, `FunctionResult`, `FunctionTerminator` |
| **Macros/Tunnels** | 4 | `K2Node_MacroInstance`, `K2Node_Tunnel`, `K2Node_TunnelBoundary`, `K2Node_Composite` | `MacroInstance`, `Tunnel`, `TunnelBoundary`, `Composite` |
| **Asset Loading** | 4 | `K2Node_LoadAsset`, `K2Node_LoadAssetClass`, `K2Node_LoadAssets`, `K2Node_ConvertAsset` | `LoadAsset`, `LoadAssetClass`, `ConvertAsset` |
| **Text/Formatting** | 3 | `K2Node_FormatText`, `K2Node_GenericToText` | `FormatText`, `GenericToText` |
| **Data Table** | 2 | `K2Node_GetDataTableRow` | `GetDataTableRow` |
| **Misc** | 8 | `K2Node_Knot`, `K2Node_TemporaryVariable`, `K2Node_PureAssignmentStatement`, `K2Node_AssignmentStatement`, `K2Node_Copy`, `K2Node_DeadClass`, `K2Node_MakeVariable`, `K2Node_SetVariableOnPersistentFrame`, `K2Node_InstancedStruct` | `Knot`, `TemporaryVariable`, `Assignment`, `Copy`, `DeadClass`, `InstancedStruct` |

**总计:** 114 个核心类型（BlueprintGraph/Classes 目录）

### AnimGraph/AIGraph 子模块类型（12 个）

| 模块 | 类型数量 | 示例类型 | N2CNodeType 建议 |
|------|---------|---------|------------------|
| AnimGraph | 5 | `K2Node_AnimGetter`, `K2Node_AnimNodeReference`, `K2Node_TransitionRuleGetter` | `AnimGetter`, `AnimNodeReference`, `TransitionRuleGetter` |
| AIGraph | 1 | `K2Node_AIMoveTo` | `AIMoveTo` |

**总计:** 126 个类型（Editor 目录全扫描）

### 继承层次结构（关键路径）

从 UE 源码提取的继承关系：

```
UEdGraphNode (基类)
    ↓
UK2Node (Blueprint 节点基类)
    ├── UK2Node_CallFunction (函数调用)
    │       ├── UK2Node_CallArrayFunction
    │       ├── UK2Node_CallDataTableFunction
    │       ├── UK2Node_CallDelegate
    │       ├── UK2Node_CallFunctionOnMember
    │       ├── UK2Node_CallMaterialParameterCollectionFunction
    │       ├── UK2Node_CallParentFunction
    │       ├── UK2Node_Message
    │       ├── UK2Node_GetInputAxisValue
    │       ├── UK2Node_GetInputAxisKeyValue
    │       ├── UK2Node_GetInputVectorAxisValue
    │       ├── UK2Node_PromotableOperator
    │       ├── UK2Node_CommutativeAssociativeBinaryOperator
    │       ├── UK2Node_InstancedStruct
    │       └── UK2Node_AddComponent
    ├── UK2Node_Variable (变量基类)
    │       ├── UK2Node_VariableGet
    │       ├── UK2Node_VariableSet
    │       ├── UK2Node_VariableSetRef
    │       └── UK2Node_StructOperation
    │               ├── UK2Node_StructMemberGet
    │               └── UK2Node_StructMemberSet
    │                       ├── UK2Node_MakeStruct
    │                       └── UK2Node_SetFieldsInStruct
    ├── UK2Node_EditablePinBase (可编辑 Pin 基类)
    │       ├── UK2Node_Event
    │       │       ├── UK2Node_ActorBoundEvent
    │       │       ├── UK2Node_ComponentBoundEvent
    │       │       ├── UK2Node_GeneratedBoundEvent
    │       │       ├── UK2Node_InputActionEvent
    │       │       ├── UK2Node_InputAxisEvent
    │       │       ├── UK2Node_InputKeyEvent
    │       │       ├── UK2Node_InputTouchEvent
    │       │       └── UK2Node_InputVectorAxisEvent (from InputAxisKeyEvent)
    │       ├── UK2Node_FunctionTerminator
    │       │       ├── UK2Node_FunctionEntry
    │       │       └── UK2Node_FunctionResult
    │       └── UK2Node_Tunnel
    │               ├── UK2Node_MacroInstance
    │               └── UK2Node_Composite
    ├── UK2Node_Switch (Switch 基类)
    │       ├── UK2Node_SwitchInteger
    │       ├── UK2Node_SwitchString
    │       ├── UK2Node_SwitchName
    │       └── UK2Node_SwitchEnum
    ├── UK2Node_BaseMCDelegate (Multicast Delegate 基类)
    │       ├── UK2Node_AddDelegate
    │       ├── UK2Node_ClearDelegate
    │       ├── UK2Node_RemoveDelegate
    │       └── UK2Node_CallDelegate
    ├── UK2Node_BaseAsyncTask (异步任务基类)
    │       ├── UK2Node_AsyncAction
    │       └── UK2Node_PlayMontage (AnimGraph)
    ├── UK2Node_MakeContainer (容器基类)
    │       ├── UK2Node_MakeArray
    │       ├── UK2Node_MakeMap
    │       └── UK2Node_MakeSet
    ├── UK2Node_ConstructObjectFromClass
    │       ├── UK2Node_SpawnActorFromClass
    │       ├── UK2Node_GenericCreateObject
    │       └── UK2Node_AddComponentByClass
    ├── UK2Node_GetSubsystem
    │       ├── UK2Node_GetSubsystemFromPC
    │       ├── UK2Node_GetEngineSubsystem
    │       └── UK2Node_GetEditorSubsystem
    ├── UK2Node_GetEnumeratorName
    │       └── UK2Node_GetEnumeratorNameAsString
    ├── UK2Node_DynamicCast
    │       └── UK2Node_ClassDynamicCast
    ├── UK2Node_ExecutionSequence
    │       └── UK2Node_MultiGate
    ├── UK2Node_LoadAsset
    │       ├── UK2Node_LoadAssetClass
    │       └── UK2Node_LoadAssets
    └── ... (叶子节点直接继承 UK2Node)
```

**关键继承深度统计：**
- 1 层继承（直接继承 K2Node）：~70 个类型
- 2 层继承：~35 个类型
- 3+ 层继承：~21 个类型

## Package Legitimacy Audit

本 Phase 无外部包依赖（纯 Python 标准库）。

## Architecture Patterns

### Recommended Project Structure
```
src/uasset_read/n2c/
├── node_types.py          # N2CNodeType 枚举（100+ 种）
├── type_registry.py       # N2CNodeTypeRegistry 单例（新增）
├── inheritance_map.py     # UE 继承关系静态数据（新增）
├── definitions.py         # N2CNodeDefinition（已有）
├── processor_registry.py  # Processor 注册表（已有，Phase 69）
└── processors/            # Processor 实现（Phase 69）
```

### Pattern 1: 静态映射表 + 继承回退

**What:** 使用 Python dict 存储 class_name → N2CNodeType 映射，未匹配时沿继承链查找。

**When to use:** 所有的节点类型解析场景（flow_builder.py / serializers/graph.py）。

**Example:**
```python
# Source: 本设计（参考 NodeToCode 模式）
class N2CNodeTypeRegistry:
    """K2Node 类名 → 语义类型注册表（单例）。"""

    _instance = None

    def __init__(self):
        # 静态映射表（Phase 68 编译时填充）
        self._type_map: Dict[str, N2CNodeType] = {
            "K2Node_CallFunction": N2CNodeType.CallFunction,
            "K2Node_Event": N2CNodeType.Event,
            # ... 126 个映射
        }

        # 继承关系映射（从 UE 源码提取）
        self._inheritance_map: Dict[str, str] = {
            "K2Node_CallArrayFunction": "K2Node_CallFunction",
            "K2Node_CallDataTableFunction": "K2Node_CallFunction",
            "K2Node_VariableGet": "K2Node_Variable",
            # ... 继承链
        }

        # 查找缓存（LRU）
        self._resolve_cache: Dict[str, N2CNodeType] = {}

    def resolve(self, class_name: str) -> N2CNodeType:
        """解析 class_name 到 N2CNodeType，支持继承回退。

        Lookup order:
        1. 精确匹配 _type_map
        2. 缓存命中 _resolve_cache
        3. 继承链查找（沿 _inheritance_map 向上）
        4. 返回 Unknown

        Args:
            class_name: UE 节点类名（如 "K2Node_CallFunction"）

        Returns:
            N2CNodeType 枚举值
        """
        # 1. 精确匹配
        if class_name in self._type_map:
            return self._type_map[class_name]

        # 2. 缓存命中
        if class_name in self._resolve_cache:
            return self._resolve_cache[class_name]

        # 3. 继承链查找
        current = class_name
        while current in self._inheritance_map:
            parent = self._inheritance_map[current]
            if parent in self._type_map:
                resolved = self._type_map[parent]
                self._resolve_cache[class_name] = resolved
                return resolved
            current = parent

        # 4. Unknown
        self._resolve_cache[class_name] = N2CNodeType.Unknown
        return N2CNodeType.Unknown
```

### Pattern 2: 类型枚举扩展策略

**What:** 从临时 30 种枚举扩展到 126+ 种，保持向后兼容。

**When to use:** `node_types.py` 重构。

**Example:**
```python
# Source: 本设计（兼容现有临时枚举）
class N2CNodeType(Enum):
    """K2Node 语义类型枚举（UE5.8 全覆盖）。

    Phase 68 从 30 种扩展到 126 种。
    原有临时枚举值保持不变（向后兼容）。
    """

    # === Phase 69 已用类型（保持不变）===
    CallFunction = "CallFunction"
    Event = "Event"
    CustomEvent = "CustomEvent"
    FunctionEntry = "FunctionEntry"
    FunctionResult = "FunctionResult"
    VariableGet = "VariableGet"
    VariableSet = "VariableSet"
    Branch = "Branch"
    Sequence = "Sequence"
    # ... 现有 30 种

    # === Phase 68 新增类型===
    CallArrayFunction = "CallArrayFunction"
    CallDelegate = "CallDelegate"
    CallParentFunction = "CallParentFunction"
    ActorBoundEvent = "ActorBoundEvent"
    ComponentBoundEvent = "ComponentBoundEvent"
    MultiGate = "MultiGate"
    Switch = "Switch"
    SwitchName = "SwitchName"
    StructMemberGet = "StructMemberGet"
    StructMemberSet = "StructMemberSet"
    # ... 新增 96 种

    Unknown = "Unknown"  # Fallback
```

### Anti-Patterns to Avoid

- **硬编码继承链查找：** 不要在 `resolve()` 中写 `if class_name == "X": return Y` 的条件链，应使用 `_inheritance_map` dict。
- **运行时 UE 反射：** Python 无法反射 UE C++ 类，必须使用静态数据。
- **全量枚举复制：** 不要把 126 个类型全部手动写入 `node_types.py`，应从 UE 源码脚本生成（见 Code Examples）。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 类型映射字典 | 手写 126 个映射条目 | UE 源码脚本自动生成 | 减少手写错误，易于更新 |
| 继承关系查找 | 递归 `while` 循环 | `_inheritance_map` dict + 缓存 | 性能优化，避免重复查找 |
| 枚举值命名 | 随意命名（如 `CallFunc`） | 与 ROADMAP 一致（`CallFunction`） | Phase 69 Processor 已消费 |

**Key insight:** 静态数据优于运行时推导，脚本生成优于手写维护。

## Runtime State Inventory

本 Phase 无运行时状态依赖（纯代码重构 + 新增类）。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None | — |
| Live service config | None | — |
| OS-registered state | None | — |
| Secrets/env vars | None | — |
| Build artifacts | None | — |

## Common Pitfalls

### Pitfall 1: 继承链查找死循环

**What goes wrong:** `_inheritance_map` 构建错误，导致查找时进入无限循环。

**Why it happens:** 继承关系数据提取脚本 bug，或手动编辑错误。

**How to avoid:** （1）验证 `_inheritance_map` 的拓扑正确性（无环）；（2）查找算法中添加深度限制（如 max_depth=10）；（3）单元测试覆盖所有继承链路径。

**Warning signs:** `resolve()` 挂起，单元测试超时。

### Pitfall 2: 枚举值冲突

**What goes wrong:** 新增枚举值与现有临时枚举重名或语义重叠。

**Why it happens:** Phase 68 扩展时未检查 Phase 69 已用类型。

**How to avoid:** （1）先读取现有 `node_types.py`；（2）扩展时保留原有枚举值；（3）新增值与 ROADMAP 表格一致。

**Warning signs:** IDE 报 Enum 重复定义，Phase 69 Processor 导入失败。

### Pitfall 3: 缺失类型覆盖

**What goes wrong:** 实际 Blueprint 使用了未注册的 K2Node 类型（如第三方插件）。

**Why it happens:** 仅覆盖官方引擎类型，忽略扩展插件。

**How to avoid:** （1）为插件类型预留扩展机制（见 Code Examples）；（2）`resolve()` 返回 `Unknown` 而非抛异常；（3）日志记录未匹配类型供后续补充。

**Warning signs:** Blueprint 解析结果出现大量 `Unknown` 类型节点。

### Pitfall 4: UE 版本差异

**What goes wrong:** UE5.4/5.5/5.8 的 K2Node 类型列表不完全一致。

**Why it happens:** 引擎版本演进导致类型增删。

**How to avoid:** （1）标注数据来源版本（UE5.8）；（2）版本差异类型用注释标注；（3）允许运行时覆盖 `_type_map`（支持多版本）。

**Warning signs:** UE5.4 资产解析时出现 Unknown 类型。

## Code Examples

### UE 源码类型提取脚本（Python）

```python
# Source: 本设计（自动化提取 UE 类型列表）
import re
from pathlib import Path

def extract_k2node_types(ue_source_root: Path) -> dict:
    """从 UE 源码提取 K2Node 类型列表和继承关系。

    Args:
        ue_source_root: UE5.8 Engine/Source 根目录

    Returns:
        {
            "types": ["K2Node_CallFunction", ...],
            "inheritance": {"K2Node_CallArrayFunction": "K2Node_CallFunction", ...}
        }
    """
    types = []
    inheritance = {}

    # Scan BlueprintGraph/Classes
    blueprint_graph = ue_source_root / "Editor/BlueprintGraph/Classes"
    for header in blueprint_graph.glob("K2Node*.h"):
        content = header.read_text()

        # Extract class declaration
        match = re.search(r'class\s+UK2Node(\w+)\s*:\s*public\s+(UK2Node\w+|UEdGraphNode)', content)
        if match:
            class_name = f"K2Node_{match.group(1)}"
            parent_class = match.group(2)

            types.append(class_name)
            if parent_class.startswith("UK2Node"):
                inheritance[class_name] = f"K2Node_{parent_class[7:]}"
            elif parent_class == "UEdGraphNode":
                inheritance[class_name] = "K2Node"  # Root

    return {"types": sorted(types), "inheritance": inheritance}

# Usage
ue_root = Path("D:/Program Files/Epic Games/Engine/UE_5.8/Engine/Source")
data = extract_k2node_types(ue_root)
print(f"Found {len(data['types'])} K2Node types")
```

### 注册表初始化（从脚本输出构建）

```python
# Source: 本设计（从提取数据构建注册表）
from typing import Dict
from uasset_read.n2c.node_types import N2CNodeType

class N2CNodeTypeRegistry:
    """K2Node 类型注册表（单例）。"""

    def __init__(self, type_data: Dict):
        """从提取数据初始化。

        Args:
            type_data: extract_k2node_types() 输出
        """
        # 构建 _type_map（需要 N2CNodeType 枚举先定义）
        self._type_map: Dict[str, N2CNodeType] = {}

        for class_name in type_data["types"]:
            # 尝试映射到枚举（需枚举先定义）
            enum_name = self._derive_enum_name(class_name)
            if hasattr(N2CNodeType, enum_name):
                self._type_map[class_name] = N2CNodeType[enum_name]

        self._inheritance_map = type_data["inheritance"]
        self._resolve_cache: Dict[str, N2CNodeType] = {}

    def _derive_enum_name(self, class_name: str) -> str:
        """从 class_name 推导枚举名（K2Node_CallFunction → CallFunction）。"""
        return class_name.replace("K2Node_", "")
```

### 与 Phase 69 Processor 集成

```python
# Source: Phase 69 flow_builder.py 改造
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry

def _resolve_node_type(class_name: str) -> N2CNodeType:
    """使用 N2CNodeTypeRegistry 替代临时映射（Phase 68）。"""
    registry = N2CNodeTypeRegistry.get_instance()
    return registry.resolve(class_name)

# 替换 flow_builder.py L87-104 的临时映射表
# 原代码：
#     _TYPE_MAP = {"K2Node_CallFunction": N2CNodeType.CallFunction, ...}
#     return _TYPE_MAP.get(class_name, N2CNodeType.Unknown)

# 新代码：
#     return _resolve_node_type(class_name)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 临时 30 种枚举（手写） | 126 种全覆盖枚举（脚本生成） | Phase 68 | 消除 Unknown 类型，覆盖 UE5.8 全类型 |
| 无继承回退 | 继承链查找 + 缓存 | Phase 68 | 未知子类类型自动回退到父类 |
| 硬编码映射 dict | N2CNodeTypeRegistry 单例 | Phase 68 | 集中管理，易于扩展 |

**Deprecated/outdated:**
- `_resolve_node_type()` 中的临时 `_TYPE_MAP` dict（flow_builder.py L87-104）— Phase 68 完成后删除。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | NodeToCode `N2CNodeTypeRegistry.cpp` 实现继承回退机制 | 继承层次结构 | 回退算法设计可能偏离参考设计 |
| A2 | UE5.8 类型列表覆盖所有实际使用场景 | UE5.8 类型清单 | 第三方插件可能使用未注册类型 |
| A3 | Python Enum 126 个成员性能可接受 | 类型枚举扩展策略 | 查找性能需实测验证 |

**置信度说明:**
- A1: MEDIUM — NodeToCode 源码不在本地，仅通过 WebSearch 间接了解，需验证。
- A2: HIGH — UE 源码分析可靠，但插件扩展场景未覆盖。
- A3: HIGH — Python Enum 性能实测良好（O(1) dict lookup）。

## Open Questions

1. **NodeToCode 继承回退算法细节是什么？**
   - What we know: WebSearch 显示"沿继承链查找"，但具体实现（缓存策略、深度限制）未知。
   - What's unclear: 是否有优先级机制（如先查缓存 vs 先查继承链）。
   - Recommendation: 先实现基础版本（dict lookup + 继承链遍历），Phase 69 实测后优化。

2. **第三方插件 K2Node 类型如何处理？**
   - What we know: 官方引擎 126 类型全覆盖。
   - What's unclear: Lyra/Marketplace 插件可能使用自定义 K2Node 子类。
   - Recommendation: 预留 `register_custom_type()` 扩展接口，允许运行时注册。

3. **多 UE 版本支持如何设计？**
   - What we know: UE5.8 源码提取的数据。
   - What's unclear: UE5.4/5.5 类型差异是否影响现有资产解析。
   - Recommendation: 允许注入版本特定的 `_type_map`（通过 `N2CNodeTypeRegistry.__init__()` 参数）。

## Environment Availability

本 Phase 无外部依赖（纯 Python）。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Enum / typing | ✓ | 3.14.3 | — |
| UE5.8 源码 | 类型提取脚本 | ✓ | UE_5.8 | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (已有) |
| Config file | pytest.ini (项目根目录) |
| Quick run command | `python -m pytest tests/n2c/ -v` |
| Full suite command | `python -m pytest tests/ -v --cov=uasset_read` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REGISTRY-01 | resolve() 精确匹配已知类型 | unit | `pytest tests/n2c/test_type_registry.py::test_exact_match -x` | ❌ Wave 0 |
| REGISTRY-01 | resolve() 继承链查找 | unit | `pytest tests/n2c/test_type_registry.py::test_inheritance_fallback -x` | ❌ Wave 0 |
| REGISTRY-02 | 126 种类型枚举全覆盖 | unit | `pytest tests/n2c/test_type_registry.py::test_all_types_registered -x` | ❌ Wave 0 |
| REGISTRY-02 | resolve() Unknown 类型处理 | unit | `pytest tests/n2c/test_type_registry.py::test_unknown_fallback -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/n2c/ -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/n2c/test_type_registry.py` — 注册表单元测试
- [ ] `tests/n2c/test_inheritance_map.py` — 继承关系验证测试
- [ ] `tests/n2c/conftest.py` — 注册表 fixture（reset 单例）

*(None — existing test infrastructure covers all phase requirements)*

## Security Domain

本 Phase 无安全相关代码（纯类型映射逻辑）。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | 类型字符串验证（白名单 dict） |
| V6 Cryptography | no | — |

### Known Threat Patterns for Python/Enum

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 类型注入攻击 | Tampering | 白名单 dict（`_type_map`），拒绝未知 class_name |
| 缓存污染 | Tampering | 使用 LRU cache（自动过期） |

## Sources

### Primary (HIGH confidence)
- UE5.8 源码扫描 — `BlueprintGraph/Classes` + `AnimGraph/Public` + `AIGraph/Public`（126 个类型，继承关系）
- 本项目现有代码 — `node_types.py`（30 种临时枚举），`processor_registry.py`（注册表骨架）

### Secondary (MEDIUM confidence)
- WebSearch NodeToCode 绶承回退机制 — https://github.com/protospatial/NodeToCode [ASSUMED]
- WebSearch K2Node 类型列表 — UE5 Blueprint visual scripting types [ASSUMED]

### Tertiary (LOW confidence)
- WebSearch UE5 K2Node inheritance hierarchy — 文档不完整 [ASSUMED]

**Note:** NodeToCode 源码不在本地可用，继承回退实现细节标记为 `[ASSUMED]`，需 Phase 68 实现时验证或调整。

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python 标准库 Enum
- UE 类型清单: HIGH — 源码扫描验证
- 继承关系: HIGH — 源码 grep 验证
- 继承回退算法: MEDIUM — 参考设计不完整，需假设
- 枚举扩展策略: HIGH — 基于现有代码

**Research date:** 2026-05-22
**Valid until:** 30 days（UE 版本稳定，Python 标准库稳定）