# Phase 57 — 函数签名映射：上下文决策

> 为 researcher 和 planner 提供实现决策，避免重复讨论。

## 上游依赖

- **Phase 56 已完成**：`CppClassIR` 已有 `methods: List[Any]` 字段（Phase 56 留空），`cpp_type_mapper` 已存在，`cpp_header_formatter` 已能渲染 `.h` 文本
- **v9.0 已完成**：`build_function_graphs` 输出 function_graphs 数组，每个条目含 `signature`、`execution_flows`、节点数据流标注
- **输入数据源**：`reference/蓝图节点文本参考.md`（BP_FirstPersonCharacter 真实导出）

## 已做决策

### D-57-01：函数签名提取 — 双源交叉验证

**规则**：
1. 优先从 `blueprint_functions`（上游 `BlueprintFunction` 模型）获取签名，已有 `return_type` 和 `parameters` 结构
2. 从 `K2Node_FunctionEntry` 的 `UserDefinedPin` 提取参数作为验证
3. 两者不一致时：记录 `logger.warning`，以 `blueprint_functions` 为准
4. 无 `blueprint_functions` 时：Fallback 到 FunctionEntry 引脚
5. FunctionEntry 引脚方向全部为 `EGPD_Output`（参数是函数的输出给内部节点），C++ 中统一为 input 参数

**实现参考**：
- `build_function_graphs()` 已在 `flow_builder.py:844` 中构建 `signature` 字典
- `BlueprintFunction.parameters` 含 `name`, `param_type`, `is_input` 字段
- `K2Node_FunctionEntry.node_data` 含 `UserDefinedPin` 条目

### D-57-02：输出形态 — IR methods + 独立调用语句参考

**产物**：
1. **填充 `CppClassIR.methods`**：每个蓝图函数对应一个 `CppMethodIR` 数据模型（新增），包含：
   - `cpp_name`: C++ 函数名
   - `return_type`: C++ 返回类型（无返回值为 `void`）
   - `parameters`: 参数列表（名 + C++ 类型 + 方向）
   - `ufunction_specifiers`: UFUNCTION 宏标记（见 D-57-03）
   - `is_override`: 是否为 override 方法（来自 K2Node_Event bOverrideFunction）
2. **独立调用语句参考**：从 `K2Node_CallFunction` 节点提取 C++ 调用语句，如 `this->Jump();` 或 `Target->SomeFunction(Arg1, Arg2)`
   - 新模块：`cpp_gen/extractors/cpp_call_extractor.py`（暂定名）
   - 输出格式：`List[CppCallStatement]` 或 dict 列表

### D-57-03：UFUNCTION 宏推断 — 基于引脚结构

**规则**：
| 引脚特征 | UFUNCTION 宏 |
|----------|-------------|
| 有 `exec` 输入 pin + 有 `then` 输出 pin | `BlueprintCallable` |
| 无 `exec` pin（仅有数据 pin） | `BlueprintPure` |
| `K2Node_Event` + `bOverrideFunction=True` | 不加 UFUNCTION（override 方法） |
| `K2Node_FunctionEntry` 且 `ExtraFlags` 含 event 标志 | `BlueprintImplementableEvent` |

**实现**：检查 FunctionEntry 节点的引脚列表：
- `exec` 类别引脚存在 → Callable
- 仅 `real`/`struct`/`object` 类别引脚（无 exec）→ Pure

### D-57-04：Event 覆盖函数 — 需要处理

**范围**：`K2Node_Event` 且 `bOverrideFunction=True` 的节点
- 从 `EventReference.MemberName` 提取函数名
- 从 Event 节点的输出引脚提取参数（如 `Axis_X`, `Axis_Y`）
- 标记为 `is_override=True`，不生成 UFUNCTION 宏
- 输出形式同 MethodIR，但 `ufunction_specifiers` 为空

**示例**：`K2Node_Event_2`（Primary Thumbstick 覆盖）→ `void PrimaryThumbstick(FVector2D Axis);`

### D-57-05：CallFunction 调用语句 — 不推断 Super:: 前缀

