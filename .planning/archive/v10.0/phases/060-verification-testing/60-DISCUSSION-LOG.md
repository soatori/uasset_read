# Phase 60: 验证与测试 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 60-验证与测试
**Areas discussed:** 验证策略, 测试组织, 失败处理

---

## 验证策略

| Option | Description | Selected |
|--------|-------------|----------|
| pytest 集成测试 | 自动化回归测试，CI 可跑，需要预定义期望输出 | ✓ |
| 手动比对 | 人工审阅输出与 C++ 参考的差异，灵活但需重复劳动 | |
| 混合方案 | JSON diff + 关键字段比对，结构验证而非逐行 | |

**User's choice:** pytest 集成测试
**Notes:** 推荐选项，CI 兼容

---

| Option | Description | Selected |
|--------|-------------|----------|
| BP_FirstPersonCharacter | 已有 reference 文件，真实资产，覆盖 Move/Aim/Jump | ✓ |
| 新建测试资产 | 针对特定边界情况创建，但需要额外工作 | |
| Golden 输出文件 | 预生成的期望输出文件，比对简单但需维护 | |

**User's choice:** BP_FirstPersonCharacter
**Notes:** 使用现有参考文档，无需额外创建资产

---

| Option | Description | Selected |
|--------|-------------|----------|
| 逐行比对 | 生成的 C++ 与参考实现完全一致 | ✓ |
| 结构比对 | 只验证 AST/IR 结构，允许语法变化 | |
| 语义比对 | 允许格式、命名差异（如参数名大小写），核心逻辑匹配 | |

**User's choice:** 逐行比对
**Notes:** 严格验证，不允许语法差异

---

| Option | Description | Selected |
|--------|-------------|----------|
| 核心函数 | 只覆盖 ROADMAP.md 中明确提到的 Move/Aim/Jump | ✓ |
| 全覆盖 | 所有 Phase 56-59 的输出：骨架+函数签名+函数体+构造函数 | |
| 增量验证 | 先跑现有测试，再补充失败 case | |

**User's choice:** 核心函数
**Notes:** 避免过度测试，Phase 56-59 已有独立测试覆盖

---

## 测试组织

| Option | Description | Selected |
|--------|-------------|----------|
| 单独测试文件 | 创建新文件 test_phase60_verification.py，独立 Phase 60 测试 | ✓ |
| 合并现有 | 合入 test_cpp_gen.py 或其他现有文件 | |
| 子目录分离 | 独立文件但放在 tests/test_cpp_gen/ 目录 | |

**User's choice:** 单独测试文件
**Notes:** 避免与现有测试混淆

---

| Option | Description | Selected |
|--------|-------------|----------|
| 预生成 fixture | 预加载 BP_FirstPersonCharacter.uasset 并缓存 JSON 输出 | ✓ |
| 实时解析 | 每个测试实时解析 .uasset | |
| 参考文件驱动 | 从 reference/蓝图节点文本参考.md 提取关键数据 | |

**User's choice:** 预生成 fixture
**Notes:** pytest fixture scope="module" 模式

---

| Option | Description | Selected |
|--------|-------------|----------|
| 功能描述式 | test_move_function_body, test_jump_event_chain | ✓ |
| Requirement ID | test_TEST02_move_json_matches_cpp | |
| Phase 标记式 | test_p60_move_body_vs_reference | |

**User's choice:** 功能描述式
**Notes:** 清晰命名，易于理解测试意图

---

## 失败处理

| Option | Description | Selected |
|--------|-------------|----------|
| 详细 diff | 输出实际 vs 期望的完整 diff，高亮差异行 | ✓ |
| 简洁输出 | 只输出第一行差异位置和内容 | |
| 文件记录 | 生成失败 case 的 temp/*.diff 文件供调试 | |

**User's choice:** 详细 diff
**Notes:** 方便定位问题

---

| Option | Description | Selected |
|--------|-------------|----------|
| 全部通过 | 所有测试通过后才可推进 Phase 60 完成 | ✓ |
| Requirement 覆盖 | 至少覆盖 TEST-01/TEST-02/TEST-03 三项 Requirement | |
| 代表性验证 | 只验证 Move 函数作为代表性 case | |

**User's choice:** 全部通过
**Notes:** 严格回归要求

---

| Option | Description | Selected |
|--------|-------------|----------|
| 中间 IR 可见 | 输出中间 IR（CppClassIR/CppMethodIR）帮助定位问题 | ✓ |
| 自动 trace | 测试失败后自动生成 debug trace 文件 | |
| 标准 pytest | 只依赖 pytest 的标准输出 | |

**User's choice:** 中间 IR 可见
**Notes:** 辅助调试，打印 IR 内容

---

## Claude's Discretion

None — 所有决策由用户明确选择。

## Deferred Ideas

None — 讨论保持在 phase scope 内。