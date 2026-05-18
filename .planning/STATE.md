---
gsd_state_version: 1.0
milestone: v11.0
milestone_name: Kismet 字节码反编译器
status: planned
last_updated: "2026-05-18T06:30:00Z"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 5
  completed_plans: 0
  percent: 0
---

# v11.0 — Kismet 字节码反编译器

**Started: 2026-05-18**
**Reference:** CUE4Parse — KismetExpression / FKismetArchive / BlueprintDecompilerUtils

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 61 | Kismet 表达式系统 | EExprToken + KismetExpression 类族 + FKismetArchive | KISMET-01/02/03 | Planned (2 plans) |
| 62 | 字节码 → 表达式树 | ScriptBytecode → KismetExpression AST | BYTECODE-01/02/03 | Planned (1 plan) |
| 63 | 表达式树 → C++ 伪代码 | AST 翻译 + 控制流恢复 + MathFunctionCleaner | TRANSLATE-01/02/03/04 | Planned (1 plan) |
| 64 | 集成与验证 | pipeline 集成 + 端到端 golden-path 测试 | INTEGRATE-01/02/03 | Planned (1 plan) |

## 依赖关系

```
Phase 61 (表达式系统) → Phase 62 (字节码→AST) → Phase 63 (AST→C++) → Phase 64 (集成验证)
```

## 上下文

- CUE4Parse 参考：`E:\Develop\CUE4Parse\CUE4Parse\UE4\Kismet\` + `BlueprintDecompilerUtils.cs`
- 本项目技术栈：Python 3.10+，零运行时依赖
- 架构管道：`.uasset → FArchive → Serializers → Models → Kismet → Translators → C++`
