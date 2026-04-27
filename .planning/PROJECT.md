# uasset_read

## What This Is

Python 工具用于读取 Unreal Engine .uasset 文件，让 AI agent 能直接解析资产内容（尤其是蓝图），避免手动在 UE 编辑器中操作。

## Core Value

让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 能解析 .uasset 文件格式
- [ ] 提取蓝图节点信息
- [ ] 输出结构化文本供 agent 理解
- [ ] 输出 JSON 格式供程序解析
- [ ] 输出可读摘要供人理解
- [ ] 单文件读取不能卡死

### Out of Scope

- 导出资源文件（纹理、模型等二进制数据）
- 修改/编辑 .uasset 文件
- 实时解析/监控
- UE 编辑器集成

## Context

### 技术背景
- .uasset 是 Unreal Engine 的资产文件格式
- 包含多种类型：蓝图、材质、纹理、模型、动画等
- 当前项目主要关注蓝图相关的 .uasset

### 源码参考
- 项目内有部分 UE 源码：`UnrealEngine/` 目录
- UE 5.7 完整源码：`D:/Program Files/Epic Games/Engine/UE_5.7`
- 关键模块：CoreUObject（序列化）、BlueprintRuntime（蓝图）

### 目标用户
- AI agents（主要）
- 开发者（次要）

## Constraints

- **语言**: Python — 用户指定
- **性能**: 不能卡死，需响应及时
- **进度管理**: Git 版本控制
- **源码依赖**: 需要参考 UE 源码理解格式

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 实现 | 易于 agent 调用，快速原型开发 | — Pending |
| 参考 UE 源码 | .uasset 格式未公开文档，需要从源码推断 | — Pending |
| 结构化文本优先 | agent 直接理解，无需二次转换 | — Pending |

---
*Last updated: 2026-04-27 after initialization*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state