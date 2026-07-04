---
name: doc-version
description: 文档与版本管理——文档一致性检查、双语文档同步、版本号更新、发布前检查。当用户提到"文档一致性""版本号""bump version""发布检查""双语同步""release readiness""文档同步""changelog""release notes""wiki 同步"时触发。
---

# Doc & Version Skill

根据用户意图加载对应子文档执行。输出通常为一致性检查报告或版本更新确认。

## 路由

| 关键词 | 子文档 | 说明 |
|--------|--------|------|
| 文档一致性、版本号不一致、检查同步 | [doc-consistency.md](references/doc-consistency.md) | 跨文件文档一致性检查（只检查不修改） |
| 双语同步、README 同步、中英文 | [doc-sync.md](references/doc-sync.md) | README.md ↔ README.zh-CN.md 双向同步 |
| 版本号、bump version、更新版本、同步版本、changelog、release notes | [version-bump.md](references/version-bump.md) | 跨文件版本号更新与验证 |
| 发布检查、release readiness、发布前、wiki 同步 | [release-readiness.md](references/release-readiness.md) | 发布前检查清单 |

## 推荐工作流

发布时建议按顺序执行：version-bump → doc-sync → doc-consistency → release-readiness

## 使用方式

1. 根据上表匹配用户意图
2. 使用 Read 工具加载对应子文档
3. 按子文档指令执行
