# 蓝图节点文本 vs 生成骨架对比分析

**参考**: `reference/蓝图节点文本参考.md`  
**生成**: Phase 56 C++ 骨架输出

---

## 1. 蓝图节点类型统计

### 1.1 节点类型分布

来自 `reference/蓝图节点文本参考.md`:

| 节点类型 | 数量 | 说明 |
|---------|------|------|
| `K2Node_CallFunction` | ~15 | 函数调用节点 |
| `K2Node_EnhancedInputAction` | 4 | 增强输入动作节点 |
| `K2Node_FunctionEntry` | 1 | 自定义函数入口 (Move) |
| `EdGraphNode_Comment` | 3 | 注释框节点 |
| `K2Node_Knot` | 10+ | 连线转接节点 |

### 1.2 函数节点详情

**CallFunction 节点**:
```
K2Node_CallFunction_1193: Jump()
K2Node_CallFunction_9386: StopJumping()
K2Node_CallFunction_5/4: Move()
K2Node_CallFunction_11/6/4: Aim()
```

**EnhancedInputAction 节点**:
```
K2Node_EnhancedInputAction_2: IA_Look (触发事件)
K2Node_EnhancedInputAction_3: IA_Move (触发事件)
K2Node_EnhancedInputAction_5: IA_Jump (Started/Completed)
K2Node_EnhancedInputAction_0: IA_MouseLook
```

---

## 2. 蓝图函数结构

### 2.1 自定义函数 (Move)

```
Begin Object: K2Node_FunctionEntry_0
  FunctionReference=(MemberName="Move")
  
Pins:
  - execute (from K2Node_Knot_3)
  - then (to K2Node_CallFunction_7)
  - InputPin (Right/Forward, from K2Node_Knot_2)
  - InputPin (Forward/Backward, from K2Node_Knot_2)
```

**函数签名**:
```cpp
void Move(double Right, double Forward)
```

### 2.2 增强输入动作事件

**事件**: `K2Node_EnhancedInputAction_2` (IA_Look)

**引脚**:
```
Triggered     → K2Node_CallFunction_11 (Aim)
Started       → (未连接)
Ongoing       → (未连接)
Canceled      → (未连接)
Completed     → (未连接)
ActionValue   → Split to X/Y (double)
ElapsedSeconds
TriggeredSeconds
InputAction   → IA_Look
```

**函数签名**:
```cpp
void Look(double Yaw, double Pitch)  // 来自 ActionValue_X/Y
```

**事件连接**:
```
K2Node_EnhancedInputAction_2 (Triggered)
    ↓
K2Node_CallFunction_11 (Aim)
    ↓
K2Node_FunctionEntry_Aim
```

---

## 3. 生成骨架 vs 蓝图节点对比

### 3.1 当前生成骨架

```cpp
class A_Game_FirstPerson_Blueprints_BP_FirstPersonCharacter : public ACharacter
{
public:
    A_Game_FirstPerson_Blueprints_BP_FirstPersonCharacter();

protected:
    // Components
    ArrowComponent* Arrow;
    CameraComponent* CameraComponent_0__CCE3C0B4;
    CapsuleComponent* CollisionCylinder;
    CharacterMovementComponent* CharMoveComp;
    SkeletalMeshComponent* FirstPersonMesh_GEN_VARIABLE;
    SkeletalMeshComponent* CharacterMesh0;

    UPROPERTY(, Category = "variable")
    IntProperty BlueprintSystemVersion = 2;
    // ... 更多系统变量
};
```

### 3.2 蓝图实际内容

**组件** (匹配):
- ✅ FirstPersonMesh (SkeletalMeshComponent)
- ✅ FirstPersonCamera (CameraComponent)
- ✅ CollisionCylinder (CapsuleComponent)
- ⚠️ CharMoveComp (CharacterMovementComponent)
- ⚠️ Arrow (未在 C++ 中声明)
- ⚠️ CharacterMesh0 (未在 C++ 中声明)

