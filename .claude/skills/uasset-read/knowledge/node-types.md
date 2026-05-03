# Node Types - K2Node节点类型详解

本文档详细解释蓝图图中各种 K2Node 节点类型，帮助 AI 正确识别和解读节点信息。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. K2Node类型概述

### 1.1 K2Node概念

**K2Node** 是 Unreal Engine 蓝图节点系统的基类前缀。所有蓝图节点都以 `K2Node_` 开头，后接具体类型名称。`K2` 代表 "Kismet 2"（UE 蓝图系统的原名）。

**节点分类体系：**

```
K2Node (基类)
├── K2Node_Event        # 事件节点（红色入口点）
├── K2Node_CallFunction # 函数调用节点
├── K2Node_VariableGet  # 读取变量
├── K2Node_VariableSet  # 设置变量
├── K2Node_IfThenElse   # 条件分支
├── K2Node_MacroInstance # 宏调用
├── K2Node_DynamicCast  # 类型转换
├── K2Node_Self         # Self引用
├── K2Node_ComponentBoundEvent # 组件事件
└── ...更多类型
```

### 1.2 节点分类

蓝图节点按功能分为三大类：

| 类别 | 特点 | 常见类型 |
|------|------|----------|
| **事件节点** | 红色标题栏，执行流程起点 | `K2Node_Event` |
| **操作节点** | 执行动作、调用函数 | `K2Node_CallFunction`、`K2Node_VariableSet` |
| **数据节点** | 读取数据、转换类型 | `K2Node_VariableGet`、`K2Node_DynamicCast` |

---

## 2. 事件节点类型

### 2.1 K2Node_Event

**K2Node_Event** 是蓝图的事件入口点，红色标题栏，表示"当某事件发生时，从这里开始执行"。

**常见事件类型：**

| 事件名称 | node_name示例 | 触发时机 |
|----------|---------------|----------|
| `ReceiveBeginPlay` | `Event BeginPlay` | 游戏开始时 |
| `ReceiveTick` | `Event Tick` | 每帧更新 |
| `ReceiveActorBeginOverlap` | `Event ActorBeginOverlap` | 碰撞开始 |
| `ReceiveActorEndOverlap` | `Event ActorEndOverlap` | 碰撞结束 |
| `ReceiveDestroyed` | `Event Destroyed` | 销毁时 |
| `ReceiveAnyDamage` | `Event AnyDamage` | 受到伤害 |
| `ReceivePointDamage` | `Event PointDamage` | 点伤害 |
| `Construction Script` | `Construction Script` | 构造脚本 |

**JSON结构：**
```json
{
  "node_name": "Event BeginPlay",
  "node_type": "K2Node_Event",
  "pins": [
    {
      "pin_name": "then",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": ["K2Node_CallFunction_123"]
    }
  ]
}
```

**解析示例：**
```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 查找事件节点
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        for node in graph.nodes:
            if node.node_type == "K2Node_Event":
                print(f"事件节点: {node.node_name}")

                # 获取事件函数名
                # node_name格式: "Event {FunctionName}"
                event_func = node.node_name.replace("Event ", "")
                print(f"  对应函数: Receive{event_func}")
```

### 2.2 K2Node_ComponentBoundEvent

**组件绑定事件**，当组件触发特定事件时执行。常见于碰撞检测、输入事件等。

**常见类型：**

| 事件名称 | 组件类型 | 说明 |
|----------|----------|------|
| `OnComponentBeginOverlap` | CollisionComponent | 碰撞开始 |
| `OnComponentEndOverlap` | CollisionComponent | 碰撞结束 |
| `OnComponentHit` | CollisionComponent | 碰撞撞击 |
| `OnInputAction` | InputComponent | 输入动作 |

**JSON结构：**
```json
{
  "node_name": "OnComponentBeginOverlap",
  "node_type": "K2Node_ComponentBoundEvent",
  "pins": [
    {
      "pin_name": "OtherActor",
      "pin_type": "object",
      "connected_to": []
    },
    {
      "pin_name": "OtherComp",
      "pin_type": "object",
      "connected_to": []
    }
  ]
}
```

---

## 3. 函数调用节点

### 3.1 K2Node_CallFunction

**K2Node_CallFunction** 是最常见的操作节点，用于调用 UObject 的成员函数或静态函数。

**节点结构：**

