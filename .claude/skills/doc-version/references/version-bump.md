# Version Bump Skill

## Overview

自动更新项目中所有文件的版本号，确保一致性。合并了原 `version-sync` 的验证能力。

## 触发场景

- 发布新版本前更新版本号
- 修复 issue 后递增 patch 版本
- 用户要求 "bump version to X.Y.Z" / "更新版本号" / "同步版本号"
- 需要验证当前版本号是否一致

## 工作流

```
确定新版本号 → 更新 __init__.py → 同步到其他文件 → 验证一致性 → 提交
```

### Step 1: 确定新版本号

版本号格式：`v{major}.{minor}.{patch}.{issue_count}`（如 v0.5.1.186）

```bash
# 读取当前版本号
grep -r "__version__" src/uasset_read/__init__.py

# 查看当前 issue 数量（自动计算 issue_count）
gh issue list --state open --limit 1 --json number | jq '.[0].number'
```

版本号规则：
- **major**：重大架构变更（罕见）
- **minor**：新功能添加
- **patch**：bug 修复
- **issue_count**：累计修复的 issue 数量（如 #186 → 版本号末尾为 186）

### Step 2: 更新 __init__.py

```python
# src/uasset_read/__init__.py
__version__ = "0.5.1.186"  # 无 v 前缀
```

### Step 3: 同步到其他文件

需要更新的文件：

| 文件 | 更新位置 | 格式 |
|------|----------|------|
| `__init__.py` | `src/uasset_read/__init__.py` | `"0.5.1.186"`（无 v 前缀） |
| `README.md` | 顶部 badges、功能描述 | `v0.5.1.186` |
| `README.zh-CN.md` | 顶部 badges、功能描述 | `v0.5.1.186` |
| `CLAUDE.md` | 项目概述 | `版本 0.5.1.186` |
| `wiki/01-Overview/Overview.md` | 版本信息 | `v0.5.1.186` |
| `docs/release-notes/changelog.md` | 新增条目 | 版本号 + 变更说明 |

更新命令模板：

```bash
# Windows PowerShell（本项目主要开发环境）
(Get-Content README.md) -replace 'v0\.5\.1\.18', 'v0.5.1.186' | Set-Content README.md

# Linux/Mac
sed -i "s/v0\.5\.1\.18/v0.5.1.186/g" README.md README.zh-CN.md CLAUDE.md
```

### Step 4: 验证一致性

使用 Python 脚本一次性验证所有文件：

```python
import re

files = ['src/uasset_read/__init__.py', 'README.md', 'README.zh-CN.md', 'CLAUDE.md']
versions = set()
for f in files:
    with open(f) as fh:
        content = fh.read()
        matches = re.findall(r'v?\d+\.\d+\.\d+\.\d+', content)
        versions.update(matches)
if len(versions) == 1:
    print(f'✅ 版本一致: {versions.pop()}')
else:
    print(f'❌ 版本不一致: {versions}')
```

或使用 grep 检查旧版本号是否残留：

```bash
grep -r "0\.5\.1\.18" --include="*.md" --include="*.py" . | grep -v ".git" | grep -v "temp/"
# 应返回空（旧版本号已全部替换）
```

### Step 5: 提交

```bash
git add src/uasset_read/__init__.py README.md README.zh-CN.md CLAUDE.md
git commit -m "chore: bump version to v0.5.1.186"
```

## 注意事项

- **版本号不含 v 前缀**：`__init__.py` 中为 `"0.5.1.186"`，其他文件中为 `v0.5.1.186`
- **issue_count 自动计算**：从 GitHub issue 数量自动获取，无需手动输入
- **wiki 独立仓库**：wiki/ 的版本更新需要在 wiki/master 分支单独提交
- **changelog 更新**：更新版本号时应同步更新 `docs/release-notes/changelog.md`
- **项目无 pyproject.toml**：版本号仅在 `__init__.py` 中定义

## 版本号变更示例

```
v0.5.1.185 → v0.5.1.186  (修复 #186)
v0.5.1.186 → v0.5.2.190   (添加新功能，修复到 #190)
v0.5.2.190 → v0.6.0.195   (重大重构)
```