**变量** (不匹配):
- ❌ 蓝图有 InputAction 变量 (JumpAction, MoveAction, LookAction, MouseLookAction)
- ❌ 生成骨架只显示系统变量 (BlueprintSystemVersion, SimpleConstructionScript...)

**原因**: 蓝图中的 InputAction 是通过 "Enhanced Input" 系统配置的，不是普通的 BlueprintVariable

---

## 4. 函数/方法对比

### 4.1 蓝图中的函数定义

来自蓝图节点文本:

| 函数名 | 节点类型 | 引脚签名 | C++ 签名 |
|--------|---------|---------|---------|
| `Move` | K2Node_FunctionEntry | execute, then, double Right, double Forward | `void Move(double Right, double Forward)` |
| `Aim` | K2Node_Event | execute, then, float Yaw, double Pitch | `void Aim(float Yaw, float Pitch)` |

**注意**: `Aim` 事件来自 Event Graph (K2Node_Event)，不是自定义函数

### 4.2 生成骨架的缺失

| 项目 | 蓝图中存在 | 生成骨架 | 状态 |
|------|-----------|---------|------|
| Move 函数声明 | ✅ K2Node_FunctionEntry | ❌ 缺失 | Phase 57 处理 |
| Aim 函数声明 | ✅ K2Node_Event | ❌ 缺失 | Phase 57 处理 |
| Move 函数体 | ✅ AddMovementInput | ❌ 缺失 | Phase 58 处理 |
| Aim 函数体 | ✅ AddControllerYaw/PitchInput | ❌ 缺失 | Phase 58 处理 |

### 4.3 执行流分析

**Jump 执行流**:
```
K2Node_EnhancedInputAction_5 (Started)
    ↓ (execute)
K2Node_CallFunction_1193 (Jump)
    ↓ (then)
```

**Aim 执行流**:
```
K2Node_EnhancedInputAction_2 (Triggered)
    ↓ (execute)
K2Node_CallFunction_11 (Aim)
    ↓ (then)
```

**Move 执行流**:
```
K2Node_Key_EnhancedInputAction_3 (Triggered)
    ↓ (execute)
K2Node_CallFunction_5 (Move)
    ↓ (then)
    ↓ (Left/Right) → AddMovementInput
    ↓ (Forward/Backward) → AddMovementInput
```

---

## 5. 引脚类型映射

### 5.1 PinType 结构

来自蓝图节点文本示例:

```
PinType.PinCategory="real"
PinType.PinSubCategory="double"
PinType.PinSubCategoryObject=None
```

**类型映射**:
| PinCategory | PinSubCategory | C++ 类型 |
|-------------|---------------|---------|
| exec | - | `FathEvent` (exec 引脚) |
| object | Class | `ACharacter*` |
| object | ScriptStruct | `FVector2D` |
| struct | Vector2D | `FVector2D` |
| real | double | `double` |
| real | float | `float` |

### 5.2 当前骨架的缺失类型映射

| UE 类型 | C++ 类型 | 状态 |
|---------|---------|------|
| `InputAction` | `UInputAction*` | ❌ 缺失 |
| `EnhancedInputComponent` | `UEnhancedInputComponent*` | ❌ 缺失 |

**影响**:
- Phase 57 无法正确生成 `SetupPlayerInputComponent` 函数签名
- Phase 58 无法正确生成 `EnhancedInputComponent->BindAction()` 调用

---

## 6. 建议

### 6.1 Phase 56-05 扩展类型映射

添加以下类型到 `UE_TO_CPP_TYPE_MAP`:

```python
UE_TO_CPP_TYPE_MAP = {
    # ... 现有类型 ...
    "InputAction": "UInputAction*",
    "EnhancedInputComponent": "UEnhancedInputComponent*",
    "FInputActionValue": "FInputActionValue",
    "InputAction": "UInputAction*",  # .uasset 中的实际类型路径
}
```

