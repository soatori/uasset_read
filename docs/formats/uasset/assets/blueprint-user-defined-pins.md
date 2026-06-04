# 蓝图自定义引脚 (UserDefinedPin) 说明

Blueprint 编译器生成的函数图中，自定义引脚的定义机制。

---

## 概述

当蓝图函数有用户定义的输入/输出引脚时（通过蓝图编辑器添加的可编辑引脚），编译器会生成 `CustomProperties UserDefinedPin` 条目来描述这些引脚的元数据。

UserDefinedPin **不参与运行时连接**，仅作为编译器提示，定义用户可编辑的引脚结构。

---

## 基本语法

```
CustomProperties UserDefinedPin (PinName="Left / Right", PinType=(PinCategory="real", PinSubCategory="double"), DesiredPinDirection=EGPD_Output)
```

### 格式对比

| 类型 | 语法 | 用途 |
|------|------|------|
| `CustomProperties Pin` | `PinId=..., PinName=..., ...LinkedTo=(...),` | 运行时连接引脚 |
| `CustomProperties UserDefinedPin` | `PinName=..., PinType=(...), DesiredPinDirection=...` | 用户定义引脚元数据 |

---

## UserDefinedPin 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| PinName | string | 引脚名称 |
| PinType | struct | 引脚类型定义 |
| PinType.PinCategory | string | 主类型（real, struct, object, exec 等） |
| PinType.PinSubCategory | string | 子类别（double, float 等） |
| PinType.PinSubCategoryObject | TWeakObjectPtr<UObject> | 子类别对象（结构体/类路径） |
| PinType.PinSubCategoryMemberReference | FSimpleMemberReference | 子类别成员引用（委托等） |
| PinType.ContainerType | EPinContainerType | 容器类型（None/Array/Map/Set） |
| PinType.bIsReference | bool | 是否为引用传递 |
| PinType.bIsConst | bool | 是否为 const 值 |
| PinType.bIsWeakPointer | bool | 是否为弱指针 |
| PinType.bIsUObjectWrapper | bool | 是否为 UObject 包装器 |
| DesiredPinDirection | EGPD | 期望的引脚方向 |

### DesiredPinDirection 枚举

| 值 | 说明 |
|----|------|
| EGPD_Input | 输入引脚 |
| EGPD_Output | 输出引脚 |
| EGPD_Unknown | 未知方向 |

---

## 典型示例

### 示例 1: 自定义函数参数

```
Begin Object Class=/Script/BlueprintGraph.K2Node_FunctionEntry Name="K2Node_FunctionEntry_0"
   FunctionReference=(MemberName="Move")
   bIsEditable=True
   CustomProperties Pin (...)  // 实际连接引脚
   CustomProperties UserDefinedPin (
       PinName="Left / Right",
       PinType=(PinCategory="real", PinSubCategory="double"),
       DesiredPinDirection=EGPD_Output
   )
   CustomProperties UserDefinedPin (
       PinName="Forward / Backward",
       PinType=(PinCategory="real", PinSubCategory="double"),
       DesiredPinDirection=EGPD_Output
   )
End Object
```

**说明**：
- 这两个 UserDefinedPin 定义了函数的输入参数
- `DesiredPinDirection=EGPD_Output` 表示这些参数从函数"输出"到调用者
- 实际连接通过 `CustomProperties Pin` 的 `ActionValue_X`/`ActionValue_Y` 类型引脚完成

### 示例 2: 自定义输入（反向方向）

```
Begin Object Class=/Script/BlueprintGraph.K2Node_CallFunction Name="K2Node_CallFunction_7445"
   FunctionReference=(MemberName="AddMovementInput",bSelfContext=True)
   CustomProperties Pin (
       PinId=F7F1DA6A4A9AD273C811828673CC525C,
       PinName="WorldDirection",
       PinType.PinCategory="struct",
       PinType.PinSubCategoryObject="...",
   )
   // 可能存在的 UserDefinedPin（函数参数原始定义）
   CustomProperties UserDefinedPin (
       PinName="WorldDirection",
       PinType=(PinCategory="struct", PinSubCategoryObject="..."),
       DesiredPinDirection=EGPD_Input
   )
End Object
```

---

## UserDefinedPin 与 Pin 的关系

```
┌─────────────────────────────────────────────────────────────┐
│ K2Node_FunctionEntry_0 (Move function)                      │
├─────────────────────────────────────────────────────────────┤
│ UserDefinedPin (元数据定义)                                  │
│   PinName="Left / Right"                                    │
│   PinType=(PinCategory="real", PinSubCategory="double")     │
│   DesiredPinDirection=EGPD_Output                           │
│                                                             │
│ Pin (实际连接点)                                             │
│   PinId=84E069914221C8BA662D2CACACA212D4                    │
│   PinName="Left / Right"                                    │
│   Direction="EGPD_Output"                                   │
│   LinkedTo=(K2Node_Knot_2 ...)                              │
└─────────────────────────────────────────────────────────────┘
```

