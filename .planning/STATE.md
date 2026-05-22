---
gsd_state_version: 1.2
milestone: v12.0
milestone_name: — N2C 中间格式 + 节点分类体系 + 处理器架构
status: in_progress
last_updated: "2026-05-22T00:00:00.000Z"
prev_milestone: v11.0 (archived 2026-05-21)
progress:
  total_phases: 5
  completed_phases: 3
  skipped_phases: 0
  total_plans: 7
  completed_plans: 7
  percent: 60
---

# v12.0 — N2C 中间格式 + 节点分类体系 + 处理器架构

**Started: 2026-05-21**
**Status: In Progress — Phase 67 Complete, Phase 69 Complete, Phase 70 Complete**

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 67 | 序列化格式修复 | UE5.4+ PropertyTag 兼容 + FString 健壮性 | SERIALIZE-01/02 | ✅ Complete |
| 68 | N2CNodeTypeRegistry | 100+ K2Node 语义类型注册表 + 继承回退 | REGISTRY-01/02 | 🆕 Planned |
| 69 | 节点处理器架构 | Processor 模式替代 switch/case | PROCESSOR-01/02 | ✅ Complete |
| 70 | N2CStruct JSON Schema | LLM 优化中间格式 + 双向序列化 | SCHEMA-01/02 | ✅ Complete |
| 71 | 执行流链式表达 | `N1->N2->N3` 格式替代逐对连接 | CHAIN-01/02 | 🆕 Planned |

## 依赖关系

```
Phase 67 (序列化修复) ← v12.0 起点
        ↓
Phase 68 (NodeTypeRegistry)
        ↓
Phase 69 (Processor 架构)
        ↓
Phase 70 (N2CStruct Schema)
        ↓
Phase 71 (执行流链式表达)
```

## 当前状态

**当前阶段:** Phase 71 (执行流链式表达) — 下一步
**Phase 67 完成:** 2026-05-21 — 6 类序列化错误全部修复，UAT 6/6 通过，所有单元测试通过（24/24）
**Phase 69 完成:** 2026-05-22 — 节点处理器架构迁移，1200 tests passed, 0 failed
**Phase 70 完成:** 2026-05-22 — N2CStruct JSON Schema + 双向序列化 + 72.6% token 压缩，142 tests passed

## v12.0 完成度

| 版本 | 范围 | 日期 | 状态 |
|------|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 2026-04-28 ~ 05-13 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 2026-05-14 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 2026-05-17 | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 2026-05-17 | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 2026-05-18 | 已归档 |
| v11.0 | Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66) | 2026-05-20 | 已归档 |
| v12.0 P67 | 序列化修复 ✅ | 2026-05-21 | ✅ Complete |
| v12.0 P68 | N2CNodeTypeRegistry | 计划中 | 🆕 Planned |
| v12.0 P69 | 节点处理器架构 ✅ | 2026-05-22 | ✅ Complete |
| v12.0 P70 | N2CStruct JSON Schema ✅ | 2026-05-22 | ✅ Complete |
| v12.0 P71 | 执行流链式表达 | 计划中 | 🆕 Planned |

## v12.0 背景（NodeToCode 参考）

**参考设计:** NodeToCode (protospatial) — N2CNodeTypeRegistry / N2CNodeProcessor / N2CStruct / N2CSerializer

目标：将 graph.py 输出转化为 Agent 可理解的结构化 JSON，优化 LLM token 使用（60-90% 压缩）。

核心能力：
1. **N2CNodeTypeRegistry** — 100+ K2Node 语义类型完整映射
2. **节点处理器架构** — 每类型独立 Processor 替代 switch/case
3. **N2CStruct JSON Schema** — LLM/Agent 优化中间格式 ✅
4. **执行流链式表达** — `N1->N2->N3` 简洁格式 ✅ (已在 P70 实现)

## 上游里程碑

- v11.0 (P61-66): Kismet 字节码反编译器 + Agent 翻译管线 — ✅ 已归档 2026-05-21
  - 提供了 decompile_uasset() 端到端管线、AgentTranslationPipeline、CppFileWriter
  - 修复了图解析关键差距（FMemberReference、Pin 连接、Struct 映射）
  - v12.0 在此基础上构建 N2C 中间格式