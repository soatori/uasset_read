# Phase 63: 表达式树 → C++ 伪代码 - Plan

**Goal:** 将 Phase 62 产出的 `list[KismetExpression]` 翻译为可读的 C++ 伪代码。交付三个核心能力：`line_cpp()` 单行翻译、`to_function_body()` 完整函数体组装、`MathFunctionCleaner` 数学函数美化。

**Decisions:** 7 (D-01 ~ D-07, all locked in 63-CONTEXT.md)
**Tasks:** 12
**Waves:** 6 (sequential within waves, waves run sequentially for safety)
**Files:** 3 new source + 5 new test + 2 modified

---

## Wave 1: 基础设施 — TypeRegistry + MathFunctionCleaner

### Task 1: TypeRegistry 实现
**File:** `src/uasset_read/kismet/translator.py` (部分)
**Action:** Create `TypeRegistry` class with `register_variable(name, type)` and `lookup(name) -> str | None`

Details:
- `__init__`: empty dict `_types: dict[str, str]`
- `register_variable(name: str, cpp_type: str) -> None`
- `lookup(name: str) -> str | None`
- `populate_from_metadata(metadata: dict) -> None` — 从 BlueprintMetadata/BlueprintVariable 批量初始化
- UE → C++ 类型映射表（30+ 种，对齐 CUE4Parse GetPropertyType）：
  - `IntProperty` → `int`, `FloatProperty` → `float`, `BoolProperty` → `bool`
  - `StrProperty` → `FString`, `NameProperty` → `FName`, `TextProperty` → `FText`
  - `ObjectProperty` → `UObject*`, `ArrayProperty` → `TArray<T>`, etc.
- `auto` fallback 当 lookup 返回 None 时

**Tests:** `tests/kismet/test_type_registry.py`
- 注册和查找基本功能
- 元数据批量填充
- 未知变量返回 None
- 类型映射表覆盖主要 UE 类型

### Task 2: MathFunctionCleaner 实现
**File:** `src/uasset_read/kismet/translator.py` (部分)
**Action:** Create `MathFunctionCleaner` static module/class with 80+ function mappings

Details:
- `clean(class_name: str, func_name: str, params: list[str]) -> str`
- 使用有序列表的 (predicate, transformer) 模式，按特异性排序
- 库覆盖：
  - **KismetMathLibrary** (70+): arithmetic, comparison, boolean, conversion, vector/rotator/transform
  - **KismetStringLibrary** (15+): string operations, conversions
  - **KismetSystemLibrary** (10+): delays, soft references
  - **KismetArrayLibrary** (12+): array operations via FinalFunctionCleaner
  - **BlueprintMapLibrary** (5+): map operations
  - **BlueprintSetLibrary** (5+): set operations
- 未匹配时回退 `ClassName::func_name(params)` 格式

**Tests:** `tests/kismet/test_math_cleaner.py`
- 算术函数: `Add_IntInt(a, b)` → `a + b`
- 比较函数: `EqualEqual_IntInt(a, b)` → `a == b`
- Boolean 函数: `BooleanAND(a, b)` → `a && b`
- 类型转换: `Conv_IntToBool(a)` → `(a != 0)`
- Break 函数: `BreakVector(v)` → 多行赋值
- Select 三元组: `Select(a, b, cond)` → `(cond ? a : b)`
- 未匹配函数回退格式
- String library: `Concat_StrStr(a, b)` → `a += b`
- Array library: `Array_Length(a)` → `a.Length`

---

## Wave 2: 核心 line_cpp() — 基础表达式类型

### Task 3: 中央调度器骨架 + 变量/字面量翻译
**File:** `src/uasset_read/kismet/translator.py`
**Action:** Create `KismetTranslator` class with `line_cpp(expr, type_registry=None)` dispatch

