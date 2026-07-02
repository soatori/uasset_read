---
name: fix-exec
description: 修复与批量执行——按计划文档执行修复、从 GitHub Issues 批量修复。当用户提到"修复计划""批量修复""issue 修复""按计划执行""修复所有 issues""批量关闭 issue""close issues""gh issue"时触发。
---

# Fix Execution Skill

根据用户意图加载对应子文档执行。输出通常为修复执行报告或批量修复汇总。

## 路由

| 关键词 | 子文档 | 说明 |
|--------|--------|------|
| 修复计划、按计划执行、fix plan、计划文档 | [fix-plan-execution.md](references/fix-plan-execution.md) | 执行预定义修复计划 |
| 批量修复、issue 修复、批量关闭、open issues、close issues、gh issue | [issue-batch-fix.md](references/issue-batch-fix.md) | 从 GitHub Issues 批量修复 |

## 使用方式

1. 根据上表匹配用户意图
2. 使用 Read 工具加载对应子文档
3. 按子文档指令执行
