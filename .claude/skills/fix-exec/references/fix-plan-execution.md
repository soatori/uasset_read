# Fix Plan Execution

## Overview

读取已写好的修复计划（markdown），按依赖关系排序，逐个执行：创建分支 → 修复 → 测试 → 提交 → 合并。

## 触发场景

- 用户提供了 `docs/plans/` 下的修复计划文档
- 从 issue 批量修复计划转为执行阶段
- 计划文档已确认，需要实施

## 工作流

```
读取计划 → 解析任务依赖 → 拓扑排序 → 逐个执行 → 汇总结果
```

### Step 1: 读取计划

```bash
# 查找计划文档
ls docs/plans/*.md
ls temp/*plan*.md
```

计划格式要求：
```markdown
# 修复计划

## Task 1: {标题}
- 文件: {修改的文件}
- 步骤: {具体步骤}
- 验证: {测试命令}
- 提交: {commit message}

## Task 2: {标题}
- 依赖: Task 1
- ...
```

### Step 2: 拓扑排序

根据依赖关系确定执行顺序，无依赖的任务可并行。

### Step 3: 逐个执行

对每个任务：

```bash
# 1. 创建分支（如需要）
git checkout -b fix/{task-name} develop

# 2. 实施修复
# 编辑文件...

# 3. 运行验证
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5

# 4. 提交
git add {files}
git commit -m "{commit_message}"

# 5. 合并
git checkout develop
git merge fix/{task-name} --no-ff
git branch -d fix/{task-name}
```

### Step 4: 汇总报告

```markdown
# 修复执行报告

## 结果
| 任务 | 状态 | 耗时 |
|------|------|------|
| Task 1: 修复 var_type | ✅ | 2min |
| Task 2: 修复 FText | ✅ | 3min |
| Task 3: 设计方案 | ✅ | 1min |

## 总计
- 完成: 3/3
- 失败: 0
```

## 并行策略

无依赖的任务可使用并行 subagent 执行，每个 agent 独立工作区（git worktree），依次合并避免冲突。

## 注意事项

- 测试必须通过才能提交
- 每个任务独立分支，避免互相干扰
- 提交格式遵循项目规范：`<type>: <描述>`
- 如任务失败，记录错误并继续下一个
