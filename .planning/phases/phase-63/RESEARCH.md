# Phase 63: 表达式树 → C++ 伪代码 - Research

**Researched:** 2026-05-20
**Domain:** Kismet bytecode to C++ pseudocode translation
**Confidence:** HIGH

## Summary

Phase 63 implements the translation of `list[KismetExpression]` (from Phase 62) into readable C++ pseudocode. CUE4Parse provides the reference implementation via two key mechanisms: (1) `GetLineExpression()` in `BlueprintDecompilerUtils.cs` — a large switch-based dispatcher that recursively renders each expression type to a C++ string, and (2) `MathFunctionCleaner` — a pattern-matching function that converts UE Kismet library calls like `UKismetMathLibrary::Add_IntInt(a, b)` into idiomatic C++ like `a + b`.

**Primary recommendation:** Follow CUE4Parse's `GetLineExpression()` pattern directly — a recursive switch/dispatch function that takes a `KismetExpression` and returns `str`. Implement `MathFunctionCleaner` as an inline function called from `EX_CallMath`/`EX_FinalFunction` handlers. Add `to_function_body()` as a separate assembler that iterates expressions with indentation control, and a structured control-flow reconstructor that identifies Push/Pop/JumpIfNot patterns.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Expression→string rendering | API / Backend | — | Pure string transformation, no I/O |
| MathFunctionCleaner | API / Backend | — | Pattern matching + substitution |
| Control flow reconstruction | API / Backend | — | Bytecode-level analysis |
| Type registry | API / Backend | — | Metadata lookup from blueprint info |
| Function body assembly | API / Backend | — | String composition with indentation |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 同时提供两种输出 API — `line_cpp()` (单个表达式的单行 C++ 字符串) 和 `to_function_body()` (完整函数体，带缩进、分号、花括号)
- **D-02:** 双路径控制流还原 — `line_cpp()` 保留 `goto Label_X` 格式；`to_function_body()` 尝试结构化还原为 `if/for/while` 块结构
- **D-03:** 结构化算法不需要完美 — 优先处理常见模式（if/else、for 循环、while 循环），无法识别时回退到 goto
- **D-04:** MathFunctionCleaner 在翻译时内联执行 — 在 `EX_FinalFunction`/`EX_CallMath` 的 `line_cpp()` 方法内部调用
- **D-05:** MathFunctionCleaner 覆盖范围对齐 CUE4Parse：`KismetMathLibrary`、`KismetStringLibrary`、`KismetSystemLibrary`、`KismetArrayLibrary`、`BlueprintMapLibrary`、`BlueprintSetLibrary`
- **D-06:** 变量类型混合策略 — 优先从上游 blueprint 元数据推断，获取不到时回退 `auto`；维护 `TypeRegistry`
- **D-07:** 类型注册表接口：`register_variable(name, type)` + `lookup(name) -> str | None`

### Claude's Discretion
- 结构化控制流算法的具体实现方式（递归下降 vs 工作列表）由 planner 自行判断
- 类型注册表的具体数据结构和填充策略由实现者自行判断

### Deferred Ideas (OUT OF SCOPE)
None

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (match/case) | 3.10+ | Expression dispatch | Zero dependency, clean pattern matching — already used in project |
| Python dataclasses | 3.10+ | Method addition to existing expression classes | Project convention — all models use @dataclass |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| — | — | No external packages needed | This is pure string transformation |

**Installation:** No new packages required. Python 3.10+ stdlib only.

## Package Legitimacy Audit

No external packages to audit.

## CUE4Parse GetLineExpression Pattern

### Architecture

CUE4Parse uses a **single centralized dispatch function** `GetLineExpression(KismetExpression expression)` in `BlueprintDecompilerUtils.cs` (line 1162-1781). This is a static method with a massive `switch` statement that handles every `KismetExpression` subclass.

**Key design decisions:**

1. **Recursive rendering:** Every case calls `GetLineExpression()` on child expressions, building strings bottom-up.
2. **No per-class method:** Unlike the Python project's `from_archive()` pattern, CUE4Parse does NOT put `GetLineExpression()` on each expression class. It's a single external function.
3. **Shared global state:** `_executionFlowStack` (line 26) is a static `Stack<int>` used by Push/Pop/JumpIfNot cases to track return addresses.
4. **Helper functions:** `MathFunctionCleaner()` and `FinalFunctionCleaner()` are called inline from the `EX_FinalFunction`/`EX_CallMath` cases.

