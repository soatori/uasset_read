---
gsd_state_version: 1.2
milestone: v11.0
milestone_name: — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线
status: mid-flight
last_updated: "2026-05-20T23:45:00.000Z"
next_milestone: v12.0 — N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-70, NEXT)
progress:
  total_phases: 10
  completed_phases: 5
  skipped_phases: 1
  total_plans: 13
  completed_plans: 8
  percent: 50
---

# v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线

**Started: 2026-05-18**
**Updated: 2026-05-20 (Phase 66 跳过 → v12.0 P67-70 为下一活跃里程碑)**

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 61 | Kismet 表达式系统 | EExprToken + KismetExpression 类族 + FKismetArchive | KISMET-01/02/03 | ✅ Done (4 waves) |
| 62 | 字节码 → 表达式树 | ScriptBytecode → KismetExpression AST | BYTECODE-01/02/03 | ✅ Done (1 plan) |
| 63 | 表达式树 → C++ 伪代码 | AST 翻译 + 控制流恢复 + MathFunctionCleaner | TRANSLATE-01/02/03/04 | ✅ Done (1 plan, 131 tests) |
| 64 | Kismet 集成验证 | pipeline 集成 + 端到端 golden-path 测试 | INTEGRATE-01/02/03 | ✅ Done (2 plans, 24 tests) |
| 65 | 图解析器修复 | FMemberReference + Pin 连接 + Struct 映射 + 函数签名 | GRAPH-FIX-01/02/03 | ✅ Done (2 plans) — 2026-05-20 |
| **66** | **Agent 翻译管线** | ~~BP 节点 JSON → C++ 代码生成 + golden 测试~~ → 提供 Agent 可理解的中间格式输出 | TRANSLATE-BP-01/02 | ⏭️ Skipped (目标调整为 v12.0 中间格式) |
| **67** | **N2CNodeTypeRegistry** | 100+ K2Node 语义类型注册表 + 继承回退 | REGISTRY-01/02 | 🆕 Planned |
| **68** | **节点处理器架构** | Processor 模式替代 switch/case | PROCESSOR-01/02 | 🆕 Planned |
| **69** | **N2CStruct JSON Schema** | LLM 优化中间格式 + 双向序列化 | SCHEMA-01/02 | 🆕 Planned |
| **70** | **执行流链式表达** | `N1->N2->N3` 格式替代逐对连接 | CHAIN-01/02 | 🆕 Planned |

## 依赖关系

```
Phase 61 → Phase 62 → Phase 63 → Phase 64 (Kismet 集成) ✅
                              ↓
                      Phase 65 (图解析修复) ✅
                              ↓
                    ⏭️ Phase 66 (跳过 → 目标合并至 v12.0)
                              ↓
                        Phase 67 (NodeTypeRegistry) 🆕 ← v12.0 起点
                              ↓
                        Phase 68 (Processor 架构) 🆕
                              ↓
                        Phase 69 (N2CStruct Schema) 🆕
                              ↓
                        Phase 70 (执行流链式表达) 🆕
```

Phase 64 和 65 已完成 — 64 修 kismet/ 层，65 修 graph.py 层。
Phase 66 已跳过 — 原始目标（BP → C++ 代码生成）调整为"提供 Agent 可理解的中间格式输出"，该目标直接由 v12.0（Phase 67-70）的 N2CStruct 中间格式实现。
Phase 67-70（v12.0）为下一个活跃里程碑，直接承接 Phase 65 修复后的 graph.py 输出。

## 当前状态

**当前阶段:** Phase 65 已完成 ✅ → v12.0 (P67-70) 为下一活跃里程碑
**上次完成:** Phase 65 (65-01/65-02) — 2026-05-20
**Phase 66:** ⏭️ 跳过 — 原始 C++ 生成目标调整为"提供 Agent 可理解的中间格式输出"，由 v12.0 实现
**下一步:** `/gsd:plan-phase 67` — 开始 v12.0 Phase 67 (N2CNodeTypeRegistry)

## v12.0 背景（NodeToCode 参考）

对 `protospatial/NodeToCode` 项目的差距分析识别出 4 项核心能力（P0）需要在 Phase 65 之后补充：

