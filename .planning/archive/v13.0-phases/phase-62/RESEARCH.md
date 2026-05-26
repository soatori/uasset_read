# Phase 62: 字节码 → 表达式树 - Research

**Researched:** 2026-05-20
**Domain:** Unreal Engine Kismet bytecode deserialization (UStruct → FKismetArchive → KismetExpression[])
**Confidence:** HIGH

## Summary

Phase 62 的核心任务是从 UStruct 节点中提取 ScriptBytecode 字节流，通过 FKismetArchive 将其反序列化为 KismetExpression 表达式列表。CUE4Parse 提供了完整的参考实现：UStruct.cs 定义了 ScriptBytecode 的序列化格式（`bytecodeBufferSize` + `serializedScriptSize` 两个 int header，随后是 `byte[serializedScriptSize]` 数据段），FKismetArchive.cs 实现了基于 switch 分派的逐条读取，UClass.cs 的 `DecompileBlueprintToPseudo()` 展示了从函数遍历到表达式输出的完整流程。

本项目 Phase 61 已完成 FKismetArchive 及 ~90 个 KismetExpression 子类的实现，所有在 EXPR_CLASS_MAP 中注册的表达式类都有完整的 `from_archive()` 实现（无 stub/NotImplementedError）。Phase 62 的关键缺口在于：(1) 如何从已有的属性解析链路中提取 ScriptBytecode 原始字节，(2) 如何构建从 K2Node_FunctionEntry / EventGraph 节点到 FKismetArchive 的入口函数。

**Primary recommendation:** 新增 `kismet/bytecode_extractor.py` 模块，通过 UStruct 反序列化模式（bytecodeBufferSize + serializedScriptSize header + byte[] 数据）读取字节流，复用 FKismetArchive.read_expression() 循环直到 EX_EndOfScript，返回 `list[KismetExpression]`。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** ScriptBytecode 从函数图（K2Node_FunctionEntry）和事件图（EventGraph）节点中提取。覆盖两种入口点，确保完整的字节码解析范围。
- **D-02:** ScriptBytecode 的序列化格式参考 CUE4Parse UStruct.cs：头部为 `bytecodeBufferSize` (int) + `serializedScriptSize` (int)，随后是 `byte[]` 数据段。需要先读取两个 int header，再用 serializedScriptSize 长度的字节数组构建 FKismetArchive。
- **D-03:** 采用 CUE4Parse BlueprintDecompilerUtils 的方式——在表达式树遍历阶段处理 JMP/Label，不在 Phase 62 预构建 CFG。Phase 62 负责把字节码读成带嵌套子树的表达式列表，JMP 的 CodeOffset 作为属性存储。控制流结构化（JMP/CMP/POP → if/while/for）留给 Phase 63。
- **D-04:** 遵循 CUE4Parse ReadExpressionArray() 模式：循环调用 read_expression() 直到遇到 EX_EndOfScript。每个表达式的 from_archive() 自动递归读取子节点（如 EX_Call 读取参数、EX_Context 读取左右子表达式、EX_JumpIfNot 读取 BooleanExpression）。最终得到 `list[KismetExpression]`。
- **D-05:** FKismetArchive 支持可切换模式：默认严格模式（未知 token 抛 ParseError），可通过构造参数切换为容错模式（跳过未知字节到下一个已知边界继续解析）。与项目现有 FArchive tolerant 模式一致。

### Claude's Discretion
- ScriptBytecode 属性的具体读取路径（从 PropertyTag → PropertyValue → 字节数组提取）由实现者根据 Phase 61 已有的属性解析链路自行判断
- 表达式列表的输出格式（flat list vs 带层级关系的树结构）由实现者判断，建议同时支持两种视图

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ScriptBytecode 字节提取 | API / Backend (Deserializer) | — | 从已反序列化的 UStruct 属性数据中提取字节数组 |
| 字节流 → 表达式树 | Kismet Module (FKismetArchive) | — | Phase 61 已实现的字节码反序列化器 |
| 表达式列表输出 | API / Backend | — | 返回 flat list + 嵌套子树（由 from_archive 递归构建） |
| 函数图节点定位 | Blueprint Module | Link Module | 通过 K2Node_FunctionEntry / EventGraph 找到含字节码的函数 |

## CUE4Parse Serialization Pattern (UStruct → Bytecode Bytes)

**Source:** `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UStruct.cs` lines 18-67 [CITED: CUE4Parse UStruct.cs]

### Deserialization Flow

