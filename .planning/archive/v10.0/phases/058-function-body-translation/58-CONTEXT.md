# Phase 58 — 函数体逻辑翻译：上下文决策

> 为 planner 提供实现决策，避免重复讨论。

## 上游依赖

- **Phase 56 已完成**：`CppClassIR` 有 `methods` 和 `constructor` 字段
- **Phase 57 已完成**：函数签名提取完成，`CppMethodIR` 包含 `ufunction_specifiers` 和 `parameters`
- **v9.0 已完成**：`build_function_graphs` 输出 `execution_flows` 和 `data_flows`
- **输入数据源**：`reference/蓝图节点文本参考.md` + Phase 56 分析

## 已做决策

### D-58-01：执行流翻译 — 从 exec pin 链到 C++ 语句序列

**规则**：
1. 从 `K2Node_FunctionEntry` 的 `then` exec pin 开始追踪执行流
2. 每个带 exec 输出的节点 → C++ 语句（或语句块）
3. 执行流按 `LinkedTo` 连接顺序生成 C++ 语句序列
4. `exec` pin 只存在于输入/输出连接，不对应 C++ 语句
5. `then` pin 的连接目标决定语句顺序

**实现参考**：
- `execution_flows` 数组已按 start_event 组织
- 每个 flow 的 `nodes` 列表按执行顺序排列
- `LinkedTo` 字段提供节点间的 exec 连接关系

### D-58-02：数据流翻译 — 从 pure function 到 C++ 表达式

**规则**：
1. Pure 函数（无 exec pin）→ C++ 表达式（内联或中间变量）
2. 数据流追踪：从 `LinkedTo` 的源 pin 到目标 pin
3. 数据流结果用于填充 CallFunction 的参数
4. Pure 函数调用优先内联，避免不必要的中间变量

**数据流模式**（来自 Phase 56 分析）：
```
ActionValue_X (EnhancedInputAction) → Pin "Yaw" (CallFunction)
ActionValue_Y (EnhancedInputAction) → Pin "Pitch" (CallFunction)

ActionValue_X (EnhancedInputAction) → Pin "Left/Right" (CallFunction)
ActionValue_Y (EnhancedInputAction) → Pin "Forward/Backward" (CallFunction)
```

**处理策略**：
- 如果源 pin 来自 `K2Node_FunctionEntry` 的参数 → 参数名引用
- 如果源 pin 来自 `K2Node_Event` 的参数 → 参数名引用
- 如果源 pin 来自 `K2Node_CallFunction` 的输出 → 内联或中间变量

### D-58-03：CallFunction 调用翻译 — 填充函数体

**规则**：
1. `K2Node_CallFunction` 节点 → C++ 调用语句
2. 参数来源 via `LinkedTo`：
   - `real`/`double` → Pin 名称（如 `"Yaw"`, `"Left/Right"`）
   - `bool` → Pin 名称
   - `struct`/`object` → Pin 名称或引用
3. 参数顺序：按 pin 定义顺序，跳过 `exec`, `then`, `self`
4. 空参数函数：如 `Jump()`, `StopJumping()`

**引用对象**（bSelfContext=False）：
- `self` pin 的 `PinSubCategoryObject` → 目标变量名
- 从组件数组或变量名推导

### D-58-04：Pure 函数内联 — 避免不必要的变量

**规则**：
1. Pure 函数，如果所有使用者都是单一使用者 → 内联
2. Pure 函数，如果被多个使用者共享 → 中间变量
3. 内联表达式示例：
   - `GetActorRightVector()` → 直接使用
   - `Multiply_VectorFloat(Vector, Float)` → 内联 `Vector * Float`

**启发式**：
- 查看 `LinkedTo` 目标数量
- 单一目标 → 内联
- 多个目标 → 创建临时变量

### D-58-05：函数体包装 — 从 IR 到 .cpp 文本

**产物**：
1. **.cpp 模板文件**：包含函数体
2. **调用参考**：`CppMethodIR` 中的 `call_statements` 字段

