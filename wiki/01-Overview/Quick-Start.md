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

```python
from uasset_read import parse_uasset
result = parse_uasset("path/to/MyBlueprint.uasset")
print(result.exports)      # 导出列表
print(result.blueprint)    # 蓝图数据
print(result.graphs)       # 图结构
```

## CLI 命令

```bash
uasset-read file.uasset                  # JSON 输出（默认）
uasset-read file.uasset --text           # 人类可读文本
uasset-read file.uasset --markdown       # Markdown + Mermaid
uasset-read file.uasset --blueprint-text # 蓝图节点文本
uasset-read file.uasset --cpp-skeleton   # C++ 类骨架
uasset-read file.uasset --n2c            # N2C 中间格式
uasset-read file.uasset --strict         # 遇到警告停止
```

## PAK 解析

```python
from uasset_read import parse_package, PakFileReader
reader = PakFileReader("game.pak")
result = parse_package("Game/Content/MyAsset.uasset", provider=reader)
```
