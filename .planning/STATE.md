---
gsd_state_version: 1.2
milestone: v12.0
milestone_name: — N2C 中间格式 + 节点分类体系 + 处理器架构
status: ready
last_updated: "2026-05-21T00:15:00.000Z"
prev_milestone: v11.0 (archived 2026-05-21)
progress:
  total_phases: 4
  completed_phases: 0
  skipped_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# v12.0 — N2C 中间格式 + 节点分类体系 + 处理器架构

**Started: 2026-05-21**
**Status: Ready — 需要运行 `/gsd:new-milestone` 创建 REQUIREMENTS.md**

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 67 | N2CNodeTypeRegistry | 100+ K2Node 语义类型注册表 + 继承回退 | REGISTRY-01/02 | 🆕 Planned |
| 68 | 节点处理器架构 | Processor 模式替代 switch/case | PROCESSOR-01/02 | 🆕 Planned |
| 69 | N2CStruct JSON Schema | LLM 优化中间格式 + 双向序列化 | SCHEMA-01/02 | 🆕 Planned |
| 70 | 执行流链式表达 | `N1->N2->N3` 格式替代逐对连接 | CHAIN-01/02 | 🆕 Planned |

## 依赖关系

```
Phase 67 (NodeTypeRegistry) ← v12.0 起点
        ↓
Phase 68 (Processor 架构)
        ↓
Phase 69 (N2CStruct Schema)
        ↓
Phase 70 (执行流链式表达)
```

## 当前状态

**当前阶段:** v12.0 初始化
**上次归档:** v11.0 (P61-66) — 2026-05-21
**下一步:** `/gsd:new-milestone` — 创建 v12.0 REQUIREMENTS.md 和详细规划

## v12.0 背景（NodeToCode 参考）

**参考设计:** NodeToCode (protospatial) — N2CNodeTypeRegistry / N2CNodeProcessor / N2CStruct / N2CSerializer

目标：将 graph.py 输出转化为 Agent 可理解的结构化 JSON，优化 LLM token 使用（60-90% 压缩）。

核心能力：
1. **N2CNodeTypeRegistry** — 100+ K2Node 语义类型完整映射
2. **节点处理器架构** — 每类型独立 Processor 替代 switch/case
3. **N2CStruct JSON Schema** — LLM/Agent 优化中间格式
4. **执行流链式表达** — `N1->N2->N3` 简洁格式

## 上游里程碑

- v11.0 (P61-66): Kismet 字节码反编译器 + Agent 翻译管线 — ✅ 已归档 2026-05-21
  - 提供了 decompile_uasset() 端到端管线、AgentTranslationPipeline、CppFileWriter
  - 修复了图解析关键差距（FMemberReference、Pin 连接、Struct 映射）
  - v12.0 在此基础上构建 N2C 中间格式