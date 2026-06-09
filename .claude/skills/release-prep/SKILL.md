---
name: release-prep
description: Use when preparing a release — version bump, test verification, doc update, changelog, and commit. Covers the full release workflow from dev to tagged release.
---

# Release Prep

## Overview

完整的版本发布流程：版本号同步 → 测试验证 → 文档更新 → changelog → 提交打标。

## When to Use

- "准备发布"
- "发布新版本"
- "release v0.x.x"
- 从 `-dev` 切换到正式版本时

## Inputs

- 目标版本号，格式为 `X.Y.Z`
- 发布范围或 changelog 要点
- 当前测试状态；未知时必须重新运行完整测试

## Outputs

- 同步后的版本号
- 通过的测试结果和更新后的测试统计
- changelog / release notes
- release commit 和 `vX.Y.Z` tag（用户确认需要推送时再推送）

## 发布流程

### Phase 0: 分支策略确认

发布从 `develop` 分支开始，合并到 `master`：

1. 确认当前在 `develop` 分支，所有改动已提交
2. 版本号同步（Phase 1）在 `develop` 完成
3. 测试（Phase 2）在 `develop` 完成
4. 文档更新（Phase 3）在 `develop` 完成
5. **合并到 master**（见下方合并流程）
6. 在 `develop` 继续下一个版本开发

### Phase 1: 版本号同步

1. 确定目标版本号（格式：`X.Y.Z`，不带 `-dev` 后缀）
2. 调用或参考 [version-sync](../version-sync/SKILL.md) 完成所有文件的版本号替换
3. 验证所有版本引用一致

### Phase 2: 测试验证

1. 调用或参考 [test-runner](../test-runner/SKILL.md) 运行完整测试套件：`python -m pytest tests/ -v`
2. 确认结果：
   - 通过率 100%（xfail 除外）
   - 无新增 skipped 或 xfail
   - 资产类型覆盖 ≥ 12 种
3. 如有失败，修复后重新运行（不要带着失败发布）

### Phase 3: 文档更新

1. 更新 `CLAUDE.md` 和 `README.md` 中的测试统计数字
2. 更新 `docs/release-notes/changelog.md`，新增版本条目：
   ```markdown
   ## vX.Y.Z (YYYY-MM-DD)

   ### 新增
   - ...

   ### 修复
   - ...

   ### 变更
   - ...
   ```
3. 如有重大变更，创建 `docs/release-notes/vX.Y.Z-release-notes.md`
4. 调用或参考 [doc-consistency](../doc-consistency/SKILL.md) 验证文档链接和术语

### Phase 4: 提交与打标（develop）

1. 提交所有变更：
   ```
   git add -A
   git commit -m "release: vX.Y.Z"
   ```
2. 创建 tag：`git tag vX.Y.Z`

### Phase 5: 合并到 master

master 仅保留发布内容。此流程只用于发布合并，不用于普通工作区清理。

执行选择性合并前必须满足：

1. `develop` 上 release commit 和 tag 已创建。
2. `git status --short` 为空，没有未提交改动。
3. 已列出将被排除或清理的开发目录，并获得用户明确确认。

```bash
git checkout master
git merge develop --no-commit

# 排除仅开发文件（不在 master 白名单）
git reset HEAD \
    wiki/ \
    docs/guides/ \
    docs/superpowers/ \
    docs/reports/ \
    scripts/ \
    .claude/skills/ \
    .claude/workflows/ \
    .claude/agents/

# 恢复这些目录到 master 原始状态
git checkout HEAD -- \
    wiki/ docs/guides/ docs/superpowers/ docs/reports/ scripts/ \
    .claude/skills/ .claude/workflows/ .claude/agents/ 2>/dev/null

# 清理新增的开发文件
git clean -fd \
    wiki/ docs/guides/ docs/superpowers/ docs/reports/ scripts/ \
    .claude/skills/ .claude/workflows/ .claude/agents/

# 提交合并
git commit -m "Merge develop (vX.Y.Z) into master"
```

