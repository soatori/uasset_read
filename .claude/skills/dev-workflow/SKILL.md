---
name: dev-workflow
description: Use when 用户需要执行开发任务、任务分解、并行开发、代码审查或分支合并
trigger: true
---

# Dev Workflow

本技能定义了完整的开发工作流程，涵盖任务规划、并行执行、代码审查和收尾合并的全流程。

## Orca 编排 Skills

Orca 编排技能用于任务级别的规划和协调，优先调用：

### `/writing-plans` — 编写任务计划

将复杂需求拆解为可执行的任务列表，每个任务有明确的输入/输出和验收标准。

- **调用方式**: `/writing-plans <需求描述>`
- **适用场景**:
  - 新功能开发前的任务拆解
  - 重构工作的步骤规划
  - Bug 修复的排查路径设计
  - 跨模块改动的影响分析和执行顺序
- **输出格式**: 结构化的任务列表，包含优先级、依赖关系、预估复杂度
- **注意事项**:
  - 计划应粒度适中，每个任务可在一次会话内完成
  - 标注任务间的依赖关系，避免循环依赖
  - 对高风险任务增加验证步骤

### `/dispatching-parallel-agents` — 并行派发 Agent 执行

将计划中的独立任务分配给多个 subagent 并行执行，加速开发效率。

- **调用方式**: `/dispatching-parallel-agents`
- **适用场景**:
  - 多个独立模块需要同步开发
  - 测试用例需要批量编写
  - 代码审查需要从多个维度并行检查
  - 大规模重构中互不依赖的子任务
- **执行原则**:
  - 仅在任务间无依赖时使用并行
  - 每个 agent 负责单一职责，边界清晰
  - 合并前需验证各 agent 的输出一致性
- **注意事项**:
  - 文件冲突风险：多个 agent 同时编辑同一文件会导致冲突
  - 上下文隔离：每个 agent 独立工作，需在 prompt 中提供充足上下文
  - 结果汇总：主 agent 负责合并结果并处理冲突

### `/finishing-a-development-branch` — 分支收尾合并

完成开发分支的收尾工作，包括最终验证、冲突解决和合并到目标分支。

- **调用方式**: `/finishing-a-development-branch`
- **适用场景**:
  - 功能开发完成，准备合并到 develop 或 master
  - 需要清理临时文件和调试代码
  - 需要运行完整测试套件确认无回归
  - 需要撰写合并提交信息
- **执行步骤**:
  1. 运行全量测试，确认通过
  2. 检查是否有遗留的调试代码或临时文件
  3. 确认代码符合项目约束（参考 `.claude/rules/constraints.md`）
  4. 解决合并冲突（如有）
  5. 生成规范的提交信息

### `/brainstorming` — 头脑风暴

针对开放式问题进行多角度探索，生成候选方案并评估优劣。

- **调用方式**: `/brainstorming <主题或问题>`
- **适用场景**:
  - 架构设计方案选型
  - 技术方案可行性探索
  - 性能优化策略讨论
  - 新功能的实现路径探索
- **输出内容**:
  - 多个候选方案及其优缺点分析
  - 推荐方案及理由
  - 潜在风险和缓解措施

## Orca Runtime Skills

Orca 运行时技能提供底层编排和工作区管理能力：

### `orchestration` — 多 Agent 编排

结构化多 agent 协调：线程消息、阻塞 ask/reply、任务派发、任务 DAG、决策门、协调循环。

- **适用场景**:
  - 复杂任务需要多 agent 协作
  - 需要任务依赖关系（DAG）管理
  - 需要决策门（decision gates）控制流程
  - 需要协调循环（coordinator loops）监控进度
- **加载完整指南**: `ORCA skills get orchestration`
- **与 dispatching-parallel-agents 区别**: orchestration 适用于需要状态协调的复杂 DAG；dispatching 适用于独立任务并行

### `orca-cli` — Orca 工作区管理

管理 Orca 工作区、终端、worktree、自动化、技能共享。

- **适用场景**:
  - 需要创建/管理工作区（worktree）
  - 需要终端控制（读取、发送、等待）
  - 需要 handoff（将任务交给另一个 agent）
  - 需要 Orca 内置浏览器
- **加载完整指南**: `ORCA skills get orca-cli`
- **关键命令**: `ORCA worktree ps`, `ORCA terminal list`, `ORCA status --json`

### `computer-use` — 桌面应用交互

通过无障碍树、截图和安全 UI 操作检查和操作本地桌面应用窗口。

- **适用场景**:
  - 需要读取桌面应用状态（Spotify、Slack 等）
  - 需要点击、输入、滚动等 UI 操作
  - 需要截图或读取无障碍树
- **加载完整指南**: `ORCA skills get computer-use`
- **注意**: 仅用于 Orca 管理的桌面 UI；浏览器内嵌页面用 Orca 浏览器

## Superpowers Skills

Superpowers 技能用于执行层面的质量保障和效率提升：

### `requesting-code-review` — 代码审查

对已完成的代码进行系统化审查，发现潜在问题。

- **适用场景**:
  - 功能开发完成后、合并前的自查
  - 复杂逻辑的正确性验证
  - 代码风格和项目规范一致性检查