```csharp
// UStruct.cs lines 40-66
var bytecodeBufferSize = Ar.Read<int>();        // int: buffer size
var serializedScriptSize = Ar.Read<int>();       // int: actual script data size

if (Ar.Owner!.Provider?.ReadScriptData == true && serializedScriptSize > 0)
{
    using var kismetAr = new FKismetArchive(Name, Ar.ReadBytes(serializedScriptSize), Ar.Owner, Ar.Versions);
    var tempCode = new List<KismetExpression>();
    try
    {
        while (kismetAr.Position < kismetAr.Length)  // Loop until stream exhausted
        {
            tempCode.Add(kismetAr.ReadExpression());
        }
    }
    catch (Exception e)
    {
        Log.Warning(e, $"Failed to serialize script bytecode in {Name}");
    }
    finally
    {
        ScriptBytecode = [.. tempCode];
    }
}
else
{
    Ar.Position += serializedScriptSize;  // Skip bytecode if not reading
}
```

### Key Findings

1. **Header format:** Two consecutive `int` values: `bytecodeBufferSize` (total buffer capacity) and `serializedScriptSize` (actual bytecode data length). The bytecode data is exactly `serializedScriptSize` bytes. [VERIFIED: CUE4Parse UStruct.cs]

2. **Loop termination:** CUE4Parse loops `while (kismetAr.Position < kismetAr.Length)` — it does NOT check for EX_EndOfScript as a loop terminator. The stream naturally ends when all bytes are consumed. EX_EndOfScript (0x53) is the last expression in the stream. [VERIFIED: CUE4Parse UStruct.cs line 49]

3. **Error handling:** try/catch around the entire loop — any exception logs a warning and the partially-parsed list is still assigned to ScriptBytecode. [VERIFIED: CUE4Parse UStruct.cs lines 47-60]

4. **Provider flag:** `Ar.Owner.Provider.ReadScriptData` controls whether bytecode is actually parsed. If false, the stream position is simply advanced by `serializedScriptSize`. [VERIFIED: CUE4Parse UStruct.cs line 43]

5. **UStruct hierarchy:** UStruct extends UField. UFunction (which represents blueprint functions) inherits from UStruct, so UFunction instances automatically have the ScriptBytecode field populated during deserialization. [VERIFIED: CUE4Parse UStruct.cs line 13]

### Difference from FKismetArchive.ReadExpressionArray()

```csharp
// FKismetArchive.cs lines 177-188
public KismetExpression[] ReadExpressionArray(EExprToken endToken)
{
    var newData = new List<KismetExpression>();
    KismetExpression? currExpression = null;
    while (currExpression == null || currExpression.Token != endToken)
    {
        if (currExpression != null) newData.Add(currExpression);
        currExpression = ReadExpression();
    }
    return newData.ToArray();
}
```

**Critical difference:** `ReadExpressionArray()` uses an explicit `endToken` parameter to terminate the loop, while `UStruct.Deserialize()` loops until the byte stream is exhausted. Both produce equivalent results because the bytecode stream always ends with EX_EndOfScript (0x53). [VERIFIED: CUE4Parse FKismetArchive.cs]

## FKismetArchive ReadExpressionArray Pattern

**Source:** `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Readers\FKismetArchive.cs` [CITED: CUE4Parse FKismetArchive.cs]

### ReadExpression() Switch Dispatch

Lines 32-150: Reads 1 byte token, then uses C# `switch` expression to construct the appropriate `KismetExpression` subclass. Each expression's constructor receives `this` (the FKismetArchive) and reads its own fields. The pattern is:

```csharp
var index = Index;                          // Save position before reading
var token = (EExprToken)Read<byte>();       // Read token byte
KismetExpression expression = token switch  // Switch dispatch
{
    EExprToken.EX_LocalVariable => new EX_LocalVariable(this),
    EExprToken.EX_IntConst => new EX_IntConst(this),
    // ... ~85 more cases
    _ => throw new ParserException($"Unknown EExprToken {token}")
};
expression.StatementIndex = index;          // Assign saved position
return expression;
```

### Our Python Equivalent

`E:\Develop\uasset_read\src\uasset_read\kismet\archive.py` lines 29-47:

```python
def read_expression(self) -> KismetExpression:
    stmt_index = self.tell()
    token_byte = self.read_u8()
    token = EExprToken(token_byte)
    expr_class = EXPR_CLASS_MAP.get(token)
    if expr_class is None:
        raise ParseError(f"Unknown EExprToken {token.name} (0x{token_byte:02X}) at offset {stmt_index}")
    if hasattr(expr_class, 'from_archive'):
        expr = expr_class.from_archive(self, self._name_map)
    else:
        expr = expr_class()
    expr.StatementIndex = stmt_index
    return expr
```

