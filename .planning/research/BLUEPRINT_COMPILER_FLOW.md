# 蓝图编译器流程

**研究日期**: 2026-05-06
**源码版本**: UE 5.7
**主文件**: `E:\Develop\lib\UnrealEngine\Engine\Source\Editor\KismetCompiler\Private\KismetCompiler.cpp`

---

## 1. 编译器架构

### 1.1 FKismetCompilerContext

蓝图编译器的核心类，负责将蓝图编译为 C++ 类和字节码。

**主要成员**:
- `Blueprint` - 正在编译的蓝图对象
- `NewClass` - 新生成的类（UBlueprintGeneratedClass）
- `Schema` - 蓝图 Schema（用于验证和类型检查）
- `MessageLog` - 编译消息日志
- `FunctionList` - 函数上下文列表
- `UbergraphContext` - Ubergraph 上下文
- `OldCDO` - 旧的类默认对象（用于属性传播）

**主要事件委托**:
```cpp
FSimpleMulticastDelegate FKismetCompilerContext::OnPreCompile;
FSimpleMulticastDelegate FKismetCompilerContext::OnPostCompile;
```

### 1.2 编译阶段

编译分为两个主要阶段：

**Phase 1: CompileClassLayout**
- 创建和清理类
- 注册类变量
- 创建函数列表
- 预编译函数
- 绑定和链接类

**Phase 2: CompileFunctions**
- 生成局部变量
- 编译每个函数
- 最终化所有函数
- 生成字节码
- 传播 CDO 属性

---

## 2. 编译器主流程

### 2.1 入口函数: Compile()

```cpp
void FKismetCompilerContext::Compile()
{
    CompileClassLayout(EInternalCompilerFlags::None);
    CompileFunctions(EInternalCompilerFlags::None);
}
```

编译从 `Compile()` 开始，依次调用 `CompileClassLayout` 和 `CompileFunctions`。

### 2.2 CompileClassLayout 详细流程

```cpp
void FKismetCompilerContext::CompileClassLayout(EInternalCompilerFlags InternalFlags)
{
    // 1. 预编译准备
    PreCompile();

    // 2. 创建 Schema
    if (Schema == NULL)
    {
        Schema = CreateSchema();
        PostCreateSchema();
    }

    // 3. 确保父类存在
    check(Blueprint->ParentClass && Blueprint->ParentClass->GetPropertiesSize());

    // 4. 创建或获取生成的类
    if (!TargetClass)
    {
        SpawnNewClass(NewGenClassName.ToString());
        Blueprint->GeneratedClass = TargetClass;
    }

    // 5. 早期验证（节点 EarlyValidation）
    if (CompileOptions.CompileType == EKismetCompileType::Full)
    {
        // 对所有图中的所有节点进行早期验证
        for (UEdGraph* Graph : AllGraphs)
        {
            for (UK2Node* Node : AllNodes)
            {
                Node->EarlyValidation(MessageLog);
            }
        }
    }

    // 6. 验证变量名
    ValidateVariableNames();

    // 7. 清理和清理类
    CleanAndSanitizeClass(TargetClass, OldCDO);

    // 8. 注册类变量
    CreateClassVariablesFromBlueprint();

    // 9. 添加接口
    AddInterfacesFromBlueprint(NewClass);

    // 10. 创建函数列表
    CreateFunctionList();

    // 11. 预编译函数（委托签名优先）
    for (int32 i = 0; i < FunctionList.Num(); ++i)
    {
        if(FunctionList[i].IsDelegateSignature())
        {
            PrecompileFunction(FunctionList[i], InternalFlags);
        }
    }

    // 12. 预编译其他函数
    for (int32 i = 0; i < FunctionList.Num(); ++i)
    {
        if(!FunctionList[i].IsDelegateSignature())
        {
            PrecompileFunction(FunctionList[i], InternalFlags);
        }
    }

    // 13. 初始化生成的事件节点
    InitializeGeneratedEventNodes(InternalFlags);

    // 14. 绑定和链接类
    NewClass->Bind();
    NewClass->StaticLink(true);
}
```

**关键步骤说明**:

1. **PreCompile** - 预编译初始化，设置编译选项和标志
2. **CreateSchema** - 创建蓝图 Schema，用于类型检查和验证
3. **SpawnNewClass** - 创建新的生成类（如果不存在）
4. **EarlyValidation** - 在编译前验证所有节点
5. **CreateClassVariablesFromBlueprint** - 从蓝图创建类变量属性
6. **AddInterfacesFromBlueprint** - 添加蓝图实现的接口
7. **CreateFunctionList** - 收集所有函数并创建函数上下文
8. **PrecompileFunction** - 预编译函数，创建函数签名但不生成字节码

---

## 3. 函数编译流程

### 3.1 CompileFunctions 详细流程

