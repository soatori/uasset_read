# Pin Type Mapping - Pin类型映射

本文档详细解释蓝图 Pin（连接点）类型与 JSON 数据类型的映射关系，帮助 AI 正确解读数据流。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. Pin概念

### 1.1 Pin定义

**Pin（引脚/连接点）** 是蓝图节点上的数据接口点。每个节点有多个 Pin，用于：
- **执行流传递** — 白色 exec Pin 控制执行顺序
- **数据流传递** — 其他颜色 Pin 传递数据值

**Pin属性：**

| 属性 | JSON字段 | 说明 |
|------|----------|------|
| `pin_name` | Pin名称 | 如 "Health"、"InString" |
| `pin_type` | Pin数据类型 | 如 "float"、"string"、"exec" |
| `direction` | 方向 | "input" 或 "output" |
| `connected_to` | 连接目标 | 连接的节点/Pin列表 |

### 1.2 输入Pin vs 输出Pin

**输入Pin（Input）：**
- 位于节点左侧
- 接收数据或执行流
- 常见名称：`execute`、`self`、`Value`

**输出Pin（Output）：**
- 位于节点右侧
- 发送数据或执行流
- 常见名称：`then`、`Health`、`Return Value`

**JSON结构示例：**
```json
{
  "pin_name": "InString",
  "pin_type": "string",
  "direction": "input",
  "connected_to": []
},
{
  "pin_name": "then",
  "pin_type": "exec",
  "direction": "output",
  "connected_to": ["K2Node_CallFunction_456"]
}
```

---

## 2. Pin类型分类

### 2.1 基础类型

| Pin类型 | JSON类型 | 默认值示例 | 说明 |
|---------|----------|------------|------|
| `bool` | boolean | `true`, `false` | 布尔值 |
| `int` | number | `42`, `-1` | 整数 |
| `float` | number | `100.0`, `3.14` | 浮点数 |
| `string` | string | `"Hello"` | 字符串 |
| `name` | string | `"MyName"` | FName（名称） |
| `text` | string | `"Localized Text"` | FText（本地化文本） |

### 2.2 复合类型

| Pin类型 | JSON类型 | 结构示例 | 说明 |
|---------|----------|----------|------|
| `vector` | object | `{"X": 0, "Y": 0, "Z": 0}` | FVector（三维向量） |
| `rotator` | object | `{"Roll": 0, "Pitch": 0, "Yaw": 0}` | FRotator（旋转） |
| `transform` | object | `{"Location": {...}, "Rotation": {...}, "Scale": {...}}` | FTransform（变换） |
| `color` | object | `{"R": 255, "G": 128, "B": 0, "A": 255}` | FLinearColor（颜色） |

### 2.3 对象类型

| Pin类型 | JSON类型 | 值示例 | 说明 |
|---------|----------|--------|------|
| `object` | string | `"FirstPersonCharacter_C"` | UObject引用 |
| `class` | string | `"BlueprintGeneratedClass"` | UClass引用 |
| `softobject` | string | `"/Game/Assets/MyMesh.MyMesh"` | 软对象引用（TSoftObjectPtr） |
| `softclass` | string | `"/Game/BPs/MyBP.MyBP_C"` | 软类引用（TSoftClassPtr） |

### 2.4 特殊类型

| Pin类型 | JSON类型 | 说明 |
|---------|----------|------|
| `exec` | 无数据值 | 执行流连接点（仅控制流） |
| `delegate` | object | 委托/多播委托 |
| `enum` | string | 枚举值（如 "MoveState::Walking"） |
| `array` | array | 数组（TArray<T>） |
| `map` | object | 映射（TMap<K,V>） |
| `set` | array | 集合（TSet<T>） |

---

## 3. Pin类型→JSON类型映射表

### 3.1 完整映射