**格式**：
```cpp
void AMyCharacter::Aim(float Yaw, double Pitch)
{
    if (GetController())
    {
        AddControllerYawInput(Yaw);
        AddControllerPitchInput(Pitch);
    }
}
```

### D-58-06：Enhanced Input 补充 — InputAction 处理

**范围**：Phase 56 分析发现的 `K2Node_EnhancedInputAction` 节点

**处理策略**：
1. **不翻译 InputAction 节点本身**（它是事件源，不是函数调用）
2. **翻译 InputAction 的 Triggered/Started 等事件输出**
3. **翻译绑定的 CallFunction 节点的参数**

**数据流路径**（来自 Phase 56 分析）：
```
EnhancedInputAction (Triggered output)
    ↓ (exec)
CallFunction (Aim/Move/Jump)
    ↓ (data pins)
ActionValue_X/Y → Yaw/Pitch/Left/Right
```

**C++ 输出**：
- 不生成 `InputAction` 类的定义（这是引擎类）
- 不生成 `BindAction<UInputAction>()` 调用（这是 Phase 59 的构造函数）
- 只生成事件处理函数体（Aim/Move/Jump）

## 范围外（重定向到后续 Phase 或不处理）

| 想法 | 重定向到 | 原因 |
|------|---------|------|
| 函数声明 | Phase 57 | 已处理 |
| 组件初始化 | Phase 59 | 需要 CreateDefaultSubobject |
| UFUNCTION 宏 | Phase 57 | 已处理 |
| 构造函数 | Phase 59 | 需要组件层次信息 |

## 关键数据参考（来自 Phase 56 分析）

### 执行流示例（Jump）

```
execution_flows:
  - start_event: K2Node_EnhancedInputAction_5 (Started)
    nodes:
      - node_guid: F923268743B7B52D669FFB960CA79833
        node_type: K2Node_CallFunction
        function_name: Jump
  - start_event: K2Node_EnhancedInputAction_5 (Completed)
    nodes:
      - node_guid: E60E51D14AFDDB3C7284AE89737920FE
        node_type: K2Node_CallFunction
        function_name: StopJumping
```

**C++ 输出**：
```cpp
// Jump handling
void AMyCharacter::Jump()
{
    Super::Jump();
}

// StopJumping handling
void AMyCharacter::StopJumping()
{
    Super::StopJumping();
}
```

### 执行流示例（Aim）

```
execution_flows:
  - start_event: K2Node_EnhancedInputAction_2 (Triggered)
    nodes:
      - node_guid: E7B1717D492D9E3EDA20629D2F0CA01C
        node_type: K2Node_CallFunction
        function_name: Aim
```

**数据流**：
```
ActionValue_X → Yaw pin
ActionValue_Y → Pitch pin
```

**C++ 输出**：
```cpp
void AMyCharacter::Aim(float Yaw, double Pitch)
{
    if (GetController())
    {
        AddControllerYawInput(Yaw);
        AddControllerPitchInput(Pitch);
    }
}
```

### 执行流示例（Move）

```
execution_flows:
  - start_event: K2Node_EnhancedInputAction_3 (Triggered)
    nodes:
      - node_guid: C8057E68458317EB785601A49208A829
        node_type: K2Node_CallFunction
        function_name: Move
```

**数据流**：
```
ActionValue_X → Left/Right pin
ActionValue_Y → Forward/Backward pin
```

**C++ 输出**：
```cpp
void AMyCharacter::Move(double LeftRight, double ForwardBackward)
{
    if (GetController())
    {
        AddMovementInput(GetActorRightVector(), LeftRight);
        AddMovementInput(GetActorForwardVector(), ForwardBackward);
    }
}
```

## 增强 InputAction 处理补充（Phase 56 发现）

### 问题：InputAction 作为类的处理

**发现**：
- 蓝图中有 `UInputAction*` 类型的变量（如 `JumpAction`, `MoveAction`）
- 这些变量在 C++ 中需要：
  1. **声明**（Phase 57 或 56 扩展）
  2. **初始化**（Phase 59 构造函数）
  3. **使用**（绑定到 EnhancedInputComponent）