### Pattern by Expression Category

#### Variable References (line 1166-1168)
```csharp
case EX_VariableBase variableBase:
    return variableBase.Variable.ToString();
```
Simply returns the property name from `FKismetPropertyPointer`.

#### Assignments (line 1176-1196)
```csharp
case EX_Let let:
    var assignment = GetLineExpression(let.Assignment);
    var variable = GetLineExpression(let.Variable);
    return $"{variable} = {assignment}";
```
All `EX_Let*` variants render as `variable = assignment`.

#### Context (line 1197-1219)
```csharp
case EX_Context context:
    var function = context?.ContextExpression is not null ? GetLineExpression(context?.ContextExpression).SubstringAfter("::") : "failedplaceholder";
    var obj = context?.ObjectExpression is not null ? GetLineExpression(context?.ObjectExpression) : "failedplaceholder";
    if (obj == "FindObject<UObject>(nullptr, this)" || obj.Contains("KismetArrayLibrary") || ...)
        customStringBuilder.Append(function);
    else
        customStringBuilder.Append($"{obj}->{function}");
```
Renders as `obj->function()` or just `function()` depending on context.

#### Function Calls (line 1220-1253)
```csharp
case EX_FinalFunction final:
    // ... collect parameters ...
    if (expression is EX_CallMath) return MathFunctionCleaner(className, functionName, parametersList, parameters);
    if (expression is EX_LocalFinalFunction) return $"{...}::{functionName}({parameters})";
    return FinalFunctionCleaner(className, functionName, parametersList, parameters);
```

#### Literals (line 1318-1397)
Each literal type has a simple render:
- `EX_IntConst` → `Value.ToString()`
- `EX_FloatConst` → `Value.ToString(CultureInfo.CurrentCulture)`
- `EX_StringConst` → `"\"{value.Replace("\r\n", "\\n")}\""`
- `EX_True` → `"true"`, `EX_False` → `"false"`
- `EX_IntZero` → `"0"`, `EX_IntOne` → `"1"`
- `EX_Self` → `"this"`
- `EX_NoObject`/`EX_NoInterface` → `"nullptr"`

#### Control Flow (line 1416-1493)
```csharp
case EX_PushExecutionFlow pushExecutionFlow:
    _executionFlowStack.Push((int)pushExecutionFlow.PushingAddress);
    return "";

case EX_PopExecutionFlow:
    if (_executionFlowStack.Count == 0) return "return";
    var target = _executionFlowStack.Pop();
    return $"goto Label_{target}";

case EX_JumpIfNot jumpIfNot:
    var booleanExpression = GetLineExpression(jumpIfNot.BooleanExpression);
    // ... check if target is EX_Return ...
    return $"goto Label_{jumpIfNot.CodeOffset}";

case EX_Jump jump:
    return $"goto Label_{jump.CodeOffset}";
```

#### Casts (line 1402-1414, 1530-1555)
```csharp
case EX_Cast cast:
    var target = GetLineExpression(cast.Target);
    var conversionType = cast.ConversionType switch {
        ECastToken.CST_ObjectToBool => "bool",
        ECastToken.CST_DoubleToFloat => "float",
        ...
    };
    return $"Cast<{conversionType}>({target})";

case EX_CastBase cast:
    return $"Cast<{GetClassWithPrefix(cast.ClassPtr.Load<UStruct>())}>({variable})";
```

#### Collections (line 1259-1304, 1599-1655)
```csharp
case EX_ArrayConst constArray:
    return $"TArray<{constArray.InnerProperty}>({string.Join(", ", values)})";

case EX_MapConst mapConst:
    return "TMap { key: value, ... }";
```

#### Switch (line 1656-1693)
```csharp
case EX_SwitchValue switchValue:
    if (switchValue.Cases.Length == 2)
        return $"{indexTerm} ? {case1} : {case0}";  // ternary optimization
    // full switch/case rendering
```

## MathFunctionCleaner Details

### Location
`BlueprintDecompilerUtils.cs` lines 102-253

### Function Signature
```csharp
private static string MathFunctionCleaner(
    string className,
    string functionName,
    List<string> parametersList,
    string parameters)
```

### Complete Function Mappings

#### KismetMathLibrary / SolarisMathLibrary_* (lines 108-207)