**Assessment:** The Python implementation is functionally equivalent to CUE4Parse. EXPR_CLASS_MAP serves the same purpose as the C# switch expression. [VERIFIED: code comparison]

### read_expression_array() Analysis

`E:\Develop\uasset_read\src\uasset_read\kismet\archive.py` lines 49-57:

```python
def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]:
    result = []
    while True:
        expr = self.read_expression()
        if expr.Token == end_token:
            break
        result.append(expr)
    return result
```

**Assessment:** Correctly mirrors CUE4Parse's ReadExpressionArray() pattern. The end_token expression is NOT included in the result. When called with `EExprToken.EX_EndOfScript`, it will read all expressions up to and including EX_EndOfScript, then return the list excluding EX_EndOfScript itself. [VERIFIED: logic analysis]

## Blueprint Decompilation Pipeline

**Source:** `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UClass.cs` lines 108-339 [CITED: CUE4Parse UClass.cs]

### High-Level Flow

```
DecompileBlueprintToPseudo()
  ├── Get class hierarchy (derivedClass, baseClass, accessSpecifier)
  ├── Collect variables from Properties + ChildProperties
  ├── ── PASS 1: Reverse iteration of FuncMap ──────────────────
  │   └── For each UFunction.ScriptBytecode:
  │       └── Collect jump targets (EX_Jump, EX_LocalFinalFunction,
  │           EX_CallMath with Delay, EX_PushExecutionFlow)
  │       └── Build jumpCodeOffsetsMap: label_name -> [offsets]
  │
  └── ── PASS 2: Forward iteration of FuncMap ───────────────────
      └── For each UFunction:
          ├── Extract return type and parameters from ChildProperties
          ├── For each expression in ScriptBytecode:
          │   ├── Skip end markers (EX_EndOfScript, EX_EndFunctionParms, etc.)
          │   ├── Insert Label_NNN: if jump target
          │   └── GetLineExpression(expr) -> pseudo-code string
          └── Output function body
```

### Key Observations for Phase 62

1. **FuncMap iteration:** Functions are accessed via `FuncMap.Values`, each resolved to a `UFunction` export. `UFunction.ScriptBytecode` is already a `KismetExpression[]` (populated by UStruct.Deserialize()). [VERIFIED: UClass.cs lines 164-167]

2. **ScriptBytecode null check:** `if (function?.ScriptBytecode == null) continue;` — functions without bytecode are skipped (native functions, etc.). [VERIFIED: UClass.cs line 168]

3. **Expression filtering:** Lines 305-306 skip all "end marker" expressions during output:
   ```csharp
   if (kismetExpression is EX_Nothing or EX_NothingInt32 or EX_EndFunctionParms
       or EX_EndStructConst or EX_EndArray or EX_EndArrayConst or EX_EndSet
       or EX_EndMap or EX_EndMapConst or EX_EndSetConst or EX_EndOfScript)
       continue;
   ```

4. **Label insertion:** Jump target offsets are matched against `StatementIndex` to insert `Label_NNN:` markers. This is Phase 63 territory. [VERIFIED: UClass.cs lines 308-309]

## Current Implementation Gap Analysis

### What Exists (Phase 61)

| Component | File | Status |
|-----------|------|--------|
| FKismetArchive | `kismet/archive.py` | Complete — read_expression, read_expression_array, xfer_string/unicode, read_fname_kismet |
| EExprToken enum | `kismet/tokens.py` | Complete — all tokens 0x00-0xFF, including game-specific |
| ECastToken enum | `kismet/tokens.py` | Complete |
| Helper enums | `kismet/tokens.py` | Complete — EScriptInstrumentationType, EBlueprintTextLiteralType, EAutoRtfmStopTransactMode |
| EXPR_CLASS_MAP | `kismet/expressions/__init__.py` | 82 token-to-class mappings |
| ~90 expression classes | `kismet/expressions/*.py` | Complete — all have from_archive() or are zero-parameter |
| FKismetPropertyPointer | `kismet/property_pointer.py` | Complete — FFieldPath + bNew/bOld handling |

### What's Missing (Phase 62 Scope)

| Gap | Description | Required? |
|-----|-------------|-----------|
| Bytecode entry point | No function to extract ScriptBytecode bytes from UStruct/deserialized nodes | YES |
| UStruct model | No UStruct dataclass with ScriptBytecode field | YES |
| Function graph node identification | No mechanism to find K2Node_FunctionEntry / EventGraph nodes that contain bytecode | YES |
| Tolerant mode for FKismetArchive | D-05 requires switchable strict/tolerant mode | YES |
| End-of-stream vs end-token reading | read_expression_array uses end_token; UStruct uses stream exhaustion | Design choice |

