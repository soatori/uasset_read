---
title: Kismet Decompilation
section: kismet
---

# Kismet Decompilation

`kismet/` implements Kismet bytecode extraction, AST parsing, and C++ code translation.

<!-- data-api="decompile_uasset" -->
```python
decompile_uasset(path: str, tolerant: bool) → List[KismetDecompiledResult]
```

<!-- data-api="extract_bytecode_bytes" -->
```python
extract_bytecode_bytes(archive, export, summary, name_map, import_map, export_map) → bytes
```

<!-- data-api="parse_bytecode_stream" -->
```python
parse_bytecode_stream(bytecode_bytes, name_map, tolerant) → List[KismetExpression]
```

## Expression Class Hierarchy

```
KismetExpression (abstract base class)
├── KismetExpressionT[T] (with value)
├── EX_VariableBase → EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable
├── EX_LetBase (assignment) → EX_Let, EX_LetBool, EX_LetDelegate
├── EX_FinalFunction (call) → EX_CallMath, EX_LocalFinalFunction
├── EX_CastBase → EX_Cast, EX_DynamicCast, EX_MetaCast
├── EX_ContextBase → EX_Context, EX_Context_FailSilent, EX_ClassContext
├── Literals: EX_IntConst, EX_FloatConst, EX_StringConst, EX_VectorConst
└── Control flow: EX_Jump, EX_JumpIfNot, EX_Return, EX_EndOfScript
```

## Key Design

- **Two-phase translation**: Phase 62 binary→AST, Phase 63 AST→C++
- **MathFunctionCleaner**: beautifies `UKismetMathLibrary::Add_IntInt(a,b)` → `a + b`
- **BPGC fallback**: UE5 baked blueprint bytecode is in BlueprintGeneratedClass.script_serial_region
- **Structured flow vs Goto**: StructuredControlFlow detects Push/Pop patterns, falls back to goto on failure

> [!TIP]
> **Related sections**: [[Blueprint]] · [[CPP-Generator]]