**规则**：
- `FunctionReference.MemberName` → 调用方法名
- `bSelfContext=True` → `this->MethodName(Args)`
- `bSelfContext=False` → 从 self pin 的 `PinSubCategoryObject` 推导目标变量名，如 `Target->MethodName(Args)`
- **不自动推断 `Super::` 前缀**——即使 `PinSubCategoryObject` 指向父类，也原样输出 `this->Jump()`
- 参数顺序：按引脚定义顺序，跳过 `exec`、`then`、`self` 三个特殊引脚

**实现参考**：
- CallFunction 节点的 `FunctionReference` 含 `MemberName`、`bSelfContext`
- 参数引脚：`PinCategory != "exec"` 且 `PinName != "self"` 且 `PinName != "then"`
- 参数值来源：`LinkedTo` 指向的数据流（Phase 57 仅提取签名，不填充实际参数值）

### D-57-06：参数方向推断 — 从 PinType 字段

**规则**：
- `PinType.bIsReference=True` + `PinType.bIsConst=True` → `const Type&`
- `PinType.bIsReference=True` + `PinType.bIsConst=False` → `Type&`
- 其余 → 值传递 `Type`
- 使用 Phase 56 的 `cpp_type_mapper` 做蓝图类型 → C++ 类型转换

## 范围外（重定向到后续 Phase）

| 想法 | 重定向到 | 原因 |
|------|---------|------|
| 函数体逻辑翻译 | Phase 58 | 需要执行流→C++ 语句映射 |
| 组件初始化代码 | Phase 59 | 需要组件层次→CreateDefaultSubobject 映射 |
| 纯函数内联表达式 | Phase 58 | 需要数据流→C++ 表达式翻译 |
| UFUNCTION 类别手动标注 | Phase 58+ | 需要用户配置或更复杂的启发式 |

## 模块设计建议

```
cpp_gen/
  extractors/
    cpp_function_signature_extractor.py   # FunctionEntry/Event → MethodIR
    cpp_call_extractor.py                  # CallFunction → CppCallStatement
  formatters/
    cpp_method_formatter.py                # MethodIR → C++ 声明文本（.h）
    cpp_call_formatter.py                  # CppCallStatement → C++ 调用文本（.cpp）
```

- `CppMethodIR` 数据模型：建议放在 `cpp_gen/formatters/cpp_json_ir.py` 中（与 `CppProperty` 同级）
- `extract_cpp_functions()` 入口：建议放在 `cpp_gen/extract_cpp_skeleton.py` 中扩展（与 `extract_cpp_skeleton()` 同级）

## 关键数据参考

### FunctionEntry 示例（Move 函数）
```
K2Node_FunctionEntry_0:
  FunctionReference=(MemberName="Move")
  bIsEditable=True
  Pins:
    - "then" (exec, EGPD_Output)
    - "Left / Right" (real/double, EGPD_Output)
    - "Forward / Backward" (real/double, EGPD_Output)
  UserDefinedPin: ("Left / Right", PinCategory="real", PinSubCategory="double")
  UserDefinedPin: ("Forward / Backward", PinCategory="real", PinSubCategory="double")
```
→ 期望 C++：`UFUNCTION(BlueprintCallable) void Move(double LeftRight, double ForwardBackward);`

### CallFunction 示例（Jump 调用）
```
K2Node_CallFunction_1193:
  FunctionReference=(MemberName="Jump", bSelfContext=True)
  Pins:
    - "execute" (exec, Input, LinkedTo=...)
    - "then" (exec, Output)
    - "self" (object, PinSubCategoryObject="/Script/CoreUObject.Class'/Script/Engine.Character'")
```
→ 期望 C++ 调用参考：`this->Jump();`

### Event 覆盖示例（Primary Thumbstick）
```
K2Node_Event_2:
  EventReference=(MemberParent=...BPI_TouchInterface_C', MemberName="Primary Thumbstick")
  bOverrideFunction=True
  Pins:
    - "OutputDelegate" (delegate, EGPD_Output)
    - "then" (exec, EGPD_Output)
    - "Axis" (struct/Vector2D, EGPD_Output)
      SubPins: Axis_X (real/double), Axis_Y (real/double)
```
→ 期望 C++：`void PrimaryThumbstick(double Axis_X, double Axis_Y);` （无 UFUNCTION，标记 override）
