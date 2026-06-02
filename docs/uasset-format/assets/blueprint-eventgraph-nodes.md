# 蓝图 EventGraph 节点类型参考

EventGraph 是蓝图中处理事件驱动逻辑的核心图表。本文档详细说明BP_FirstPersonCharacter 中使用的各类节点。

---

## 目录
- [节点类型速查](#节点类型速查)
- [详细说明](#详细说明)
- [节点连接模式](#节点连接模式)

---

## 节点类型速查

| 节点类名 | Name 前缀 | 用途 | 节点数 (BP_FirstPerson) |
|----------|-----------|------|------------------------|
| K2Node_CallFunction | K2Node_CallFunction_ | 函数调用 | 12 |
| K2Node_Event | K2Node_Event_ | 事件响应 | 6 |
| K2Node_EnhancedInputAction | K2Node_EnhancedInputAction_ | 增强输入动作 | 4 |
| EdGraphNode_Comment | EdGraphNode_Comment_ | 注释框 | 6 |
| K2Node_FunctionEntry | K2Node_FunctionEntry_ | 自定义函数入口 | 1 |
| K2Node_Knot | K2Node_Knot_ | 连线转接 | 4 |

---

## 详细说明

### 1. K2Node_CallFunction - 函数调用节点

调用UE函数库或类方法的标准节点。

```
Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction Name="K2Node_CallFunction_11"
   FunctionReference=(MemberName="Aim",MemberGuid=B1DC7C9F43E4AE141B78D0AC49E86308,bSelfContext=True)
   NodePosX=2384
   NodePosY=-1632
   NodeGuid=E7B1717D492D9E3EDA20629D2F0CA01C
   CustomProperties Pin (...)  // execute, then, self, Yaw, Pitch
End Object
```

**核心字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| FunctionReference.MemberName | 要调用的函数名 | "Aim", "Move", "Jump" |
| FunctionReference.MemberGuid | 函数的 GUID | B1DC7C9F43E4AE141B78D0AC49E86308 |
| FunctionReference.bSelfContext | 是否使用 self 作为目标 | True/False |
| NodePosX/Y | 画布坐标 | 2384, -1632 |

**典型引脚**：

| PinName | Direction | PinType | 说明 |
|---------|-----------|---------|------|
| execute | Input | exec | 触发调用 |
| then | Output | exec | 调用完成输出 |
| self | Input | object (self) | 调用目标 |
| 参数名... | Input | various | 函数参数 |

**BP_FirstPerson 中的调用函数**：

| 函数名 | 用途 | 节点 |
|--------|------|------|
| Move | 移动控件 | K2Node_CallFunction_5, _4 |
| Aim | 旋转控件 | K2Node_CallFunction_11, _6, _7, _1193 |
| Jump | 跳跃 | K2Node_CallFunction_1193 |
| StopJumping | 停止跳跃 | K2Node_CallFunction_9386 |
| GetActorForwardVector | 获取前向向量 | K2Node_CallFunction_8029 |
| GetActorRightVector | 获取右向量 | K2Node_CallFunction_8520 |
| AddMovementInput | 添加移动输入 | K2Node_CallFunction_7445, _7346 |

### 2. UK2Node_Event - 事件节点

绑定到接口函数的事件响应节点。

**UK2Node_Event 源码定义**（K2Node_Event.h:38-100）：
```cpp
class UK2Node_Event : public UK2Node_EditablePinBase, public IK2Node_EventNodeInterface
```

```
Begin Object Class=/Script/BlueprintGraph.K2Node_Event Name="K2Node_Event_2"
   EventReference=(
       MemberParent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",
       MemberName="Primary Thumbstick"
   )
   bOverrideFunction=True
   NodePosX=2080
   NodePosY=-816
   NodeGuid=4C15CD904D7C99C3D86790857331A576
   CustomProperties Pin (...)
End Object
```

**核心字段**：

| 字段 | 类型 | 说明 | 源码位置 |
|------|------|------|----------|
| EventReference | FMemberReference | 引用的事件函数 | K2Node_Event.h:53 |
| bOverrideFunction | uint32 | 是否覆盖父类函数 | K2Node_Event.h:57 |
| bInternalEvent | uint32 | 是否为内部机制事件 | K2Node_Event.h:61 |
| CustomFunctionName | FName | 自定义函数名（非覆盖时） | K2Node_Event.h:65 |
| FunctionFlags | uint32 | 附加函数标志 | K2Node_Event.h:69 |

**BP_FirstPerson 中的事件**：

| 成员名 | 说明 |
|--------|------|
| Primary Thumbstick | 主摇杆事件 |
| Secondary Thumbstick | 副摇杆事件 |
| Touch Jump Start | 触摸跳跃开始 |
| Touch Jump End | 触摸跳跃结束 |

**典型引脚**：

| PinName | Direction | PinType | 说明 |
|---------|-----------|---------|------|
| OutputDelegate | Output | delegate | 事件委托输出（DelegateOutputName 常量） |
| then | Output | exec | 事件触发执行流 |
| Axis / ActionValue | Output | struct | 事件数据（Vector2D） |

### 3. K2Node_EnhancedInputAction - 增强输入动作

UE5 增强输入系统的核心节点。

```
Begin Object Class=/Script/InputBlueprintNodes.K2Node_EnhancedInputAction Name="K2Node_EnhancedInputAction_2"
   InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Look.IA_Look'"
   NodePosX=2096
   NodePosY=-1616
   AdvancedPinDisplay=Hidden
   CustomProperties Pin (...)
End Object
```

**核心字段**：

| 字段 | 说明 |
|------|------|
| InputAction | 输入动作资源路径 |
| AdvancedPinDisplay | 高级引脚显示模式（Hidden/Visible） |

**触发类型引脚**：

| PinName | 说明 |
|---------|------|
| Triggered | 触发发生（已触发） |
| Started | 开始触发（计算开始） |
| Ongoing | 触发进行中 |
| Canceled | 触发取消 |
| Completed | 触发完成 |

**数据输出引脚**：

| PinName | PinType | 说明 |
|---------|---------|------|
| ActionValue | struct (Vector2D) | 输入值 |
| ActionValue_X | real (double) | X 分量 |
| ActionValue_Y | real (double) | Y 分量 |
| ElapsedSeconds | real (double) | 持续时间 |
| TriggeredSeconds | real (double) | 触发时刻 |

**BP_FirstPerson 中的输入动作**：

| 动作 | 用途 | 节点 |
|------|------|------|
| IA_Look | 旋转视角 | K2Node_EnhancedInputAction_2 |
| IA_Move | 移动控制 | K2Node_EnhancedInputAction_3 |
| IA_Jump | 跳跃 | K2Node_EnhancedInputAction_5 |
| IA_MouseLook | 鼠标旋转 | K2Node_EnhancedInputAction_0 |

### 4. EdGraphNode_Comment - 注释框

用于组织和分组节点。

```
Begin Object Class=/Script/UnrealEd.EdGraphNode_Comment Name="EdGraphNode_Comment_1"
   CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
   bCommentBubbleVisible_InDetailsPanel=False
   CommentDepth=-2
   NodePosX=1968
   NodePosY=-1712
   NodeWidth=1440
   NodeHeight=544
   NodeComment="Camera Input"
End Object
```

**核心字段**：

| 字段 | 说明 |
|------|------|
| CommentColor | 注释框颜色 (RGBA) |
| CommentDepth | 层级深度 |
| NodePosX/Y | 位置 |
| NodeWidth/Height | 尺寸 |
| NodeComment | 注释文本 |

**BP_FirstPerson 中的注释框**：

| 注释 | 说明 |
|------|------|
| Camera Input | 相机控制区域 |
| Movement Input | 移动控制区域 |
| Jump Input | 跳跃控制区域 |
| Left/Right | 方向注释 |
| Forward / Backward | 前后注释 |

### 5. UK2Node_FunctionEntry - 函数入口

自定义函数的起始节点。

**UK2Node_FunctionEntry 源码定义**（K2Node_FunctionEntry.h:36-80）：
```cpp
class UK2Node_FunctionEntry : public UK2Node_FunctionTerminator
```

```
Begin Object Class=/Script/BlueprintGraph.K2Node_FunctionEntry Name="K2Node_FunctionEntry_0"
   FunctionReference=(MemberName="Move")
   CustomGeneratedFunctionName="CustomMove"   // 可选
   bEnforceConstCorrectness=True               // 是否强制 const 正确性
   LocalVariables=(...)                         // 局部变量列表
   CustomProperties Pin (...)
End Object
```

**核心字段**：

| 字段 | 类型 | 说明 | 源码位置 |
|------|------|------|----------|
| CustomGeneratedFunctionName | FName | 自定义生成的函数名 | K2Node_FunctionEntry.h:42 |
| MetaData | FKismetUserDeclaredFunctionMetadata | 函数元数据 | K2Node_FunctionEntry.h:46 |
| LocalVariables | TArray<FBPVariableDescription> | 局部变量列表 | K2Node_FunctionEntry.h:50 |
| bEnforceConstCorrectness | bool | 是否强制 const 正确性 | K2Node_FunctionEntry.h:54 |

**典型引脚**：

| PinName | Direction | PinType | 说明 |
|---------|-----------|---------|------|
| then | Output | exec | 函数入口执行 |
| 参数名... | Output | various | 函数参数输出 |

### 6. K2Node_Knot - 节点转接

用于整理连线布局的中转节点，不改变数据。

```
Begin Object Class=/Script/BlueprintGraph.K2Node_Knot Name="K2Node_Knot_1"
   NodePosX=2544
   NodePosY=-784
   NodeGuid=5DA12B624225F8CD19A59BB18E30848F
   CustomProperties Pin (
       PinId=F9EAD3EB4E49044404B771AC20C28436,
       PinName="InputPin",
       bDefaultValueIsIgnored=True,
   )
   CustomProperties Pin (
       PinId=5246D4F84ECABD92CC322BBAD7DCD742,
       PinName="OutputPin",
       Direction="EGPD_Output",
   )
End Object
```

**核心字段**：

| 字段 | 说明 |
|------|------|
| InputPin | 输入引脚（通常忽略默认值） |
| OutputPin | 输出引脚 |

---

## 节点连接模式

### 模式 1: 输入动作 → 函数调用

```
K2Node_EnhancedInputAction_2 (Triggered)
    ↓ (LinkedTo)
K2Node_CallFunction_11 (execute)
    ↓
K2Node_CallFunction_11 (then)
    ↓
K2Node_CallFunction_7 (execute)
```

### 模式 2: 事件 → 多个处理节点

```
K2Node_Event_2 (then)
    ↓
K2Node_CallFunction_4 (execute)
    ↓
K2Node_Knot_3 (转接 ActionValue_Y)

K2Node_Event_2 (Axis)
    ↓ (SubPins)
K2Node_Knot_2 → K2Node_Knot_1 (ActionValue_X)
```

### 模式 3: 向量分解 → 多个目标

```
K2Node_EnhancedInputAction_2 (ActionValue_X)
    ↓
K2Node_CallFunction_11 (Yaw)
    ↓
K2Node_CallFunction_7 (Yaw)

K2Node_EnhancedInputAction_2 (ActionValue_Y)
    ↓
K2Node_CallFunction_11 (Pitch)
    ↓
K2Node_CallFunction_7 (Pitch)
```

---

## 节点分组逻辑

BP_FirstPersonCharacter 的 EventGraph 分组：

```
┌─────────────────────────────────────────────────────────────┐
│ EdGraphNode_Comment_1: "Camera Input"                       │
│   K2Node_EnhancedInputAction_2 (IA_Look)                    │
│   K2Node_CallFunction_11 (Aim)                              │
│   K2Node_CallFunction_7 (Aim from mouse)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ EdGraphNode_Comment_4: "Movement Input"                     │
│   K2Node_EnhancedInputAction_3 (IA_Move)                    │
│   K2Node_CallFunction_5 (Move)                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ EdGraphNode_Comment_0: "Jump Input"                         │
│   K2Node_EnhancedInputAction_5 (IA_Jump)                    │
│   K2Node_CallFunction_1193 (Jump)                           │
│   K2Node_CallFunction_9386 (StopJumping)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ EdGraphNode_Comment_5/6: "Left/Right / Forward/Backward"    │
│   K2Node_FunctionEntry_0 (Move)                             │
│   K2Node_Knot_1, _2, _3, _4 (routing)                       │
│   K2Node_CallFunction_7445, _7346 (AddMovementInput)        │
│   K2Node_CallFunction_8520, _8029 (vectors)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 源码引用

| 文件 | 说明 |
|------|------|
| Editor/BlueprintGraph/Classes/K2Node_CallFunction.h | K2Node_CallFunction 定义 |
| Editor/BlueprintGraph/Classes/K2Node_Event.h | UK2Node_Event 定义 |
| Editor/BlueprintGraph/Classes/K2Node_FunctionEntry.h | UK2Node_FunctionEntry 定义 |
| Editor/InputBlueprintNodes/Classes/K2Node_EnhancedInputAction.h | 增强输入节点 |
| Editor/UnrealEd/Classes/EdGraphNode_Comment.h | 注释节点 |
| Editor/BlueprintGraph/Classes/K2Node_Knot.h | 节点转接 |

---

## 版本差异

### UE5
- K2Node_EnhancedInputAction 新增 5 种触发类型
- 输入动作资源路径格式：`/Script/EnhancedInput.InputAction'...`
- UK2Node_Event 新增 bInternalEvent 字段标记内部事件

### UE4
- 使用基本 InputAction 节点（非 Enhanced）
- Triggered/Started/Canceled/Completed 仅通过一个引脚

---

*Source: UE5 Engine Source (K2Node_Event.h, K2Node_FunctionEntry.h 验证), BlueprintGraph, InputBlueprintNodes Modules*
*Phase: 05-蓝图与动画资产*