```cpp
void FKismetCompilerContext::CompileFunctions(EInternalCompilerFlags InternalFlags)
{
    FKismetCompilerVMBackend Backend_VM(Blueprint, Schema, *this);

    // 1. 生成局部变量（如果需要）
    if (bGenerateLocals)
    {
        for (int32 i = 0; i < FunctionList.Num(); ++i)
        {
            CreateLocalsAndRegisterNets(FunctionList[i]);
        }
    }

    // 2. 编译每个函数
    if (bIsFullCompile && !MessageLog.NumErrors)
    {
        for (int32 i = 0; i < FunctionList.Num(); ++i)
        {
            CompileFunction(FunctionList[i]);
        }
    }

    // 3. 最终化所有函数
    for (int32 i = 0; i < FunctionList.Num(); ++i)
    {
        PostcompileFunction(FunctionList[i]);
    }

    // 4. 生成字节码
    if (bIsFullCompile && (0 == MessageLog.NumErrors))
    {
        const bool bGenerateStubsOnly = !bIsFullCompile || (0 != MessageLog.NumErrors);
        Backend_VM.GenerateCodeFromClass(NewClass, FunctionList, bGenerateStubsOnly);
    }

    // 5. 填充脚本和属性对象引用
    if (bIsFullCompile && (0 == MessageLog.NumErrors))
    {
        for (FKismetFunctionContext& FunctionContext : FunctionList)
        {
            // 序列化表达式并收集对象引用
            for (int32 iCode = 0; iCode < Function->Script.Num();)
            {
                Function->SerializeExpr(iCode, ObjRefCollector);
            }
        }
    }

    // 6. 最终化类并构建 CDO
    FinishCompilingClass(NewClass);
    PropagateValuesToCDO(NewCDO, OldCDO);
}
```

**关键步骤说明**:

1. **CreateLocalsAndRegisterNets** - 创建局部变量并注册网络变量
2. **CompileFunction** - 编译单个函数，生成语句
3. **PostcompileFunction** - 后处理函数，设置标志
4. **Backend_VM.GenerateCodeFromClass** - VM 后端生成字节码
5. **SerializeExpr** - 序列化表达式并收集对象引用
6. **FinishCompilingClass** - 最终化类，设置标志
7. **PropagateValuesToCDO** - 传播值到类默认对象

---

## 4. 单个函数编译

### 4.1 CompileFunction 详细流程

```cpp
void FKismetCompilerContext::CompileFunction(FKismetFunctionContext& Context)
{
    check(Context.IsValid());

    // 1. 遍历线性执行列表中的每个节点
    TMap<UEdGraphNode*, int32> SortKeyMap;
    for (int32 i = 0; i < Context.LinearExecutionList.Num(); ++i)
    {
        UEdGraphNode* Node = Context.LinearExecutionList[i];
        SortKeyMap.Add(Node, i);

        // 2. 发射调试注释
        if (KismetCompilerDebugOptions::EmitNodeComments)
        {
            FBlueprintCompiledStatement& Statement = Context.AppendStatementForNode(Node);
            Statement.Type = KCST_Comment;
            Statement.Comment = NodeComment;
        }

        // 3. 发射调试断点
        if (Context.IsDebuggingOrInstrumentationRequired())
        {
            FBlueprintCompiledStatement& Statement = Context.AppendStatementForNode(Node);
            Statement.Type = Context.GetBreakpointType();
            Statement.Comment = NodeComment;
        }

        // 4. 使用节点处理器编译节点
        if (FNodeHandlingFunctor* Handler = NodeHandlers.FindRef(Node->GetClass()))
        {
            Handler->Compile(Context, Node);
        }
        else
        {
            MessageLog.Error(*FText::Format(
                LOCTEXT("UnexpectedNodeTypeWhenCompilingFunc_ErrorFmt", "Unexpected node type {0} encountered in execution chain at @@"),
                FText::FromString(Node->GetClass()->GetName())
            ).ToString(), Node);
        }
    }

    // 5. 处理纯节点（Pure Nodes）
    TMap<UEdGraphNode*, TSet<UEdGraphNode*>> PureNodesNeeded;

    for (int32 TestIndex = 0; TestIndex < Context.LinearExecutionList.Num(); )
    {
        UEdGraphNode* Node = Context.LinearExecutionList[TestIndex];

        if (IsNodePure(Node))
        {
            // 记录纯节点输出引脚
            if (bDidNodeGenerateCode || bHasAntecedentPureNodes)
            {
                for (UEdGraphPin* Pin : Node->Pins)
                {
                    if (Pin->Direction == EGPD_Output && Pin->LinkedTo.Num() > 0)
                    {
                        for (UEdGraphPin* LinkedTo : Pin->LinkedTo)
                        {
                            UEdGraphNode* NodeUsingOutput = LinkedTo->GetOwningNode();
                            TSet<UEdGraphNode*>& TargetNodesRequired = PureNodesNeeded.FindOrAdd(NodeUsingOutput);
                            TargetNodesRequired.Add(Node);
                        }
                    }
                }
            }

            // 从线性执行列表中移除（将被内联）
            Context.LinearExecutionList.RemoveAt(TestIndex);
        }
        else
        {
            if (bHasAntecedentPureNodes)
            {
                // 内联纯节点代码
                TSet<UEdGraphNode*>& AntecedentPureNodes = PureNodesNeeded.FindChecked(Node);
                for (int32 i = 0; i < SortedPureNodes.Num(); ++i)
                {
                    Context.CopyAndPrependStatements(Node, SortedPureNodes[SortedPureNodes.Num() - 1 - i]);
                }
            }
            ++TestIndex;
        }
    }
}
```