Details:
- `line_cpp(expr: KismetExpression, type_registry: TypeRegistry = None) -> str`
- 使用 match/case 分派（对齐 CUE4Parse 的 switch 模式）
- **Variables:** `EX_LocalVariable`, `EX_InstanceVariable`, `EX_DefaultVariable`, `EX_LocalOutVariable`, `EX_ClassSparseDataVariable` → 返回变量名，使用 type_registry 查询类型
- **Literals:** `EX_IntConst`, `EX_FloatConst`, `EX_StringConst`, `EX_UnicodeStringConst`, `EX_TextConst`, `EX_IntZero`, `EX_IntOne`, `EX_True`, `EX_False`, `EX_ByteConst`, `EX_Int64Const`, `EX_UInt64Const`, `EX_DoubleConst`
- **Object/Name:** `EX_ObjectConst`, `EX_NameConst`, `EX_SoftObjectConst`
- **Vector consts:** `EX_VectorConst`, `EX_RotationConst`, `EX_TransformConst`, `EX_Vector3fConst`
- **Special:** `EX_Self` → `"this"`, `EX_NoObject`/`EX_NoInterface` → `"nullptr"`, `EX_EndOfScript` → `""`
- StringConst 需要转义换行符和引号

**Tests:** 包含在 `tests/kismet/test_line_cpp.py` 中

### Task 4: 赋值 + 函数调用翻译
**File:** `src/uasset_read/kismet/translator.py`
**Action:** Add `EX_Let*`, `EX_FinalFunction`, `EX_CallMath` 等翻译

Details:
- **Assignments:** `EX_Let` → `var = assignment`, `EX_LetBool`, `EX_LetDelegate`, `EX_LetObj`, `EX_LetWeakObjPtr`, `EX_LetMulticastDelegate`, `EX_LetValueOnPersistentFrame` (UberGraphFrame 特殊处理)
- **Functions:** `EX_FinalFunction` — 收集参数，调用 `line_cpp()` 递归，调用 MathFunctionCleaner 内联美化
- `EX_CallMath` — 同上，但始终走 MathFunctionCleaner 路径
- `EX_LocalFinalFunction`, `EX_VirtualFunction`, `EX_LocalVirtualFunction` — 类名::函数名(参数) 格式
- `EX_CallMulticastDelegate`, `EX_InstanceDelegate` — 委托调用格式
- `EX_EndParmValue`, `EX_EndFunctionParms` → `""` (不输出)
- **Return:** `EX_Return` → `return expression`

**Tests:** `tests/kismet/test_line_cpp.py`
- 赋值: `Let(x, 5)` → `x = 5`
- 函数调用: `CallMath(KismetMathLibrary, Add_IntInt, [a, b])` → `a + b`
- 原始函数调用: `FinalFunction(SomeClass, SomeFunc, [a])` → `SomeClass::SomeFunc(a)`
- Return: `Return(x)` → `return x`

---

## Wave 3: line_cpp() — 剩余表达式类型

### Task 5: 控制流 + 转换 + 上下文翻译
**File:** `src/uasset_read/kismet/translator.py`
**Action:** Add control flow, cast, context expression translation

Details:
- **Control flow (goto path):**
  - `EX_Jump` → `goto Label_{CodeOffset}` (检查目标是否为 EX_Return，是则优化为 `return`)
  - `EX_JumpIfNot` → `if (!condition) goto Label_{CodeOffset}`
  - `EX_ComputedJump` → `goto {variable}`
  - `EX_PushExecutionFlow` → `""` (内部维护 stack 状态)
  - `EX_PopExecutionFlow` → `goto Label_{target}` 或 `return`
  - `EX_PopExecutionFlowIfNot` → `if (!condition) goto/return`
  - `EX_Skip` → `goto Label_{CodeOffset}`
  - `EX_SkipOffsetConst` → `""`
- **Casts:** `EX_Cast` → `Cast<type>(expr)`, `EX_MetaCast` → `Cast<type>(expr)`, `EX_DynamicCast`, `EX_ObjToInterfaceCast`, `EX_CrossInterfaceCast`, `EX_InterfaceToObjCast` → `Cast<ClassType>(var)`
- **Context:** `EX_Context` → `obj->function()`, `EX_Context_FailSilent` → 类似但标注 silent, `EX_ClassContext`, `EX_InterfaceContext`, `EX_StructMemberContext` → `struct.member`

**Tests:** `tests/kismet/test_line_cpp.py`
- Jump: `EX_Jump(offset=100)` → `goto Label_100`
- JumpIfNot: `EX_JumpIfNot(cond, 50)` → `if (!cond) goto Label_50`
- Cast: `EX_Cast(target, CST_IntToFloat)` → `Cast<float>(expr)`
- Context: `EX_Context(obj, func)` → `obj->func()`

### Task 6: 容器 + 结构体 + 委托 + 特殊类型翻译
**File:** `src/uasset_read/kismet/translator.py`
**Action:** Add containers, structs, delegates, special, RTFM translation

