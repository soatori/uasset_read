# 蓝图虚拟机

**研究日期**: 2026-05-06
**源码版本**: UE 5.7
**主文件**:
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\Script.h`
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\Stack.h`
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\ScriptCore.cpp`

---

## 1. 虚拟机架构

### 1.1 概述

蓝图虚拟机（Kismet VM）是用于执行蓝图字节码的引擎。它采用栈式虚拟机架构，使用 FFrame 表示执行栈帧。

### 1.2 核心组件

**主要组件**:
- `FFrame` - 执行栈帧
- `FBlueprintContext` - 蓝图上下文
- `FVirtualStackAllocator` - 虚拟栈分配器
- `EExprToken` - 字节码指令集
- `GNatives` - 原生函数表

---

## 2. 虚拟机上下文

### 2.1 FFrame 结构

```cpp
struct FFrame : public FOutputDevice
{
public:
    // 当前执行的函数
    UFunction* Node;
    // 当前执行的对象
    UObject* Object;
    // 字节码指针
    uint8* Code;
    // 局部变量指针
    uint8* Locals;

    // 最近访问的属性
    FProperty* MostRecentProperty;
    // 最近访问的属性地址
    uint8* MostRecentPropertyAddress;
    // 最近访问的属性容器
    uint8* MostRecentPropertyContainer;

    // 执行流栈
    FlowStackType FlowStack;

    // 前一栈帧
    FFrame* PreviousFrame;

    // 输出参数链表
    FOutParmRec* OutParms;

    // 编译内联函数的属性链
    FField* PropertyChainForCompiledIn;

    // 当前执行的原生函数
    UFunction* CurrentNativeFunction;

    // 虚拟栈分配器缓存
    FVirtualStackAllocator* CachedThreadVirtualStackAllocator;

    // 前一追踪帧
    FFrame* PreviousTrackingFrame;

    // 数组上下文是否失败
    bool bArrayContextFailed;