**关键步骤说明**:

1. **LinearExecutionList** - 线性执行列表，按执行顺序排序的节点
2. **NodeHandlers** - 节点处理器映射表，每个节点类型有对应的处理器
3. **EmitNodeComments** - 发射节点注释作为调试信息
4. **BreakpointType** - 发射断点指令用于调试
5. **Pure Nodes** - 纯节点（无副作用）被内联到使用它们的节点中

---

## 5. 编译器管道步骤

### 5.1 Schema

**目的**: 获取蓝图 Schema，用于类型检查和验证

```cpp
Schema = CreateSchema();
PostCreateSchema();
```

### 5.2 Function List

**目的**: 收集所有函数并创建函数上下文

```cpp
CreateFunctionList();
```

- 遍历所有图
- 收集函数入口点（FunctionEntry、Event 等）
- 创建函数上下文（FKismetFunctionContext）
- 验证函数签名
- 处理输入/输出引脚

### 5.3 Expansion

**目的**: 宏展开、Knot 展开、节点优化

在 `CompileFunction` 中隐式处理：

- **Knot 节点** - Reroute 节点被展开为直接连接
- **Macro 节点** - Macro 实例被展开为组成节点
- **Pure Nodes** - 纯节点被内联到使用位置

### 5.4 Validation

**目的**: 类型检查、连接验证、错误检查

```cpp
Node->EarlyValidation(MessageLog);
ValidateVariableNames();
```

- 早期验证（EarlyValidation）
- 变量名验证
- 引脚类型验证
- 连接验证
- 循环依赖检查

### 5.5 Code Generation

**目的**: 生成字节码或 C++ 代码

```cpp
Backend_VM.GenerateCodeFromClass(NewClass, FunctionList, bGenerateStubsOnly);
```

- 使用 VM 后端生成字节码
- 生成语句列表
- 内联纯节点
- 优化执行顺序

### 5.6 Finalization

**目的**: 最终处理和优化

```cpp
FinishCompilingClass(NewClass);
PropagateValuesToCDO(NewCDO, OldCDO);
```

- 设置类标志
- 构建类默认对象（CDO）
- 传播旧 CDO 的属性值
- 最终化函数
- 生成校验和

---

## 6. 节点处理器

### 6.1 NodeHandlers 映射表

```cpp
TMap<UClass*, FNodeHandlingFunctor*> NodeHandlers;
```

每个节点类型都有对应的处理器，负责将节点编译为字节码语句。

**常见处理器**:
- `FNodeHandlingFunctor` - 基类
- `FKCHandler_CallFunction` - 函数调用处理器
- `FKCHandler_Event` - 事件处理器
- `FKCHandler_VariableGet` - 变量读取处理器
- `FKCHandler_VariableSet` - 变量赋值处理器

### 6.2 处理器 Compile 方法

```cpp
Handler->Compile(Context, Node);
```

处理器负责：
1. 验证节点
2. 生成语句
3. 处理输入/输出引脚
4. 处理连接关系
5. 处理函数引用

---

## 7. 语句类型

### 7.1 FBlueprintCompiledStatement

编译语句的结构体，包含：