| Pattern Prefix | Output Template | Example Input → Output |
|---|---|---|
| `EqualEqual_ByteByte` | `((!{p0}) == (!{p1}))` | `EqualEqual_ByteByte(a, b)` → `((!a) == (!b))` |
| `EqualEqual_` | `{p0} == {p1}` | `EqualEqual_IntInt(a, b)` → `a == b` |
| `NotEqual_` | `({p0} !== {p1})` | `NotEqual_StringString(a, b)` → `(a !== b)` |
| `NotEqualExactly_` | `({p0} != {p1})` | `NotEqualExactly_(a, b)` → `(a != b)` |
| `LessEqual_` | `({p0} <= {p1})` | `LessEqual_FloatFloat(a, b)` → `(a <= b)` |
| `Less_` | `({p0} < {p1})` | `Less_IntInt(a, b)` → `(a < b)` |
| `GreaterEqual_` | `({p0} >= {p1})` | `GreaterEqual_(a, b)` → `(a >= b)` |
| `Greater_` | `({p0} > {p1})` | `Greater_(a, b)` → `(a > b)` |
| `Add_` | `{p0} + {p1}` | `Add_IntInt(a, b)` → `a + b` |
| `Subtract_` | `{p0} - {p1}` | `Subtract_FloatFloat(a, b)` → `a - b` |
| `Multiply_` | `({p0} * {p1})` | `Multiply_FloatFloat(a, b)` → `(a * b)` |
| `Divide` (no underscore) | `({p0} / {p1})` | `Divide_(a, b)` → `(a / b)` |
| `Percent_` | `({p0} % {p1})` | `Percent_(a, b)` → `(a % b)` |
| `Xor_` | `({p0} ^ {p1})` | `Xor_(a, b)` → `(a ^ b)` |
| `Or_` | `({p0} \| {p1})` | `Or_(a, b)` → `(a \| b)` |
| `Not_PreBool` | `!{p0}` | `Not_PreBool(a)` → `!a` |
| `Not_` | `(~{p0})` | `Not_Int(a)` → `(~a)` |
| `Select` | `({p2} ? {p0} : {p1})` | `Select(a, b, cond)` → `(cond ? a : b)` |
| `AddEquals` | `({p0} += {p1})` | `AddEquals(a, b)` → `(a += b)` |
| `Subtract` (no _) | `({p0} - {p1})` | — |
| `BooleanAND` | `{p0} && {p1}` | `BooleanAND(a, b)` → `a && b` |
| `BooleanNAND` | `!({p0} && {p1})` | — |
| `BooleanOR` | `({p0} \|\| {p1})` | — |
| `BooleanXOR` | `{p0} ^ {p1}` | — |
| `BooleanNOR` | `!({p0} \|\| {p1})` | — |
| `Floor` | `Floor({p0})` | — |
| `Abs` | `{p0} < 0.0 ? -{p0} : {p0}` | — |
| `Max` | `(({p0} > {p1}) ? {p0} : {p1})` | — |
| `Clamp` | `(({p0} < {p1}) ? {p1} : (({p0} > {p2}) ? {p2} : {p0}))` | `Clamp(value, min, max)` |
| `Lerp` | `{p0} + {p2} * ({p1} - {p0})` | `Lerp(a, b, alpha)` |
| `Negate` | `-{p0}` | — |
| `Ceil` | `Ceil({p0})` | — |
| `MakeTransform` | `FTransform({p0}, {p1}, {p2})` | location, rotation, scale |
| `MakeRotator` | `FRotator({p0}, {p1}, {p2})` | pitch, yaw, roll |
| `MakeVector` | `FVector({p0}, {p1}, {p2})` | x, y, z |
| `MakeVector2D` | `FVector({p0}, {p1})` | — |
| `MakeColor` | `FLinearColor({p0}, {p1}, {p2}, {p3})` | r, g, b, a |
| `MakeTimespan` | `FTimespan({p0}, {p1}, {p2}, {p4} * 1000 * 1000)` | — |
| `Conv_VectorToTransform` | `FTransform({p0})` | — |
| `Conv_IntToBool` | `({p0} != 0)` | — |
| `Conv_BoolToInt` | `({p0} ? 1 : 0)` | — |
| `Conv_BoolToFloat` | `({p0} ? 1.0f : 0.0f)` | — |
| `*ToDouble` / `*ToFloat` / `*ToInt64` / `*ToInt` / `*ToByte` | C-style cast | `(double){p0}`, `(int32){p0}` |
| `BreakRotator` | Multi-line assignment | `p1 = p0.Roll; p2 = p0.Pitch; p3 = p0.Yaw` |
| `BreakVector` | Multi-line assignment | `p1 = p0.X; p2 = p0.Y; p3 = p0.Z` |
| `BreakTransform` | Multi-line assignment | `p1 = p0.Location; p2 = p0.Rotation; p3 = p0.Scale` |
| `BreakColor` | Multi-line assignment | `p1 = p0.R; p2 = p0.G; p3 = p0.B; p4 = p0.A` |
| `ComposeRotators` | `FRotator(FQuat({p0}) * FQuat({p1}))` | — |
| `*ToVector` | `FVector((float){p0})` | — |
| `*ToLinearColor` | `FLinearColor({p0})` | — |
| `UncheckedConvertI32I64` | `{p0}` (passthrough) | — |