1. **N2CNodeTypeRegistry** — 100+ K2Node 语义类型完整映射（当前仅覆盖有限类型）
2. **节点处理器架构** — 每类型独立 Processor 替代 switch/case
3. **N2CStruct JSON Schema** — LLM/Agent 优化中间格式（60-90% token 压缩）
4. **执行流链式表达** — `N1->N2->N3` 简洁格式替代逐对连接

这 4 项构成 v12.0 里程碑（Phase 67-70），目标是将 graph.py 的输出转化为 **Agent 可理解的结构化 JSON**，作为后续 LLM 翻译的高质量输入。

Phase 66（AgentTranslationPipeline C++ 生成）已跳过，其"提供 Agent 可理解输出"的目标直接由 v12.0 中间格式实现。

可选增强（v13.0+ 讨论）：结构体/枚举提取、参考代码注入、多语言输出、深度控制、Knot 节点追踪。

## Phase 65 完成摘要

**GAP 修复状态:**
- ✅ GAP-01: FMemberReference.member_name 正确（13/13 CallFunction 节点有效）
- 🔶 GAP-02: Pin 连接格式理解改进（linked_to_raw 仍为空，需要 fallback）
- ✅ GAP-03: StructProperty 类型正确识别为 Vector/Rotator
- ✅ GAP-07: 函数签名提取实现（Pin-based fallback）

**已知限制:** linked_to_raw 空数组，v12.0 中间格式需要 fallback 策略处理连接数据。

## 新增 Phase 背景（来自 64-GAP-REPORT.md）

对 `BP_FirstPersonCharacter.uasset` 的实际解析发现：
- **GAP-01:** FMemberReference 解析失败 → 无法获取"调用的是什么函数"（P0，已修复）
- **GAP-02:** Pin 连接全部为空 → 无法获取数据流（P0，部分修复，需 fallback）
- **GAP-03:** StructProperty → UnknownStruct → 缺失变量类型信息（P1，已修复）
- **GAP-05:** ExecuteUbergraph 字节码未提取 → 70%+ 逻辑丢失（P1，Phase 64 已修复）
- **GAP-06/07:** 执行流和函数签名全空 → 依赖 GAP-02 修复（Phase 65 已修复）

Phase 65 修复 GAP-01/02/03/06/07（graph.py 层）。
v12.0 利用修复后的输出构建 N2C 中间格式，直接作为 Agent 可理解的输入。

## 上下文

- CUE4Parse 参考：`E:\Develop\CUE4Parse\CUE4Parse\UE4\Kismet\` + `BlueprintDecompilerUtils.cs`
- UE 源码参考：`E:\Develop\lib\UnrealEngine\Engine\Source\Editor\UnrealEd\Private\Kismet2\`
  - `K2Node_CallFunction.cpp` — FK2Node_CallFunction::Serialize()
  - `EdGraphPin.cpp` — UEdGraphPin::Serialize()
  - `BlueprintEditorUtils.cpp` — FBlueprintEditorUtils::ReadPinReference()
- **NodeToCode 参考**：`E:\Develop\temp_NodeToCode\` — N2CNodeTypeRegistry / N2CNodeProcessor / N2CStruct / N2CSerializer
  - `N2CNodeTypeRegistry.cpp` — 100+ K2Node 类型映射 + 继承回退
  - `Utils/Processors/` — N2CFunctionCallProcessor / N2CEventProcessor / N2CFlowControlProcessor
  - `N2CSerializer.h` — 双向 JSON 序列化（to_n2c_json / from_n2c_json）
  - `N2CBlueprint.h` — N2CStruct / N2CEnum / N2CGraph 数据模型
  - `Content/Prompting/CodeGen_CPP.md` — LLM prompt + 输出 JSON Schema
- 差距分析：`.planning/phases/phase-64/64-GAP-REPORT.md`
- 本项目技术栈：Python 3.10+，零运行时依赖
- 架构管道：`.uasset → FArchive → Serializers → Models → Kismet → N2CStruct → Translators → C++`

## 上游里程碑

- v10.0 (P56-60): Blueprint-to-C++ 代码生成参考 — ✅ 已归档 2026-05-19
  - 提供了 cpp_gen 模块骨架、类型映射、函数签名/体翻译、组件初始化
  - v11.0 在字节码层（EExprToken → KismetExpression → C++）补充 Phase 58 无法覆盖的 60+ 种表达式类型