### 6.2 Phase 57 函数签名提取

从蓝图节点提取函数签名:

1. **K2Node_FunctionEntry** → 自定义函数声明
2. **K2Node_Event** → 事件函数声明
3. **Pin 名称和类型** → 参数列表
4. **LinkedTo** → 连接关系

**示例**:

```
K2Node_FunctionEntry_0:
  MemberName = "Move"
  Pins:
    - execute (exec)
    - then (exec)
    - InputPin (double) → Right
    - InputPin (double) → Forward
```

**生成**:
```cpp
void Move(double Right, double Forward);
```

### 6.3 Phase 58 函数体翻译

从 CallFunction 节点提取 C++ 调用:

**K2Node_CallFunction_5 (Move)**:
```
FunctionReference=(MemberName="Move",bSelfContext=True)
Pins:
  - Left/Right (linked to K2Node_EnhancedInputAction_3 ActionValue_X)
  - Forward/Backward (linked to K2Node_EnhancedInputAction_3 ActionValue_Y)
```

**生成** (Phase 58):
```cpp
void AFirstPersonCharacter::Move(double Right, double Forward)
{
    if (GetController())
    {
        AddMovementInput(GetActorRightVector(), Right);
        AddMovementInput(GetActorForwardVector(), Forward);
    }
}
```

**数据流追踪**:
```
ActionValue_X (K2Node_EnhancedInputAction_3)
    ↓ (LinkedTo)
K2Node_CallFunction_5 Pin "Left/Right"
    ↓ (执行流)
K2Node_CallFunction_7 "AddMovementInput"
Pins:
  - Self (this)
  - Vector (GetActorRightVector())
  - Scale (Right)
```

---

## 7. 总结

### 7.1 当前差距

| 范畴 | 完成度 | 说明 |
|------|--------|------|
| 继承链 | 100% | ✅ 正确识别 |
| 组件声明 | 100% | ✅ 正确生成 UPROPERTY |
| 类型映射 | 95% | ⚠️ 缺少 EnhancedInput 类型 |
| 函数声明 | 0% | ❌ Phase 57 |
| 函数体 | 0% | ❌ Phase 58 |
| 构造函数 | 0% | ❌ Phase 59 |

### 7.2 预期架构

```
Phase 56: 类骨架提取
  ├─ 继承链 ✅
  ├─ 组件 UPROPERTY ✅
  ├─ 变量 UPROPERTY ⚠️ (部分)
  └─ 类型映射 ⚠️ (需扩展)

Phase 57: 函数签名映射
  ├─ 自定义函数 (K2Node_FunctionEntry)
  ├─ 事件函数 (K2Node_Event)
  └─ 从 Pin 提取参数

Phase 58: 函数体翻译
  ├─ CallFunction → C++ 调用
  ├─ 数据流追踪 (LinkedTo)
  └─ 执行流生成

Phase 59: 构造函数初始化
  ├─ CreateDefaultSubobject
  ├─ SetupAttachment
  └─ 属性赋值
```

### 7.3 关键发现

1. **蓝图中的 InputAction 不是普通变量**:
   - 它们通过 EnhancedInput 系统配置
   - 在 `K2Node_EnhancedInputAction` 节点中引用
   - 类型路径是 `/Script/EnhancedInput.InputAction`

2. **蓝图函数结构**:
   - 自定义函数: `K2Node_FunctionEntry` (Move)
   - 事件函数: `K2Node_Event` (Aim)
   - 函数调用: `K2Node_CallFunction`

3. **数据流**:
   - `LinkedTo` 指定引脚连接
   - `ActionValue_X/Y` 从 InputAction 到函数参数
   - 执行流从 `execute` 引脚传递

---

**分析日期**: 2026-05-18  
**参考文件**: `reference/蓝图节点文本参考.md`  
**生成版本**: Phase 56 (56-UAT.md)
