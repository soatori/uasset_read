---
name: version-sync
description: Use when updating version numbers across multiple files, preparing a release, or fixing inconsistent version strings
---

# Version Sync

## Overview

统一更新项目中所有版本号，避免多处不一致。

## When to Use

- "更新版本号"
- 发布新版本时同步所有版本引用
- 发现版本号不一致

## Inputs

- 目标版本号，格式为 `X.Y.Z-dev` 或 `X.Y.Z`
- 版本同步范围；未指定时使用本 skill 的扫描文件清单

## Outputs

- 所有项目版本引用同步后的改动
- 版本残留检查结果
- 不应替换的 UE 引擎版本或测试资产版本说明

## 扫描文件清单

| 文件 | 说明 |
|---|---|
| `CLAUDE.md` | 项目约束中的版本 |
| `README.md` / `README.zh-CN.md` | 仓库介绍版本 |
| `src/uasset_read/__init__.py` | `__version__` 常量 |
| `docs/guides/{dev-guide,contributing}.md` | 开发与贡献文档版本 |
| `docs/release*/**/*.md` / `docs/release*/*.md` | 发布说明标题 |
| `wiki/**/*.md` | Wiki 文档版本引用 |

## 操作流程

1. 确定目标版本号（格式：`X.Y.Z-dev` 或 `X.Y.Z`）
2. `rg -l "v?0\.[0-9]+\.[0-9]+(-[a-z]+)?" -g "CLAUDE.md" -g "README*.md" -g "src/**/*.py" -g "docs/**/*.md" -g "wiki/**/*.md"` 扫描所有候选文件
3. 逐个确认并替换，保持格式一致
4. 运行 `rg "v?0\.[0-9]+\.[0-9]+" -g "CLAUDE.md" -g "README*.md" -g "src/**/*.py" -g "docs/**/*.md" -g "wiki/**/*.md"` 验证无遗漏
5. 提交时消息：`chore: bump version to <VERSION>`

## Verification

- 检查 `__version__`、README、docs、wiki 是否一致
- 检查 `-dev` 后缀是否符合发布阶段
- 对正式发布版本，确认 release notes 或 changelog 中存在对应条目

## Boundaries

- 不替换 UE 引擎版本、资产格式版本或测试样本文件名
- 不更新测试统计数字；需要时使用 [test-runner](../test-runner/SKILL.md)
- 不创建 tag；发布打标由 [release-prep](../release-prep/SKILL.md) 处理

## 注意事项

- 区分 `-dev` 预发布和正式发布版本号
- 不要替换测试资产文件名中的版本（如 `ue4.27_*.uasset`）
- 测试统计数字（如 994 passed）不在本次替换范围内

## Common Mistakes

- **误替换 UE 版本标识**：资产文件名中的 `ue4.27`、`ue5.0` 是引擎版本，不是项目版本
- **遗漏 wiki/ 目录**：wiki 镜像文档也有版本引用，容易遗漏
- **格式不一致**：有些地方用 `v0.4.4`（带 v 前缀），有些用 `0.4.4`，替换后保持原格式