#### KismetStringLibrary (lines 208-231)

| Pattern | Output |
|---------|--------|
| `EqualEqual_` | `{p0} == {p1}` |
| `NotEqual_` | `({p0} !== {p1})` |
| `Conv_BoolToString` | `{p0} ? "true" : "false"` |
| `*ToString` | `FString({p0})` |
| `*ToName` | `FName({p0})` |
| `Concat_StrStr` | `p0 += p1` (string join with +=) |
| `ParseIntoArray` | `{p0}.Split({p1}, /* removeEmpty = */ {p2})` |
| `Contains` | `{p0}.Contains({p1}, ...)` |
| `JoinStringArray` | `{p0}.Join({p1})` |
| `Replace` | `{p0}.Replace({p1}, {p2}, ...)` |
| `StartsWith` | `{p0}.startswith({p1}, ...)` |
| `IsNumeric` | `{p0}.IsNumeric()` |
| `Len` | `{p0}.Length` |

#### KismetSystemLibrary (lines 232-242)

| Pattern | Output |
|---------|--------|
| `IsValid` / `Conv_SoftClass*` / `Conv_SoftObject*` / `Make*` (1 param) | `{p0}` (passthrough) |
| `Conv_ObjectToSoftObjectReference` | `TSoftObjectPtr<UObject>({p0})` |
| `Delay` (3 params) | `Delay({p1}f);\n{p2}` |
| `Conv_ClassToSoftClassReference` | `TSoftClassPtr<UObject>(*{p0})` |

#### KismetInputLibrary / BlueprintGameplayTagLibrary / FortKismetLibrary / KismetTextLibrary (lines 243-248)

| Pattern | Output |
|---------|--------|
| `EqualEqual_` | `{p0} == {p1}` |
| `NotEqual_` | `({p0} !== {p1})` |
| `*ToText` | `FText({p0})` |
| `*ToString` | `FString({p0})` |

#### FinalFunctionCleaner — KismetArrayLibrary (lines 261-274)

| Pattern | Output |
|---------|--------|
| `Array_Length` | `{p0}.Length` |
| `Array_IsNotEmpty` | `{p0}.Length > 0` |
| `Array_LastIndex` | `{p0}.Length - 1` |
| `Array_Clear` | `{p0}.Clear()` |
| `Array_Identical` | `{p0} == {p1}` |
| `Array_Remove` | `{p0}.Remove({p1})` |
| `Array_Add` | `{p0}.Add({p1})` |
| `Array_Get` | `{p2} = {p0}[{p1}]` |
| `Array_Contains` | `{p0}[{p1}]` |
| `Array_IsValidIndex` | `{p0}[{p1}]` |
| `Array_Insert` | `{p0}[{p2}] = {p1}` |

#### BlueprintMapLibrary (lines 276-282)

| Pattern | Output |
|---------|--------|
| `Map_Length` | `{p0}.Length` |
| `Map_Remove` | `{p0}.Remove({p1})` |
| `Map_Contains` | `{p0}[{p1}]` |
| `Map_Get` | `{p2} = {p0}[{p1}]` |

#### BlueprintSetLibrary (lines 284-290)

| Pattern | Output |
|---------|--------|
| `Set_AddItems` | `{p0}.Add({p1})` |
| `Set_Clear` | `{p0}.Clear()` |
| `Set_Difference` | `{p2} = {p0} == {p1}` |
| `Set_IsEmpty` | `{p0}.Length == 0` |

### Implementation Pattern

