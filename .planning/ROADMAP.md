# 路线图

## 里程碑

| 版本 | 范围 | 日期 | 状态 |
|------|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 2026-04-28 ~ 05-13 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 2026-05-14 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 2026-05-17 | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 2026-05-17 | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 2026-05-18 | [已归档](milestones/v10.0-ROADMAP.md) |
| **v11.0** | **Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66)** | 计划中 | **活跃** |

历史详情：`.planning/archive/`

## v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (PLANNED)

**参考设计:** CUE4Parse — KismetExpression / FKismetArchive / BlueprintDecompilerUtils
**差距分析:** `.planning/phases/phase-64/64-GAP-REPORT.md`

- [x] Phase 61: Kismet 表达式系统 — EExprToken + KismetExpression 类族 + FKismetArchive (4 waves)
- [x] Phase 62: 字节码 → 表达式树 — ScriptBytecode → KismetExpression AST (1 plan, 6 tasks)
- [x] Phase 63: 表达式树 → C++ 伪代码 — AST 翻译 + 控制流恢复 + MathFunctionCleaner (1 plan, 131 tests)
- [x] Phase 64: Kismet 集成验证 — pipeline 集成 + 端到端 golden-path 测试 (64-01/02) ✅ 2026-05-20
- [ ] Phase 65: 图解析器修复 — FMemberReference + Pin 连接 + Struct 映射 + 函数签名 (2 plans)
- [ ] Phase 66: Agent 翻译管线 — BP 节点 JSON → C++ 代码生成 + golden 测试

**依赖:** 61 → 62 → 63 → 64; 65 → 66; 64 ∥ 65 (可并行)

Plans:
- [x] 64-01-PLAN.md — KismetDecompiledResult + decompile_uasset() pipeline ✅
- [x] 64-02-PLAN.md — _post_process integration + golden file tests ✅
- [x] 65-01-PLAN.md — FMemberReference + Pin 连接修复 (Wave 1: Task 1+2+3) ✅
- [x] 65-02-PLAN.md — Struct 映射 + 函数签名修复 (Wave 2: Task 4+5+6) ✅
- [ ] 66-PLAN.md — Agent translation pipeline: BP JSON → C++ codegen

## 能力对比

| 维度 | Phase 58 (已有) | v11.0 新增 |
|------|----------------|-----------|
| 输入 | execution_flows JSON | ScriptBytecode 字节流 |
| 粒度 | 4 种语句类型 | 60+ 种 EExprToken |
| 控制流 | K2Node_IfThenElse → if | Jump/Push/Pop → 结构化 if/for/while |
| 变量/常量 | 缺失 | 全类型支持 |
| 数学美化 | 缺失 | MathFunctionCleaner |

---

*Updated: 2026-05-20 (v11.0 Phase 65 plans created)*