    // 是否中止执行
    bool bAbortingExecution;

#if PER_FUNCTION_SCRIPT_STATS
    // 栈深度计数器
    uint8 DepthCounter;
#endif
};
```

**关键成员说明**:
- `Node` - 当前正在执行的 UFunction
- `Object` - 执行蓝图的对象
- `Code` - 字节码指针，指向当前指令
- `Locals` - 局部变量存储区域
- `FlowStack` - 执行流栈，用于处理跳转和分支
- `PreviousFrame` - 调用链中的前一帧
- `OutParms` - 输出参数列表

### 2.2 FOutParmRec 结构

```cpp
struct FOutParmRec
{
    FProperty* Property;
    uint8*      PropAddr;
    FOutParmRec* NextOutParm;
};
```

**作用**: 记录输出参数的信息，用于函数调用时的参数传递。

### 2.3 FBlueprintContext

```cpp
class FBlueprintContext
{
public:
    static FBlueprintContext* GetThreadSingleton();
    FVirtualStackAllocator* GetVirtualStackAllocator();

private:
    FVirtualStackAllocator VirtualStackAllocator;
};
```

**作用**: 提供线程局部的虚拟栈分配器，用于分配临时数据。

---

## 3. 字节码执行流程

### 3.1 Step 函数

```cpp
void FFrame::Step(UObject* Context, RESULT_DECL)
```

**功能**: 执行一条字节码指令，推进执行指针。

**执行步骤**:
1. 读取当前字节码指令
2. 根据指令类型执行相应操作
3. 推进 Code 指针
4. 处理返回值（如果有）

### 3.2 ProcessScriptFunction

```cpp
void ProcessScriptFunction(UObject* Context, UFunction* Function, FFrame& Stack, RESULT_DECL, Exec ExecFtor)
{
    FFrame NewStack(Context, Function, nullptr, &Stack, Function->ChildProperties);
    NewStack.Step(Context, RESULT_PARAM);
}
```

**功能**: 处理脚本函数的执行。

---

## 4. 虚拟机指令集

### 4.1 指令分类

#### 变量引用指令

| 指令 | 说明 |
|------|------|
| EX_LocalVariable | 局部变量 |
| EX_InstanceVariable | 对象变量 |
| EX_DefaultVariable | 类默认变量 |
| EX_LocalOutVariable | 局部输出参数（按引用传递） |

#### 控制流指令

| 指令 | 说明 |
|------|------|
| EX_Jump | 无条件跳转 |
| EX_JumpIfNot | 条件跳转（如果为假则跳转） |
| EX_ComputedJump | 计算跳转（跳转到指定地址） |
| EX_Return | 从函数返回 |
| EX_EndOfScript | 脚本结束 |

#### 常量指令

| 指令 | 说明 |
|------|------|
| EX_IntConst | 整数常量 |
| EX_IntZero | 零 |
| EX_IntOne | 一 |
| EX_FloatConst | 浮点常量 |
| EX_DoubleConst | 双精度常量 |
| EX_BoolConst | 布尔常量（EX_True/EX_False） |
| EX_StringConst | 字符串常量 |
| EX_NameConst | 名称常量 |
| EX_ObjectConst | 对象常量 |
| EX_NoObject | 空对象 |
| EX_VectorConst | 向量常量 |
| EX_RotationConst | 旋转常量 |
| EX_TransformConst | 变换常量 |
| EX_TextConst | FText 常量 |
| EX_StructConst | 结构体常量 |
| EX_EndStructConst | 结构体常量结束 |
| EX_ArrayConst | 数组常量 |
| EX_EndArrayConst | 数组常量结束 |
| EX_MapConst | 映射常量 |
| EX_EndMapConst | 映射常量结束 |
| EX_SetConst | 集合常量 |
| EX_EndSetConst | 集合常量结束 |
| EX_FieldPathConst | 字段路径常量 |
| EX_SoftObjectConst | 软对象常量 |

#### 函数调用指令

| 指令 | 说明 |
|------|------|
| EX_FinalFunction | 调用最终函数（静态绑定） |
| EX_VirtualFunction | 调用虚拟函数 |
| EX_LocalFinalFunction | 本地最终函数（快速调用） |
| EX_LocalVirtualFunction | 本地虚拟函数（快速调用） |
| EX_Context | 通过对象上下文调用函数 |
| EX_Context_FailSilent | 通过对象上下文调用函数（可静默失败） |
| EX_InterfaceContext | 通过接口上下文调用函数 |
| EX_CallMulticastDelegate | 调用多播委托 |
| EX_BindDelegate | 绑定对象和名称到委托 |
| EX_InstanceDelegate | 委托或函数对象引用 |

#### 类型转换指令

| 指令 | 说明 |
|------|------|
| EX_Cast | 类型转换（读取类型为后续字节） |
| EX_DynamicCast | 安全动态类型转换 |
| EX_MetaCast | 元类转换 |
| EX_ObjToInterfaceCast | 对象转接口 |
| EX_InterfaceToObjCast | 接口转对象 |
| EX_CrossInterfaceCast | 接口间转换 |

#### 赋值指令

| 指令 | 说明 |
|------|------|
| EX_Let | 赋值任意大小的值到变量 |
| EX_LetBool | 赋值布尔值 |
| EX_LetObj | 赋值对象引用 |
| EX_LetWeakObjPtr | 赋值弱对象指针 |
| EX_LetDelegate | 赋值委托 |
| EX_LetMulticastDelegate | 赋值多播委托 |
| EX_LetValueOnPersistentFrame | 持久帧赋值 |

#### 容器操作指令

| 指令 | 说明 |
|------|------|
| EX_SetArray | 设置数组元素 |
| EX_EndArray | 数组操作结束 |
| EX_SetSet | 设置集合元素 |
| EX_EndSet | 集合操作结束 |
| EX_SetMap | 设置映射元素 |
| EX_EndMap | 映射操作结束 |
| EX_ArrayGetByRef | 按引用获取数组元素 |

#### 流控制指令

| 指令 | 说明 |
|------|------|
| EX_PushExecutionFlow | 推入执行流地址 |
| EX_PopExecutionFlow | 弹出执行流地址 |
| EX_PopExecutionFlowIfNot | 如果条件为假则弹出执行流地址 |

#### 其他指令

| 指令 | 说明 |
|------|------|
| EX_Nothing | 无操作 |
| EX_Assert | 断言 |
| EX_Skip | 可跳过表达式 |
| EX_SkipOffsetConst | CodeSizeSkipOffset 常量 |
| EX_Self | 自身对象 |
| EX_ClassContext | 类默认对象上下文 |
| EX_StructMemberContext | 结构体成员上下文 |
| EX_ClassSparseDataVariable | 稀疏数据变量 |
| EX_AddMulticastDelegate | 添加到多播委托 |
| EX_ClearMulticastDelegate | 清空多播委托 |
| EX_RemoveMulticastDelegate | 从多播委托移除 |
| EX_SwitchValue | Switch 值 |
| EX_CallMath | 调用数学函数 |
| EX_InstrumentationEvent | 插桩事件 |
| EX_Breakpoint | 断点（仅编辑器） |
| EX_Tracepoint | 追踪点（仅编辑器） |
| EX_WireTracepoint | 线路追踪点（仅编辑器） |

### 4.2 类型转换指令（ECastToken）

```cpp
enum ECastToken : uint8
{
    CST_ObjectToInterface  = 0x00,
    CST_ObjectToBool       = 0x01,
    CST_InterfaceToBool    = 0x02,
    CST_DoubleToFloat      = 0x03,
    CST_FloatToDouble      = 0x04,
    CST_Max                = 0xFF,
};
```

---

## 5. 栈管理

### 5.1 操作栈

**用途**: 存储临时值、函数参数、返回值。

**操作**:
- 通过 `Step` 函数隐式管理
- 使用 `RESULT_PARAM` 指定返回值位置
- 使用 `MostRecentProperty` 和 `MostRecentPropertyAddress` 跟踪最近访问的属性

### 5.2 调用栈

**结构**: 链式结构，通过 `PreviousFrame` 指针连接。

**操作**:
- 函数调用时创建新 FFrame
- 函数返回时销毁当前 FFrame
- 通过 `GTopTrackingStackFrame` 线程局部变量跟踪栈顶

### 5.3 栈帧管理

```cpp
FFrame::FFrame(
    UObject* InObject,
    UFunction* InNode,
    void* InLocals,
    FFrame* InPreviousFrame = NULL,
    FField* InPropertyChainForCompiledIn = NULL
);
```

**参数说明**:
- `InObject` - 执行对象
- `InNode` - 执行的函数
- `InLocals` - 局部变量存储
- `InPreviousFrame` - 调用者栈帧
- `InPropertyChainForCompiledIn` - 编译内联函数的属性链

---

## 6. 参数传递

### 6.1 输入参数

通过栈传递，字节码按顺序将参数值推入栈。

### 6.2 输出参数

使用 `FOutParmRec` 结构记录：
- `Property` - 属性描述
- `PropAddr` - 属性地址
- `NextOutParm` - 下一个输出参数

### 6.3 返回值

通过 `RESULT_PARAM` 指定返回值位置：
```cpp
#define RESULT_PARAM Z_Param__Result
#define RESULT_DECL void*const RESULT_PARAM
```

---

## 7. 原生函数表

### 7.1 GNatives

```cpp
COREUOBJECT_API constinit TStaticArray<FNativeFuncPtr, EX_Max> GNatives(InPlace, &UObject::execUndefined);
```

**作用**: 存储所有原生函数的函数指针，按指令索引。

### 7.2 注册原生函数

```cpp
#define IMPLEMENT_VM_FUNCTION(BytecodeIndex, func) \
    STORE_INSTRUCTION_NAME(BytecodeIndex) \
    IMPLEMENT_FUNCTION(func) \
    static uint8 UObject##func##BytecodeTemp = GRegisterNative(BytecodeIndex, &UObject::func);