The cleaner uses **prefix matching** (`StartsWith`) and **suffix matching** (`EndsWith`) on the function name. The order matters — more specific patterns come first (e.g., `NotEqualExactly_` before `NotEqual_`, `EqualEqual_ByteByte` before `EqualEqual_`).

**Python implementation strategy:** Use a list of `(predicate, transformer)` tuples ordered by specificity, or a trie-based lookup for performance.

## Control Flow Patterns

### CUE4Parse Approach

CUE4Parse does **not** implement full structured control flow reconstruction. It uses a **goto-based approach** with a shared execution flow stack:

1. **`EX_PushExecutionFlow`**: Pushes the return address onto `_executionFlowStack`, returns empty string.
2. **`EX_PopExecutionFlow`**: Pops from stack → `goto Label_{target}`. If stack empty → `return`.
3. **`EX_PopExecutionFlowIfNot`**: `if (!condition)` then pop+goto or return.
4. **`EX_Jump`**: Direct `goto Label_{offset}`.
5. **`EX_JumpIfNot`**: `if (!condition) goto Label_{offset}` or `return`.

**Key insight from CUE4Parse (lines 1451-1479):** Both `EX_Jump` and `EX_JumpIfNot` check if the target instruction is an `EX_Return`. If so, they render `return` instead of `goto`. This is a simple optimization that eliminates unnecessary gotos at function exit points.

### Push/Pop Pattern for Structured Reconstruction

The Push/Pop/JumpIfNot pattern is UE's way of encoding structured control flow in bytecode:

```
PushExecutionFlow(else_offset)   → push else_offset, ""
JumpIfNot(condition, else_offset) → if (!condition) goto else_offset
... then block ...
PopExecutionFlow()                → pop → goto else_offset
... else block ...
Label_else_offset:
```

This pattern maps to:
```cpp
if (condition) {
    // then block
} else {
    // else block
}
```

**For `to_function_body()`**, the structured reconstructor should:
1. Build a CFG from the expression list
2. Identify Push/Pop pairs to detect branch boundaries
3. Reconstruct if/else blocks from matching Push+JumpIfNot+Pop patterns
4. Detect loop patterns (back-jumps to earlier offsets)
5. Fall back to goto for unrecognized patterns

## Type Mapping Patterns

### CUE4Parse GetPropertyType (lines 332-454)

CUE4Parse maps UE property types to C++ types:

| UE Property Type | C++ Type |
|---|---|
| `IntProperty` | `int` |
| `Int8/16/64Property` | `int8/int16/int64` |
| `UInt16/32/64Property` | `uint16/uint32/uint64` |
| `ByteProperty` | `byte` |
| `BoolProperty` | `bool` (or `uint8` if not native bool) |
| `FloatProperty` | `float` |
| `DoubleProperty` | `double` |
| `StrProperty` / `VerseStringProperty` | `FString` |
| `NameProperty` | `FName` |
| `TextProperty` | `FText` |
| `ObjectProperty` / `ClassProperty` | `class UClass*` |
| `SoftObjectProperty` / `AssetObjectProperty` | `FSoftObjectPath` |
| `StructProperty` | `struct F{StructName}` |
| `InterfaceProperty` | `F{InterfaceName}` |
| `ArrayProperty` | `TArray<{InnerType}>` |
| `MapProperty` | `TMap<{KeyType}, {ValueType}>` |
| `EnumProperty` | `{EnumName}` |
| `OptionalProperty` | `TOptional<{ValueType}>` |

**Pointer logic (lines 322-325):** If `ReferenceParm`, `InstancedReference`, `ContainsInstancedReference`, or `ObjectProperty` → append `*`.

**Reference logic (lines 450-451):** If `OutParm` and not `ReturnParm` → append `&`.

**Const logic (lines 338-340):** If `ConstParm` → prepend `const `.

### Class Prefix (lines 34-97)

UE convention for class prefixes:
- `Actor` → `A` prefix
- `Interface` → `I` prefix
- `Object` → `U` prefix

CUE4Parse walks the inheritance chain to find the right prefix. For our implementation, we can use a simpler heuristic: check the parent class name.

## Python Implementation Architecture

Based on CUE4Parse analysis and project conventions, recommend the following structure:

### Option A: Methods on Expression Classes (RECOMMENDED)

Add `line_cpp(self, type_registry=None) -> str` method to each `KismetExpression` subclass. This follows the project's existing pattern where each class knows how to serialize itself (`to_dict()`).

