# Phase 34: 等价验证 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 34-等价验证
**Areas discussed:** 验证方法、验证范围、测试资产、差异处理、验证工具、报告形式

---

## 验证方法

| Option | Description | Selected |
|--------|-------------|----------|
| 整体 diff | 将 JSON 输出序列化后进行字符串级 diff，最简单直观 | |
| 逐字段对比 | 逐字段遍历 dict 结构，对比每个 key 的值 | |
| 两者结合 | 先用整体 diff 快速验证，失败时再用逐字段对比定位差异 | ✓ |

**User's choice:** 两者结合
**Notes:** 用户希望先快速验证，失败时精确定位差异位置

---

## 验证范围

| Option | Description | Selected |
|--------|-------------|----------|
| JSON 输出 | 完整 JSON 输出（format_json_full） | ✓ |
| JSON Summary | 精简 JSON 输出（format_json_summary） | ✓ |
| Text 输出 | YAML 风格文本输出（format_text_full） | ✓ |
| Markdown 输出 | Markdown + Mermaid 流程图输出（format_markdown） | ✓ |

**User's choice:** 全部四种格式
**Notes:** 不跳过任何输出格式，确保全面验证

---

## 测试资产

| Option | Description | Selected |
|--------|-------------|----------|
| 现有测试资产 | 使用 tests/ 目录中已有的合成测试资产 | |
| 真实蓝图资产 | 使用真实蓝图资产（如 BP_FirstPersonCharacter） | |
| 两者结合 | 同时测试合成资产和真实资产，覆盖边界场景 | ✓ |

**User's choice:** 两者结合
**Notes:** 合成资产覆盖边界场景，真实资产验证实际解析

---

## 差异处理

| Option | Description | Selected |
|--------|-------------|----------|
| 记录并继续 | 发现差异后记录并继续验证，最后生成完整差异报告 | ✓ |
| 立即修复 | 发现第一个差异后立即停止验证，修复后重新验证 | |
| 批量修复 | 同时记录所有差异，然后自动修复常见问题 | |

**User's choice:** 记录并继续
**Notes:** 不中断验证流程，生成完整差异报告后再处理

---

## 验证工具

| Option | Description | Selected |
|--------|-------------|----------|
| 测试文件 | 在 tests/ 目录中创建专门的验证测试文件，使用 pytest 运行 | ✓ |
| 独立脚本 | 创建独立的 scripts/verify_equivalence.py 脚本 | |
| 模块内置 | 在 src/uasset_read/ 模块中添加验证函数 | |

**User's choice:** 测试文件
**Notes:** 验证是测试阶段工具，使用 pytest 框架运行

---

## 报告形式

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown 报告 | 生成 VERIFICATION.md 文件，记录所有差异和修复状态 | ✓ |
| 终端输出 | 仅在终端输出差异信息，不生成文件 | |
| JSON 报告 | 生成 JSON 格式的差异报告 | |

**User's choice:** Markdown 报告
**Notes:** 生成 `.planning/phases/34-equivalence-verification/VERIFICATION.md`

---

## Claude's Discretion

- 测试用例的具体分组和命名由规划阶段确定
- diff 工具的具体实现由规划阶段确定
- 差异报告的具体字段格式由规划阶段确定

## Deferred Ideas

None — discussion stayed within phase scope.