| 字段 | 含义 |
|------|------|
| `node_name` | 函数名称（如 "Print String"） |
| `node_type` | "K2Node_CallFunction" |
| `pins` | 输入/输出参数和执行连接 |

**常见函数调用：**

| 函数名 | node_name | 说明 |
|--------|-----------|------|
| `PrintString` | `Print String` | 打印日志 |
| `GetActorLocation` | `Get Actor Location` | 获取位置 |
| `SetActorLocation` | `Set Actor Location` | 设置位置 |
| `SpawnActor` | `Spawn Actor` | 生成Actor |
| `PlaySound2D` | `Play Sound 2D` | 播放2D音效 |
| `GetGameInstance` | `Get Game Instance` | 获取GameInstance |
| `GetWorld` | `Get World` | 获取World |

**JSON结构：**
```json
{
  "node_name": "Print String",
  "node_type": "K2Node_CallFunction",
  "pins": [
    {
      "pin_name": "execute",
      "pin_type": "exec",
      "direction": "input",
      "connected_to": ["K2Node_Event_0"]
    },
    {
      "pin_name": "then",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": ["K2Node_CallFunction_456"]
    },
    {
      "pin_name": "InString",
      "pin_type": "string",
      "direction": "input",
      "connected_to": []
    }
  ]
}
```

### 3.2 从graphs_summary获取函数调用

`graphs_summary` 提供顶层执行流程概览，包含 `function_name` 和 `params`：

```python
from uasset_read import parse_uasset, format_json_summary

result = parse_uasset("BP_FirstPersonCharacter.uasset")
output = format_json_summary(result)

# 遍历执行流程
for flow in output.get("graphs_summary", []):
    print(f"图: {flow['graph_name']}")

    for exec_flow in flow["execution_flows"]:
        func_name = exec_flow["function_name"]
        params = exec_flow["params"]

        print(f"  函数: {func_name}")
        if params:
            print(f"  参数: {[p['type'] for p in params]}")
```

### 3.3 函数名→C++映射

常见蓝图函数名对应的 C++ 函数：

| 蓝图函数名 | C++函数 | 类 |
|------------|---------|-----|
| `PrintString` | `UKismetSystemLibrary::PrintString()` | KismetSystemLibrary |
| `GetActorLocation` | `AActor::GetActorLocation()` | Actor |
| `SetActorLocation` | `AActor::SetActorLocation()` | Actor |
| `SpawnActor` | `UGameplayStatics::SpawnActor()` | GameplayStatics |
| `GetGameInstance` | `UWorld::GetGameInstance()` | World |
| `GetWorld` | `UObject::GetWorld()` | UObject |

---

## 4. 变量节点类型

### 4.1 K2Node_VariableGet

**K2Node_VariableGet** 读取变量值，紫色标题栏。

**JSON结构：**
```json
{
  "node_name": "Get Health",
  "node_type": "K2Node_VariableGet",
  "pins": [
    {
      "pin_name": "Health",
      "pin_type": "float",
      "direction": "output",
      "connected_to": ["K2Node_CallFunction_789"]
    },
    {
      "pin_name": "self",
      "pin_type": "object",
      "direction": "input",
      "connected_to": []
    }
  ]
}
```

**解析示例：**
```python
for graph in result.graphs:
    for node in graph.nodes:
        if node.node_type == "K2Node_VariableGet":
            # 提取变量名（从 node_name 或 pin_name）
            var_name = node.node_name.replace("Get ", "")
            print(f"读取变量: {var_name}")
```

### 4.2 K2Node_VariableSet

**K2Node_VariableSet** 设置变量值，紫色标题栏，有执行输入/输出。

**JSON结构：**
```json
{
  "node_name": "Set Health",
  "node_type": "K2Node_VariableSet",
  "pins": [
    {
      "pin_name": "execute",
      "pin_type": "exec",
      "direction": "input",
      "connected_to": ["K2Node_Event_0"]
    },
    {
      "pin_name": "then",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": []
    },
    {
      "pin_name": "Health",
      "pin_type": "float",
      "direction": "output",
      "connected_to": []
    },
    {
      "pin_name": "Value",
      "pin_type": "float",
      "direction": "input",
      "connected_to": ["K2Node_CallFunction_123"]
    }
  ]
}
```

### 4.3 变量名提取

变量节点名称格式：
- `Get {VariableName}` — VariableGet节点
- `Set {VariableName}` — VariableSet节点