**Pros:** Natural fit with existing architecture, easy to extend per-type, testable individually.
**Cons:** Requires touching every expression file.

### Option B: Central Dispatcher

Single `KismetTranslator` class with a `match/case` dispatch, mirroring CUE4Parse's approach.

**Pros:** Single file, easier to maintain, exactly matches CUE4Parse pattern.
**Cons:** Diverges from project's per-class pattern, large file.

**Recommendation:** Option B for `line_cpp()` (central dispatcher), because:
1. It exactly mirrors CUE4Parse's proven pattern
2. Easier to keep in sync with CUE4Parse updates
3. All translation logic in one place for review
4. The `match/case` pattern is already used in the project

For `to_function_body()`, use a separate `FunctionBodyBuilder` class that takes the expression list and assembles the output.

## Code Examples

### line_cpp() for EX_CallMath

```python
def line_cpp_math_function(className: str, functionName: str, params: list[str]) -> str:
    if className in ("KismetMathLibrary",) or className.startswith("SolarisMathLibrary_"):
        if functionName.startswith("EqualEqual_ByteByte"):
            return f"((!{params[0]}) == (!{params[1]}))"
        if functionName.startswith("EqualEqual_"):
            return f"{params[0]} == {params[1]}"
        if functionName.startswith("Add_"):
            return f"{params[0]} + {params[1]}"
        # ... more patterns ...
    return f"{get_prefix(className)}{className}::{functionName}({', '.join(params)})"
```

### StackNode parsing (from CUE4Parse)

CUE4Parse parses the StackNode string to extract class and function names:
```csharp
var stackNode = final.StackNode.ToString();
var functionName = stackNode.SubstringAfter(':').Trim('\'');
var className = stackNode.SubstringAfter('.').SubstringBefore(':');
```

In Python, StackNode is an `int` (package index). The class/function name resolution requires the linker to resolve the index to a name string. This will be done via the linker in Phase 62's output.

### to_function_body() assembly

```python
def to_function_body(expressions: list[KismetExpression], type_registry: TypeRegistry) -> str:
    lines = []
    label_map = build_label_map(expressions)
    for i, expr in enumerate(expressions):
        cpp = expr.line_cpp(type_registry)
        if not cpp:
            continue
        if is_terminator(expr):
            lines.append(f"    {cpp};")
        else:
            lines.append(f"    {cpp};")
    return "\n".join(lines)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Function name beautification | Custom regex engine | MathFunctionCleaner pattern | CUE4Parse's prefix/suffix matching is proven and covers all UE library functions |
| Type mapping | Manual if/else for each type | Table-driven mapping from GetPropertyType | 30+ UE types, CUE4Parse already mapped them all |
| Control flow reconstruction | Full decompiler (e.g., angr) | Push/Pop pattern matching + goto fallback | UE bytecode uses a specific execution flow stack pattern, not arbitrary jumps |
| String formatting | Manual concatenation | f-strings + indentation helper | CUE4Parse uses CustomStringBuilder with indent control |

**Key insight:** CUE4Parse's approach is mature and battle-tested across dozens of games. The MathFunctionCleaner alone has 80+ function mappings — rebuilding this from scratch without the reference would miss edge cases.

## Common Pitfalls

### Pitfall 1: String Token Parsing in EX_FinalFunction
**What goes wrong:** In CUE4Parse, `StackNode.ToString()` produces a path like `'Default__KismetMathLibrary.Add_IntInt:0'`. The code extracts className and functionName via substring operations.
**Why it happens:** In our Python code, `StackNode` is stored as `int` (package index), not a resolved string.
**How to avoid:** The linker (Phase 62) must resolve StackNode to a full name string before line_cpp() is called. Or use the linker during translation to resolve the index.
**Warning signs:** `line_cpp()` outputs raw integers instead of function names.

### Pitfall 2: Execution Flow Stack State Leakage
**What goes wrong:** CUE4Parse uses a static `_executionFlowStack` shared across all `GetLineExpression()` calls. If called concurrently or for multiple functions without clearing, state leaks between calls.
**Why it happens:** The stack is a module-level static variable.
**How to avoid:** In Python, make the execution flow stack an instance variable of the translator class, reset it per function body.

### Pitfall 3: Parameter Order in Select/Cleanup Functions
**What goes wrong:** `Select` function takes `(trueValue, falseValue, condition)` but the ternary output needs `condition ? trueValue : falseValue`. CUE4Parse handles this as `{p2} ? {p0} : {p1}`.
**Why it happens:** UE Kismet function parameter order differs from C++ ternary order.
**How to avoid:** Explicitly document parameter reordering for `Select` and similar functions.

### Pitfall 4: StringConst Null Terminator
**What goes wrong:** CUE4Parse reads `XFERSTRING()` then manually advances position past the null terminator (`Ar.Position++`).
**Why it happens:** UE string constants are null-terminated in bytecode.
**How to avoid:** Already handled in Phase 62's `EX_StringConst.from_archive()`. Just ensure `line_cpp()` wraps the value in quotes and escapes newlines.

### Pitfall 5: Missing Expression Types in Switch
**What goes wrong:** CUE4Parse throws `NotImplementedException` for unhandled expression types. The comment at line 1771-1777 lists known gaps: `EX_Assert`, `EX_Skip`, `EX_InstrumentationEvent`, `EX_FieldPathConst`, `EX_ClassContext`.
**Why it happens:** Not all expression types are commonly encountered, so some are left unimplemented.
**How to avoid:** Our implementation should handle ALL expression types in EXPR_CLASS_MAP (90+ classes). For rare/unsupported types, output `/* unsupported: {type_name} */`.

## Anti-Patterns to Avoid

- **Post-processing string replacement:** Don't generate raw output then regex-replace it. Do the right thing during translation (MathFunctionCleaner is called inline, not as a post-process).
- **Hardcoding UE type names:** Don't hardcode `UKismetMathLibrary` everywhere. Use the class name from the bytecode and let the cleaner match generically.
- **Ignoring EX_EndOfScript:** The end-of-script marker should not produce output. CUE4Parse returns `""` for it.

## Key Code Excerpts

### EX_Jump with Return Optimization (CUE4Parse line 1470-1479)
```csharp
case EX_Jump jump:
    var targetIndex = (int)jump.CodeOffset;
    targetIndex = Array.FindIndex(Function.ScriptBytecode, stmt => stmt.StatementIndex == targetIndex);
    if (targetIndex >= 0 && targetIndex < Function.ScriptBytecode.Length &&
        (Function.ScriptBytecode[targetIndex] is EX_Return || Function.ScriptBytecode[targetIndex++] is EX_Return))
    {
        return "return";
    }
    return $"goto Label_{jump.CodeOffset}";