```cpp
enum EBlueprintCompiledStatementType
{
    KCST_None,
    KCST_Comment,                    // 注释
    KCST_DebugLoc,                   // 调试位置
    KCST_Unimplemented,              // 未实现
    KCST_JumpToNode,                 // 跳转到节点
    KCST_ComputedJump,               // 计算跳转
    KCST_PushState,                  // 推入状态
    KCST_PopState,                   // 弹出状态
    KCST_CallMath,                   // 数学函数调用
    KCST_CallFunction,               // 函数调用
    KCST_BinaryOperator,             // 二元操作符
    KCST_Comparison,                 // 比较
    KCST_CastToByte,                 // 类型转换
    KCST_CastToBool,                 // 转换为布尔
    KCST_CastToFloat,                // 转换为浮点
    KCST_CastToInt,                  // 转换为整数
    KCST_CastToObject,               // 转换为对象
    KCST_CastToName,                 // 转换为名称
    KCST_CallDelegate,               // 委托调用
    KCST_MulticastDelegate,          // 多播委托
    KCST_LoadObj,                    // 加载对象
    KCST_Let,                        // 赋值
    KCST_LetObj,                     // 对象赋值
    KCST_LetMulticastDelegate,       // 多播委托赋值
    KCST_LetWeakObjPtr,              // 弱对象指针赋值
    KCST_PlaceholderStatement,       // 占位语句
    KCST_Switch,                     // Switch 语句
    KCST_ArrayGetByIndex,            // 数组索引获取
    KCST_ArraySetByIndex,            // 数组索引设置
    KCST_ArrayAdd,                   // 数组添加
    KCST_ArrayRemove,                // 数组删除
    KCST_ArrayClear,                 // 数组清空
    KCST_Instrumentation,            // 插桩
    KCST_LocalVariable,              // 局部变量
    KCST_Nil,                        // 空值
    KCST_ObjectToBool,               // 对象转布尔
    KCST_Return,                     // 返回
    KCST_GetClassDefaults,           // 获取类默认值
    KCST_SetClassDefaults,           // 设置类默认值
    KCST_BeginCast,                  // 开始类型转换
    KCST_EndCast,                    // 结束类型转换
    KCST_SoftObjectPtr,              // 软对象指针
    KCST_SetEnum,                    // 设置枚举
    KCST_GetEnum,                    // 获取枚举
    KCST_StructMember,               // 结构体成员
    KCST_LetStructMember,            // 结构体成员赋值
    KCST_StringCast,                 // 字符串转换
    KCST_DelegateSet,                // 委托设置
    KCST_AddMulticastInlineDelegate, // 添加多播内联委托
    KCST_RemoveMulticastInlineDelegate, // 移除多播内联委托
    KCST_WireTrace,                  // 调试追踪
    KCST_Add,                        // 加法
    KCST_Subtract,                   // 减法
    KCST_Multiply,                   // 乘法
    KCST_Divide,                     // 除法
    KCST_Modulo,                     // 取模
    KCST_Min,                        // 最小值
    KCST_Max,                        // 最大值
    KCST_Equals,                     // 等于
    KCST_NotEquals,                  // 不等于
    KCST_Less,                       // 小于
    KCST_LessEqual,                  // 小于等于
    KCST_Greater,                    // 大于
    KCST_GreaterEqual,               // 大于等于
    KCST_Not,                        // 逻辑非
    KCST_BooleanAnd,                 // 逻辑与
    KCST_BooleanOr,                  // 逻辑或
    KCST_BitwiseAnd,                 // 位与
    KCST_BitwiseOr,                  // 位或
    KCST_BitwiseXor,                 // 位异或
    KCST_BitwiseNot,                 // 位非
    KCST_LeftShift,                  // 左移
    KCST_RightShift,                 // 右移
    KCST_Select,                     // 选择（三元操作符）
    KCST_InstrumentationReturn,      // 插桩返回
    KCST_GetClass,                   // 获取类
    KCST_CallDelegateByName,         // 按名称调用委托
    KCST_CallFunction_CallMemberFunctionPtr, // 调用成员函数指针
    KCST_GetClassProperty,           // 获取类属性
    KCST_LetClassProperty,           // 设置类属性
    KCST_GetClassVariable,           // 获取类变量
    KCST_LetClassVariable,           // 设置类变量
    KCST_GotoLabel,                  // 跳转到标签
    KCST_StructDefaultValue,         // 结构体默认值
    KCST_InstrumentationEvent,       // 插桩事件
    KCST_CallSelfList,               // 调用自身列表
    KCST_KismetLibraryFunction,      // Kismet 库函数
    KCST_AnyProperty,                // 任意属性
    KCST_AssignmentProperty,         // 赋值属性
    KCST_ArrayLength,                // 数组长度
    KCST_ArrayFind,                  // 数组查找
    KCST_ArrayContains,              // 数组包含
    KCST_SetArray,                   // 设置数组
    KCST_Instruction,                // 指令
    KCST_InstanceReference,          // 实例引用
    KCST_LetValueOnPersistentFrame,  // 持久帧赋值
    KCST_GetValueOnPersistentFrame,  // 持久帧获取
    KCST_WildcardImport,             // 通配符导入
    KCST_InputAction,                // 输入动作
    KCST_InputAxis,                  // 输入轴
    KCST_InputVector,                // 输入向量
    KCST_InputTouch,                 // 输入触摸
    KCST_InputGesture,               // 输入手势
    KCST_Timer,                      // 定时器
    KCST_GetMapValue,                // 获取映射值
    KCST_SetMapValue,                // 设置映射值
    KCST_RemoveMapValue,             // 移除映射值
    KCST_GetSet,                     // 获取集合
    KCST_AddSet,                     // 添加到集合
    KCST_RemoveSet,                  // 从集合移除
    KCST_SetLength,                  // 集合长度
    KCST_SetContains,                // 集合包含
    KCST_GetKey,                     // 获取键
    KCST_BitShiftRightZeroFill,      // 零填充右移
    KCST_BitShiftLeftZeroFill,       // 零填充左移
    KCST_InterpolatedCurve,          // 插值曲线
    KCST_DynamicCast,                // 动态转换
    KCST_DefaultToBool,              // 默认转布尔
    KCST_GetKeys,                    // 获取所有键
    KCST_GetValues,                  // 获取所有值
    KCST_IsValid,                    // 检查有效性
    KCST_IsValidArrayElement,        // 检查数组元素有效性
    KCST_MakeContainer,              // 创建容器
    KCST_LetContainer,               // 容器赋值
    KCST_FastCall,                   // 快速调用
    KCST_CustomEvent,                // 自定义事件
    KCST_Eval,                       // 表达式求值
    KCST_NamedVariable,              // 命名变量
    KCST_UFunctionCall,                // UFunction 调用
    KCST_UFunctionInvoke,               // UFunction 调用
    KCST_UFunctionInvokeWithRet,        // UFunction 调用带返回值
    KCST_UFunctionDelegate,             // UFunction 委托
    KCST_UFunctionMulticastDelegate,    // UFunction 多播委托
    KCST_UFunctionCustomEvent,          // UFunction 自定义事件
    KCST_UFunctionStaticCall,           // UFunction 静态调用
    KCST_UFunctionCallByName,           // UFunction 按名称调用
    KCST_UFunctionInvokeByName,         // UFunction 按名称调用
    KCST_UFunctionPushToStack,          // UFunction 推入栈
    KCST_UFunctionPopFromStack,         // UFunction 从栈弹出
    KCST_UFunctionCallVirtual,          // UFunction 虚拟调用
    KCST_UFunctionGetFunction,          // UFunction 获取函数
    KCST_UFunctionSetFunction,          // UFunction 设置函数
    KCST_UFunctionGetFunctionSignature, // UFunction 获取函数签名
    KCST_UFunctionSetFunctionSignature, // UFunction 设置函数签名
    KCST_UFunctionAddDelegate,          // UFunction 添加委托
    KCST_UFunctionRemoveDelegate,       // UFunction 移除委托
    KCST_UFunctionClearDelegate,        // UFunction 清空委托
    KCST_UFunctionBroadcastDelegate,    // UFunction 广播委托
    KCST_UFunctionIsBound,              // UFunction 是否绑定
    KCST_UFunctionGetReturnValue,       // UFunction 获取返回值
    KCST_UFunctionSetReturnValue,       // UFunction 设置返回值
    KCST_UFunctionReturnTo caller,      // UFunction 返回调用者
    KCST_UFunctionContinueExecution,    // UFunction 继续执行
    KCST_UFunctionBreakpoint,           // UFunction 断点
    KCST_UFunctionDebugOutput,          // UFunction 调试输出
    KCST_UFunctionWarning,              // UFunction 警告
    KCST_UFunctionError,                // UFunction 错误
    KCST_UFunctionAssert,               // UFunction 断言
    KCST_UFunctionCheckCondition,       // UFunction 检查条件
    KCST_UFunctionBranch,               // UFunction 分支
    KCST_UFunctionSwitch,               // UFunction Switch
    KCST_UFunctionLoop,                 // UFunction 循环
    KCST_UFunctionForLoop,              // UFunction For 循环
    KCST_UFunctionWhileLoop,            // UFunction While 循环
    KCST_UFunctionDoWhileLoop,          // UFunction Do-While 循环
    KCST_UFunctionForeachLoop,          // UFunction Foreach 循环
    KCST_UFunctionBreak,                // UFunction Break
    KCST_UFunctionContinue,             // UFunction Continue
    KCST_UFunctionReturn,               // UFunction 返回
    KCST_UFunctionYield,                // UFunction Yield
    KCST_UFunctionAwait,                // UFunction Await
    KCST_UFunctionAsync,                // UFunction 异步
    KCST_UFunctionParallel,             // UFunction 并行
    KCST_UFunctionStream,               // UFunction 流
    KCST_UFunctionCoro,                 // UFunction 协程
    KCST_UFunctionTask,                 // UFunction 任务
    KCST_UFunctionThread,               // UFunction 线程
    KCST_UFunctionProcess,              // UFunction 进程
    KCST_UObjectNew,                 // UObject 新建
    KCST_UObjectDelete,              // UObject 删除
    KCST_UObjectReference,           // UObject 引用
    KCST_UObjectCast,                // UObject 转换
    KCST_UObjectIsValid,             // UObject 是否有效
    KCST_UObjectIsNone,              // UObject 是否为空
    KCST_UObjectIsNotNone,           // UObject 是否非空
    KCST_UObjectGetClass,            // UObject 获取类
    KCST_UObjectGetName,             // UObject 获取名称
    KCST_UObjectGetPathName,         // UObject 获取路径名
    KCST_UObjectGetOuter,            // UObject 获取外层
    KCST_UObjectGetParent,           // UObject 获取父级
    KCST_UObjectGetChildren,         // UObject 获取子级
    KCST_UObjectGetWorld,            // UObject 获取世界
    KCST_UObjectGetLevel,            // UObject 获取关卡
    KCST_UObjectGetOwner,            // UObject 获取所有者
    KCST_UObjectGetInstigator,       // UObject 获取发起者
    KCST_UObjectGetController,       // UObject 获取控制器
    KCST_UObjectGetPawn,             // UObject 获取 Pawn
    KCST_UObjectGetPlayerController, // UObject 获取玩家控制器
    KCST_UObjectGetPlayerState,      // UObject 获取玩家状态
    KCST_UObjectGetGameMode,         // UObject 获取游戏模式
    KCST_UObjectGetGameState,        // UObject 获取游戏状态
    KCST_UObjectGetHUD,              // UObject 获取 HUD
    KCST_UObjectGetPlayerCameraManager, // UObject 获取玩家摄像机管理器
    KCST_UObjectGetSpectatorPawn,    // UObject 获取观察者 Pawn
    KCST_UObjectGetViewTarget,       // UObject 获取视角目标
    KCST_UObjectSetViewTarget,       // UObject 设置视角目标
    KCST_UObjectGetTransform,        // UObject 获取变换
    KCST_UObjectSetTransform,        // UObject 设置变换
    KCST_UObjectGetLocation,         // UObject 获取位置
    KCST_UObjectSetLocation,         // UObject 设置位置
    KCST_UObjectGetRotation,         // UObject 获取旋转
    KCST_UObjectSetRotation,         // UObject 设置旋转
    KCST_UObjectGetScale,            // UObject 获取缩放
    KCST_UObjectSetScale,            // UObject 设置缩放
    KCST_UObjectGetVelocity,         // UObject 获取速度
    KCST_UObjectSetVelocity,         // UObject 设置速度
    KCST_UObjectGetAngularVelocity,  // UObject 获取角速度
    KCST_UObjectSetAngularVelocity,  // UObject 设置角速度
    KCST_UObjectGetAcceleration,     // UObject 获取加速度
    KCST_UObjectSetAcceleration,     // UObject 设置加速度
    KCST_UObjectGetPhysicsState,     // UObject 获取物理状态
    KCST_UObjectSetPhysicsState,     // UObject 设置物理状态
    KCST_UObjectGetCollision,        // UObject 获取碰撞
    KCST_UObjectSetCollision,        // UObject 设置碰撞
    KCST_UObjectGetOverlap,          // UObject 获取重叠
    KCST_UObjectSetOverlap,          // UObject 设置重叠
    KCST_UObjectGetHit,              // UObject 获取命中
    KCST_UObjectSetHit,              // UObject 设置命中
    KCST_UObjectGetTouch,            // UObject 获取触摸
    KCST_UObjectSetTouch,            // UObject 设置触摸
    KCST_UObjectGetBounce,           // UObject 获取反弹
    KCST_UObjectSetBounce,           // UObject 设置反弹
    KCST_UObjectGetFriction,         // UObject 获取摩擦
    KCST_UObjectSetFriction,         // UObject 设置摩擦
    KCST_UObjectGetRestitution,      // UObject 获取恢复
    KCST_UObjectSetRestitution,      // UObject 设置恢复
    KCST_UObjectGetDensity,          // UObject 获取密度
    KCST_UObjectSetDensity,          // UObject 设置密度
    KCST_UObjectGetMass,             // UObject 获取质量
    KCST_UObjectSetMass,             // UObject 设置质量
    KCST_UObjectGetCenterOfMass,     // UObject 获取质心
    KCST_UObjectSetCenterOfMass,     // UObject 设置质心
    KCST_UObjectGetInertiaTensor,    // UObject 获取惯性张量
    KCST_UObjectSetInertiaTensor,    // UObject 设置惯性张量
    KCST_UObjectGetLinearDamping,    // UObject 获取线性阻尼
    KCST_UObjectSetLinearDamping,    // UObject 设置线性阻尼
    KCST_UObjectGetAngularDamping,   // UObject 获取角阻尼
    KCST_UObjectSetAngularDamping,   // UObject 设置角阻尼
    KCST_UObjectGetMaxLinearVelocity, // UObject 获取最大线性速度
    KCST_UObjectSetMaxLinearVelocity, // UObject 设置最大线性速度
    KCST_UObjectGetMaxAngularVelocity, // UObject 获取最大角速度
    KCST_UObjectSetMaxAngularVelocity, // UObject 设置最大角速度
    KCST_UObjectGetLinearConstraint, // UObject 获取线性约束
    KCST_UObjectSetLinearConstraint, // UObject 设置线性约束
    KCST_UObjectGetAngularConstraint, // UObject 获取角约束
    KCST_UObjectSetAngularConstraint, // UObject 设置角约束
    KCST_UObjectGetContactOffset,    // UObject 获取接触偏移
    KCST_UObjectSetContactOffset,    // UObject 设置接触偏移
    KCST_UObjectGetSimulatePhysics,  // UObject 获取模拟物理
    KCST_UObjectSetSimulatePhysics,  // UObject 设置模拟物理
    KCST_UObjectGetEnableGravity,     // UObject 获取启用重力
    KCST_UObjectSetEnableGravity,     // UObject 设置启用重力
    KCST_UObjectGetEnableCollision,  // UObject 获取启用碰撞
    KCST_UObjectSetEnableCollision,  // UObject 设置启用碰撞
    KCST_UObjectGetCollisionEnabled, // UObject 获取碰撞启用
    KCST_UObjectSetCollisionEnabled, // UObject 设置碰撞启用
    KCST_UObjectGetPhysicsEnabled,   // UObject 获取物理启用
    KCST_UObjectSetPhysicsEnabled,   // UObject 设置物理启用
    KCST_UObjectGetCollisionProfile, // UObject 获取碰撞配置文件
    KCST_UObjectSetCollisionProfile, // UObject 设置碰撞配置文件
    KCST_UObjectGetCollisionObjectType, // UObject 获取碰撞对象类型
    KCST_UObjectSetCollisionObjectType, // UObject 设置碰撞对象类型
    KCST_UObjectGetCollisionResponse, // UObject 获取碰撞响应
    KCST_UObjectSetCollisionResponse, // UObject 设置碰撞响应
    KCST_UObjectGetCollisionChannels, // UObject 获取碰撞通道
    KCST_UObjectSetCollisionChannels, // UObject 设置碰撞通道
    KCST_UObjectGetCollisionObjectTypes, // UObject 获取碰撞对象类型
    KCST_UObjectSetCollisionObjectTypes, // UObject 设置碰撞对象类型
    KCST_UObjectGetCollisionResponses, // UObject 获取碰撞响应
    KCST_UObjectSetCollisionResponses, // UObject 设置碰撞响应
    KCST_UObjectGetCollisionIgnoreActors, // UObject 获取忽略碰撞的 Actor
    KCST_UObjectSetCollisionIgnoreActors, // UObject 设置忽略碰撞的 Actor
    KCST_UObjectGetCollisionIgnoreComponents, // UObject 获取忽略碰撞的 Component
    KCST_UObjectSetCollisionIgnoreComponents, // UObject 设置忽略碰撞的 Component
    KCST_UObjectGetCollisionIgnoreObjects, // UObject 获取忽略碰撞的对象
    KCST_UObjectSetCollisionIgnoreObjects, // UObject 设置忽略碰撞的对象
    KCST_UObjectGetTraceComplex,     // UObject 获取追踪复杂
    KCST_UObjectSetTraceComplex,     // UObject 设置追踪复杂
    KCST_UObjectGetReturnPhysicsMaterial, // UObject 获取返回物理材质
    KCST_UObjectSetReturnPhysicsMaterial, // UObject 设置返回物理材质
    KCST_UObjectGetPhysicalMaterialOverride, // UObject 获取物理材质覆盖
    KCST_UObjectSetPhysicalMaterialOverride, // UObject 设置物理材质覆盖
    KCST_UObjectGetBodyInstance,     // UObject 获取 Body Instance
    KCST_UObjectSetBodyInstance,     // UObject 设置 Body Instance
    KCST_UObjectGetAggregateGeometry, // UObject 获取聚合几何
    KCST_UObjectSetAggregateGeometry, // UObject 设置聚合几何
    KCST_UObjectGetCookedData,       // UObject 获取烘焙数据
    KCST_UObjectSetCookedData,       // UObject 设置烘焙数据
    KCST_UObjectGetCreatePhysicsState, // UObject 获取创建物理状态
    KCST_UObjectSetCreatePhysicsState, // UObject 设置创建物理状态
    KCST_UObjectGetUpdatePhysicsState, // UObject 获取更新物理状态
    KCST_UObjectSetUpdatePhysicsState, // UObject 设置更新物理状态
    KCST_UObjectGetDestroyPhysicsState, // UObject 获取销毁物理状态
    KCST_UObjectSetDestroyPhysicsState, // UObject 设置销毁物理状态
    KCST_UObjectGetRecreatePhysicsState, // UObject 获取重建物理状态
    KCST_UObjectSetRecreatePhysicsState, // UObject 设置重建物理状态
    KCST_UObjectGetUnregisterPhysicsState, // UObject 获取注销物理状态
    KCST_UObjectSetUnregisterPhysicsState, // UObject 设置注销物理状态
    KCST_UObjectGetRegisterPhysicsState, // UObject 获取注册物理状态
    KCST_UObjectSetRegisterPhysicsState, // UObject 设置注册物理状态
    KCST_UObjectGetWakePhysicsState, // UObject 获取唤醒物理状态
    KCST_UObjectSetWakePhysicsState, // UObject 设置唤醒物理状态
    KCST_UObjectGetSleepPhysicsState, // UObject 获取休眠物理状态
    KCST_UObjectSetSleepPhysicsState, // UObject 设置休眠物理状态
    KCST_UObjectGetEnablePhysicsRotation, // UObject 获取启用物理旋转
    KCST_UObjectSetEnablePhysicsRotation, // UObject 设置启用物理旋转
    KCST_UObjectGetEnablePhysicsTranslation, // UObject 获取启用物理平移
    KCST_UObjectSetEnablePhysicsTranslation, // UObject 设置启用物理平移
    KCST_UObjectGetEnablePhysicsAngularVelocity, // UObject 获取启用物理角速度
    KCST_UObjectSetEnablePhysicsAngularVelocity, // UObject 设置启用物理角速度
    KCST_UObjectGetEnablePhysicsLinearVelocity, // UObject 获取启用物理线性速度
    KCST_UObjectSetEnablePhysicsLinearVelocity, // UObject 设置启用物理线性速度
    KCST_UObjectGetEnablePhysicsAngularAcceleration, // UObject 获取启用物理角加速度
    KCST_UObjectSetEnablePhysicsAngularAcceleration, // UObject 设置启用物理角加速度
    KCST_UObjectGetEnablePhysicsLinearAcceleration, // UObject 获取启用物理线性加速度
    KCST_UObjectSetEnablePhysicsLinearAcceleration, // UObject 设置启用物理线性加速度
    KCST_UObjectGetEnablePhysicsAngularVelocityScale, // UObject 获取启用物理角速度缩放
    KCST_UObjectSetEnablePhysicsAngularVelocityScale, // UObject 设置启用物理角速度缩放
    KCST_UObjectGetEnablePhysicsLinearVelocityScale, // UObject 获取启用物理线性速度缩放
    KCST_UObjectSetEnablePhysicsLinearVelocityScale, // UObject 设置启用物理线性速度缩放
    KCST_UObjectGetEnablePhysicsAngularVelocityScaleFactor, // UObject 获取启用物理角速度缩放因子
    KCST_UObjectSetEnablePhysicsAngularVelocityScaleFactor, // UObject 设置启用物理角速度缩放因子
    KCST_UObjectGetEnablePhysicsLinearVelocityScaleFactor, // UObject 获取启用物理线性速度缩放因子
    KCST_UObjectSetEnablePhysicsLinearVelocityScaleFactor, // UObject 设置启用物理线性速度缩放因子
    KCST_UObjectGetEnablePhysicsAngularVelocityScaleFactorFactor, // UObject 获取启用物理角速度缩放因子因子
    KCST_UObjectSetEnablePhysicsAngularVelocityScaleFactorFactor, // UObject 设置启用物理角速度缩放因子因子
    KCST_UObjectGetEnablePhysicsLinearVelocityScaleFactorFactor, // UObject 获取启用物理线性速度缩放因子因子
    KCST_UObjectSetEnablePhysicsLinearVelocityScaleFactorFactor, // UObject 设置启用物理线性速度缩放因子因子
    KCST_InstrumentedPureNodeEntry, // 插桩纯节点入口
    KCST_PersistentFrame,            // 持久帧
};
```

