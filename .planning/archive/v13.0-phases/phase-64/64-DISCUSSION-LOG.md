# Phase 64: 集成与验证 - Discussion Log

**Date:** 2026-05-20
**Mode:** Default (interactive)

## Discussion Areas

### 1. 集成点 (Pipeline Integration)
**Question:** Phase 64 的 pipeline 集成点在哪里？Kismet 反编译结果如何接入现有 parse_uasset() 管线？

**Options:**
- A: parse_uasset 管线内嵌 — 在 _post_process() 中自动触发
- B: 独立 decompile_uasset() 入口 — 不修改现有 parse_uasset()
- C: 两者都要 — 共享底层逻辑，提供两种视图

**Selected:** C — 两者都要

**Rationale:** 用户需要灵活的访问方式 — 既有管线内嵌的自动提取，也有独立函数用于专门的反编译场景。

### 2. 测试策略 (Testing Strategy)
**Question:** 端到端 golden-path 测试的策略是什么？如何验证反编译输出正确性？

**Options:**
- A: Golden file 对比测试（推荐）— 使用 golden file 做端到端验证
- B: 单元测试 + 集成测试 — 更细粒度
- C: 仅端到端 golden 测试 — 简单但定位慢

**Selected:** A — Golden file 对比测试（Phase 64 新编写）

**Rationale:** Golden file 测试直接验证最终输出，与 Phase 63 的 131 个测试互补。

### 3. 输出格式 (Output Format)
**Question:** 反编译结果的输出格式是什么？下游用户如何消费这些结果？

**Options:**
- A: C++ 伪代码字符串 — 人类可读
- B: 结构化 JSON + 字符串 — 机器可读 + 人类可读
- C: Markdown 报告 — 文档化

**Selected:** B — 结构化 JSON + 字符串

**Rationale:** 同时支持机器消费（测试断言、下游工具）和人类查看。

### 4. CLI 入口 (CLI Entry Point)
**Question:** 是否需要新增 CLI 入口来触发 Kismet 反编译？

**Options:**
- A: 新增 --decompile 标志
- B: 独立子命令
- C: 暂不添加 CLI

**Selected:** C — 暂不添加 CLI

**Rationale:** 优先验证核心 API 功能，CLI 留给后续 phase。

### 5. Golden 文件来源
**Question:** Golden file 是复用 Phase 63 已有的还是新编写？

**Options:**
- A: 复用 Phase 63 已有
- B: Phase 64 新编写

**Selected:** B — Phase 64 新编写

**Rationale:** Phase 64 需要覆盖完整的端到端链路（包括 pipeline 集成部分），与 Phase 63 的单元级测试互补。

### 6. 集成字段 (Integration Field)
**Question:** ParseResult 中 Kismet 反编译结果放在哪个字段？

**Selected:** Claude's Discretion — 选择 `decompiled_functions` 字段，与 `blueprint_metadata` 同级

**Rationale:** 保持一致性，扁平字段便于访问。完整元数据通过 KismetDecompiledResult 封装。

## Deferred Ideas
- CLI 入口（`--decompile` 标志或 `uasset-decompile` 子命令）
- Markdown 格式反编译报告

---

*Phase: 64-集成与验证*
*Discussion completed: 2026-05-20*
