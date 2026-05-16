# Phase 50: EnhancedInput 语义增强 — CONTEXT.md

**Date:** 2026-05-16  
**Phase:** 050-enhancedinput-semantic  
**Goal:** TriggerEvent 类型可识别,使 K2Node_EnhancedInputAction 的 JSON 输出可与 C++ InputAction 事件处理器对照

---

## 背景

### UE5 EnhancedInput 基础

Unreal Engine 5 的 EnhancedInput 系统通过 `InputAction` 定义手势(如 Move、Look、Jump),通过 `TriggerEvent` 定义触发时机:

| TriggerEvent | 含义 | C++ 回调类型 |
|-------------|------|-------------|
| `Started` | 手势开始(按键按下) | `Started` delegate |
| `Ongoing` | 手势持续(按键按住) | `Started` + `Centered` |
| `Completed` | 手势结束(按键松开) | `Completed` delegate |
| `Canceled` | 手势取消 | `Canceled` delegate |

在蓝图中,`K2Node_EnhancedInputAction` 节点通过不同的 exec output pins 表示这些时机:
- `Started` pin → 动作开始时执行
- `Ongoing` pin → 动作持续时执行
- `Completed` pin → 动作结束时执行
- `Canceled` pin → 动作取消时执行

### 当前状态

Phase 47 已修复 Pin LinkedTo 功能,Phase 48-49 正在进行中。Phase 50 在此基础上增强语义识别。

**当前 JSON 输出示例** (简化):
```json
{
  "class_name": "K2Node_EnhancedInputAction",
  "node_data": {
    "input_action_path": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:InputAction"
  },
  "pins": [
    {
      "pin_name": "FormGroup",
      "pin_category": "text",
      "pin_subcategory_object": 0
    },
    {
      "pin_name": "exec",
      "pin_category": "exec",
      "pin_subcategory_object": 0
    },
    {
      "pin_name": "EventArgs",
      "pin_category": "struct",
      "pin_subcategory_object": 1
    },
    {
      "pin_name": "Completed",
      "pin_category": "exec",
      "pin_subcategory_object": 0
    },
    {
      "pin_name": "Started",
      "pin_category": "exec",
      "pin_subcategory_object": 0
    },
    {
      "pin_name": "Ongoing",
      "pin_category": "exec",
      "pin_subcategory_object": 0
    },
    {
      "pin_name": "Canceled",
      "pin_category": "exec",
      "pin_subcategory_object": 0
    }
  ]
}
```

**问题**: TriggerEvent 类型(Started/Ongoing/Completed/Canceled)在 pin_name 中可见,但未在 `node_data` 中显式标识,无法与 C++ InputAction 的 event handler 明确对应。

### 验证标准 — JSON 可翻译性

Phase 50 完成后,JSON 输出应覆盖 C++ 文件中的 InputAction 事件绑定:

**C++ 示例** (`FirstPersonCharacter.cpp`):
```cpp
void AFirstPersonCharacter::BeginPlay()
{
    Super::BeginPlay();
    
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem = UEnhancedInputLocalPlayerSubsystem::GetSubsystem(PC->GetLocalPlayer()))
        {
            UInputAction* MoveAction = Cast<UInputAction>(StaticLoadObject(UInputAction::StaticClass(), nullptr, TEXT("/Game/FirstPerson/Blueprints/IA_Movement.IA_Movement")));
            UInputAction* LookAction = Cast<UInputAction>(StaticLoadObject(UInputAction::StaticClass(), nullptr, TEXT("/Game/FirstPerson/Blueprints/IA_Look.IA_Look")));
            
            Subsystem->AddMappingContext(MappingContext, 0);
            
            if (MoveAction) PC->GetLocalPlayer()->SubscribeToAction(MoveAction, &AFirstPersonCharacter::Move);
            if (LookAction) PC->GetLocalPlayer()->SubscribeToAction(LookAction, &AFirstPersonCharacter::Look);
        }
    }
}
```

**JSON 输出目标** (`BP_FirstPersonCharacter.uasset`):
```json
{
  "graphs": [{
    "nodes": [{
      "class_name": "K2Node_EnhancedInputAction",
      "node_data": {
        "input_action_path": "/Game/FirstPerson/Blueprints/IA_Movement.IA_Movement",
        "trigger_events": ["Started", "Ongoing", "Completed", "Canceled"]
      },
      "pins": [...]
    }]
  }],
  "execution_flows": [{
    "start_event": "K2Node_EnhancedInputAction.Started",
    "nodes": [{"node_type": "K2Node_CallFunction", "function_name": "Move"}]
  }, {
    "start_event": "K2Node_EnhancedInputAction.Ongoing",
    "nodes": []
  }, {
    "start_event": "K2Node_EnhancedInputAction.Completed",
    "nodes": []
  }]
}
```