**master 白名单**（允许进入 master 的目录）：

| 允许 | 排除（仅 develop） |
|---|---|
| `src/uasset_read/` | `wiki/` |
| `.github/workflows/` | `docs/guides/`、`docs/superpowers/`、`docs/reports/` |
| `README.md`、`README.zh-CN.md` | `scripts/` |
| `CLAUDE.md`、`LICENSE` | `.claude/skills/`、`.claude/workflows/`、`.claude/agents/` |
| `pytest.ini`、`run.py` | `temp/` |
| `.claude/rules/` | |
| `tests/`（CI 需要） | |
| `docs/formats/`、`docs/designs/`、`docs/reference/`、`docs/agents/`、`docs/release-notes/` | |

**CI 自动校验**：master 的 CI 包含目录合规检查，违反白名单将被拒绝。

### Phase 6: 推送

仅在用户明确要求推送后执行：

1. 推送 develop：`git push origin develop`
2. 推送 master：`git push origin master`
3. 推送 tag：`git push origin vX.Y.Z`

## Verification

- `rg "v?0\.[0-9]+\.[0-9]+(-dev)?"` 复查版本号残留
- `python -m pytest tests/ -v` 全量通过
- `git status --short` 只包含发布相关变更
- `git tag --list "vX.Y.Z"` 确认 tag 存在
- master 合规检查：`git ls-files | grep -E "^(wiki/|docs/guides/|docs/superpowers/|scripts/)"` 应为空
- 推送前确认用户已明确要求推送 develop/master/tag

## Boundaries

- 不带着失败测试发布
- 不自动推送到远端，除非用户明确要求
- 不在 release commit 中混入未验证的功能改动
- 不将开发文件（wiki/docs/superpowers/scripts/.claude/skills）合并到 master
- 所有开发工作在 `develop` 分支完成，不直接在 `master` 上开发

## 分支管理规则

### 日常开发

- **默认分支**：`develop`（所有开发任务基于此）
- **master 仅发布**：不包含 wiki、docs/guides、scripts 等开发文件
- **wiki 独立维护**：wiki/ 目录仅在 develop 和 wiki/master 分支

### CI 触发条件

| 分支 | CI 触发 | 说明 |
|---|---|---|
| `master` | ✅ 触发 | 运行测试 + 目录合规检查 |
| `develop` | ❌ 不触发 | 本地测试即可 |

### 提交规范

格式：`<type>: <描述>`

类型：
- `feat` — 新功能
- `fix` — Bug 修复
- `refactor` — 重构
- `test` — 测试相关
- `docs` — 文档更新
- `chore` — 杂项
- `release` — 版本发布

## 版本号规范

| 阶段 | 格式 | 示例 |
|---|---|---|
| 开发中 | `X.Y.Z-dev` | `0.4.5-dev` |
| 正式发布 | `X.Y.Z` | `0.4.5` |
| 补丁修复 | `X.Y.Z` | `0.4.5` → `0.4.6` |

## Checklist

- [ ] 版本号已同步到所有文件（develop）
- [ ] 测试 100% 通过（develop）
- [ ] 测试统计已更新到文档（develop）
- [ ] changelog 已更新（develop）
- [ ] 无未提交的临时文件（`temp/` 已清理）
- [ ] commit message 格式：`release: vX.Y.Z`
- [ ] tag 已创建
- [ ] master 合并完成（排除开发文件）
- [ ] CI 目录合规检查通过
- [ ] 用户明确要求后，develop/master/tag 已推送到 origin

## Common Mistakes

- **带着测试失败发布**：任何失败都必须先修复，不能标记为"已知问题"跳过
- **忘记更新测试统计**：新增测试后 README 中的数字可能已过时
- **遗漏 wiki/ 版本引用**：wiki 镜像文档也需同步
- **tag 名称格式错误**：使用 `vX.Y.Z`（带 v 前缀），不是 `X.Y.Z`
