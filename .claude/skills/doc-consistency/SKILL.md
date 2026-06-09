---
name: doc-consistency
description: Use when asked to check documentation consistency, verify cross-references, audit doc structure, or after structural changes
---

# Doc Consistency

## Overview

检查项目文档一致性，修复链接失效、结构违规、引用不一致。

## When to Use

- "检查文档一致性"
- 大规模重构后验证文档未过期
- 添加/删除/移动文件后更新索引

## Inputs

- 文档目录、最近移动/新增/删除的文件，或用户指定的文档范围
- 版本发布、架构变更、测试统计更新后的文档核对需求

## Outputs

- 修复后的 Markdown 链接、目录结构、术语和交叉引用
- 未能自动判断的问题清单

## 检查项清单

### 链接验证

```bash
# 查找所有本地 markdown 链接
rg '\[[^]]+\]\([^)]+\)' -g "*.md" --no-line-number | rg -v '\]\((https?://|mailto:|#)'
```

- 相对路径目标文件是否存在
- `CLAUDE.md` / `README.md` 中的路径是否可访问

### 文档结构合规

按 [docs/ 结构约定](../../../CLAUDE.md#文档结构) 验证：

- `docs/guides/**/*.md` — 只有开发规范文件
- `docs/designs/**/*.md` — 只有永久设计规格
- `docs/reference/**/*.md` — 技术参考资料
- `docs/reports/**/*.md` — 技术报告
- `docs/release*/**/*.md` / `docs/release*/*.md` — 版本发布说明

错误放置的文件需要移到正确目录。

### 版本一致性

见 [version-sync skill](../version-sync/SKILL.md)

### 术语统一

| 术语 | 正确写法 |
|---|---|
| 蓝图/Blueprint | 中文文档用"蓝图"，代码/注释用 Blueprint |
| uasset | `.uasset`（带反引号和点号） |
| Cooked | Cooked（首字母大写） |
| IR | IR（中间表示，大写） |

## 修复流程

1. 运行检查清单，列出所有不一致项
2. 按优先级修复：链接失效 > 结构违规 > 术语不一致 > 格式问题
3. 对移动文件更新所有相对链接和索引入口
4. 提交消息：`docs: fix consistency issues`

## Verification

- 用 `rg` 复查失效路径、旧术语和旧文件名
- 对跨目录移动的文档，至少检查源目录、目标目录、`README*.md` 和 `CLAUDE.md` 中的引用

## Boundaries

- 不改写技术结论，除非能从代码、测试或 UE 源码验证
- 不把一次性调查记录移动到永久设计文档目录
- 版本号不一致时调用或参考 [version-sync](../version-sync/SKILL.md)

## Common Mistakes

- **跨目录引用路径错误**：`docs/designs/` 引用 `docs/guides/` 时用 `../guides/` 而非 `guides/`
- **锚点链接失效**：重命名标题后未更新目录内锚点引用
- **把设计文档放进 guides/**：`guides/` 只放开发规范，设计规格应放 `designs/`
