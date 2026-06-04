# 蓝图引脚 (Pin) 语法详解

蓝图节点的输入/输出引脚定义。Pin 是节点间数据流向的连接点，支持多种类型和高级特性。

## 目录
- [基本结构](#基本结构)
- [引脚类型](#引脚类型)
- [连接机制](#连接机制)
- [高级特性](#高级特性)
- [特殊节点类型](#特殊节点类型)

---

## 基本结构

每个 Pin 定义在 `CustomProperties Pin (...)` 块中：

```
CustomProperties Pin (
    PinId=823F8329464DAED6E551D6B72B7F2671,      // 唯一 GUID（32 位无连字符）
    PinName="execute",                             // 引脚名称
    Direction="EGPD_Input",                        // 方向（可选）
    PinType.PinCategory="exec",                    // 主类型
    PinType.PinSubCategory="",                     // 子类别
    PinType.PinSubCategoryObject=None,             // 子类别对象引用
    PinType.PinSubCategoryMemberReference=(),       // 子类别成员引用
    PinType.PinValueType=(),                       // 值类型（Map 容器使用）
    PinType.ContainerType=None,                    // 容器类型（Array/Map/Set）
    PinType.bIsReference=False,                    // 是否为引用
    PinType.bIsConst=False,                        // 是否为常量
    PinType.bIsWeakPointer=False,                  // 是否为弱指针
    PinType.bIsUObjectWrapper=False,               // 是否为 UObject 包装器
    PinType.bSerializeAsSinglePrecisionFloat=False, // 是否序列化为单精度浮点
    LinkedTo=(K2Node_CallFunction_1 1A2B3C4D,),   // 连接的引脚（输入端）
    PersistentGuid=00000000000000000000000000000000, // 持久 GUID
    bHidden=False,                                 // 是否隐藏
    bNotConnectable=False,                         // 是否不可连接
    bDefaultValueIsReadOnly=False,                 // 默认值是否只读
    bDefaultValueIsIgnored=False,                  // 默认值是否忽略
    bAdvancedView=False,                           // 是否高级视图显示
    bOrphanedPin=False,                            // 是否孤立引脚
)
```

### FEdGraphPinType 结构（UE5 源码验证）

位于 `EdGraphPin.h:76-193`，字段如下：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| PinCategory | FName | 主类型（exec、object、struct 等） |
| PinSubCategory | FName | 子类别（self、float、double 等） |
| PinSubCategoryObject | TWeakObjectPtr<UObject> | 子类别对象（类/结构体路径） |
| PinSubCategoryMemberReference | FSimpleMemberReference | 子类别成员引用（用于委托） |
| PinValueType | FEdGraphTerminalType | Map 容器的值类型 |
| ContainerType | EPinContainerType | 容器类型（None/Array/Map/Set） |
| bIsArray | uint8 (已弃用) | UE 4.17 前的数组标志，已废弃 |
| bIsReference | uint8 | 是否为引用传递 |
| bIsConst | uint8 | 是否为 const 值 |
| bIsWeakPointer | uint8 | 是否为弱指针 |
| bIsUObjectWrapper | uint8 | 是否为 UObject 包装器（如 TSubclassOf<T>） |
| bSerializeAsSinglePrecisionFloat | uint8 | 是否以单精度浮点序列化 |

### FSimpleMemberReference 结构

位于 `EdGraphPin.h:26-64`，用于委托等成员引用：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| MemberParent | TObjectPtr<UObject> | 成员定义的父对象（通常是类） |
| MemberName | FName | 成员名称 |
| MemberGuid | FGuid | 成员 GUID |

### FEdGraphTerminalType 结构

位于 `EdGraphNode.h:37-93`，用于容器内部类型：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| TerminalCategory | FName | 容器内部主类型 |
| TerminalSubCategory | FName | 容器内部子类别 |
| TerminalSubCategoryObject | TWeakObjectPtr<UObject> | 容器内部子类别对象 |
| bTerminalIsConst | bool | 容器内部是否为 const |
| bTerminalIsWeakPointer | bool | 容器内部是否为弱指针 |
| bTerminalIsUObjectWrapper | bool | 容器内部是否为 UObject 包装器 |

### EEdGraphPinDirection 枚举

位于 `EdGraphPin.h:97-100`：

| 枚举值 | 说明 |
|--------|------|
| EGPD_Input | 输入引脚 |
| EGPD_Output | 输出引脚 |

### EPinContainerType 枚举

| 枚举值 | 说明 |
|--------|------|
| None | 非容器 |
| Array | 数组 |
| Set | 集合 |
| Map | 映射 |

---

## 引脚类型

### 1. 执行引脚 (exec)

用于控制流，函数调用的触发信号。

```
PinName="execute"    // 输入执行引脚
PinName="then"       // 输出执行引脚
PinType.PinCategory="exec"
```

**特点**：
- 只能连接到其他 exec 引脚
- 没有数据值，只传递执行顺序
- 每个有执行输入的节点必须有 "execute" 引脚
- 每个有执行输出的节点必须有 "then" 引脚

### 2. 对象类型 (object)

引用其他对象（类、组件、资源等）。

```
PinName="self"
PinType.PinCategory="object"
PinType.PinSubCategoryObject="/Script/Engine.Character"
```

| 子类别 | 说明 |
|--------|------|
| `self` | 当前节点的目标对象（隐式 this） |
| 空字符串 | 显式对象引用 |
| 类路径 | 具体类引用（如 `/Script/Engine.MeshComponent`） |

### 3. 结构体类型 (struct)

传递结构体数据，如 Vector、Rotator、Vector2D。

```
PinName="WorldDirection"
PinType.PinCategory="struct"
PinType.PinSubCategoryObject="/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.Vector'"
```

常见结构体：
- `/Script/CoreUObject.Vector` - 三维向量
- `/Script/CoreUObject.Vector2D` - 二维向量
- `/Script/CoreUObject.Vector4` - 四维向量
- `/Script/CoreUObject.Rotator` - 旋转
- `/Script/CoreUObject.Quat` - 四元数
- `/Script/Engine.Color` - 颜色

### 4. 基础类型

#### 实数 (real)
```
PinType.PinCategory="real"
PinType.PinSubCategory="double"   // 双精度 (64-bit)
PinType.PinSubCategory="float"    // 单精度 (32-bit)
```

#### 布尔 (bool)
```
PinType.PinCategory="bool"
```

#### 字符串 (string)
```
PinType.PinCategory="string"
```

#### 整数 (int)
```
PinType.PinCategory="int"
```

#### 字节 (byte)
```
PinType.PinCategory="byte"
```

#### 类引用 (class)
```
PinType.PinCategory="class"
```

### 5. 委托类型 (delegate)

```
PinName="OutputDelegate"
PinType.PinCategory="delegate"
PinType.PinSubCategoryMemberReference=(
    MemberParent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",
    MemberName="Primary Thumbstick"
)
```

委托引脚用于事件响应，连接到事件节点的输出。

### 6. 文本类型 (text)

```
PinType.PinCategory="text"
```

用于本地化文本和富文本。

---

## 连接机制

### LinkedTo 数组

连接目标列表，仅在**输入引脚**上存在：

```
LinkedTo=(
    K2Node_EnhancedInputAction_5 6412140B4E7EF6147A86BA8D2AFE9BA4,
    K2Node_Event_4 5B51114047AD12FFBCC0B4B41D99E92B,
)
```

**格式**: `节点名 引脚ID`

- 节点名：目标引脚所在的节点 Name
- 引脚ID：目标引脚的 PinId（无连字符的 GUID）

**规则**：
- 输入引脚有 `LinkedTo`，输出引脚无 `LinkedTo`
- 可以连接多个输出到单个输入（条件或）
- 循环连接会导致编译错误

### Direction 字段

明确指定引脚方向（可选，通常可推断）：

```
Direction="EGPD_Input"    // 输入
Direction="EGPD_Output"   // 输出
```

- 输入引脚：数据进入节点
- 输出引脚：数据离开节点
- 执行引脚 "execute" 总是输入，"then" 总是输出

---

## 高级特性

### SubPins（子引脚）

用于结构体的单个字段展开显示：

```
CustomProperties Pin (
    PinId=B1FD31FC4491F9E880F9549F8EBB231B,
    PinName="ActionValue",
    PinType.PinCategory="struct",
    PinType.PinSubCategoryObject="...",
    SubPins=(
        K2Node_EnhancedInputAction_2 19CFB869422928FE453A6B83C4F843E0,
        K2Node_EnhancedInputAction_2 F4EF37754BE47ECBD10D709B5FD29346,
    ),
    bHidden=True,              // 父引脚隐藏
    bNotConnectable=True,      // 父引脚不可连接
)

// 子引脚定义
CustomProperties Pin (
    PinId=19CFB869422928FE453A6B83C4F843E0,
    PinName="ActionValue_X",
    ParentPin=K2Node_EnhancedInputAction_2 B1FD31FC4491F9E880F9549F8EBB231B,
    // ... 其他字段
)
```

**规则**：
- 子引脚通过 `ParentPin` 字段关联到父结构体引脚
- 父引脚设置 `bHidden=True` 隐藏
- 子引脚显示为可连接的独立引脚（X/Y/Radius 等）

**常见使用场景**：
- Vector2D：ActionValue → ActionValue_X, ActionValue_Y
- Vector：WorldDirection → WorldDirection_X, WorldDirection_Y, WorldDirection_Z
- Color：Color → R, G, B, A

### PersistentGuid

用于追踪引脚即使名称更改：

```
PersistentGuid=00000000000000000000000000000000
```

- 通常为 0（无持久化需求）
- 编辑器可能设置非零值用于跨保存追踪

### 自定义属性字段

```
PinFriendlyName=NSLOCTEXT("K2Node", "Target", "Target")  // 友好显示名称
ToolTip="触发发生在一个或多个处理tick之后"             // 悬停提示
DefaultValue="0.0"                                      // 默认值
AutogeneratedDefaultValue="0.0"                         // 自动生成的默认值
DefaultObject="/Game/Input/Actions/IA_Look.IA_Look"     // 对象默认值
```

---

## 特殊节点类型

### 1. 节点转接 (K2Node_Knot)

用于整理连线布局的中转节点：

```
Begin Object Class=/Script/BlueprintGraph.K2Node_Knot Name="K2Node_Knot_1"
   NodePosX=2544
   NodePosY=-784
   CustomProperties Pin (
       PinId=F9EAD3EB4E49044404B771AC20C28436,
       PinName="InputPin",
       bDefaultValueIsIgnored=True,  // 转接节点输入忽略默认值
   )
   CustomProperties Pin (
       PinId=5246D4F84ECABD92CC322BBAD7DCD742,
       PinName="OutputPin",
       Direction="EGPD_Output",
   )
End Object
```

**特点**：
- `InputPin` 和 `OutputPin` 成对出现
- `bDefaultValueIsIgnored=True` on input
- 不改变数据，仅用于布局

### 2. 事件节点 (UK2Node_Event)

绑定到接口函数的事件：

```
Begin Object Class=/Script/BlueprintGraph.K2Node_Event Name="K2Node_Event_2"
   EventReference=(
       MemberParent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",
       MemberName="Primary Thumbstick"
   )
   bOverrideFunction=True
   CustomProperties Pin (
       PinId=9B246F914AAB2FB17D40BCA46C80BFDD,
       PinName="then",
       LinkedTo=(K2Node_CallFunction_4 8866157948C5B01482A4389D8750E9B9,),
   )
End Object
```

**UK2Node_Event 核心字段**（K2Node_Event.h:38-100）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| EventReference | FMemberReference | 引用的事件函数 |
| bOverrideFunction | uint32 | 是否覆盖父类函数 |
| bInternalEvent | uint32 | 是否为内部机制事件 |
| CustomFunctionName | FName | 自定义函数名（非覆盖时） |
| FunctionFlags | uint32 | 附加函数标志 |

**典型引脚**：
| PinName | Direction | PinType | 说明 |
|---------|-----------|---------|------|
| then | Output | exec | 事件触发执行流 |
| OutputDelegate | Output | delegate | 事件委托输出（DelegateOutputName 常量） |

### 3. 函数入口 (UK2Node_FunctionEntry)

自定义函数的起始节点：

```
Begin Object Class=/Script/BlueprintGraph.K2Node_FunctionEntry Name="K2Node_FunctionEntry_0"
   FunctionReference=(MemberName="Move")
   CustomGeneratedFunctionName="CustomMove"   // 可选，自定义生成的函数名
   bEnforceConstCorrectness=True              // 是否强制 const 正确性
   LocalVariables=(...)                        // 局部变量列表
   CustomProperties Pin (...)
End Object
```

**UK2Node_FunctionEntry 核心字段**（K2Node_FunctionEntry.h:36-80）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| CustomGeneratedFunctionName | FName | 自定义生成的函数名 |
| MetaData | FKismetUserDeclaredFunctionMetadata | 函数元数据 |
| LocalVariables | TArray<FBPVariableDescription> | 局部变量列表 |
| bEnforceConstCorrectness | bool | 是否强制 const 正确性 |

### 4. 注释框 (EdGraphNode_Comment)

```
Begin Object Class=/Script/UnrealEd.EdGraphNode_Comment Name="EdGraphNode_Comment_1"
   CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
   CommentDepth=-2
   NodePosX=1968
   NodePosY=-1712
   NodeWidth=1440
   NodeHeight=544
   NodeComment="Camera Input"
End Object
```

---

## 引脚类型完整对照表

| PinCategory | PinSubCategory | 说明 | 示例值 |
|-------------|----------------|------|--------|
| exec | - | 执行流 | - |
| object | "" / "self" / 类路径 | 对象引用 | `/Script/Engine.Character` |
| struct | - | 结构体 | `/Script/CoreUObject.Vector` |
| real | float / double | 浮点数 | 3.14 |
| int | - | 整数 | 42 |
| bool | - | 布尔 | true / false |
| string | - | 字符串 | "Hello" |
| text | - | 文本 | Localized Text |
| delegate | - | 委托 | 事件引用 |
| byte | - | 字节 | 0-255 |
| class | - | 类引用 | `/Script/Engine.Class'Character'` |

---

## 源码引用

| 文件 | 说明 |
|------|------|
| Runtime/Engine/Classes/EdGraph/EdGraphPin.h | FEdGraphPinType、FSimpleMemberReference 定义 |
| Runtime/Engine/Classes/EdGraph/EdGraphNode.h | FEdGraphTerminalType、EEdGraphPinDirection 定义 |
| Runtime/Engine/Classes/EdGraph/EdGraph.h | UEdGraph 类定义 |
| Editor/BlueprintGraph/Classes/K2Node_Event.h | UK2Node_Event 定义 |
| Editor/BlueprintGraph/Classes/K2Node_FunctionEntry.h | UK2Node_FunctionEntry 定义 |

---

## 版本差异

### UE5 新增/变更
- **FEdGraphPinType 新增字段**: PinSubCategoryMemberReference（委托成员引用）
- **EPinContainerType**: Map 和 Set 容器类型支持
- **SubPins 语法稳定化**：子引脚语法从早期版本标准化
- **Enhanced Input 节点**：K2Node_EnhancedInputAction 新增触发类型（Started, Ongoing, Canceled, Completed）
- **bSerializeAsSinglePrecisionFloat**: 新增单精度浮点序列化控制

### UE4
- 基础类型支持
- Pin 可能使用不同默认值格式
- bIsArray 已弃用，替换为 ContainerType

---

*Source: UE5 Engine Source (EdGraphPin.h, EdGraphNode.h, K2Node_Event.h, K2Node_FunctionEntry.h 验证)*
*Phase: 05-蓝图与动画资产*
