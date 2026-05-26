# 节点到 C++ 映射

**研究日期**: 2026-05-06
**源码版本**: UE 5.7
**参考文件**:
- `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\BlueprintGraph\Classes\K2Node.h`
- `E:\Develop\uasset_read\.planning\BLUEPRINT_TO_CPP_TEST.md`

---

## 1. 节点类型分类

### 1.1 基础节点类型

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_CallFunction` | 函数调用节点 | 函数调用语句 |
| `UK2Node_Event` | 事件节点 | 虚函数重写 |
| `UK2Node_CustomEvent` | 自定义事件节点 | 虚函数声明 |
| `UK2Node_Knot` | Knot 节点（reroute） | 变量引用（内联） |
| `UK2Node_IfThenElse` | 条件分支节点 | if/else 语句 |
| `UK2Node_Switch` | Switch 节点 | switch 语句 |
| `UK2Node_VariableGet` | 变量读取节点 | 变量读取表达式 |
| `UK2Node_VariableSet` | 变量赋值节点 | 变量赋值语句 |
| `UK2Node_Composite` | 复合节点 | 子图内联 |
| `UK2Node_MacroInstance` | 宏实例节点 | 宏展开（内联） |

### 1.2 输入相关节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_InputAction` | 输入动作节点 | 委托绑定 |
| `UK2Node_InputAxis` | 输入轴节点 | 委托绑定 |
| `UK2Node_InputKeyEvent` | 输入按键事件节点 | 委托绑定 |
| `UK2Node_EnhancedInputAction` | 增强输入动作节点 | 增强输入系统调用 |
| `UK2Node_EnhancedInputAction` | 增强输入轴节点 | 增强输入系统调用 |

### 1.3 流控制节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_ForLoop` | For 循环节点 | for 循环语句 |
| `UK2Node_ForLoopWithBreak` | 可中断 For 循环 | for 循环语句（带 break） |
| `UK2Node_WhileLoop` | While 循环节点 | while 循环语句 |
| `UK2Node_DoWhileLoop` | Do-While 循环节点 | do-while 循环语句 |
| `UK2Node_ForEachLoop` | ForEach 循环节点 | 范围 for 循环 |
| `UK2Node_Break` | Break 节点 | break 语句 |
| `UK2Node_Continue` | Continue 节点 | continue 语句 |
| `UK2Node_Return` | Return 节点 | return 语句 |

### 1.4 数学运算节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_CallMath` | 数学函数调用 | 数学库函数调用 |
| `UK2Node_CommutativeAssociativeBinaryOperator` | 交换结合二元运算符 | 运算符表达式 |
| `UK2Node_BitmaskLiteral` | 位掩码字面量 | 位掩码常量 |

### 1.5 类型转换节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_CastByteToEnum` | 字节转枚举 | static_cast |
| `UK2Node_ClassDynamicCast` | 类动态转换 | Cast<T>() |
| `UK2Node_StructBreak` | 结构体分解 | 结构体成员访问 |

### 1.6 委托节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_AddDelegate` | 添加委托 | 委托 += 操作 |
| `UK2Node_AssignDelegate` | 赋值委托 | 委托 = 操作 |
| `UK2Node_BindDelegate` | 绑定委托 | 委托.Bind() |
| `UK2Node_ClearDelegate` | 清空委托 | 委托.Clear() |
| `UK2Node_CallDelegate` | 调用委托 | 委托.Execute() |
| `UK2Node_RemoveDelegate` | 移除委托 | 委托 -= 操作 |

### 1.7 容器操作节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_CallArrayFunction` | 数组函数调用 | 数组成员函数调用 |
| `UK2Node_CallDataTableFunction` | 数据表函数调用 | 数据表 API 调用 |

### 1.8 其他节点

| 节点类 | 说明 | C++ 对应 |
|--------|------|----------|
| `UK2Node_ActorBoundEvent` | Actor 绑定事件 | 委托绑定 |
| `UK2Node_ComponentBoundEvent` | Component 绑定事件 | 委托绑定 |
| `UK2Node_AsyncAction` | 异步操作节点 | 异步调用 |
| `UK2Node_BaseAsyncTask` | 基础异步任务 | 异步调用 |
| `UK2Node_AddComponent` | 添加组件 | AddComponent() |
| `UK2Node_BitmaskLiteral` | 位掩码字面量 | 位掩码常量 |
| `UK2Node_Comment` | 注释节点 | 注释 |
| `UK2Node_Timeline` | Timeline 节点 | Timeline 组件操作 |