Details:
- **Containers:** `EX_SetArray` → `TArray<type>{items}`, `EX_SetMap` → `TMap<K,V>{k:v, ...}`, `EX_SetSet` → `TSet<type>{items}`, `EX_ArrayConst`, `EX_MapConst`, `EX_SetConst`, `EX_ArrayGetByRef` → `array[index]`
- **Structs:** `EX_StructConst` → `FStructName{field=value, ...}`, `EX_BitFieldConst`, `EX_PropertyConst`
- **Delegates:** `EX_AddMulticastDelegate` → `delegate.Add(func)`, `EX_ClearMulticastDelegate`, `EX_BindDelegate`, `EX_RemoveMulticastDelegate`
- **Special:** `EX_SwitchValue` → 如果 2 个 case 用三元运算符 `cond ? a : b`, 否则 `switch/case`, `EX_Assert` → `assert(condition)`, `EX_Nothing`/`EX_NothingInt32` → `""`, `EX_InstrumentationEvent`, `EX_FieldPathConst`
- **RTFM:** `EX_AutoRtfmTransact`, `EX_AutoRtfmStopTransact`, `EX_AutoRtfmAbortIfNot` → `/* RTFM: ... */`
- **Deprecated:** `EX_DeprecatedOp4A`, `EX_Breakpoint`, `EX_Tracepoint`, `EX_WireTracepoint` → `/* deprecated */`

**Tests:** `tests/kismet/test_line_cpp.py`
- Array: `SetArray([1, 2, 3])` → `TArray<int>{1, 2, 3}`
- Switch (2 cases): `SwitchValue(idx, [a, b])` → `idx ? b : a`
- Delegate: `AddMulticastDelegate(delegate, func)` → `delegate.Add(func)`

---

## Wave 4: FunctionBodyBuilder — 基础组装

### Task 7: FunctionBodyBuilder 实现
**File:** `src/uasset_read/kismet/body_builder.py`
**Action:** Create `FunctionBodyBuilder` class with `to_function_body(expressions, type_registry, func_name=None) -> str`

Details:
- 接受 `list[KismetExpression]` 和 `TypeRegistry`
- 构建 byte_offset → statement_index 映射（用于标签生成）
- 遍历表达式列表，调用 `line_cpp()` 获取每行 C++
- 空字符串跳过（EX_EndOfScript, EX_PushExecutionFlow 等）
- 添加 `;` 分号（控制流语句如 goto/if/return 已有分号的不重复添加）
- 4 空格缩进
- 输出格式:
  ```cpp
  void FunctionName() {
      line1;
      line2;
      return result;
  }
  ```
- 标签生成: `Label_{byte_offset}:` 格式
- `EX_EndOfScript` 作为终止符，不生成输出但触发 `}` 闭合

**Tests:** `tests/kismet/test_function_body.py`
- 简单函数: [Let(x,1), Let(y,2), Return(Add(x,y))] → 缩进函数体
- 含 goto 的函数体
- 空表达式列表 → 空函数体
- 带函数名的输出

---

## Wave 5: StructuredControlFlow — 结构化还原

### Task 8: 结构化控制流重建器
**File:** `src/uasset_read/kismet/structured_flow.py`
**Action:** Create `StructuredControlFlow` class with `reconstruct(expressions) -> list[str]`

Details:
- **算法:** 工作列表 + Push/Pop 模式匹配（不阻塞在边缘情况）
- 步骤:
  1. 构建 CFG: byte_offset → expression 索引映射
  2. 识别 PushExecutionFlow + JumpIfNot + PopExecutionFlow 配对 → if/else 块
  3. 识别回跳 (back-jump 到更早 offset) → while/for 循环
  4. 无法识别的模式回退到 goto
- **if/else 模式识别:**
  ```
  Push(else_offset)
  JumpIfNot(cond, else_offset) → if (cond) { ... }
  ... then block ...
  Pop() → jump to else_offset
  ... else block ...
  Label(else_offset):
  ```
- **for 循环模式:** Push → JumpIfNot(退出) → body → Pop(回跳) → Jump(条件)
- **while 循环模式:** JumpIfNot(退出) → body → Jump(开始)
- 输出带缩进的字符串列表，直接用于 `to_function_body()`
- **Decision D-03 落实:** 不追求完美，未识别模式回退 goto