| Pin类型字符串 | Python/JSON类型 | JSON值示例 |
|---------------|-----------------|------------|
| `exec` | 无（控制流） | 不在数据pins中出现 |
| `bool` | `bool` | `true` |
| `int` / `IntProperty` | `int` | `42` |
| `float` / `FloatProperty` | `float` | `100.0` |
| `string` / `StrProperty` | `str` | `"Hello World"` |
| `name` / `NameProperty` | `str` | `"MyVariable"` |
| `text` / `TextProperty` | `str` | `"Localized Text"` |
| `vector` / `StructProperty` | `dict` | `{"X": 0.0, "Y": 0.0, "Z": 0.0}` |
| `rotator` | `dict` | `{"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0}` |
| `transform` | `dict` | `{"Location": {...}, "Rotation": {...}, "Scale": {...}}` |
| `object` / `ObjectProperty` | `str` | `"ActorReference"` |
| `class` / `ClassProperty` | `str` | `"AActor"` |
| `softobject` / `SoftObjectProperty` | `str` | `"/Game/Path/Asset.Asset"` |
| `softclass` / `SoftClassProperty` | `str` | `"/Game/Path/BP.BP_C"` |
| `array` / `ArrayProperty` | `list` | `[item1, item2, ...]` |
| `map` / `MapProperty` | `dict` | `{"key1": value1, ...}` |
| `set` / `SetProperty` | `list` | `[item1, item2, ...]` |
| `delegate` | `str` | `"DelegateName"` |
| `enum` / `EnumProperty` | `str` | `"EnumType::Value"` |

### 3.2 类型识别代码

```python
def get_json_type_for_pin(pin_type: str) -> str:
    """将Pin类型映射到JSON类型"""
    type_map = {
        "exec": "none",
        "bool": "boolean",
        "int": "number",
        "IntProperty": "number",
        "float": "number",
        "FloatProperty": "number",
        "string": "string",
        "StrProperty": "string",
        "name": "string",
        "NameProperty": "string",
        "text": "string",
        "TextProperty": "string",
        "vector": "object",
        "StructProperty": "object",
        "rotator": "object",
        "transform": "object",
        "object": "string",
        "ObjectProperty": "string",
        "class": "string",
        "ClassProperty": "string",
        "softobject": "string",
        "SoftObjectProperty": "string",
        "array": "array",
        "ArrayProperty": "array",
        "map": "object",
        "MapProperty": "object",
        "delegate": "string",
        "enum": "string",
    }
    return type_map.get(pin_type, "unknown")
```

---

## 4. 连接关系解析

### 4.1 connected_to字段

`connected_to` 字段表示此 Pin 连接到哪些其他节点/Pin：

**格式：**
```json
{
  "connected_to": ["NodeID_PinName", ...]
}
```

**示例：**
```json
{
  "pin_name": "then",
  "pin_type": "exec",
  "direction": "output",
  "connected_to": ["K2Node_CallFunction_123"]
}
```

**解析连接：**
```python
for node in graph.nodes:
    for pin in node.pins:
        if pin.connected_to:
            print(f"Pin {pin.pin_name} 连接到:")
            for target in pin.connected_to:
                print(f"  → {target}")
```

### 4.2 多连接Pin

某些 Pin 可以连接多个目标（如输出Pin连接多个输入）：

**示例：**
```json
{
  "pin_name": "Health",
  "pin_type": "float",
  "direction": "output",
  "connected_to": [
    "K2Node_CallFunction_100_InValue",
    "K2Node_VariableSet_200_Value"
  ]
}
```

**解析：**
```python
# 查找多连接Pin
for node in graph.nodes:
    for pin in node.pins:
        if len(pin.connected_to) > 1:
            print(f"多连接Pin: {node.node_name}.{pin.pin_name}")
            print(f"  连接数: {len(pin.connected_to)}")
```

### 4.3 执行流追踪

追踪 exec Pin 的执行流程：

```python
def trace_execution_flow(graph):
    """追踪EventGraph执行流程"""
    flow = []

    # 找到事件起点
    for node in graph.nodes:
        if node.node_type == "K2Node_Event":
            flow.append(f"START: {node.node_name}")

            # 追踪 then Pin
            for pin in node.pins:
                if pin.pin_name == "then" and pin.connected_to:
                    for target in pin.connected_to:
                        flow.append(f"  → {target}")

    return flow

# 使用示例
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        flow = trace_execution_flow(graph)
        for step in flow:
            print(step)
```

---

## 5. 解析示例

### 5.1 提取节点所有Pins

```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

for graph in result.graphs:
    for node in graph.nodes:
        print(f"\n节点: {node.node_name} ({node.node_type})")
        print(f"  Pin数: {len(node.pins)}")

        # 分类Pin
        inputs = [p for p in node.pins if p.direction == "input"]
        outputs = [p for p in node.pins if p.direction == "output"]

        print(f"  输入Pins: {[p.pin_name for p in inputs]}")
        print(f"  输出Pins: {[p.pin_name for p in outputs]}")
```

