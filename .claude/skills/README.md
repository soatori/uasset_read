# Claude Skills

本目录存放项目专用 Claude skills。每个 skill 必须位于独立目录，并以 `SKILL.md` 作为入口：

```text
.claude/skills/
├── code-quality-fix/SKILL.md
├── doc-consistency/SKILL.md
├── release-prep/SKILL.md
├── test-runner/SKILL.md
├── ue-source-research/SKILL.md
├── ue-wiki-lookup/SKILL.md
└── version-sync/SKILL.md
```

## Skill 索引

| Skill | 类型 | 主要用途 | 典型产出 |
|---|---|---|---|
| `test-runner` | 验证 | 运行测试、解析 pytest 结果、更新测试统计 | 测试结果、文档统计更新 |
| `code-quality-fix` | 修复 | 分级处理代码质量问题、代码审查问题 | 小范围代码修复、验证结果 |
| `doc-consistency` | 文档 | 检查文档链接、目录结构、术语和引用 | 文档一致性修复清单 |
| `version-sync` | 版本 | 跨 README、源码、docs、wiki 同步版本号 | 版本号一致性变更 |
| `release-prep` | 编排 | 发布前完整流程 | 版本同步、测试、文档、changelog、tag |
| `ue-source-research` | 研究 | 对照 UE C++ 源码确认 `.uasset` 格式和蓝图/Kismet 语义 | 源码证据、解析修复、回归测试 |
| `ue-wiki-lookup` | 研究 | 从 UE wiki 获取源码路径、模块和架构上下文 | wiki context、CodeGraph 查询建议 |

## 编排关系

`release-prep` 是发布流程的总入口，按顺序调用或参考：

1. `version-sync`：同步目标版本号。
2. `test-runner`：运行完整测试并更新测试统计。
3. `doc-consistency`：验证发布相关文档、链接和术语。
4. `release-prep`：汇总 changelog、提交、打 tag。

`code-quality-fix` 不属于发布流程的固定阶段；当测试、审查或质量门禁暴露代码问题时再使用。

`ue-source-research` 是解析器功能开发和格式问题修复的前置 skill；当 `code-quality-fix` 涉及 `.uasset` 二进制格式、蓝图图结构或 Kismet 语义时，应先使用它确认源码依据。

`ue-wiki-lookup` 用于先从 UE wiki 获取模块、源码路径或架构上下文；需要确认序列化行为或改解析器时，继续使用 `ue-source-research`。

## 维护规则

- 保持目录名、frontmatter `name`、调用名一致。
- `description` 写触发条件，不写实现细节。
- `SKILL.md` 必须包含：适用场景、输入、流程、验证、边界。
- 只记录项目专用约束；通用 Claude 行为放在根目录 `CLAUDE.md`。
- 跨 skill 引用使用相对链接，例如 `../version-sync/SKILL.md`。
- 不把临时计划、执行日志或一次性脚本放进 skill 目录；这些内容放入 `.claude/plans/`、`.claude/workflows/` 或 `temp/`。
- 不为通用 Git 操作、一次性清理、宽泛自动化编排创建独立 skill；这些规则放入 `CLAUDE.md`、`.claude/rules/` 或任务计划。
