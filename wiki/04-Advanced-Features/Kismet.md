---
title: Kismet 反编译
section: kismet
---

# Kismet 反编译

`kismet/` 实现 Kismet 字节码提取、AST 解析和 C++ 代码翻译。

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

## 表达式类层次

```
KismetExpression (抽象基类)
├── KismetExpressionT[T] (带值)
├── EX_VariableBase → EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable
├── EX_LetBase (赋值) → EX_Let, EX_LetBool, EX_LetDelegate
├── EX_FinalFunction (调用) → EX_CallMath, EX_LocalFinalFunction
├── EX_CastBase → EX_Cast, EX_DynamicCast, EX_MetaCast
├── EX_ContextBase → EX_Context, EX_Context_FailSilent, EX_ClassContext
├── 字面量: EX_IntConst, EX_FloatConst, EX_StringConst, EX_VectorConst
└── 控制流: EX_Jump, EX_JumpIfNot, EX_Return, EX_EndOfScript
```

## 关键设计

- **两阶段翻译**：Phase 62 二进制→AST，Phase 63 AST→C++
- **MathFunctionCleaner**：美化 `UKismetMathLibrary::Add_IntInt(a,b)` → `a + b`
- **BPGC 回退**：UE5 烘焙蓝图字节码在 BlueprintGeneratedClass.script_serial_region
- **结构化流 vs Goto**：StructuredControlFlow 检测 Push/Pop 模式，失败时回退 goto

> [!TIP]
> **相关章节**: [[Blueprint]] · [[CPP-Generator]]