### 5.2 查找特定类型的Pin

```python
def find_pins_by_type(graph, target_type):
    """查找特定类型的Pin"""
    found = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.pin_type == target_type:
                found.append({
                    "node": node.node_name,
                    "pin": pin.pin_name,
                    "connected": len(pin.connected_to) > 0
                })

    return found

# 查找所有浮点数Pin
for graph in result.graphs:
    float_pins = find_pins_by_type(graph, "float")
    print(f"浮点数Pins: {len(float_pins)}")
    for pin_info in float_pins:
        print(f"  {pin_info['node']}.{pin_info['pin']}")
```

### 5.3 查找未连接的Pin

```python
def find_unconnected_pins(graph):
    """查找未连接的Pins"""
    unconnected = []

    for node in graph.nodes:
        for pin in node.pins:
            if not pin.connected_to and pin.pin_type != "exec":
                unconnected.append({
                    "node": node.node_name,
                    "pin": pin.pin_name,
                    "type": pin.pin_type,
                    "direction": pin.direction
                })

    return unconnected

# 使用示例
for graph in result.graphs:
    unconnected = find_unconnected_pins(graph)
    print(f"未连接Pins: {len(unconnected)}")
    for pin_info in unconnected[:10]:  # 只显示前10个
        print(f"  {pin_info['direction']}: {pin_info['node']}.{pin_info['pin']} ({pin_info['type']})")
```

---

## 6. C++类型映射

### 6.1 Pin类型→C++类型

| Pin类型 | C++类型 | 说明 |
|---------|---------|------|
| `bool` | `bool` | 布尔 |
| `int` | `int32` | 32位整数 |
| `float` | `float` | 单精度浮点 |
| `string` | `FString` | UE字符串 |
| `name` | `FName` | UE名称 |
| `text` | `FText` | 本地化文本 |
| `vector` | `FVector` | 三维向量 |
| `rotator` | `FRotator` | 旋转（度数） |
| `transform` | `FTransform` | 变换 |
| `object` | `UObject*` | UObject指针 |
| `class` | `TSubclassOf<UObject>` | 类引用 |
| `softobject` | `TSoftObjectPtr<UObject>` | 软对象引用 |
| `array` | `TArray<T>` | 动态数组 |
| `map` | `TMap<K,V>` | 映射 |
| `delegate` | `FDelegate` / `FMulticastDelegate` | 委托 |

### 6.2 JSON值→C++值示例

| JSON值 | C++代码 |
|--------|---------|
| `{"X": 100, "Y": 0, "Z": 50}` | `FVector(100.0f, 0.0f, 50.0f)` |
| `{"Roll": 0, "Pitch": 90, "Yaw": 0}` | `FRotator(0.0f, 90.0f, 0.0f)` |
| `"FirstPersonCharacter_C"` | `Cast<AFirstPersonCharacter>(Obj)` |
| `"/Game/Assets/MyMesh"` | `FSoftObjectPath("/Game/Assets/MyMesh")` |

---

## 7. 常见问题

### Q1: exec Pin 有数据值吗？

**答案：** 没有。`exec` Pin 仅用于控制执行流，不传递数据。在 JSON 中，exec Pin 不包含 `value` 字段。

```json
{
  "pin_name": "execute",
  "pin_type": "exec",
  "direction": "input",
  "connected_to": ["K2Node_Event_0"]
  // 无 value 字段
}
```

### Q2: 如何区分输入和输出Pin？

**检查 `direction` 字段：**
```python
for pin in node.pins:
    if pin.direction == "input":
        print(f"输入: {pin.pin_name}")
    elif pin.direction == "output":
        print(f"输出: {pin.pin_name}")
```

### Q3: Pin类型和Property类型有什么区别？

**区别：**
- **Pin类型** — 节点连接点的数据类型（如 `float`、`exec`）
- **Property类型** — UObject属性的序列化类型（如 `FloatProperty`）

两者映射关系相同，但命名风格略有不同。

---

## 8. 参考链接

- **蓝图语义:** [blueprint-semantics.md](blueprint-semantics.md)
- **节点类型:** [node-types.md](node-types.md)
- **蓝图→C++转换:** [cpp-conversion.md](cpp-conversion.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*