**提取变量名代码：**
```python
def extract_variable_name(node):
    """从节点名称提取变量名"""
    if node.node_type == "K2Node_VariableGet":
        return node.node_name.replace("Get ", "")
    elif node.node_type == "K2Node_VariableSet":
        return node.node_name.replace("Set ", "")
    return None

# 使用示例
for graph in result.graphs:
    for node in graph.nodes:
        var_name = extract_variable_name(node)
        if var_name:
            print(f"变量操作: {node.node_type} → {var_name}")
```

---

## 5. 其他节点类型

### 5.1 K2Node_IfThenElse

**条件分支节点**，根据布尔值选择执行路径。

**JSON结构：**
```json
{
  "node_name": "Branch",
  "node_type": "K2Node_IfThenElse",
  "pins": [
    {
      "pin_name": "execute",
      "pin_type": "exec",
      "direction": "input",
      "connected_to": ["K2Node_Event_0"]
    },
    {
      "pin_name": "Condition",
      "pin_type": "bool",
      "direction": "input",
      "connected_to": ["K2Node_VariableGet_45"]
    },
    {
      "pin_name": "then",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": ["K2Node_CallFunction_100"]
    },
    {
      "pin_name": "else",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": ["K2Node_CallFunction_200"]
    }
  ]
}
```

**C++对应：**
```cpp
if (Condition) {
    // then 分支
} else {
    // else 分支
}
```

### 5.2 K2Node_MacroInstance

**宏调用节点**，执行预定义的蓝图宏。

**常见宏：**

| 宏名称 | 说明 |
|--------|------|
| `ForEachLoop` | 遍历数组 |
| `WhileLoop` | 循环 |
| `DoOnce` | 只执行一次 |
| `Gate` | 门控执行 |
| `Delay` | 延迟执行 |
| `FlipFlop` | 翻转输出 |
| `IsValid` | 检查对象有效性 |

**JSON结构：**
```json
{
  "node_name": "ForEachLoop",
  "node_type": "K2Node_MacroInstance",
  "pins": [
    {
      "pin_name": "Array",
      "pin_type": "array",
      "direction": "input",
      "connected_to": []
    },
    {
      "pin_name": "LoopBody",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": []
    },
    {
      "pin_name": "Completed",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": []
    }
  ]
}
```

### 5.3 K2Node_DynamicCast

**动态类型转换节点**，尝试将对象转换为特定类型。

**JSON结构：**
```json
{
  "node_name": "Cast to FirstPersonCharacter",
  "node_type": "K2Node_DynamicCast",
  "pins": [
    {
      "pin_name": "Object",
      "pin_type": "object",
      "direction": "input",
      "connected_to": []
    },
    {
      "pin_name": "CastSuccess",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": []
    },
    {
      "pin_name": "CastFailure",
      "pin_type": "exec",
      "direction": "output",
      "connected_to": []
    },
    {
      "pin_name": "AsFirstPersonCharacter",
      "pin_type": "object",
      "direction": "output",
      "connected_to": []
    }
  ]
}
```

**C++对应：**
```cpp
AFirstPersonCharacter* CastedActor = Cast<AFirstPersonCharacter>(Object);
if (CastedActor) {
    // CastSuccess 分支
} else {
    // CastFailure 分支
}
```

### 5.4 K2Node_Self

**Self引用节点**，获取当前蓝图实例。

**JSON结构：**
```json
{
  "node_name": "Self",
  "node_type": "K2Node_Self",
  "pins": [
    {
      "pin_name": "self",
      "pin_type": "object",
      "direction": "output",
      "connected_to": ["K2Node_VariableGet_10"]
    }
  ]
}
```

---

## 6. 节点类型→JSON映射表

### 6.1 完整映射表

| node_type | 分类 | 含义 | 主要pins |
|-----------|------|------|----------|
| `K2Node_Event` | 事件 | 事件入口点 | `then`(输出) |
| `K2Node_ComponentBoundEvent` | 事件 | 组件绑定事件 | `OtherActor`、`OtherComp` |
| `K2Node_CallFunction` | 操作 | 函数调用 | `execute`、`then`、参数pins |
| `K2Node_VariableGet` | 数据 | 读取变量 | `{变量名}`(输出) |
| `K2Node_VariableSet` | 操作 | 设置变量 | `execute`、`then`、`Value` |
| `K2Node_IfThenElse` | 流程 | 条件分支 | `Condition`、`then`、`else` |
| `K2Node_MacroInstance` | 流程 | 宏调用 | 宏特定pins |
| `K2Node_DynamicCast` | 数据 | 类型转换 | `Object`、`CastSuccess`、`CastFailure` |
| `K2Node_Self` | 数据 | Self引用 | `self`(输出) |
| `K2Node_CreateWidget` | 操作 | 创建Widget | `Class`、`Return Value` |
| `K2Node_AddDelegate` | 操作 | 添加委托绑定 | `Delegate`、`Event` |
| `K2Node_ClearDelegate` | 操作 | 清除委托绑定 | `Delegate` |
| `K2Node_AssignmentStatement` | 操作 | 赌值语句 | `LHS`、`RHS` |

