---
name: git-branch-workflow
description: 一条命令完成分支创建/合并/清理/PR 创建全流程
---

# Git Branch Workflow（分支管理）

## 适用场景

- "合并至 dev/master"
- "创建 PR"
- "清理工作区"
- "推送并创建发布"

## 输入

- 操作类型：merge / pr / cleanup / release
- 源分支和目标分支（可选，默认按项目规范）
- PR 标题和描述（可选）

## 流程

### 合并操作（merge）

1. **检查状态**
   ```bash
   git status
   git branch --show-current
   ```

2. **清理工作区**
   ```bash
   git stash --include-untracked
   git worktree prune
   ```

3. **合并分支**
   ```bash
   git checkout <target>
   git merge <source> --no-ff
   ```

4. **处理冲突**（如有）
   - 列出冲突文件
   - 询问用户解决策略
   - 或自动解决（如果是简单的文本冲突）

5. **推送远程**
   ```bash
   git push origin <target>
   ```

### PR 创建（pr）

1. **确保分支已推送**
   ```bash
   git push -u origin <branch>
   ```

2. **创建 PR**
   ```bash
   gh pr create --title "<title>" --body "<body>" --base <target>
   ```

3. **输出 PR 链接**

### 清理操作（cleanup）

1. **删除已合并分支**
   ```bash
   git branch --merged | grep -v "main\|master\|develop" | xargs git branch -d
   ```

2. **清理工作树**
   ```bash
   git worktree prune
   ```

3. **清理 stash**
   ```bash
   git stash clear
   ```

### 发布操作（release）

1. **版本号同步**
   - 调用 `version-sync` skill

2. **运行测试**
   - 调用 `test-runner` skill

3. **合并至 master**
   - 按项目规范排除开发文件

4. **创建 tag**
   ```bash
   git tag -a v<version> -m "Release v<version>"
   git push origin v<version>
   ```

5. **创建 GitHub Release**
   ```bash
   gh release create v<version> --title "v<version>" --notes "<changelog>"
   ```

## 输出

- 操作结果摘要
- 新分支/PR/Release 链接
- 下一步建议

## 边界

- 不强制推送（除非明确要求）
- 不删除未合并分支（除非明确要求）
- master 分支操作前必须确认
- 发布前必须运行完整测试

## 项目特定约束

- 默认工作分支：`develop`
- master 仅包含发布内容（见 CLAUDE.md 白名单）
- 提交格式：`<type>: <描述>`
