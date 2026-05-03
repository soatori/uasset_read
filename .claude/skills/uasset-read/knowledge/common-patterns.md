# Common Patterns - 常见蓝图模式

本文档总结常见蓝图执行模式，帮助 AI 从 `graphs_summary` 快速识别蓝图功能意图。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. BeginPlay初始化模式

### 1.1 模式特征

**识别标志：**
- `graphs_summary[].execution_flows[0].function_name = "ReceiveBeginPlay"`
- EventGraph 第一个节点是 `Event BeginPlay`

**典型流程：**
```
Event BeginPlay → 组件初始化 → 变量设置 → 后续逻辑
```

### 1.2 JSON模式识别

```json
{
  "graphs_summary": [
    {
      "graph_name": "EventGraph",
      "execution_flows": [
        {
          "function_name": "ReceiveBeginPlay",
          "params": []
        }
      ]
    }
  ]
}
```

**识别代码：**
```python
from uasset_read import parse_uasset, format_json_summary

result = parse_uasset("BP_Character.uasset")
output = format_json_summary(result)

for flow in output.get("graphs_summary", []):
    if flow["graph_name"] == "EventGraph":
        first_flow = flow["execution_flows"][0]

        if first_flow["function_name"] == "ReceiveBeginPlay":
            print("检测到 BeginPlay 初始化模式")
            print("  → C++函数: void BeginPlay() override")
```

### 1.3 C++对应

```cpp
void AMyCharacter::BeginPlay()
{
    Super::BeginPlay();

    // 组件初始化
    if (CharacterMesh)
    {
        // 设置Mesh等
    }

    // 变量初始化
    Health = MaxHealth;
    bIsAlive = true;

    // 后续逻辑...
}
```

---

## 2. 输入绑定模式

### 2.1 模式特征

**识别标志：**
- EventGraph 包含 `Event Move`、`Event Look` 等输入事件
- 节点类型 `K2Node_Event` + 输入相关名称
- 常见于 Character 蓝图

**典型流程：**
```
Event IA_Move → Get Movement Component → Add Movement Input
Event IA_Look → Get Player Controller → Add Control Input
```

### 2.2 JSON模式识别

```json
{
  "execution_flows": [
    {"function_name": "ReceiveBeginPlay"},
    {"function_name": "IA_Move"},      // Enhanced Input 动作
    {"function_name": "IA_Look"},
    {"function_name": "IA_Jump"}
  ]
}
```

**识别代码：**
```python
input_events = ["IA_Move", "IA_Look", "IA_Jump", "IA_Fire"]

for flow in output["graphs_summary"]:
    if flow["graph_name"] == "EventGraph":
        for exec_flow in flow["execution_flows"]:
            if exec_flow["function_name"] in input_events:
                print(f"检测到输入绑定: {exec_flow['function_name']}")
```

### 2.3 C++对应

```cpp
// Enhanced Input 绑定（在 SetupPlayerInputComponent 中）
void AMyCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    if (UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(PlayerInputComponent))
    {
        if (IA_MoveAction)
        {
            EnhancedInput->BindAction(IA_MoveAction, ETriggerEvent::Triggered, this, &AMyCharacter::Move);
        }
        if (IA_LookAction)
        {
            EnhancedInput->BindAction(IA_LookAction, ETriggerEvent::Triggered, this, &AMyCharacter::Look);
        }
    }
}

void AMyCharacter::Move(const FInputActionValue& Value)
{
    FVector2D MoveVector = Value.Get<FVector2D>();
    AddMovementInput(GetActorForwardVector(), MoveVector.Y);
    AddMovementInput(GetActorRightVector(), MoveVector.X);
}
```

---

## 3. 组件初始化模式

### 3.1 模式特征

**识别标志：**
- `exports[]` 包含多个 `*Component` 类型对象
- `is_component: true` 的变量
- 有 `transforms` 字段（RelativeLocation/Rotation/Scale）

**典型流程：**
```
构造时: CreateDefaultSubobjects → SetupAttachment → SetRelativeTransform
BeginPlay时: 组件属性设置（Mesh、AnimBlueprint等）
```

### 3.2 JSON模式识别

```json
{
  "exports": [
    {"name": "CharacterMesh0", "class": "SkeletalMeshComponent", "transforms": {...}},
    {"name": "FirstPersonCamera", "class": "CameraComponent", "transforms": {...}}
  ]
}
```

**识别代码：**
```python
from uasset_read import parse_uasset

result = parse_uasset("BP_Character.uasset")

# 查找组件导出对象
components = []
for export in result.export_map:
    if "Component" in export.class_name:
        components.append(export)

print(f"检测到 {len(components)} 个组件")
for comp in components:
    print(f"  - {comp.object_name} ({comp.class_name})")

    # 检查变换
    if hasattr(comp, 'transforms') and comp.transforms:
        loc = comp.transforms.get("RelativeLocation")
        if loc:
            print(f"    位置: ({loc['X']}, {loc['Y']}, {loc['Z']})")
```

### 3.3 C++对应

```cpp
AMyCharacter::AMyCharacter()
{
    // 创建组件
    CharacterMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CharacterMesh0"));
    CharacterMesh->SetupAttachment(GetCapsuleComponent());
    CharacterMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -90.0f));

    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0.0f, 0.0f, 64.0f));
}
```

---

## 4. 变量读写模式

### 4.1 模式特征

**识别标志：**
- 节点类型 `K2Node_VariableGet` / `K2Node_VariableSet`
- 节点名称格式 `Get {VariableName}` / `Set {VariableName}`