---

## 根因分析

### 当前 K2Node_EnhancedInputAction 解析逻辑

**文件:** `src/uasset_read/serializers/graph.py:629-635`

```python
def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段,返回字典(作为 node_data)。"""
    input_action_path = archive.read_fstring()
    return {
        "input_action_path": input_action_path,
    }
```

**问题:**
1. 只读取 `input_action_path`,未解析节点 pins 的 TriggerEvent 类型
2. K2Node_EnhancedInputAction 可能包含额外的 serialized properties(UE5 >= 1011 SerializationControlExtensions)
3. 未在 node_data 中显式标识 trigger_events 列表

### 偏移计算

K2Node_EnhancedInputAction 无自定义 serialized properties,TriggerEvent 信息隐含在 pins 中:
- pin_name ∈ {"Started", "Ongoing", "Completed", "Canceled"} → trigger_events

---

## 任务

### Task 1: 增强 `read_k2node_enhanced_input()` 解析 TriggerEvent

**文件:** `src/uasset_read/serializers/graph.py`

扩展 `read_k2node_enhanced_input()` 以解析节点 pins 并提取 trigger_events:

```python
def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段,返回字典(作为 node_data)。"""
    input_action_path = archive.read_fstring()
    # TODO: 后续版本可能需要读取额外 properties
    return {
        "input_action_path": input_action_path,
    }
```

**注意:** Phase 47 已在 `flow_builder.py` 中实现从 pins 提取 trigger_events,Phase 50 需将此逻辑前置到 node_data。

### Task 2: 在 node_data 中显式标识 trigger_events

**文件:** `src/uasset_read/serializers/graph.py`

修改节点创建逻辑,在 `create_node_from_archive()` 中为 K2Node_EnhancedInputAction 提取 trigger_events:

```python
elif class_name == "K2Node_EnhancedInputAction":
    node_data = read_k2node_enhanced_input(archive, name_map)
    # 提取 trigger_events from nodes.pins
    trigger_events = _extract_trigger_events(node.pins)
    if trigger_events:
        node_data["trigger_events"] = trigger_events
    base_node.node_data = node_data
```

或在 `K2NodeEnhancedInputAction` dataclass 中添加属性:

```python
@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction 输入动作节点。"""
    input_action_path: str = ""
    trigger_events: List[str] = field(default_factory=list)
```

### Task 3: 验证 TriggerEvent 提取正确性

运行以下测试:

```bash
python -c "
from uasset_read import parse_uasset
result = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset')

for graph in result.graphs:
    for node in graph.nodes:
        if node.class_name == 'K2Node_EnhancedInputAction':
            nd = node.node_data
            if isinstance(nd, dict):
                print(f'InputAction: {nd.get(\"input_action_path\")}')
                print(f'TriggerEvents: {nd.get(\"trigger_events\")}')
                assert 'trigger_events' in nd, 'trigger_events not in node_data'
                assert len(nd['trigger_events']) > 0, 'trigger_events empty'
"
```

预期输出:

```
InputAction: /Game/FirstPerson/Blueprints/IA_Movement.IA_Movement
TriggerEvents: ['Started', 'Ongoing', 'Completed', 'Canceled']
```

### Task 4: 新增测试

**文件:** `tests/test_phase50_enhancedinput_trigger.py`

- 解析 `BP_FirstPersonCharacter.uasset`
- 断言至少一个 K2Node_EnhancedInputAction 节点的 `node_data.trigger_events` 非空
- 断言 `execution_flows` 中至少一条 flow 的 `start_event` 以 `K2Node_EnhancedInputAction.*` 开头
- 断言 trigger_events ∈ {"Started", "Ongoing", "Completed", "Canceled"}

---

## 关联 Phase

- **Phase 47**: Pin LinkedTo 修复 — 提供 pin 连接信息基础
- **Phase 48**: 组件属性递归解析 — 与 K2Node_VariableSet 配合
- **Phase 49**: 函数调用引脚解析 — 联动 CallFunction 节点的 function_reference

---

## 风险

- **UE4 兼容:** 不处理 UE4。测试资产为 UE5.7。
- **其他节点类型不受影响:** 此修改仅影响 K2Node_EnhancedInputAction。
- **Backward compatibility:** `trigger_events` 字段可选,旧 JSON 输出仍可解析。

---

## 执行顺序

1 → 2 → 3 → 4（顺序执行,Task 2 实现后 Task 3 验证,Task 4 最后写测试）

*Created: 2026-05-16*
