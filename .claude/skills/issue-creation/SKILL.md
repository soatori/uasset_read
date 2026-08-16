---
name: issue-creation
description: Use when 用户需要创建 GitHub Issue、报告 bug、请求功能或提交增强建议
trigger: true
---

# Issue Creation

## 标题规范

### 格式要求

- **长度限制**: 不超过 72 字符（含前缀）
- **前缀标签**: 必须使用以下前缀之一，后跟冒号和空格

| 前缀 | 用途 |
|------|------|
| `[Bug]` | 缺陷报告、功能异常 |
| `[Feature]` | 全新功能请求 |
| `[Enhancement]` | 现有功能改进 |
| `[Docs]` | 文档相关变更 |
| `[Refactor]` | 代码重构（无功能变化） |
| `[Test]` | 测试相关 |
| `[Chore]` | 工具、CI、配置等维护任务 |

### 写作原则

- **使用祈使句**: 以动词开头，描述期望行为（如 "Fix crash when parsing..." 而非 "Fixing..." 或 "A bug in..."）
- **简明扼要**: 一句话概括核心问题，避免冗余修饰
- **具体明确**: 包含关键组件/模块名称（如 "[Bug] Fix FLinkerLoad offset calculation for IoStore assets"）
- **不加标点**: 标题末尾不加句号

### 好坏示例

```
[Bug] Fix crash when parsing Blueprint with circular references
[Feature] Add support for animation blueprint state machine export
[Enhancement] Improve error messages for corrupted export table entries
[Docs] Add UE5.4 serialization format changes to wiki

# 反例
[Bug] Fix bug                    # 太模糊
[Feature] 添加新功能              # 中文标题不符合项目约定
[Enhancement] Fix and improve    # 未描述具体问题
```

---

## Issue 模板

### Bug Report

```markdown
## Describe the bug

<!-- 一句话概括问题本质 -->

## To Reproduce

<!-- 最小复现步骤，按顺序编号 -->

1. ...
2. ...
3. ...

## Expected behavior

<!-- 期望的正确行为 -->

## Actual behavior

<!-- 实际行为，附错误信息/堆栈 -->

```
<!-- 粘贴完整错误输出 -->
```

## Environment

- OS: Windows 11
- Python: 3.10+
- Project version: (如 v0.5.5)
- Sample file: (如有)

## Additional context

<!-- 补充信息：截图、相关 issue、相关代码路径等 -->
```

### Feature Request

```markdown
## Problem statement

<!-- 描述你遇到的问题或需求背景 -->

## Proposed solution

<!-- 你期望的解决方案 -->

## Alternatives considered

<!-- 你考虑过的其他方案 -->

## Acceptance criteria

<!-- 完成该功能的验收标准，用复选框列出 -->

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Additional context

<!-- 补充信息：参考实现、相关文档、设计图等 -->
```

### Enhancement

```markdown
## Current behavior

<!-- 当前行为描述 -->

## Proposed improvement

<!-- 改进方案描述 -->

## Motivation

<!-- 为什么需要这个改进（性能、易用性、准确性等） -->

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Additional context

<!-- 补充信息 -->
```

---

## Description 结构规范

### Problem / Steps / Expected / Actual 四段式

所有 Bug Report 必须包含以下四个部分：

| 部分 | 作用 | 写作要点 |
|------|------|----------|
| **Problem** | 问题本质 | 一句话概括，说明"什么出了问题" |
| **Steps to Reproduce** | 复现路径 | 编号列表，从初始状态开始，步骤可重复 |
| **Expected Behavior** | 期望行为 | 描述正常情况下应该发生什么 |
| **Actual Behavior** | 实际行为 | 描述实际发生了什么，附错误信息 |

### 写作建议

- **Steps** 应该是任何人都能按顺序执行并得到相同结果的
- **Actual Behavior** 尽量包含完整的错误输出（堆栈、日志）
- **Expected Behavior** 不要笼统地说"应该正常工作"，要具体说明正确行为
- 如果问题只在特定条件下出现，在 Problem 中说明条件

---

## Acceptance Criteria 格式

验收标准用于明确"做到什么程度算完成"，是 Issue 最重要的部分之一。

### 格式要求

- 使用 `- [ ]` 复选框列表
- 每条标准必须是**可验证的**（能明确判断是否满足）
- 每条标准只描述**一个**可测试的行为
- 优先使用"当...时，系统应该..."的句式

### 示例

