# Issue Batch Fix Skill

## Overview

系统性地从 GitHub Issues 获取待修复问题，分类分组，按优先级逐个或并行修复，每个 issue 使用独立工作区，验证通过后合并。

## 触发场景

当用户需要：
- "把所有 open issues 都修了"
- 批量处理 GitHub issue（分类、优先级排序、逐个修复）
- 从 issue 列表创建修复分支并验证合并
- 并行修复多个无依赖的 issue

## 工作流

```
gh issue list → 分类分组 → 逐个/并行修复 → 测试验证 → 合并分支 → 关闭 issue
```

### Step 1: 获取并分类 Issues

```bash
gh issue list --state open --limit 50 --json number,title,labels,body
```

分类维度：
- **按优先级**：P0（崩溃/数据损坏）→ P1（功能缺失）→ P2（改进）→ P3（清理）
- **按模块**：serialization / kismet / graph / renderer / linker / archive / cpp / pak
- **按依赖**：有依赖的排后面，无依赖的可并行

### Step 2: 创建修复计划

输出到 `temp/issue-fix-plan.md`：

```markdown
# Issue 修复计划

## P0 - 立即修复
| Issue | 标题 | 模块 | 工作区 | 状态 |
|-------|------|------|--------|------|
| #175 | 非蓝图 JSON 渲染 | renderer | — | 待修复 |

## P1 - 高优先级
...

## 并行组
- 组 A（无依赖）：#175, #172, #171
- 组 B（依赖 #175）：#174
```

### Step 3: 逐个修复

对每个 issue：

```bash
# 1. 创建分支
git checkout -b fix/issue-{N}-{short-description} develop

# 2. 分析问题
gh issue view {N} --json title,body,labels
# 读取相关源码，定位问题根因

# 3. 实施修复
# 编辑代码...

# 4. 运行测试
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5

# 5. 提交
git add {files}
git commit -m "fix: #{N} {简要描述}"

# 6. 推送并创建 PR
git push origin fix/issue-{N}-{short-description}
gh pr create --title "fix: #{N} {标题}" --body "Fixes #{N}"
```

### Step 4: 验证合并

```bash
# 等待 CI 通过
gh pr checks {PR_NUMBER}

# 合并到 develop
git checkout develop
git merge fix/issue-{N}-{short-description}
git branch -d fix/issue-{N}-{short-description}

# 关闭 issue
gh issue close {N} --reason completed
```

### Step 5: 批量汇总

报告格式：
```
=== 批量修复汇总 ===
修复: #175, #172, #171, #174 (4/5)
跳过: #179 (依赖未满足)
失败: 无

模块分布:
  renderer: 1
  kismet: 2
  linker: 1
```

## 并行修复策略

当多个 issue 无依赖关系时，可使用并行 subagent 加速修复：

1. 每个 agent 独立工作区（git worktree）
2. 独立分支、独立测试
3. 依次合并，避免冲突

## 注意事项

- **先研究再修复**：不要直接改代码，先读相关源码和 UE 参考
- **每个 issue 独立工作区**：避免修复间互相干扰
- **测试必须通过**：合并前验证 `python -m pytest tests/ -x -q`
- **提交格式**：`fix: #{N} {描述}`
- **不要猜测 UE 格式**：必须参考 `E:\Develop\lib\UnrealEngine` 源码