---

## 2. 节点到 C++ 映射表

### 2.1 函数调用节点

#### K2Node_CallFunction → C++ 函数调用

**蓝图节点**:
```cpp
// 节点属性
FunctionReference = FMemberReference
{
    MemberName = "Jump",
    bSelfContext = true
}
```

**C++ 代码**:
```cpp
// 纯函数调用（无返回值）
Jump();

// 带返回值的函数调用
float Health = GetHealth();

// 带参数的函数调用
TakeDamage(100.0f, DamageEvent);

// 成员函数调用
MyCharacter->Jump();

// 静态函数调用
UGameplayStatics::SpawnActor(this);
```

**关键字段**:
- `FunctionReference.MemberName` - 函数名称
- `FunctionReference.bSelfContext` - 是否为 self 上下文（成员函数）
- `bIsPureFunc` - 是否为纯函数

#### K2Node_Event → C++ 事件重写

**蓝图节点**:
```cpp
// 节点属性
EventReference = FMemberReference
{
    MemberParent = "/Script/Engine.Actor",
    MemberName = "BeginPlay",
    bOverrideFunction = true
}
```

**C++ 代码**:
```cpp
// 头文件
class MYGAME_API AMyCharacter_C : public ACharacter
{
    GENERATED_BODY()

protected:
    virtual void BeginPlay() override;
};

// 实现文件
void AMyCharacter_C::BeginPlay()
{
    Super::BeginPlay();
    // 蓝图代码
}
```

**关键字段**:
- `EventReference.MemberName` - 事件名称
- `EventReference.MemberParent` - 父类路径
- `bOverrideFunction` - 是否为重写函数

### 2.2 变量节点

#### K2Node_VariableGet → 变量读取

**蓝图节点**:
```cpp
// 节点属性
VariableReference = FMemberReference
{
    MemberName = "Health",
    MemberGuid = {Guid}
}
```

**C++ 代码**:
```cpp
// 读取成员变量
float Health = this->Health;

// 读取静态变量
float MaxHealth = UMyClass::MaxHealth;
```

**关键字段**:
- `VariableReference.MemberName` - 变量名称

#### K2Node_VariableSet → 变量赋值

**蓝图节点**:
```cpp
// 节点属性
VariableReference = FMemberReference
{
    MemberName = "Health",
    MemberGuid = {Guid}
}
Value = 100.0f
```

**C++ 代码**:
```cpp
// 赋值成员变量
this->Health = 100.0f;

// 赋值静态变量
UMyClass::MaxHealth = 200.0f;
```

**关键字段**:
- `VariableReference.MemberName` - 变量名称
- `Value` - 赋值表达式

### 2.3 流控制节点

#### K2Node_IfThenElse → if/else 语句

**蓝图节点**:
```cpp
// 节点属性
Condition = (BooleanExpression)
TruePin = (Then)
FalsePin = (Else)
```

**C++ 代码**:
```cpp
if (Condition)
{
    // True 分支代码
    ThenLogic();
}
else
{
    // False 分支代码
    ElseLogic();
}
```

#### K2Node_Switch → switch 语句

**蓝图节点**:
```cpp
// 节点属性
Selection = (IntExpression)
PinNames = {Case1, Case2, Case3}
```

**C++ 代码**:
```cpp
switch (Selection)
{
    case Case1:
        // Case 1 代码
        break;
    case Case2:
        // Case 2 代码
        break;
    case Case3:
        // Case 3 代码
        break;
    default:
        // Default 代码
        break;
}
```

#### K2Node_ForLoop → for 循环

**蓝图节点**:
```cpp
// 节点属性
FirstIndex = 0
LastIndex = Count
```

**C++ 代码**:
```cpp
for (int32 i = 0; i < Count; ++i)
{
    // 循环体代码
}
```

#### K2Node_WhileLoop → while 循环

**蓝图节点**:
```cpp
// 节点属性
Condition = (BooleanExpression)
```