**Tests:** `tests/kismet/test_structured_flow.py`
- if/else 模式: Push + JumpIfNot + Pop → if/else 块
- 简单 if (无 else): JumpIfNot → goto (回退)
- 回跳模式 → while 循环
- 无法识别模式 → goto 回退

### Task 9: 集成结构化流到 FunctionBodyBuilder
**File:** `src/uasset_read/kismet/body_builder.py` (修改)
**Action:** Add `to_function_body_structured()` method

Details:
- 尝试 `StructuredControlFlow.reconstruct()` 首先
- 如果结构化成功 → 使用结构化输出
- 如果失败/部分失败 → 回退到 goto-based 输出
- API: `to_function_body(expressions, type_registry, structured=True)` 参数控制

---

## Wave 6: 导出 + 集成测试

### Task 10: 模块导出更新
**Files:** `src/uasset_read/kismet/translator.py`, `src/uasset_read/kismet/__init__.py`, `src/uasset_read/kismet/expressions/__init__.py`
**Action:** Export new symbols

Details:
- `kismet/__init__.py` 导出: `KismetTranslator`, `MathFunctionCleaner`, `TypeRegistry`, `FunctionBodyBuilder`, `StructuredControlFlow`
- `kismet/expressions/__init__.py` 不需要修改（表达式类不变，仅添加翻译器消费它们）

### Task 11: 完整 line_cpp 覆盖测试
**File:** `tests/kismet/test_line_cpp.py`
**Action:** 为所有 90+ 表达式类型编写覆盖测试

Details:
- 每个 EXPR_CLASS_MAP 中的表达式类型至少一个测试
- 重点测试: 递归翻译（嵌套表达式）、类型注册表集成、MathFunctionCleaner 内联调用
- 使用 Phase 62 的测试资产或构造模拟表达式

### Task 12: 端到端集成测试
**File:** `tests/kismet/test_integration.py` (new)
**Action:** 从字节码 → 表达式树 → C++ 伪代码的完整链路测试

Details:
- 使用已有的测试 .uasset 文件（如有）
- 或构造模拟的 FKismetArchive 数据
- 验证: `parse_bytecode() → expressions → to_function_body() → C++ string`
- 确保 554+ 已有测试不受影响

---

## Success Criteria

1. **所有 90+ 表达式类型** 有 `line_cpp()` 翻译实现
2. **MathFunctionCleaner** 覆盖 80+ 函数映射（对齐 CUE4Parse）
3. **TypeRegistry** 支持 30+ UE → C++ 类型映射
4. **to_function_body()** 输出可读的 C++ 函数体（带缩进、分号、花括号）
5. **StructuredControlFlow** 识别 if/else 和 while/for 常见模式，回退 goto
6. **所有新测试通过**，已有 554+ 测试不受影响
7. **零新依赖**，Python 3.10+ stdlib only

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| StackNode 为 int 未解析 | MEDIUM | 使用占位符 `Function_{index}` 格式，不阻塞翻译 |
| 结构化控制流边缘情况 | LOW | D-03 明确不追求完美，goto 回退 |
| MathFunctionCleaner 映射遗漏 | LOW | 对齐 CUE4Parse 已验证的 80+ 映射，未匹配回退原始格式 |
| Phase 62 输出格式变化 | LOW | 基于 Phase 62 PLAN.md 中定义的数据结构 |

## File Summary

| File | Action | Wave |
|------|--------|------|
| `src/uasset_read/kismet/translator.py` | **New** — KismetTranslator, TypeRegistry, MathFunctionCleaner | 1, 2, 3 |
| `src/uasset_read/kismet/body_builder.py` | **New** — FunctionBodyBuilder | 4, 5 |
| `src/uasset_read/kismet/structured_flow.py` | **New** — StructuredControlFlow | 5 |
| `src/uasset_read/kismet/__init__.py` | **Modify** — Export new symbols | 6 |
| `tests/kismet/test_type_registry.py` | **New** | 1 |
| `tests/kismet/test_math_cleaner.py` | **New** | 1 |
| `tests/kismet/test_line_cpp.py` | **New** | 2, 3, 6 |
| `tests/kismet/test_function_body.py` | **New** | 4 |
| `tests/kismet/test_structured_flow.py` | **New** | 5 |
| `tests/kismet/test_integration.py` | **New** | 6 |

---

*Phase: 63-表达式树 → C++ 伪代码*
*Plan created: 2026-05-20*
