# Doc Consistency

## Overview

自动检查项目文档间的一致性问题：版本号、功能描述、模块名称、渲染器数量、CLI 标志等在多个文件间是否同步。

## 触发场景

- 发布前文档同步检查
- 大规模重构后文档更新验证
- "检查文档是否过时"

## 工作流

```
提取关键字段 → 跨文件对照 → 标记不一致 → 生成修复清单
```

### Step 1: 提取关键字段

从源码提取真实值：

```bash
# 版本号
grep -r "__version__" src/uasset_read/__init__.py

# 渲染器数量
grep -c "register_renderer" src/uasset_read/renderers/*.py

# CLI 标志
python run.py --help 2>&1 | grep "^\s*--"

# 已删除的模块
find src/uasset_read -name "*.py" -path "*/formatters/*"  # 应为空
```

### Step 2: 跨文件对照

检查以下文件中的一致性：

| 检查项 | 文件 A | 文件 B | 文件 C |
|--------|--------|--------|--------|
| 版本号 | `__init__.py` | `README.md` | `CLAUDE.md` |
| 渲染器数量 | `renderers/` | `README.md` | `wiki/` |
| CLI 标志 | `cli.py` | `README.md` | `wiki/` |
| 模块列表 | `src/` | `CLAUDE.md` | `wiki/` |
| 测试命令 | `pytest.ini` | `CLAUDE.md` | `README.md` |

### Step 3: 检查清单

```markdown
## 一致性检查结果

### ✅ 一致
- 版本号: v0.5.1.18 (所有文件)
- 渲染器数量: 2 (所有文件)

### ❌ 不一致
- CLI 标志: README 提到 --text 但已移除
- 模块列表: CLAUDE.md 提到 formatters/ 但已删除
- 测试命令: README 引用 scripts/test_matrix.py 但不存在

### ⚠️ 过时
- wiki/ 渲染器数量: 6 (应为 2)
```

### Step 4: 修复建议

对每个不一致项提供具体修复方向：
- 需要删除的引用
- 需要更新的数字
- 需要同步的文件对

## 常见不一致来源

| 来源 | 表现 |
|------|------|
| 模块删除后 | 文档仍引用已删除模块 |
| CLI 重构后 | README 保留旧标志文档 |
| 渲染器合并后 | wiki 保留旧数量 |
| 版本发布后 | 部分文件忘记更新版本号 |

## 注意事项

- 仅检查，不直接修改文件
- 输出修复建议供用户确认
- 重点关注 CLAUDE.md、README.md、wiki/ 三者同步

## 相关子文档

- [doc-sync.md](doc-sync.md) — 双语文档同步（修复工具，本子文档是诊断工具）
- [version-bump.md](version-bump.md) — 跨文件版本号更新
- [release-readiness.md](release-readiness.md) — 发布前检查
