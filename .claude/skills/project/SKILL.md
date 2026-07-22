---
name: project
description: 项目统一知识库：命令参考、测试规则、核心架构、日志分析、批量解析、Issue 审查。按需加载子文档。
---

# 项目统一知识库

按需加载的项目知识库，包含命令参考、测试规则、核心架构和维护流程。

## 触发条件

根据用户输入关键词自动加载对应子文档：

| 关键词 | 加载文件 |
|--------|----------|
| "命令"、"run.py"、"pytest"、"常用命令" | `references/commands.md` |
| "测试规则"、"测试数量"、"test rules"、"测试文件" | `references/test-rules.md` |
| "架构"、"模块"、"管线"、"pipeline"、"结构" | `references/architecture.md` |
| "分析日志"、"审查 log"、"整理报错"、"日志报告" | `references/log-analysis.md` |
| "批量解析"、"测试样本"、"错误报告"、"parse samples" | `references/batch-parse.md` |
| "issue 状态"、"审查 issue"、"检查修复"、"issue status" | `references/issue-review.md` |
| 首次问及项目结构 / 无特定关键词 | 仅加载本文件（路由表） |

## 快速参考

- **commands.md** — `run.py` 用法、pytest 命令、标记说明
- **test-rules.md** — 测试文件放置规则、数量限制、命名规范
- **architecture.md** — 解析管线图、关键模块、状态模型、重要函数
- **log-analysis.md** — 6 步日志分析流程（定位→提取→归类→检查 Issue→提交→报告）
- **batch-parse.md** — 4 步批量解析流程（目标→解析→归类→报告）
- **issue-review.md** — 5 步 Issue 审查流程（获取→检查→分类→操作→汇总）

## 约束

- 所有维护操作只读分析，不修改源文件或日志
- 报告输出到 `temp/` 目录
- Issue 提交前必须检查重复
- 批量解析使用 `parse_package()` + `tolerant=True`