**关键区别**：
- **UserDefinedPin**：编译器生成的元数据，描述"用户定义的引脚应是什么样子"
- **Pin**：实际的运行时连接点，有 PinId 和 LinkedTo

---

## 编译器处理流程

```
1. 用户在蓝图编辑器添加自定义引脚
   ↓
2. 编辑器保存 UserDefinedPin 元数据
   ↓
3. 编译时生成对应的 Pin 连接点
   ↓
4. 运行时使用 Pin（非 UserDefinedPin）
```

**注意**：
- UserDefinedPin **不参与序列化连接**
- 运行时只使用 `CustomProperties Pin` 的连接信息
- UserDefinedPin 主要用于编辑器重绘和验证

---

## 常见使用场景

### 场景 1: 自定义函数参数

```
// 函数定义（用户添加了两个输入参数）
CustomProperties UserDefinedPin (
    PinName="Left / Right",
    PinType=(PinCategory="real", PinSubCategory="double"),
    DesiredPinDirection=EGPD_Input  // 输入参数
)
CustomProperties UserDefinedPin (
    PinName="Forward / Backward",
    PinType=(PinCategory="real", PinSubCategory="double"),
    DesiredPinDirection=EGPD_Input
)
```

### 场景 2: 自定义函数返回值

```
// 函数定义（用户添加了输出参数）
CustomProperties UserDefinedPin (
    PinName="Result",
    PinType=(PinCategory="struct", PinSubCategoryObject="...Vector"),
    DesiredPinDirection=EGPD_Output  // 输出返回值
)
```

### 场景 3: 事件参数

```
// 事件处理函数（用户添加了参数）
CustomProperties UserDefinedPin (
    PinName="Axis",
    PinType=(PinCategory="struct", PinSubCategoryObject="...Vector2D"),
    DesiredPinDirection=EGPD_Input
)
```

---

## 解析注意事项

### 1. 引脚名称匹配

UserDefinedPin 的 `PinName` 必须与对应 `Pin` 的 `PinName` 匹配：

```
UserDefinedPin (PinName="Left / Right")
    ↓
Pin (PinName="Left / Right", PinId=..., LinkedTo=...)
```

### 2. 方向一致性

`DesiredPinDirection` 应与 `Pin.Direction` 一致：

```
UserDefinedPin (DesiredPinDirection=EGPD_Output)
    ↓
Pin (Direction="EGPD_Output", PinName="...")
```

### 3. 类型匹配

`PinType` 应与对应 Pin 的 `PinType` 兼容：

```
UserDefinedPin (PinType=(PinCategory="real", PinSubCategory="double"))
    ↓
Pin (PinType.PinCategory="real", PinType.PinSubCategory="double")
```

---

## 实际数据（BP_FirstPersonCharacter）

### Move 函数入口

```
K2Node_FunctionEntry_0:
  UserDefinedPin 1:
    PinName="Left / Right"
    PinType=(PinCategory="real", PinSubCategory="double")
    DesiredPinDirection=EGPD_Output
    
  UserDefinedPin 2:
    PinName="Forward / Backward"
    PinType=(PinCategory="real", PinSubCategory="double")
    DesiredPinDirection=EGPD_Output
```

对应的 Pin 连接：
```
Pin (PinName="Left / Right", Direction="EGPD_Output", LinkedTo=K2Node_Knot_2...)
Pin (PinName="Forward / Backward", Direction="EGPD_Output", LinkedTo=K2Node_Knot_3...)
```

---

## 源码引用

| 文件 | 说明 |
|------|------|
| Editor/BlueprintGraph/Classes/K2Node_FunctionEntry.h | UK2Node_FunctionEntry 定义，LocalVariables 字段 |
| Editor/BlueprintGraph/Private/K2Node_FunctionEntry.cpp | 编译器实现 |
| Runtime/Engine/Classes/Engine/Blueprint.h | FBPVariableDescription 结构 |
| Runtime/Engine/Classes/EdGraph/EdGraphPin.h | FEdGraphPinType 结构 |

---

## 版本差异

### UE5
- UserDefinedPin 语法稳定
- PinType 结构新增 PinSubCategoryMemberReference 字段
- 支持 ContainerType 容器类型（Array/Map/Set）
- bIsArray 已弃用，统一使用 ContainerType

### UE4
- 基础 UserDefinedPin 支持
- PinType 结构较简单
- 使用 bIsArray 标记数组

---

## 常见问题

### Q: UserDefinedPin 会占用引脚 ID 吗？
**A**: 不会。UserDefinedPin 只是元数据，不参与连接，没有 PinId。

### Q: 可以跳过 UserDefinedPin 直接解析 Pin 吗？
**A**: 可以。UserDefinedPin 是编译器提示，运行时连接完全由 Pin 的 LinkedTo 决定。

### Q: 为什么需要 UserDefinedPin？
**A**: 用于编辑器重绘时恢复用户定义的引脚结构，以及验证引脚类型一致性。

---

*Source: UE5 Engine Source (K2Node_FunctionEntry.h, EdGraphPin.h 验证), BlueprintGraph Module*
*Phase: 05-蓝图与动画资产*
