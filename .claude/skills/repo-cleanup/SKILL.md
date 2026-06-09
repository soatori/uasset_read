---
name: repo-cleanup
description: 自动识别并清理不应提交的文件（临时文件、调试产物、CUE4Parse 痕迹等）
---

# Repo Cleanup（仓库清理）

## 适用场景

- "清理工作区"
- "移除临时文件"
- "删除 CUE4Parse 相关文档"
- "归档旧计划"
- 提交前检查不该包含的文件

## 输入

- 清理范围：working-tree / git-history / both
- 可选：特定文件类型或目录

## 流程

1. **扫描识别**
   - 检查 git status
   - 匹配清理规则（见下方）
   - 生成待清理文件列表

2. **分类确认**
   - 列出每类文件及数量
   - 询问用户确认（或自动执行如果规则明确）

3. **执行清理**
   - 工作区清理：删除/移动文件
   - 历史清理：git filter-repo（谨慎使用）
   - 更新 .gitignore

4. **验证结果**
   - 重新检查 git status
   - 确认无遗漏

## 清理规则

### 必须清理

| 类型 | 路径模式 | 处理方式 |
|---|---|---|
| 临时文件 | `temp/*`（除 .gitkeep） | 删除 |
| CodeGraph 索引 | `.codegraph/` | 删除，加入 .gitignore |
| Superpowers 计划 | `.claude/plans/*` | 移动到 `docs/plans/` 或删除 |
| CUE4Parse 文档 | `**/CUE4Parse*` | 删除 |
| 调试日志 | `*.log`, `debug_*` | 删除 |
| 对比报告 | `docs/reports/compare-*` | 归档或删除 |

### 可选清理

| 类型 | 路径模式 | 处理方式 |
|---|---|---|
| 旧测试产物 | `tests/temp/*` | 删除 |
| 备份文件 | `*.bak`, `*.orig` | 删除 |
| IDE 配置 | `.vscode/`, `.idea/`（如不在 .gitignore） | 加入 .gitignore |

### 不清理

- `temp/.gitkeep`（保留目录结构）
- `docs/reports/` 下的正式报告
- 用户明确保留的文件

## 输出

- 清理报告：删除/移动的文件列表
- .gitignore 更新（如有）
- 建议的提交消息

## 边界

- 不删除用户明确保留的文件
- git 历史清理前必须备份
- 不修改已发布版本的文件
- 大文件（>1MB）删除前确认

## 项目特定约束

- 临时文件统一放 `temp/`
- master 分支白名单见 CLAUDE.md
- 清理后运行测试确认无破坏
