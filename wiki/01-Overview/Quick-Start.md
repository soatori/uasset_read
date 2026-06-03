---
title: 快速开始
section: quick-start
---

# 快速开始

## 安装

```bash
pip install uasset-read                   # 基础安装
pip install -e ".[dev]"                   # 开发环境
pip install -e ".[pak]"                   # PAK 支持
```

## Python API

### 新 API（0.4.1+ 推荐）

```python
from uasset_read import parse_single, parse_batch

# 解析单个文件
output = parse_single("path/to/MyBlueprint.uasset", format="json")
print(output)  # JSON 字符串

# 批量解析
result = parse_batch("path/to/assets/", format="json")
print(f"成功: {len(result.success)}, 失败: {len(result.failed)}")

# 查看可用格式
from uasset_read import list_formats
print(list_formats())  # ['json', 'json_summary', 'text', 'text_summary', 'markdown', 'blueprint_text', 'blueprint_ue_text', 'cpp_skeleton']
```

### 旧 API（向后兼容）

```python
from uasset_read import parse_uasset
result = parse_uasset("path/to/MyBlueprint.uasset")
print(result.exports)      # 导出列表
print(result.blueprint)    # 蓝图数据
print(result.graphs)       # 图结构
```

## CLI 命令

```bash
uasset-read file.uasset                  # YAML 风格文本（默认）
uasset-read file.uasset --json           # JSON 输出
uasset-read file.uasset --json-summary   # JSON 摘要
uasset-read file.uasset --text           # YAML 风格全文
uasset-read file.uasset --markdown       # Markdown + Mermaid
uasset-read file.uasset --blueprint-text # 蓝图节点翻译文本
uasset-read file.uasset --blueprint-ue-text  # UE 风格蓝图文本
uasset-read file.uasset --cpp-skeleton   # C++ 类骨架
uasset-read file.uasset --list-formats   # 列出所有可用格式
uasset-read file.uasset --batch          # 批量模式
```

> [!WARNING]
> **已移除标志**：`--n2c`（N2C 模块已移除）

## PAK 解析

```python
from uasset_read import parse_package, PakFileReader
reader = PakFileReader("game.pak")
result = parse_package("Game/Content/MyAsset.uasset", provider=reader)
```