**C++ 代码**:
```cpp
while (Condition)
{
    // 循环体代码
}
```

### 2.4 Knot 节点

#### K2Node_Knot → 变量引用（内联）

**蓝图节点**:
```cpp
// Knot 节点（reroute）
// 用于简化连接图
```

**C++ 代码**:
```cpp
// Knot 节点被内联，不生成额外代码
// 直接使用变量引用
float Value = GetHealth();
Health = Value * 2.0f;
```

### 2.5 数学运算节点

#### K2Node_CallMath → 数学函数

**蓝图节点**:
```cpp
// 节点属性
FunctionReference = FMemberReference
{
    MemberName = "Add"
}
A = 10
B = 20
```

**C++ 代码**:
```cpp
// 使用数学库
float Result = FMath::Add(10.0f, 20.0f);

// 或使用运算符
float Result = 10.0f + 20.0f;

// 其他数学函数
float Sqrt = FMath::Sqrt(16.0f);
float Sin = FMath::Sin(PI);
float Clamp = FMath::Clamp(Value, 0.0f, 1.0f);
```

### 2.6 委托节点

#### K2Node_AddDelegate → 添加委托

**蓝图节点**:
```cpp
// 节点属性
Delegate = OnDamage
DelegateObject = this
```

**C++ 代码**:
```cpp
// 添加多播委托
OnDamage.AddDynamic(this, &AMyCharacter::OnTakeDamage);

// 或使用 += 操作符
OnDamage += this;
```

#### K2Node_RemoveDelegate → 移除委托

**蓝图节点**:
```cpp
// 节点属性
Delegate = OnDamage
DelegateObject = this
```

**C++ 代码**:
```cpp
// 移除多播委托
OnDamage.RemoveDynamic(this, &AMyCharacter::OnTakeDamage);

// 或使用 -= 操作符
OnDamage -= this;
```

#### K2Node_CallDelegate → 调用委托

**蓝图节点**:
```cpp
// 节点属性
Delegate = OnDamage
```

**C++ 代码**:
```cpp
// 调用单播委托
if (OnDamage.IsBound())
{
    OnDamage.Execute(DamageAmount);
}

// 调用多播委托
OnDamage.Broadcast(DamageAmount);
```

### 2.7 输入节点

#### K2Node_EnhancedInputAction → 增强输入动作

**蓝图节点**:
```cpp
// 节点属性
InputAction = EnhancedInputAction
```

**C++ 代码**:
```cpp
// 增强输入系统
UEnhancedInputLocalPlayerSubsystem* InputSubsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer());
if (InputSubsystem)
{
    InputSubsystem->AddInputMapping(InputMappingContext);
}
```

---

## 3. 节点编译逻辑

### 3.1 序列化

**过程**:
1. 读取节点类型
2. 读取节点属性
3. 读取输入 Pin
4. 读取输出 Pin
5. 读取连接关系

### 3.2 参数传递

**输入参数**:
- 通过输入 Pin 传递
- 按顺序推入栈
- 支持默认值

**输出参数**:
- 通过 `FOutParmRec` 记录
- 按引用传递
- 用于返回额外数据

### 3.3 返回值处理

**返回值位置**:
```cpp
#define RESULT_PARAM Z_Param__Result
```

**处理方式**:
1. 读取 `ReturnValue` Pin
2. 写入 `RESULT_PARAM` 位置
3. 返回函数调用结果

### 3.4 连接关系

**连接类型**:
- `EGPD_Input` - 输入连接
- `EGPD_Output` - 输出连接
- `EGPD_Max` - 无效连接

**处理方式**:
1. 读取 `LinkedTo` 数组
2. 解析目标节点和 Pin
3. 建立数据流关系

---

## 4. 示例代码

### 4.1 函数调用节点

```cpp
// 蓝图
// K2Node_CallFunction: Jump
// FunctionReference: MemberName="Jump", bSelfContext=true

// C++ 生成
// 头文件
UFUNCTION(BlueprintCallable, Category = "Character")
void Jump();

// 实现文件
void AMyCharacter_C::Jump()
{
    Super::Jump();
}
```

### 4.2 事件节点