**典型流程：**
```
VariableGet → 使用值 → ...
Event → VariableSet(Value) → 后续
```

### 4.2 JSON模式识别

```python
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        var_reads = []
        var_writes = []

        for node in graph.nodes:
            if node.node_type == "K2Node_VariableGet":
                var_name = node.node_name.replace("Get ", "")
                var_reads.append(var_name)
            elif node.node_type == "K2Node_VariableSet":
                var_name = node.node_name.replace("Set ", "")
                var_writes.append(var_name)

        print(f"读取变量: {var_reads}")
        print(f"设置变量: {var_writes}")
```

### 4.3 C++对应

```cpp
// VariableGet
float CurrentHealth = Health;

// VariableSet
Health = NewHealthValue;
```

---

## 5. 碰撞检测模式

### 5.1 模式特征

**识别标志：**
- 节点类型 `K2Node_ComponentBoundEvent`
- 节点名称 `OnComponentBeginOverlap` / `OnComponentEndOverlap`

**典型流程：**
```
OnComponentBeginOverlap → Cast to Actor → 判断逻辑 → 处理
```

### 5.2 JSON模式识别

```python
overlap_events = ["OnComponentBeginOverlap", "OnComponentEndOverlap", "OnComponentHit"]

for graph in result.graphs:
    for node in graph.nodes:
        if node.node_type == "K2Node_ComponentBoundEvent":
            if node.node_name in overlap_events:
                print(f"检测到碰撞事件: {node.node_name}")

                # 获取碰撞参数
                for pin in node.pins:
                    if pin.pin_name in ["OtherActor", "OtherComp", "Hit"]:
                        print(f"  参数: {pin.pin_name} ({pin.pin_type})")
```

### 5.3 C++对应

```cpp
// 碰撞绑定（在构造函数或BeginPlay中）
CapsuleComponent->OnComponentBeginOverlap.AddDynamic(this, &AMyCharacter::OnOverlapBegin);
CapsuleComponent->OnComponentEndOverlap.AddDynamic(this, &AMyCharacter::OnOverlapEnd);

void AMyCharacter::OnOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, ...)
{
    if (OtherActor && OtherActor != this)
    {
        // 碰撞处理逻辑
    }
}
```

---

## 6. 常见蓝图模式识别指南

### 6.1 从graphs_summary快速识别

| execution_flows特征 | 蓝图功能 |
|---------------------|----------|
| `ReceiveBeginPlay` 在首位 | 初始化模式 |
| `IA_*` 输入动作名 | 输入绑定模式 |
| `OnComponent*Overlap` | 碰撞检测模式 |
| `ReceiveTick` | 每帧更新模式 |
| `ReceiveAnyDamage` | 伤害处理模式 |
| `SpawnActor` | 动态生成模式 |

### 6.2 模式→功能映射表

| 模式名称 | 典型蓝图 | 主要节点 |
|----------|----------|----------|
| BeginPlay初始化 | 所有Actor | `K2Node_Event: BeginPlay` |
| 输入绑定 | Character | `K2Node_Event: IA_*` |
| 碰撞检测 | Trigger、Character | `K2Node_ComponentBoundEvent` |
| 变量读写 | 所有蓝图 | `K2Node_VariableGet/Set` |
| 函数调用 | 所有蓝图 | `K2Node_CallFunction` |
| 条件分支 | 所有蓝图 | `K2Node_IfThenElse` |
| 循环遍历 | 所有蓝图 | `K2Node_MacroInstance: ForEachLoop` |

### 6.3 完整模式识别代码

```python
from uasset_read import parse_uasset, format_json_summary

def analyze_blueprint_patterns(asset_path):
    """分析蓝图中的常见模式"""
    result = parse_uasset(asset_path)

    if not result.is_success:
        print("解析失败")
        return

    output = format_json_summary(result)
    patterns = []

    # 1. 检查初始化模式
    for flow in output.get("graphs_summary", []):
        if flow["graph_name"] == "EventGraph":
            exec_flows = flow["execution_flows"]

            if exec_flows and exec_flows[0]["function_name"] == "ReceiveBeginPlay":
                patterns.append("BeginPlay初始化")

            # 2. 检查输入模式
            input_actions = [f for f in exec_flows if f["function_name"].startswith("IA_")]
            if input_actions:
                patterns.append(f"输入绑定({len(input_actions)}动作)")

            # 3. 检查Tick模式
            tick_flows = [f for f in exec_flows if f["function_name"] == "ReceiveTick"]
            if tick_flows:
                patterns.append("每帧更新")

    # 4. 检查组件数量
    components = [e for e in result.export_map if "Component" in e.class_name]
    if components:
        patterns.append(f"组件初始化({len(components)}个)")

    # 5. 检查碰撞模式（需深入graphs）
    for graph in result.graphs:
        if graph.graph_name == "EventGraph":
            for node in graph.nodes:
                if node.node_type == "K2Node_ComponentBoundEvent":
                    if "Overlap" in node.node_name:
                        patterns.append("碰撞检测")

    return patterns

# 使用示例
patterns = analyze_blueprint_patterns("BP_FirstPersonCharacter.uasset")
print("检测到的模式:")
for p in patterns:
    print(f"  - {p}")
```

---

## 7. 参考链接

- **蓝图语义:** [blueprint-semantics.md](blueprint-semantics.md)
- **节点类型:** [node-types.md](node-types.md)
- **蓝图→C++转换:** [cpp-conversion.md](cpp-conversion.md)
- **故障排除:** [troubleshooting.md](troubleshooting.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*