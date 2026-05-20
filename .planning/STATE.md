---
gsd_state_version: 1.0
milestone: v11.0
milestone_name: — Kismet 字节码反编译器
status: mid-flight
last_updated: "2026-05-20T05:40:00.000Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 10
  completed_plans: 3
  percent: 50
---

# v11.0 — Kismet 字节码反编译器

**Started: 2026-05-18**
**Reference:** CUE4Parse — KismetExpression / FKismetArchive / BlueprintDecompilerUtils

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 61 | Kismet 表达式系统 | EExprToken + KismetExpression 类族 + FKismetArchive | KISMET-01/02/03 | Done (4 waves) |
| 62 | 字节码 → 表达式树 | ScriptBytecode → KismetExpression AST | BYTECODE-01/02/03 | Done (1 plan) |
| 63 | 表达式树 → C++ 伪代码 | AST 翻译 + 控制流恢复 + MathFunctionCleaner | TRANSLATE-01/02/03/04 | Done (1 plan, 131 tests) |
| 64 | 集成与验证 | pipeline 集成 + 端到端 golden-path 测试 | INTEGRATE-01/02/03 | Planned (1 plan) |

## 依赖关系

```
Phase 61 (表达式系统) → Phase 62 (字节码→AST) → Phase 63 (AST→C++) → Phase 64 (集成验证)
```

## 上下文

- CUE4Parse 参考：`E:\Develop\CUE4Parse\CUE4Parse\UE4\Kismet\` + `BlueprintDecompilerUtils.cs`
- 本项目技术栈：Python 3.10+，零运行时依赖
- 架构管道：`.uasset → FArchive → Serializers → Models → Kismet → Translators → C++`

## 上游里程碑

- v10.0 (P56-60): Blueprint-to-C++ 代码生成参考 — ✅ 已归档 2026-05-19
  - 提供了 cpp_gen 模块骨架、类型映射、函数签名/体翻译、组件初始化
  - v11.0 在字节码层（EExprToken → KismetExpression → C++）补充 Phase 58 无法覆盖的 60+ 种表达式类型