```

**宏说明**:
- `STORE_INSTRUCTION_NAME` - 存储指令名称（调试用）
- `IMPLEMENT_FUNCTION` - 实现函数并注册
- `GRegisterNative` - 注册到原生函数表

---

## 8. 调试支持

### 8.1 断点和追踪点

| 指令 | 说明 |
|------|------|
| EX_Breakpoint | 断点（仅编辑器中有效） |
| EX_Tracepoint | 追踪点（仅编辑器中有效） |
| EX_WireTracepoint | 线路追踪点（仅编辑器中有效） |

### 8.2 插桩事件

```cpp
namespace EScriptInstrumentation
{
    enum Type
    {
        Class = 0,
        ClassScope,
        Instance,
        Event,
        InlineEvent,
        ResumeEvent,
        PureNodeEntry,
        NodeDebugSite,
        NodeEntry,
        NodeExit,
        PushState,
        RestoreState,
        ResetState,
        SuspendState,
        PopState,
        TunnelEndOfThread,
        Stop
    };
}
```

### 8.3 调用栈追踪

```cpp
FString FFrame::GetScriptCallstack(bool bReturnEmpty, bool bTopOfStackOnly);
FString FFrame::GetStackTrace() const;
```

---

## 9. 性能优化

### 9.1 虚拟栈分配器

```cpp
FVirtualStackAllocator VirtualStackAllocator;
```

**特点**:
- 线程局部分配
- 支持批量分配和释放
- 减少内存分配开销

### 9.2 本地函数快速调用

| 指令 | 说明 |
|------|------|
| EX_LocalFinalFunction | 本地最终函数（快速调用） |
| EX_LocalVirtualFunction | 本地虚拟函数（快速调用） |

**优势**:
- 避免动态解析
- 减少函数查找开销

### 9.3 编译内联函数

```cpp
FField* PropertyChainForCompiledIn;
```

**作用**: 对于编译内联的函数，使用属性链直接设置参数，避免执行字节码。

---

## 10. 错误处理

### 10.1 脚本异常

```cpp
class FBlueprintCoreDelegates
{
    DECLARE_MULTICAST_DELEGATE_ThreeParams(FOnScriptDebuggingEvent, const UObject*, const struct FFrame&, const FBlueprintExceptionInfo&);
};
```

### 10.2 执行中止

```cpp
bool bAbortingExecution;
```

**作用**: 如果设置，立即停止执行并返回。

### 10.3 数组上下文失败

```cpp
bool bArrayContextFailed;
```

**作用**: 记录数组访问是否失败。

---

## 11. 时间限制

### 11.1 脚本时间限制器

```cpp
static FORCEINLINE void CheckRunaway()
{
    FBlueprintContextTracker& ContextTracker = FBlueprintContextTracker::Get();
    int32 RunawayCount = ContextTracker.AddRunaway();

    if (UNLIKELY((RunawayCount & 0xFF) == 0))
    {
        ContextTracker.EnforceScriptTimeLimit();
    }
}
```

### 11.2 配置参数

```cpp
static int32 GScriptRecurseLimit = 120;
static int32 GMaximumScriptLoopIterations = 1000000;
```

---

## 12. 统计信息

### 12.1 总体统计

```cpp
DECLARE_FLOAT_COUNTER_STAT_EXTERN(TEXT("Blueprint - (All) VM Time (ms)"), STAT_ScriptVmTime_Total, STATGROUP_Script, COREUOBJECT_API);
DECLARE_FLOAT_COUNTER_STAT_EXTERN(TEXT("Blueprint - (All) Native Time (ms)"), STAT_ScriptNativeTime_Total, STATGROUP_Script, COREUOBJECT_API);
```

### 12.2 函数级统计

```cpp
static int32 GMaxFunctionStatDepth = MAX_uint8;
```

**作用**: 记录每个函数的执行时间。

---

## 13. 总结

蓝图虚拟机采用栈式架构，使用 FFrame 表示执行栈帧，通过 EExprToken 指令集执行蓝图字节码。主要特点：

1. **栈式虚拟机** - 使用操作栈存储临时值和参数
2. **链式调用栈** - 通过 PreviousFrame 连接调用链
3. **指令集丰富** - 包含变量、控制流、函数调用、类型转换等指令
4. **性能优化** - 本地函数快速调用、编译内联、虚拟栈分配器
5. **调试支持** - 断点、追踪点、插桩事件、调用栈追踪
6. **错误处理** - 异常委托、执行中止、数组上下文失败
7. **时间限制** - 防止无限循环和递归过深

---

*研究完成日期：2026-05-06*