### No Gaps in Expression Coverage

All 82 tokens in EXPR_CLASS_MAP have corresponding expression classes with complete `from_archive()` implementations. Zero stubs found (no `pass` or `NotImplementedError` in any expression file's `from_archive` method).

## ScriptBytecode Extraction Strategy

### CUE4Parse Approach (Definitive Reference)

From `UStruct.cs` lines 40-66: The bytecode is NOT stored as a property tag value. It is embedded directly in the UStruct serialization stream:

```
[SuperStruct: FPackageIndex]
[Children: FPackageIndex[]]
[ChildProperties: FProperty[]]  (if FProperties version)
[bytecodeBufferSize: int32]
[serializedScriptSize: int32]
[bytecode data: serializedScriptSize bytes]
```

**Key insight:** ScriptBytecode is a first-class field of UStruct, not an ArrayProperty. It is read directly from the binary stream at a fixed position in the UStruct serialization layout. [VERIFIED: CUE4Parse UStruct.cs]

### Our Project's Current Deserialization Path

The existing pipeline uses:
1. `parse_properties_from_export()` → property tag loop (PropertyTag → PropertyValue)
2. `PackageLinker` → UObjectInstance preload for property extraction
3. Blueprint modules → graph/node/pin extraction from UEdGraph

**The gap:** None of these currently handle UStruct-level ScriptBytecode because:
- Properties are parsed per-export, not per-UStruct
- UStruct deserialization (with bytecode) is not yet implemented in the project
- K2Node_FunctionEntry and event graph functions may not be routed through UStruct deserialization

### Two Approaches for Phase 62

#### Approach A: UStruct Deserialization (CUE4Parse faithful)

Implement a `deserialize_ustruct(archive, export)` function that:
1. Seeks to the export's property region
2. Reads UStruct fields (SuperStruct, Children, ChildProperties if versioned)
3. Reads `bytecodeBufferSize` + `serializedScriptSize`
4. Extracts `serializedScriptSize` bytes
5. Creates FKismetArchive and reads expressions

**Pros:** Faithful to UE serialization format, handles all UStruct-derived types
**Cons:** Requires understanding of where UStruct exports are located in the export table, version-specific handling

#### Approach B: Property-Based Extraction (Leverage existing infrastructure)

If ScriptBytecode appears as an `ArrayProperty` of `ByteProperty` on K2Node nodes (the "generated implementation" approach used by UE), extract it through the existing property parsing chain:
1. Find K2Node_FunctionEntry / EventGraph CallForFunction entries
2. Locate the ScriptBytecode property in the node's property list
3. Extract the raw byte array
4. Feed to FKismetArchive

**Pros:** Reuses existing property_parser infrastructure
**Cons:** May not work if bytecode is embedded at UStruct level rather than as a property

### Recommended: Approach A with Fallback to B

CUE4Parse's definitive implementation (UStruct.cs) reads bytecode at the UStruct level, not as a property. Phase 62 should implement:

```python
def extract_bytecode_from_ustruct(archive: FArchive, export: ObjectExport) -> bytes | None:
    """Extract ScriptBytecode bytes from a UStruct export."""
    # Seek to property start
    archive.seek(export.serial_offset)

    # Skip SuperStruct (FPackageIndex = 4 bytes)
    archive.skip(4)

    # Skip Children array (depends on version)
    # ... version-specific handling

    # Skip ChildProperties (if FProperties version)
    # ... property deserialization

    # Read bytecode header
    bytecode_buffer_size = archive.read_i32()
    serialized_script_size = archive.read_i32()

    if serialized_script_size <= 0:
        return None

    # Read bytecode bytes
    return archive.read_bytes(serialized_script_size)
```

Then:
```python
def parse_bytecode(bytecode_bytes: bytes, name_map: list[str]) -> list[KismetExpression]:
    """Parse bytecode bytes into expression list."""
    archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map)
    expressions = []
    while archive.tell() < len(bytecode_bytes):
        try:
            expr = archive.read_expression()
            expressions.append(expr)
        except ParseError:
            if archive._tolerant:
                continue
            raise
    return expressions
```

### How to Find K2Node_FunctionEntry / EventGraph Nodes with Bytecode

Per CONTEXT.md D-01, both function graphs and event graphs need coverage. The discovery path:

1. **K2Node_FunctionEntry:** These are export objects in the package. Find them by iterating exports where `ObjectClass` matches "K2Node_FunctionEntry". Each has properties including the function reference.

2. **EventGraph functions:** The EventGraph itself is a UEdGraph. Its nodes include event nodes that call functions. The functions themselves are UFunction exports with ScriptBytecode.

3. **UFunction exports:** The most direct approach — iterate all exports, identify UFunction-type exports, and extract their ScriptBytecode via the UStruct deserialization path.

## Expression Class Coverage Analysis

### Complete Coverage — All Classes Have from_archive()

| File | Classes with from_archive() | Zero-Param Classes | Status |
|------|----------------------------|-------------------|--------|
| `variables.py` | EX_VariableBase (5 subclasses) | — | COMPLETE |
| `literals.py` | EX_IntConst, EX_FloatConst, EX_ByteConst, EX_IntConstByte, EX_Int64Const, EX_UInt64Const, EX_DoubleConst | EX_IntZero, EX_IntOne, EX_True, EX_False | COMPLETE |
| `string_consts.py` | EX_StringConst, EX_UnicodeStringConst, EX_TextConst, EX_SoftObjectConst | — | COMPLETE |
| `vector_consts.py` | EX_VectorConst, EX_RotationConst, EX_TransformConst, EX_Vector3fConst | — | COMPLETE |
| `control_flow.py` | EX_Jump, EX_JumpIfNot, EX_Skip, EX_ComputedJump, EX_PushExecutionFlow, EX_PopExecutionFlowIfNot, EX_SkipOffsetConst | EX_PopExecutionFlow, EX_EndOfScript | COMPLETE |
| `assignments.py` | EX_Let, EX_LetBase (5 subclasses), EX_LetValueOnPersistentFrame | — | COMPLETE |
| `functions.py` | EX_FinalFunction, EX_VirtualFunction, EX_CallMulticastDelegate | EX_EndParmValue, EX_EndFunctionParms | COMPLETE |
| `casts.py` | EX_Cast, EX_CastBase (5 subclasses) | — | COMPLETE |
| `context.py` | EX_Context, EX_InterfaceContext, EX_StructMemberContext | — | COMPLETE |
| `containers.py` | EX_SetArray, EX_SetMap, EX_SetSet, EX_ArrayConst, EX_MapConst, EX_SetConst, EX_ArrayGetByRef | EX_EndArray, EX_EndMap, EX_EndSet, EX_EndArrayConst, EX_EndMapConst, EX_EndSetConst | COMPLETE |
| `structs.py` | EX_StructConst, EX_PropertyConst, EX_BitFieldConst | EX_EndStructConst | COMPLETE |
| `delegates.py` | EX_AddMulticastDelegate, EX_ClearMulticastDelegate, EX_BindDelegate, EX_RemoveMulticastDelegate, EX_InstanceDelegate | — | COMPLETE |
| `special.py` | EX_Return, EX_Assert, EX_SwitchValue, EX_InstrumentationEvent, EX_FieldPathConst, EX_ObjectConst, EX_NameConst | EX_Nothing, EX_NothingInt32, EX_Self, EX_NoObject, EX_NoInterface, EX_DeprecatedOp4A, EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint | COMPLETE |
| `rtfm.py` | EX_AutoRtfmTransact, EX_AutoRtfmStopTransact | EX_AutoRtfmAbortIfNot | COMPLETE |

### Coverage Summary

- **Total expression classes:** ~90
- **With from_archive():** ~70
- **Zero-parameter (no from_archive needed):** ~20
- **Stubs/NotImplementedError found:** 0

### EXPR_CLASS_MAP Completeness

| Token | Mapped? | Token | Mapped? |
|-------|---------|-------|---------|
| EX_LocalVariable (0x00) | Yes | EX_UnicodeStringConst (0x34) | Yes |
| EX_InstanceVariable (0x01) | Yes | EX_Int64Const (0x35) | Yes |
| EX_DefaultVariable (0x02) | Yes | EX_UInt64Const (0x36) | Yes |
| EX_Return (0x04) | Yes | EX_DoubleConst (0x37) | Yes |
| EX_Jump (0x06) | Yes | EX_Cast (0x38) | Yes |
| EX_JumpIfNot (0x07) | Yes | EX_SetSet (0x39) | Yes |
| EX_Assert (0x09) | Yes | EX_EndSet (0x3A) | Yes |
| EX_Nothing (0x0B) | Yes | EX_SetMap (0x3B) | Yes |
| EX_NothingInt32 (0x0C) | Yes | EX_EndMap (0x3C) | Yes |
| EX_Let (0x0F) | Yes | EX_SetConst (0x3D) | Yes |
| EX_BitFieldConst (0x11) | Yes | EX_EndSetConst (0x3E) | Yes |
| EX_ClassContext (0x12) | Yes | EX_MapConst (0x3F) | Yes |
| EX_MetaCast (0x13) | Yes | EX_EndMapConst (0x40) | Yes |
| EX_LetBool (0x14) | Yes | EX_Vector3fConst (0x41) | Yes |
| EX_EndParmValue (0x15) | Yes | EX_StructMemberContext (0x42) | Yes |
| EX_EndFunctionParms (0x16) | Yes | EX_LetMulticastDelegate (0x43) | Yes |
| EX_Self (0x17) | Yes | EX_LetDelegate (0x44) | Yes |
| EX_Skip (0x18) | Yes | EX_LocalVirtualFunction (0x45) | Yes |
| EX_Context (0x19) | Yes | EX_LocalFinalFunction (0x46) | Yes |
| EX_Context_FailSilent (0x1A) | Yes | EX_LocalOutVariable (0x48) | Yes |
| EX_VirtualFunction (0x1B) | Yes | EX_DeprecatedOp4A (0x4A) | Yes |
| EX_FinalFunction (0x1C) | Yes | EX_InstanceDelegate (0x4B) | Yes |
| EX_IntConst (0x1D) | Yes | EX_PushExecutionFlow (0x4C) | Yes |
| EX_FloatConst (0x1E) | Yes | EX_PopExecutionFlow (0x4D) | Yes |
| EX_StringConst (0x1F) | Yes | EX_ComputedJump (0x4E) | Yes |
| EX_ObjectConst (0x20) | Yes | EX_PopExecutionFlowIfNot (0x4F) | Yes |
| EX_NameConst (0x21) | Yes | EX_Breakpoint (0x50) | Yes |
| EX_RotationConst (0x22) | Yes | EX_InterfaceContext (0x51) | Yes |
| EX_VectorConst (0x23) | Yes | EX_ObjToInterfaceCast (0x52) | Yes |
| EX_ByteConst (0x24) | Yes | EX_EndOfScript (0x53) | Yes |
| EX_IntZero (0x25) | Yes | EX_CrossInterfaceCast (0x54) | Yes |
| EX_IntOne (0x26) | Yes | EX_InterfaceToObjCast (0x55) | Yes |
| EX_True (0x27) | Yes | EX_WireTracepoint (0x5A) | Yes |
| EX_False (0x28) | Yes | EX_SkipOffsetConst (0x5B) | Yes |
| EX_TextConst (0x29) | Yes | EX_AddMulticastDelegate (0x5C) | Yes |
| EX_NoObject (0x2A) | Yes | EX_ClearMulticastDelegate (0x5D) | Yes |
| EX_TransformConst (0x2B) | Yes | EX_Tracepoint (0x5E) | Yes |
| EX_IntConstByte (0x2C) | Yes | EX_LetObj (0x5F) | Yes |
| EX_NoInterface (0x2D) | Yes | EX_LetWeakObjPtr (0x60) | Yes |
| EX_DynamicCast (0x2E) | Yes | EX_BindDelegate (0x61) | Yes |
| EX_StructConst (0x2F) | Yes | EX_RemoveMulticastDelegate (0x62) | Yes |
| EX_EndStructConst (0x30) | Yes | EX_CallMulticastDelegate (0x63) | Yes |
| EX_SetArray (0x31) | Yes | EX_LetValueOnPersistentFrame (0x64) | Yes |
| EX_EndArray (0x32) | Yes | EX_ArrayConst (0x65) | Yes |
| EX_PropertyConst (0x33) | Yes | EX_EndArrayConst (0x66) | Yes |
| EX_SoftObjectConst (0x67) | Yes | EX_CallMath (0x68) | Yes |
| EX_SwitchValue (0x69) | Yes | EX_ArrayGetByRef (0x6B) | Yes |
| EX_InstrumentationEvent (0x6A) | Yes | EX_ClassSparseDataVariable (0x6C) | Yes |
| EX_FieldPathConst (0x6D) | Yes | EX_AutoRtfmTransact (0x70) | Yes |
| EX_AutoRtfmStopTransact (0x71) | Yes | EX_AutoRtfmAbortIfNot (0x72) | Yes |

**Game-specific tokens (0x6E, 0x6F, 0xF9, 0xFD, 0xFE):** Intentionally NOT mapped. In strict mode these raise ParseError. [VERIFIED: EXPR_CLASS_MAP]

## Recommended Implementation Approach

### Phase 62 Deliverables

1. **`kismet/bytecode_extractor.py`** — New module containing:
   - `extract_bytecode_from_export(archive, export, name_map)` — Main entry point
   - `parse_bytecode_stream(bytecode_bytes, name_map, tolerant=False)` — Byte array to expression list

2. **FKismetArchive enhancement** — Add `tolerant` parameter to constructor (D-05):
   ```python
   def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False):
       ...
       self._tolerant = tolerant
   ```
   In `read_expression()`, when `tolerant=True` and an unknown token is encountered, skip to the next valid token boundary or return a sentinel expression.

3. **UStruct deserialization helper** — Function to locate and deserialize UStruct exports:
   - Identify UFunction/K2Node_FunctionEntry exports
   - Navigate to bytecode section (skipping SuperStruct, Children, ChildProperties)
   - Read header + extract bytes

### Implementation Sequence

1. **Enhance FKismetArchive with tolerant mode** (D-05 requirement)
2. **Implement bytecode extraction function** — read bytecodeBufferSize + serializedScriptSize from stream position
3. **Implement parse_bytecode_stream function** — FKismetArchive loop until stream exhaustion
4. **Add UStruct export locator** — iterate exports, identify UStruct-derived types
5. **Integration test** — parse bytecode from a known .uasset file, verify expression count/types

### Architecture Diagram

```
.uasset file
    │
    ▼
FArchive (binary stream)
    │
    ├── ExportMap iteration
    │   └── Identify UStruct-derived exports (UFunction, K2Node_FunctionEntry)
    │
    ▼
extract_bytecode_from_export(archive, export)
    │
    ├── Skip SuperStruct (4 bytes)
    ├── Skip Children (version-dependent)
    ├── Skip ChildProperties (if FProperties version)
    ├── Read bytecodeBufferSize (int32)
    ├── Read serializedScriptSize (int32)
    └── Read bytecode_bytes (serializedScriptSize bytes)
    │
    ▼
parse_bytecode_stream(bytecode_bytes, name_map, tolerant=False)
    │
    ├── FKismetArchive(data=bytecode_bytes, name_map=name_map)
    └── while archive.tell() < len(bytecode_bytes):
            expr = archive.read_expression()   # recursive from_archive()
            expressions.append(expr)
    │
    ▼
list[KismetExpression]  ← flat list with nested subtrees
```

## Common Pitfalls

### Pitfall 1: Assuming ScriptBytecode is an ArrayProperty
**What goes wrong:** Trying to extract ScriptBytecode through the property tag/value chain.
**Why it happens:** Most UE data goes through property tags, but UStruct's bytecode is serialized inline.
**How to avoid:** Read UStruct.cs deserialization — bytecode is read AFTER SuperStruct, Children, and ChildProperties, directly from the stream with its own header. [VERIFIED: CUE4Parse UStruct.cs lines 40-46]

### Pitfall 2: Incorrect stream positioning
**What goes wrong:** Reading bytecode header from wrong position, getting garbage sizes.
**Why it happens:** ChildProperties deserialization length depends on property count and types — must correctly skip all of them before reaching the bytecode header.
**How to avoid:** If implementing full UStruct deserialization, track position after each field. If using the existing property parsing infrastructure, identify where bytecode starts relative to the export.

### Pitfall 3: Tolerant mode byte-skipping strategy
**What goes wrong:** When encountering an unknown token in tolerant mode, blindly skipping 1 byte and retrying may land in the middle of a multi-byte value.
**Why it happens:** Expression arguments can be multi-byte (u32, f32, strings).
**How to avoid:** In tolerant mode, use heuristics: scan for known token values (0x00-0x72 range) and align to the nearest one. CUE4Parse's approach is to catch the exception and stop parsing.

### Pitfall 4: EX_EndOfScript vs stream exhaustion
**What goes wrong:** Using read_expression_array(EX_EndOfScript) vs while-position<length produces different results if there's trailing data after EX_EndOfScript.
**Why it happens:** CUE4Parse's UStruct.Deserialize() uses stream exhaustion, while ReadExpressionArray() uses end token.
**How to avoid:** For Phase 62, use stream exhaustion (position < length) as the primary loop condition — it matches how UStruct populates ScriptBytecode. EX_EndOfScript will naturally be the last expression read. [VERIFIED: CUE4Parse UStruct.cs line 49]

## Code Examples

### Bytecode Extraction (Recommended Pattern)

Based on CUE4Parse UStruct.cs lines 40-61:

```python
def extract_bytecode_bytes(archive: FArchive, export: ObjectExport) -> bytes | None:
    """Extract ScriptBytecode raw bytes from a UStruct export."""
    # Seek to the export's serialization start
    archive.seek(export.serial_offset)

    # Skip UStruct fields before bytecode:
    # SuperStruct (FPackageIndex = 4 bytes)
    archive.read_i32()

    # Children array: read count, skip entries
    if summary.file_version < FFrameworkObjectVersion.RemoveUField_Next:
        first_child = archive.read_i32()
        if first_child != 0:
            archive.read_i32()  # one more FPackageIndex
    else:
        child_count = archive.read_i32()
        archive.skip(child_count * 4)  # skip all FPackageIndex entries

    # ChildProperties: if FCoreObjectVersion.FProperties, deserialize or skip
    # This is version-dependent and complex — may need full property deserialization

    # Now at bytecode header
    bytecode_buffer_size = archive.read_i32()
    serialized_script_size = archive.read_i32()

    if serialized_script_size <= 0:
        return None

    return archive.read_bytes(serialized_script_size)
```

### Bytecode Parsing Loop

Based on CUE4Parse UStruct.cs lines 46-60:

```python
def parse_bytecode_stream(bytecode_bytes: bytes, name_map: list[str],
                          tolerant: bool = False) -> list[KismetExpression]:
    """Parse raw bytecode bytes into a list of KismetExpression trees."""
    archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map)
    archive._tolerant = tolerant  # D-05: switchable tolerant mode

    expressions = []
    while archive.tell() < len(bytecode_bytes):
        try:
            expr = archive.read_expression()
            expressions.append(expr)
        except ParseError as e:
            if not tolerant:
                raise
            # In tolerant mode: log warning and try to continue
            archive._logger.warning(f"Failed to parse expression at {archive.tell()}: {e}")

    return expressions
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Raw bytecode inspection | Expression tree with nested subtrees | Human-readable analysis |
| Manual token dispatch | EXPR_CLASS_MAP data-driven dispatch | Easy to extend |
| Flat expression list | Recursive from_archive() builds nested trees | Semantic structure preserved |
| CFG pre-construction | Defer CFG to Phase 63 | Phase 62 is focused, simpler |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | UStruct serialization order is always: SuperStruct → Children → ChildProperties → bytecodeBufferSize → serializedScriptSize → bytecode data | ScriptBytecode Extraction Strategy | If order varies by UE version, extraction will read garbage |
| A2 | K2Node_FunctionEntry exports can be identified by ObjectClass name in the export table | ScriptBytecode Extraction Strategy | If naming convention differs, function discovery will fail |
| A3 | All standard UE EExprToken values (non-game-specific) are covered by EXPR_CLASS_MAP | Expression Class Coverage Analysis | Missing tokens would cause ParseError on valid bytecode |

## Open Questions

1. **UStruct property deserialization depth:** How should we handle ChildProperties deserialization when we only need to reach the bytecode header? Options: (a) full deserialization, (b) count-and-skip based on property metadata. This affects extraction reliability.

2. **Version detection:** The bytecode header position depends on UE version flags (`FFrameworkObjectVersion.RemoveUField_Next`, `FCoreObjectVersion.FProperties`). How does our project currently track these versions per-package?

3. **EventGraph bytecode location:** D-01 mentions EventGraph coverage. EventGraph bytecode may be attached to different node types than K2Node_FunctionEntry. The exact export type needs verification with actual test assets.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None — standard pytest discovery |
| Quick run command | `python -m pytest tests/test_kismet.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| Phase 62 | Extract bytecode bytes from UStruct export | unit | `python -m pytest tests/test_bytecode_extractor.py -x` |
| Phase 62 | Parse bytecode stream into expression list | unit | `python -m pytest tests/test_bytecode_extractor.py -x` |
| Phase 62 | Tolerant mode skips unknown tokens | unit | `python -m pytest tests/test_bytecode_extractor.py -x` |

### Wave 0 Gaps
- [ ] `tests/test_bytecode_extractor.py` — new test file for Phase 62
- [ ] Test .uasset files with known bytecode content (from `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`)

## Sources

### Primary (HIGH confidence)
- CUE4Parse UStruct.cs (`E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UStruct.cs`) — ScriptBytecode deserialization, header format, loop structure
- CUE4Parse FKismetArchive.cs (`E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Readers\FKismetArchive.cs`) — ReadExpression switch dispatch, ReadExpressionArray loop
- CUE4Parse UClass.cs (`E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UClass.cs` lines 108-339) — DecompileBlueprintToPseudo pipeline
- Project source: `kismet/archive.py`, `kismet/expressions/__init__.py`, `kismet/tokens.py` — Phase 61 implementation

### Secondary (MEDIUM confidence)
- Project source: `parsers/property_parser.py`, `parsers/property_types.py` — existing property parsing infrastructure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all Phase 61 code verified, CUE4Parse sources read in full
- Architecture: HIGH — CUE4Parse provides definitive reference implementations
- Pitfalls: MEDIUM — based on code analysis, not yet tested with real .uasset files

**Research date:** 2026-05-20
**Valid until:** 2026-06-20 (stable domain — UE bytecode format does not change frequently)