### 6.2 Pin类型映射

| Pin类型 | JSON类型 | 说明 |
|---------|----------|------|
| `exec` | 无数据值 | 执行流连接点 |
| `bool` | boolean | 布尔值 |
| `int` | number | 整数 |
| `float` | number | 浮点数 |
| `string` | string | 字符串 |
| `object` | object reference | UObject引用 |
| `class` | class reference | UClass引用 |
| `vector` | `{X,Y,Z}` | FVector |
| `rotator` | `{Roll,Pitch,Yaw}` | FRotator |
| `array` | array | TArray |
| `delegate` | delegate | 委托 |

---

## 7. 解析示例

### 7.1 遍历所有节点并分类

```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 统计节点类型
node_counts = {}

for graph in result.graphs:
    for node in graph.nodes:
        node_type = node.node_type
        node_counts[node_type] = node_counts.get(node_type, 0) + 1

print("节点类型统计:")
for node_type, count in sorted(node_counts.items()):
    print(f"  {node_type}: {count}")
```

### 7.2 查找执行流程起点

```python
# 查找 EventGraph 中的事件节点
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        print(f"EventGraph 节点数: {len(graph.nodes)}")

        for node in graph.nodes:
            if node.node_type == "K2Node_Event":
                print(f"  事件起点: {node.node_name}")

                # 查找后续执行节点
                for pin in node.pins:
                    if pin.pin_name == "then" and pin.connected_to:
                        print(f"    → 连接到: {pin.connected_to}")
```

### 7.3 提取函数调用链

```python
def get_function_call_chain(graph):
    """提取执行流程中的函数调用链"""
    calls = []

    for node in graph.nodes:
        if node.node_type == "K2Node_CallFunction":
            calls.append({
                "name": node.node_name,
                "inputs": [p for p in node.pins if p.direction == "input"],
                "outputs": [p for p in node.pins if p.direction == "output"]
            })

    return calls

# 使用示例
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        calls = get_function_call_chain(graph)
        print(f"函数调用数: {len(calls)}")
        for call in calls:
            print(f"  {call['name']}")
```

---

## 8. C++转换参考

### 8.1 节点→C++映射表

| 节点类型 | C++结构 |
|----------|---------|
| `K2Node_Event: ReceiveBeginPlay` | `void BeginPlay() override { ... }` |
| `K2Node_Event: ReceiveTick` | `void Tick(float DeltaTime) override { ... }` |
| `K2Node_CallFunction: PrintString` | `UKismetSystemLibrary::PrintString(this, InString, true, false, TEXT("None"));` |
| `K2Node_VariableGet: Health` | `float HealthValue = Health;` |
| `K2Node_VariableSet: Health` | `Health = NewValue;` |
| `K2Node_IfThenElse` | `if (Condition) { ... } else { ... }` |
| `K2Node_DynamicCast` | `T* CastedObj = Cast<T>(Object); if (CastedObj) { ... }` |

### 8.2 完整转换示例

**蓝图EventGraph:**
```
Event BeginPlay → Get Player Controller → Print String
```

**对应C++:**
```cpp
void AMyCharacter::BeginPlay() override {
    Super::BeginPlay();

    APlayerController* PC = GetPlayerController();
    if (PC) {
        UKismetSystemLibrary::PrintString(this, FString("Hello"), true, false, FName("None"));
    }
}
```

---

## 9. 参考链接

- **蓝图语义:** [blueprint-semantics.md](blueprint-semantics.md)
- **Pin类型映射:** [pin-type-mapping.md](pin-type-mapping.md)
- **蓝图→C++转换:** [cpp-conversion.md](cpp-conversion.md)
- **常见模式:** [common-patterns.md](common-patterns.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*