### 处理策略

| 项目 | 处理阶段 | 说明 |
|------|---------|------|
| `UInputAction*` 变量声明 | Phase 57 (或 56 扩展) | 添加到 `CppClassIR.properties` |
| `InputAction` 资源路径 | Phase 56 类型映射 | UInputAction → UInputAction* |
| `UEnhancedInputComponent` | Phase 56 类型映射 | 增强输入组件类型 |
| `BindAction` 调用 | Phase 59 构造函数 | `InputComponent->BindAction(...)` |

### 类型映射扩展建议（Phase 56-05 / 57-01）

```python
# 增强 Input 类型映射
UE_TO_CPP_TYPE_MAP.update({
    "InputAction": "UInputAction*",
    "EnhancedInputComponent": "UEnhancedInputComponent*",
    "FInputActionValue": "FInputActionValue",
})
```

### CallFunction 参数解析（Phase 58）

**示例**：`K2Node_CallFunction_5` (Move)

```
Pins:
  - "Left / Right" (real/double, LinkedTo=EnhancedInputAction.Pin ActionValue_X)
  - "Forward / Backward" (real/double, LinkedTo=EnhancedInputAction.Pin ActionValue_Y)
```

**提取策略**：
1. 跳过 `exec`, `then`, `self` 引脚
2. 对于 `real`/`double` 类型 pin，从 `LinkedTo` 获取源 pin 名称
3. 源 pin 来自 EnhancedInputAction，则取 `ActionValue_X`/`ActionValue_Y`
4. 参数名：替换分隔符 `"Left / Right"` → `"LeftRight"`

**C++ 语句**：
```cpp
Move(LeftRight, ForwardBackward);
```

## 模块设计建议

```
cpp_gen/
  extractors/
    cpp_function_body_extractor.py      # 函数体提取（来自 execution_flows）
    cpp_call_statement_extractor.py     # CallFunction → C++ 调用语句
  formatters/
    cpp_function_body_formatter.py      # CppBodyIR → .cpp 文本
```

**数据模型**：
- `CppMethodIR` (Phase 57) → 新增 `body: List[CppStatement]` 字段
- 新增 `CppStatement` 及其子类（Assignment, Call, If, etc.）

## 关键数据流图

### 执行流翻译路径

```
K2Node_CallFunction node (from execution_flows)
  ↓
function_name from FunctionReference.MemberName
  ↓
params从LinkedTo推导 (值来自Pin的LinkedTo源)
  ↓
CppCallStatement(method_name, target, args)
  ↓
format_cpp_call_statement() → C++ text
  ↓
Append to CppMethodIR.body[]
```

### 数据流翻译路径

```
EnhancedInputAction.ActionValue_X pin
  ↓ (LinkedTo)
CallFunction.Pin "Yaw"
  ↓ (pin_type)
FEdGraphPinType(pin_category="real", pin_subcategory="float")
  ↓ (ue_path_to_cpp_type)
"float" → C++ type
  ↓
parameter: {"name": "Yaw", "cpp_type": "float"}
  ↓
Add to CallStatement.args[]
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | InputAction 变量在 Phase 56 已识别，Phase 57 只翻译函数体 | Phase 56 分析 | 如果输入动作未正确识别为变量，Phase 57 可能遗漏绑定语句 |
| A2 | EnhancedInputComponent 在蓝图中隐式存在（通过事件图） | 架构模式 | 如果需要显式声明，Phase 57 应添加到 properties |
| A3 | Pure 函数调用的参数可以直接内联 | D-58-04 | 如果某些 Pure 函数有副作用，内联可能不正确 |
| A4 | 构造函数中的 `Super::` 调用是可选的 | D-58-06 | 如果某些函数必须调用 Super，需要额外逻辑 |
| A5 | 执行流按 `start_event` 顺序处理 | D-58-01 | 如果事件触发顺序重要，需要按优先级排序 |
