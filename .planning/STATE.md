---
gsd_state_version: 1.2
milestone: v11.0
milestone_name: — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线
status: mid-flight
last_updated: "2026-05-20T23:45:00.000Z"
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 13
  completed_plans: 8
  percent: 80
---

# v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线

**Started: 2026-05-18**
**Updated: 2026-05-20 (Phase 66 计划已创建 → 准备执行)**

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 61 | Kismet 表达式系统 | EExprToken + KismetExpression 类族 + FKismetArchive | KISMET-01/02/03 | ✅ Done (4 waves) |
| 62 | 字节码 → 表达式树 | ScriptBytecode → KismetExpression AST | BYTECODE-01/02/03 | ✅ Done (1 plan) |
| 63 | 表达式树 → C++ 伪代码 | AST 翻译 + 控制流恢复 + MathFunctionCleaner | TRANSLATE-01/02/03/04 | ✅ Done (1 plan, 131 tests) |
| 64 | Kismet 集成验证 | pipeline 集成 + 端到端 golden-path 测试 | INTEGRATE-01/02/03 | ✅ Done (2 plans, 24 tests) |
| 65 | 图解析器修复 | FMemberReference + Pin 连接 + Struct 映射 + 函数签名 | GRAPH-FIX-01/02/03 | ✅ Done (2 plans) — 2026-05-20 |
| **66** | **Agent 翻译管线** | BP 节点 JSON → C++ 代码生成 + golden 测试 | TRANSLATE-BP-01/02 | 📋 Planned (3 plans) |

## 依赖关系

```
Phase 61 → Phase 62 → Phase 63 → Phase 64 (Kismet 集成) ✅
                              ↓
                      Phase 65 (图解析修复) ✅ → Phase 66 (Agent 翻译管线)
```

Phase 64 和 65 已完成 — 64 修 kismet/ 层，65 修 graph.py 层。
Phase 66 依赖 Phase 65（需要正确的函数引用和 Pin 连接）。

## 当前状态

**当前阶段:** Phase 66 — Agent 翻译管线
**上次完成:** Phase 65 (65-01/65-02) — 2026-05-20
**计划创建:** Phase 66 (66-01/02/03) — 2026-05-20
**下一步:** `/gsd:execute-phase 66` — 执行 Wave 1 (Task 1+2 并行) + Wave 2

## Phase 66 计划详情

| Plan | Wave | Tasks | 预估时长 | 依赖 |
|------|------|-------|----------|------|
| 66-01 | 1 | Task 1 (AgentTranslationPipeline integration) + TDD tests | 3-4h | 无 |
| 66-02 | 1 | Task 2 (CppFileWriter output) + TDD tests | 2-3h | 无 |
| 66-03 | 2 | Task 3 (Golden file integration test) | 2-3h | 66-01 + 66-02 |

**Wave 执行顺序:**
- Wave 1: Task 1 + Task 2 并行执行（无文件冲突，可并行）
- Wave 2: Task 3 顺序执行（依赖 Wave 1 完成）

**Fallback 策略（已知 stub）:**
- linked_to_raw 空数组 → 使用 function_reference.member_name 生成函数调用
- decompiled_functions 空数组 → 仅生成类骨架（无函数体）
- graphs 数据不完整 → 从 blueprint_functions 回退

## Phase 65 完成摘要

**GAP 修复状态:**
- ✅ GAP-01: FMemberReference.member_name 正确（13/13 CallFunction 节点有效）
- 🔶 GAP-02: Pin 连接格式理解改进（linked_to_raw 仍为空，需要 fallback）
- ✅ GAP-03: StructProperty 类型正确识别为 Vector/Rotator
- ✅ GAP-07: 函数签名提取实现（Pin-based fallback）

**已知 stub:** linked_to_raw 空数组，Phase 66 使用 fallback 策略处理。

## 新增 Phase 背景（来自 64-GAP-REPORT.md）

对 `BP_FirstPersonCharacter.uasset` 的实际解析发现：
- **GAP-01:** FMemberReference 解析失败 → 无法获取"调用的是什么函数"（P0，已修复）
- **GAP-02:** Pin 连接全部为空 → 无法获取数据流（P0，部分修复，需 fallback）
- **GAP-03:** StructProperty → UnknownStruct → 缺失变量类型信息（P1，已修复）
- **GAP-05:** ExecuteUbergraph 字节码未提取 → 70%+ 逻辑丢失（P1，Phase 64 已修复）
- **GAP-06/07:** 执行流和函数签名全空 → 依赖 GAP-02 修复（Phase 65 已修复）

Phase 65 修复 GAP-01/02/03/06/07（graph.py 层）。
Phase 66 利用修复后的输出构建 Agent 翻译管线（含 fallback 策略）。

## 上下文

- CUE4Parse 参考：`E:\Develop\CUE4Parse\CUE4Parse\UE4\Kismet\` + `BlueprintDecompilerUtils.cs`
- UE 源码参考：`E:\Develop\lib\UnrealEngine\Engine\Source\Editor\UnrealEd\Private\Kismet2\`
  - `K2Node_CallFunction.cpp` — FK2Node_CallFunction::Serialize()
  - `EdGraphPin.cpp` — UEdGraphPin::Serialize()
  - `BlueprintEditorUtils.cpp` — FBlueprintEditorUtils::ReadPinReference()
- 差距分析：`.planning/phases/phase-64/64-GAP-REPORT.md`
- 本项目技术栈：Python 3.10+，零运行时依赖
- 架构管道：`.uasset → FArchive → Serializers → Models → Kismet → Translators → C++`

## 上游里程碑

- v10.0 (P56-60): Blueprint-to-C++ 代码生成参考 — ✅ 已归档 2026-05-19
  - 提供了 cpp_gen 模块骨架、类型映射、函数签名/体翻译、组件初始化
  - v11.0 在字节码层（EExprToken → KismetExpression → C++）补充 Phase 58 无法覆盖的 60+ 种表达式类型