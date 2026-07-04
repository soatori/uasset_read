# Release Readiness Skill

## Overview

系统性检查项目是否具备发布条件，覆盖版本号、测试、CI、文档、分支状态五个维度。

## 触发场景

当用户需要：
- "检查是否可以发布了"
- 发布前验证版本号、测试、CI、文档、分支五项是否就绪
- 合并 develop 到 master 前做最终确认
- 执行发布流程（merge → tag → release）

## 工作流

```
版本号检查 → 全量测试 → CI 状态 → 文档更新 → 分支合规 → 发布决策
```

### Step 1: 版本号检查

```bash
# 检查当前版本号
grep -r "__version__" src/uasset_read/__init__.py

# 检查跨文件版本一致性
grep -r "version" README.md README.zh-CN.md pyproject.toml setup.cfg 2>/dev/null
```

版本号格式：`v{major}.{minor}.{patch}.{issue_count}`（如 v0.5.1.18）

检查项：
- `__init__.py` 版本号已更新
- README 中版本号匹配
- CLAUDE.md 中版本号匹配
- wiki 中版本号匹配（如适用）

### Step 2: 全量测试

```bash
# 快速烟雾测试
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5

# 完整测试
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# 质量门禁
python -m pytest tests/ -v -m quality 2>&1 | tail -10
```

必须全部通过，不允许有失败。

### Step 3: CI 状态

```bash
# 检查最近 CI 运行
gh run list --branch master --limit 5

# 检查 PR checks
gh pr checks {latest_pr}
```

- master 分支 CI 必须绿灯
- 白名单合规检查通过（不含 scripts/、wiki/、.claude/skills/ 等）

### Step 4: 文档更新

检查项：
- [ ] README.md 版本号和功能描述已更新
- [ ] README.zh-CN.md 同步更新
- [ ] CHANGELOG / release notes 已编写
- [ ] wiki 已同步（如修改了模块结构）

### Step 5: 分支合规

```bash
# 确认 develop 分支状态
git log --oneline develop..HEAD  # 应为空（无未合并提交）

# 确认 master 只含允许的文件
git diff --name-only develop master
```

master 白名单：`src/`、`.github/workflows/`、`README.md`、`CLAUDE.md`、`pytest.ini`、`run.py`、`tests/`、`docs/formats/`、`docs/designs/`、`docs/reference/`、`docs/release-notes/`、`.claude/rules/`

排除：`wiki/`、`scripts/`、`.claude/skills/`、`.claude/workflows/`、`temp/`

### Step 6: 发布决策

输出报告：

```
=== 发布就绪检查 ===

✅ 版本号: v0.5.1.18 (一致)
✅ 测试: 142 passed, 0 failed
✅ CI: master 分支 3 次运行全部通过
✅ 文档: README.md, README.zh-CN.md 已更新
✅ 分支: develop 已合并至 master，白名单合规

结论: ✅ 可以发布
```

或标注阻塞项：

```
=== 发布就绪检查 ===

✅ 版本号: v0.5.1.18
❌ 测试: 2 failed (test_renderers.py)
✅ CI: 通过
⚠️ 文档: wiki 未同步
✅ 分支: 合规

结论: ❌ 不可发布
阻塞: test_renderers.py 2 个测试失败
建议: 修复测试后重新检查
```

## 发布执行

确认就绪后：

```bash
# 合并 develop → master
git checkout master
git merge develop --no-ff -m "release: v0.5.1.18"

# 推送
git push origin master

# 创建 tag
git tag v0.5.1.18
git push origin v0.5.1.18

# 创建 GitHub Release
gh release create v0.5.1.18 --title "v0.5.1.18" --notes "Release notes..."
```

## 注意事项

- 发布仅在用户明确要求后执行
- master 分支不含开发文件（scripts/、wiki/、.claude/skills/ 等）
- 版本号含 issue 数量便于追踪累计修复量
- CI 白名单检查由 `.github/workflows/ci.yml` 自动执行
