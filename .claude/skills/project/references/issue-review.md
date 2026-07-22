# Issue 状态审查

审查 GitHub Issues 状态，检查是否已修复，更新或关闭。

## 参数

用户可指定 issue 编号（如 `#435`），默认审查所有 open issues。

## Step 1: 获取 Issue 列表

```bash
gh issue view <number> --json number,title,state,labels,createdAt,body
# 或所有 open issues
gh issue list --state open --json number,title,state,labels,createdAt --limit 50
```

## Step 2: 逐个检查修复状态

对每个 issue：
1. 阅读描述，理解问题
2. 检查代码变更：`git log --oneline --all --grep="#<number>"`
3. 运行相关测试（如适用）
4. 验证修复

## Step 3: 分类处理

| 状态 | 处理 |
|------|------|
| 已修复 | 添加 `fixed` 标签，关闭 issue，评论修复提交 |
| 部分修复 | 评论现状，保留 open |
| 未修复 | 保留 open，评论现状 |
| 无法复现 | 评论说明，建议关闭 |
| 重复 | 标记 duplicate，指向原 issue |

## Step 4: 执行操作

```bash
gh issue close <number> --comment "已修复：<commit_hash> <description>"
gh issue edit <number> --add-label "fixed"
gh issue comment <number> --body "## 审查状态 (YYYY-MM-DD)\n\n- **代码检查**: <findings>\n- **测试结果**: <pass/fail>\n- **结论**: <已修复/部分修复/未修复>"
```

## Step 5: 输出汇总

报告输出到 `temp/issue_status_report.md`。

## 约束

- 只读检查 + 标准 gh 操作，不修改代码
- 关闭前必须确认修复（有 commit 或测试通过）
