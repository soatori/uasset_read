---
name: code-quality-fix
description: Use when asked to fix code quality issues, standardize patterns, remove code smells, or after code review findings
---

# Code Quality Fix

## Overview

自动检测并修复常见代码质量问题，统一项目编码风格。

## When to Use

- "修复代码质量问题"
- "规范化代码"
- 代码审查后的批量修复
- 合并前质量检查

## Inputs

- 代码审查结论、测试失败、质量门禁输出，或用户明确指出的代码异味
- 需要修改的模块范围；未指定时先用 CodeGraph 或 `rg` 缩小范围

## Outputs

- 最小必要代码改动
- 对应测试或验证命令结果
- 若问题无法安全修复，列出原因和后续建议

## 检查与修复清单

### P0: 错误处理反模式

| 反模式 | 修复方案 |
|---|---|
| `except Exception: pass` | 替换为带日志的 handler |
| 缺少 `MemoryError` 处理 | 添加 `except MemoryError` |
| 静默吞掉异常 | 记录 debug 日志 |

### P1: 命名规范

| 反模式 | 修复方案 |
|---|---|
| 魔术数字（如 `0x02`, `1_000_000`, `50`） | 提取为命名常量 |
| 未使用的导入 | 移除 `from X import Y` 但未使用 |
| 跨层反向导入 | 消除模块对上层包的导入 |

### P2: 代码结构

| 反模式 | 修复方案 |
|---|---|
| 重复代码 >60% | 提取公共函数 |
| 过长函数 (>50行) | 拆分逻辑到独立函数 |
| Logger 使用不统一 | 统一为模块级 logger |

### P3: 类型注解

| 反模式 | 修复方案 |
|---|---|
| 缺少 `Callable` 注解 | 补充完整类型签名 |
| `summary` 等返回类型为 `Any` | 替换为具体类型 |

## 操作流程

1. 结构性问题优先使用 CodeGraph；字面量反模式使用 `rg` / Glob 定位
2. 按 P0→P3 优先级逐项修复
3. 修复范围尽量局部化，避免顺手重构无关模块
4. 每项修复后运行相关测试；跨模块改动运行 `python -m pytest tests/ -q`
5. 提交消息格式：`<type>: <修复描述>`
   - `fix:` 错误处理修复
   - `refactor:` 代码结构优化
   - `style:` 格式/命名统一
   - `type:` 类型注解补充

## Verification

- 单文件修复：运行对应测试文件
- 共享模块修复：运行相关测试目录或全量 `python -m pytest tests/ -q`
- 若修复影响渲染、IR 或蓝图流程，补充回归测试

## 项目特定约束

- 见 [.claude/rules/*.md](../../rules/constraints.md)
- 零运行时依赖 — 不添加第三方包
- 必须参考 UE 源码 — 禁止猜测二进制格式

## Boundaries

- 不在同一次任务中混入版本发布、文档大迁移或无关格式化
- 不自动修改二进制资产或生成文件
- 不为压制测试失败而降低断言强度

## Common Mistakes

- **过度修复**：一次性改完所有 P3 问题可能引入回归，应按优先级分批验证
- **误删有用注释**：清理死代码时不要删除有文档作用的注释
- **忽略项目约定**：某些"反模式"在项目中是有意的（如特定的异常处理策略），修复前先确认