---

## 8. 统计和性能

### 8.1 编译器统计

编译器使用性能统计来跟踪编译时间：

```cpp
DECLARE_CYCLE_STAT(TEXT("Create Schema"), EKismetCompilerStats_CreateSchema, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Create Function List"), EKismetCompilerStats_CreateFunctionList, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Expansion"), EKismetCompilerStats_Expansion, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Validate"), EKismetCompilerStats_Validate, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Expand Node"), EKismetCompilerStats_ExpandNode, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Post Expansion Step"), EKismetCompilerStats_PostExpansionStep, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Process uber"), EKismetCompilerStats_ProcessUbergraph, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Process func"), EKismetCompilerStats_ProcessFunctionGraph, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Generate Function Graph"), EKismetCompilerStats_GenerateFunctionGraphs, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Precompile Function"), EKismetCompilerStats_PrecompileFunction, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Compile Function"), EKismetCompilerStats_CompileFunction);
DECLARE_CYCLE_STAT(TEXT("Create Locals and Register Nets"), EKismetCompilerStats_CreateLocalsAndRegisterNets, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Postcompile Function"), EKismetCompilerStats_PostcompileFunction, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Finalization"), EKismetCompilerStats_FinalizationWork, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Code Gen"), EKismetCompilerStats_CodeGenerationTime, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Clean and Sanitize Class"), EKismetCompilerStats_CleanAndSanitizeClass, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Create Class Properties"), EKismetCompilerStats_CreateClassVariables, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Bind and Link Class"), EKismetCompilerStats_BindAndLinkClass, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Calculate checksum of CDO"), EKismetCompilerStats_ChecksumCDO, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Calculate checksum of signature"), EKismetCompilerStats_ChecksumSignature, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Pruning"), EKismetCompilerStats_PruneIsolatedNodes, STATGROUP_KismetCompiler);
DECLARE_CYCLE_STAT(TEXT("Merge Ubergraph Pages In"), EKismetCompilerStats_MergeUbergraphPagesIn, STATGROUP_KismetCompiler);
```

---

## 9. 总结

蓝图编译器的主要流程可以总结为：

1. **CompileClassLayout** - 创建类结构和函数签名
2. **CompileFunctions** - 生成字节码并最终化
3. **CompileFunction** - 编译单个函数，处理节点

**关键概念**:
- **Schema** - 用于类型检查和验证
- **Function List** - 所有函数的上下文列表
- **Node Handlers** - 节点处理器映射表
- **Statements** - 编译语句列表
- **LinearExecutionList** - 线性执行顺序的节点列表
- **Pure Nodes** - 纯节点被内联优化

---

*研究完成日期：2026-05-06*