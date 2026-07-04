# Doc Sync Skill

## Overview

自动同步 README.md（英文）和 README.zh-CN.md（中文）的内容，确保两个文件的结构、版本号、功能描述、CLI 标志等保持一致。

## 触发场景

- 修改 README.md 后需要同步到中文版
- 修改 README.zh-CN.md 后需要同步到英文版
- 发布前确保双语文档一致
- 大规模重构后批量更新文档

## 工作流

```
读取双语文件 → 检测差异 → 确定主版本 → 双向同步 → 验证一致性
```

### Step 1: 读取双语文件

```bash
# 读取两个文件
cat README.md
cat README.zh-CN.md
```

### Step 2: 检测差异

检查以下关键字段的一致性：

| 检查项 | 英文文件 | 中文文件 |
|--------|----------|----------|
| 版本号 | `v0.5.1.18` | `v0.5.1.18` |
| 渲染器数量 | `2 renderers` | `2 个渲染器` |
| CLI 标志 | `--json`, `--markdown` | `--json`, `--markdown` |
| 模块列表 | `archive.py`, `linker.py` 等 | 同左 |
| 测试命令 | `python -m pytest tests/` | 同左 |
| 样本路径 | `E:\Develop\lib\Samples` | 同左 |

### Step 3: 确定主版本

- 如果用户明确指定方向（如 "sync README to Chinese"），以指定方向为准
- 如果无明确方向，以**最后修改的文件**为主版本
- 版本号以 `src/uasset_read/__init__.py` 中的 `__version__` 为准

### Step 4: 双向同步

#### 英文 → 中文同步规则：

| 英文内容 | 中文对应 |
|----------|----------|
| `# uasset_read` | `# uasset_read` |
| `## Overview` | `## 概述` |
| `## Installation` | `## 安装` |
| `## Usage` | `## 使用方法` |
| `## CLI Options` | `## CLI 选项` |
| `## Architecture` | `## 架构` |
| `## Testing` | `## 测试` |
| `## Contributing` | `## 贡献指南` |
| `## License` | `## 许可证` |

#### 保持不变的内容（不翻译）：
- 代码块（```bash ... ```）
- 文件路径
- 命令行标志
- 模块名称
- 版本号格式

### Step 5: 验证一致性

```bash
# 提取版本号验证
grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+" README.md
grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+" README.zh-CN.md

# 提取 CLI 标志验证
grep -o "\-\-[a-z-]\+" README.md | sort -u
grep -o "\-\-[a-z-]\+" README.zh-CN.md | sort -u
```

## 注意事项

- **代码块不翻译**：所有 ``` 包裹的内容保持原样
- **路径不翻译**：Windows/Linux 路径保持原样
- **版本号以源码为准**：`src/uasset_read/__init__.py` 是版本号的唯一真相源
- **结构对齐**：两个文件的章节顺序应保持一致
- **增量更新**：只同步有差异的部分，避免覆盖用户的手动调整

## 常见同步场景

| 场景 | 操作 |
|------|------|
| 新增 CLI 标志 | 两个文件都添加，中文版翻译说明 |
| 删除模块 | 两个文件都删除引用 |
| 更新版本号 | 两个文件都更新，以 `__init__.py` 为准 |
| 重命名函数 | 两个文件都更新函数名 |
| 新增架构图 | 英文版添加 Mermaid 图，中文版同步 |