```
This shows CUE4Parse checking if the jump target is a return statement and optimizing to `return`.

### EX_Context Rendering (CUE4Parse line 1197-1218)
```csharp
case EX_Context context:
    var function = context?.ContextExpression is not null
        ? GetLineExpression(context?.ContextExpression).SubstringAfter("::")
        : "failedplaceholder";
    var obj = context?.ObjectExpression is not null
        ? GetLineExpression(context?.ObjectExpression)
        : "failedplaceholder";
    if (obj == "FindObject<UObject>(nullptr, this)" || obj.Contains("KismetArrayLibrary") ||
        (!function.EndsWith("Map_Find") && obj.Contains("BlueprintMapLibrary")) || obj.Contains("BlueprintSetLibrary"))
    {
        customStringBuilder.Append(function);
    }
    else
    {
        customStringBuilder.Append($"{obj}->{function}");
    }
```

### EX_LetValueOnPersistentFrame (CUE4Parse line 1170-1175)
```csharp
case EX_LetValueOnPersistentFrame persistent:
    var variableAssignment = GetLineExpression(persistent.AssignmentExpression);
    var variableToBeAssigned = persistent.DestinationProperty.ToString();
    return $"{(variableToBeAssigned.Contains("K2Node_") ? "UberGraphFrame->" + variableToBeAssigned : variableToBeAssigned)} = {variableAssignment}";