- **审查维度**:
  - 正确性：逻辑是否正确，边界条件是否处理
  - 可维护性：代码是否清晰，命名是否合理
  - 性能：是否存在明显的性能问题
  - 安全性：是否存在安全风险
  - 规范性：是否符合项目约束和编码规范

### `subagent-driven-development` — Subagent 驱动开发

利用 subagent 进行模块化开发，主 agent 负责协调和集成。

- **适用场景**:
  - 大型功能需要分模块实现
  - 需要同时处理多个独立文件的修改
  - 测试用例需要与实现同步编写
- **使用模式**:
  - 主 agent 定义接口规范和验收标准
  - Subagent 负责具体实现
  - 主 agent 验证集成结果

### `systematic-debugging` — 系统化调试

按照结构化方法定位和修复 Bug，避免盲目试错。

- **适用场景**:
  - 测试失败需要定位根因
  - 运行时错误需要排查
  - 性能问题需要定位瓶颈
- **调试流程**:
  1. 复现问题，收集错误信息
  2. 缩小范围，定位可疑代码区域
  3. 提出假设，设计验证实验
  4. 验证假设，确认根因
  5. 修复问题，编写回归测试

### `test-driven-development` — 测试驱动开发

先编写测试再实现功能，确保代码质量和可测试性。

- **适用场景**:
  - 新功能开发
  - Bug 修复（先编写复现测试）
  - 重构（先确保测试覆盖）
- **执行步骤**:
  1. 编写失败的测试用例（Red）
  2. 编写最小实现使测试通过（Green）
  3. 重构代码保持测试通过（Refactor）

### `verification-before-completion` — 完成前验证

在标记任务完成前进行最终验证，确保质量达标。

- **适用场景**:
  - 任何任务完成前的最终检查
  - 合并前的完整性验证
  - 发布前的质量把关
- **验证内容**:
  - 所有测试通过
  - 代码符合项目约束
  - 无遗留的 TODO 或 FIXME
  - 文档已更新（如需要）
  - 提交信息规范

## 工作流顺序

### 标准开发流程

```
技术分析（grep 代码、理解现有实现）
  ↓
/writing-plans — 拆解任务
  ↓
review — 审查计划合理性
  ↓
/dispatching-parallel-agents — 并行执行（如适用）
  ↓
verification-before-completion — 完成前验证
  ↓
/requesting-code-review — 代码审查
  ↓
/finishing-a-development-branch — 合并收尾
```

### 快速修复流程

```
问题发现
  ↓
systematic-debugging — 定位根因
  ↓
test-driven-development — 编写修复测试
  ↓
verification-before-completion — 验证修复
  ↓
finishing-a-development-branch — 合并
```

### 架构探索流程

```
问题定义
  ↓
/brainstorming — 探索方案
  ↓
/writing-plans — 制定实施计划
  ↓
subagent-driven-development — 分模块实现
  ↓
/requesting-code-review — 审查架构决策
  ↓
/finishing-a-development-branch — 合并
```

### 复杂编排流程（Orca Orchestration）

```
任务分解
  ↓
ORCA orchestration — 创建任务 DAG
  ↓
决策门 — 关键节点验证
  ↓
协调循环 — 监控进度
  ↓
worker_done — 收集结果
  ↓
ORCA worktree — 管理工作区
```

## 使用建议

- **技术分析先行**: 在调用 /writing-plans 之前，先 grep 代码理解现有实现，避免重复造轮子
- **任务粒度**: 每个任务应可在一次会话内完成，复杂任务需进一步拆解
- **并行判断**: 仅在任务间无文件依赖时使用并行执行
- **验证优先**: 任何代码变更后都应运行相关测试
- **约束遵守**: 始终遵循 `.claude/rules/constraints.md` 中的项目约束

## Common Mistakes

| 错误 | 正确做法 |
|------|----------|
| 跳过 `/writing-plans` 直接编码 | 先拆解任务，明确输入输出 |
| 在有文件依赖的任务间使用并行 | 检查任务间是否有共享文件 |
| 合并前不运行测试 | 执行 `verification-before-completion` |
| 忽略项目约束 | 始终参考 `.claude/rules/constraints.md` |

## Trigger Keywords

**Orca 编排**: "开发流程", "怎么做", "任务分解", "dev workflow", "orchestrate", "并行开发", "代码审查", "调试", "测试驱动", "分支合并",
"writing-plans", "dispatching", "finishing", "brainstorming", "code review", "debug", "TDD", "merge"

**Orca Runtime**: "orca", "worktree", "handoff", "handover", "handover to", "give this to", "另一个agent", "另一个工作区",
"terminal", "终端", "computer use", "桌面应用", "截图", "read app", "click", "type",

**任务管理**: "任务DAG", "决策门", "coordinator", "协调", "worker", "派发", "任务状态", "进度监控",
"task list", "task status", "escalation", "worker_done"

**工作区**: "创建工作区", "切换工作区", "清理工作区", "工作区状态", "spawn", "launch agent",
"new worktree", "list worktrees", "clean worktree"