```
- [ ] 当输入包含圆形引用的 Blueprint 时，解析器不崩溃并返回 partial 状态
- [ ] 当遇到未知 class 时，输出包含 OPAQUE_CLASS_PAYLOAD 标记
- [ ] 新增的单元测试覆盖 circular reference 场景
- [ ] 所有现有测试通过（`pytest` 零失败）
```

### 不合格示例

```
- [ ] 代码质量好          # 不可验证
- [ ] 修复所有相关问题      # 范围模糊
- [ ] 重构完成            # 未定义完成标准
```

---

## Labels 和分类

### 类型标签（互斥，选一个）

| 标签 | 说明 |
|------|------|
| `bug` | 缺陷 |
| `feature` | 新功能 |
| `enhancement` | 改进 |
| `documentation` | 文档 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 维护任务 |

### 优先级标签（可选）

| 标签 | 说明 |
|------|------|
| `priority: critical` | 阻塞发布或核心功能不可用 |
| `priority: high` | 严重影响用户体验 |
| `priority: medium` | 正常优先级 |
| `priority: low` | 低优先级，可以延后 |

### 领域标签（可选，可多选）

| 标签 | 说明 |
|------|------|
| `area: core` | 核心解析引擎 |
| `area: kismet` | Kismet/蓝图脚本 |
| `area: material` | 材质系统 |
| `area: anim-blueprint` | 动画蓝图 |
| `area: iostore` | IoStore 容器 |
| `area: pak` | PAK 文件 |
| `area: output` | JSON/Markdown 输出 |
| `area: schema` | Schema/类型定义 |

### 标签使用规则

- 每个 Issue 至少有一个类型标签
- 领域标签帮助分配责任人和搜索筛选
- 优先级由维护者在 triage 时设置，创建者可建议但不强制

---

## 创建前准备

在创建 Issue 之前，先执行以下步骤：

1. **搜索现有 Issue**: `gh issue list --search "<关键词>"` 避免重复
2. **grep 相关代码**: 使用 Grep 工具搜索受影响的文件和函数
3. **分析影响范围**: 确定所有受影响的位置，而非仅表面症状
4. **检查现有实现**: 查看代码库中是否有类似问题的正确处理模式

## 核心规则

| 规则 | 说明 | 反例 |
|------|------|------|
| **一个问题一个 Issue** | 不捆绑无关问题，即使它们相关 | "Fix crash AND add new feature" |
| **描述问题而非方案** | 让实现者决定如何解决，除非你有充分理由 | "Add try/except in line 42" |
| **定义"完成"** | Acceptance Criteria 明确、可验证、可测试 | "Make it better" |
| **可复现** | 提供最小复现步骤或示例文件 | "It doesn't work sometimes" |
| **避免 duplicate** | 创建前搜索现有 Issue | 重复提交相同问题 |
| **全面分析** | 列出所有受影响的文件和函数，而非仅表面症状 | 只描述崩溃，不分析根因 |

## Common Mistakes

| 错误 | 正确做法 |
|------|----------|
| 标题太模糊（"Fix bug"） | 包含组件名称（"Fix crash when parsing Blueprint"） |
| 缺少复现步骤 | 提供 1-2-3 编号的最小复现路径 |
| Acceptance Criteria 不可验证 | 使用"当...时，系统应该..."句式 |
| 一个 Issue 包多个问题 | 拆分为独立 Issue |
| 不搜索现有 Issue | 创建前用关键词搜索 |

### 额外最佳实践

- **引用相关代码**: 如果知道问题代码位置，引用文件路径或函数名
- **关联 Issue**: 如果此 Issue 依赖其他 Issue，使用 `Depends on #xxx` 说明
- **保持更新**: 如果问题状态变化，及时更新 Issue 描述或评论
- **关闭时说明**: 关闭 Issue 时说明关闭原因（已修复 / 无法复现 / 不在范围内）

---

## Trigger Keywords

**Issue 创建**: "创建issue", "提issue", "新issue", "new issue", "create issue", "open issue",
"bug报告", "报告问题", "report bug", "file bug", "bug report",

**功能请求**: "feature request", "提个需求", "功能请求", "新功能", "add feature", "request feature",
"增强请求", "enhancement", "improve", "优化", "改进",

**Issue 管理**: "close issue", "关闭issue", "fix issue", "修复issue", "duplicate", "重复",
"issue status", "issue状态", "triage", "分类", "label", "打标签"

**GitHub**: "gh issue", "github issue", "issue template", "issue模板", "issue列表", "open issues"