```
Shows special handling for UberGraphFrame-prefixed variables.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw bytecode dump | Expression tree → C++ pseudocode | UE4 era | Human-readable blueprint logic |
| Post-processing regex cleanup | Inline MathFunctionCleaner | CUE4Parse | Cleaner output, fewer edge cases |
| Pure goto output | Structured if/else reconstruction | Modern decompilers | Readability, maintainability |

**Deprecated/outdated:**
- **Raw EX_CallMath rendering:** Always clean via MathFunctionCleaner. Raw `UKismetMathLibrary::Add_IntInt(a, b)` output is harder to read than `a + b`.
- **Manual string concatenation:** Use f-strings with proper escaping.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | StackNode in Python project is stored as `int` (not resolved string) | Python Implementation Architecture | MEDIUM — line_cpp() will need linker lookup to resolve function names |
| A2 | `SubstringAfter` helper in C# is equivalent to Python `str.split(':', 1)[1]` | Code Excerpts | LOW — trivial string operation |
| A3 | Phase 62 output includes statement index mapping for label resolution | Control Flow Patterns | MEDIUM — Jump targets need statement index → label mapping |

## Open Questions

1. **How does StackNode resolution work in Phase 62?**
   - What we know: CUE4Parse's `StackNode.ToString()` produces a resolved name like `'Default__KismetMathLibrary.Add_IntInt:0'`. Our project stores it as `int`.
   - What's unclear: Whether Phase 62 resolves these to names during parsing, or whether Phase 63 needs to do it.
   - Recommendation: If not resolved in Phase 62, add a `resolve_function_name(stack_node_index)` helper that queries the linker's name table.

2. **Should `line_cpp()` be a method on expression classes or a central dispatcher?**
   - What we know: CUE4Parse uses a central dispatcher. Our project uses per-class `to_dict()`.
   - What's unclear: Which approach is easier to maintain and test.
   - Recommendation: Central dispatcher (Option B) for consistency with CUE4Parse, with a thin `line_cpp()` method wrapper on each class if needed.

## Environment Availability

No external dependencies. Python 3.10+ stdlib only.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | Standard pytest.ini / pyproject.toml |
| Quick run command | `python -m pytest tests/ -x -k "line_cpp or kismet" --tb=short` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01 | `line_cpp()` returns single-line C++ string per expression | unit | `pytest tests/ -k line_cpp -x` | ❌ Wave 0 |
| D-01 | `to_function_body()` returns indented function body | unit | `pytest tests/ -k function_body -x` | ❌ Wave 0 |
| D-02 | `line_cpp()` renders goto for jumps | unit | `pytest tests/ -k goto -x` | ❌ Wave 0 |
| D-02 | `to_function_body()` reconstructs if/else from Push/Pop | unit | `pytest tests/ -k structured -x` | ❌ Wave 0 |
| D-04/D-05 | MathFunctionCleaner transforms KismetMathLibrary calls | unit | `pytest tests/ -k math_cleaner -x` | ❌ Wave 0 |
| D-06/D-07 | TypeRegistry resolves variable types | unit | `pytest tests/ -k type_registry -x` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `tests/kismet/test_line_cpp.py` — covers D-01, D-02
- [ ] `tests/kismet/test_math_cleaner.py` — covers D-04, D-05
- [ ] `tests/kismet/test_type_registry.py` — covers D-06, D-07
- [ ] `tests/kismet/test_function_body.py` — covers D-01, D-02

## Sources

### Primary (HIGH confidence)
- [CUE4Parse KismetExpression.cs](E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\KismetExpression.cs) — All expression class definitions (1510 lines)
- [CUE4Parse BlueprintDecompilerUtils.cs](E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\BlueprintDecompiler\BlueprintDecompilerUtils.cs) — GetLineExpression, MathFunctionCleaner, FinalFunctionCleaner, GetPropertyType (1783 lines)
- [Project EXPR_CLASS_MAP](E:\Develop\uasset_read\src\uasset_read\kismet\expressions\__init__.py) — 90+ expression classes mapped

### Secondary (MEDIUM confidence)
- [Project expression modules](E:\Develop\uasset_read\src\uasset_read\kismet\expressions\*.py) — Data structures for all expression types
- [Project variable extractor](E:\Develop\uasset_read\src\uasset_read\blueprint\variable_extractor.py) — BlueprintVariable/BlueprintMetadata extraction
- [Project tokens.py](E:\Develop\uasset_read\src\uasset_read\kismet\tokens.py) — EExprToken/ECastToken enum definitions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — No external packages, pure Python stdlib
- Architecture: HIGH — Directly derived from CUE4Parse source code
- MathFunctionCleaner mappings: HIGH — Extracted line-by-line from BlueprintDecompilerUtils.cs
- Control flow patterns: HIGH — Directly from CUE4Parse GetLineExpression switch cases
- Type mappings: HIGH — Directly from CUE4Parse GetPropertyType
- Pitfalls: MEDIUM — Based on code analysis, not runtime testing

**Research date:** 2026-05-20
**Valid until:** 2026-06-20 (30 days — CUE4Parse source is stable, mappings unlikely to change)