```cpp
// 蓝图
// K2Node_Event: BeginPlay
// EventReference: MemberName="BeginPlay", bOverrideFunction=true

// C++ 生成
// 头文件
UFUNCTION(BlueprintOverride, Category = "Lifecycle")
void BeginPlay();

// 实现文件
void AMyCharacter_C::BeginPlay()
{
    Super::BeginPlay();

    // 蓝图事件代码
    UGameplayStatics::PlaySound2D(this, SpawnSound);
}
```

### 4.3 变量节点

```cpp
// 蓝图
// K2Node_VariableGet: Health
// K2Node_VariableSet: Health = 100.0f

// C++ 生成
// 头文件
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
float Health;

// 实现文件
this->Health = 100.0f;
float CurrentHealth = this->Health;
```

### 4.4 流控制节点

```cpp
// 蓝图
// K2Node_IfThenElse: if Health <= 0 then Die() else Continue()

// C++ 生成
if (this->Health <= 0.0f)
{
    Die();
}
else
{
    Continue();
}
```

### 4.5 委托节点

```cpp
// 蓝图
// K2Node_AddDelegate: OnDamage += OnTakeDamage
// K2Node_CallDelegate: OnDamage.Broadcast(DamageAmount)

// C++ 生成
// 头文件
UPROPERTY(BlueprintAssignable, Category = "Events")
FOnTakeDamage OnDamage;

UFUNCTION()
void OnTakeDamage(float DamageAmount);

// 实现文件
// 构造函数或 BeginPlay
OnDamage.AddDynamic(this, &AMyCharacter_C::OnTakeDamage);

// 调用时
OnDamage.Broadcast(DamageAmount);
```

---

## 5. C++ 代码生成模板

### 5.1 头文件模板

```cpp
// Auto-generated by uasset_read v5.0
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BP_MyCharacter.generated.h"

UCLASS()
class MYGAME_API ABP_MyCharacter_C : public ACharacter
{
    GENERATED_BODY()

public:
    ABP_MyCharacter_C();

protected:
    virtual void BeginPlay() override;

public:
    // 变量
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
    float Health;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
    float MaxHealth;

    // 函数
    UFUNCTION(BlueprintCallable, Category = "Character")
    void Jump();

    UFUNCTION(BlueprintCallable, Category = "Character")
    void TakeDamage(float DamageAmount);

    // 事件
    UFUNCTION(BlueprintImplementableEvent, Category = "Character")
    void OnDeath();

    // 委托
    UPROPERTY(BlueprintAssignable, Category = "Events")
    FOnTakeDamage OnDamage;
};
```

### 5.2 实现文件模板

```cpp
// Auto-generated by uasset_read v5.0
#include "BP_MyCharacter.h"

ABP_MyCharacter_C::ABP_MyCharacter_C()
{
    PrimaryActorTick.bCanEverTick = true;

    // 初始化变量
    Health = 100.0f;
    MaxHealth = 100.0f;
}

void ABP_MyCharacter_C::BeginPlay()
{
    Super::BeginPlay();

    // 蓝图事件代码
}

void ABP_MyCharacter_C::Jump()
{
    Super::Jump();
}

void ABP_MyCharacter_C::TakeDamage(float DamageAmount)
{
    Health -= DamageAmount;

    if (Health <= 0.0f)
    {
        OnDeath();
    }
}
```

---

## 6. 总结

节点到 C++ 的映射关系是蓝图转 C++ 代码生成的核心。主要映射包括：

1. **函数调用** → C++ 函数调用语句
2. **事件** → C++ 虚函数重写
3. **变量读取** → C++ 变量访问表达式
4. **变量赋值** → C++ 赋值语句
5. **流控制** → C++ if/else、switch、循环语句
6. **数学运算** → C++ 运算符或数学库函数
7. **委托操作** → C++ 委托操作（+=、-=、Broadcast）

**关键数据结构**:
- `FMemberReference` - 成员引用（函数、变量、事件）
- `UEdGraphPin` - 引脚定义（输入/输出）
- `UEdGraphNode` - 节点基类

**关键字段**:
- `MemberName` - 成员名称
- `MemberParent` - 父类路径
- `bSelfContext` - 是否为成员函数
- `bOverrideFunction` - 是否为重写函数

---

*研究完成日期：2026-05-06*