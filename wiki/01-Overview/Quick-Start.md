---
title: 快速开始
section: quick-start
---

# 快速开始

## 安装

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

零运行时依赖，Python 3.10+。

## 直接调用

```bash
python run.py file.uasset                  # JSON 输出到 stdout
python run.py file.uasset --markdown       # Markdown + Mermaid
python run.py file.uasset --output out.json  # 保存到文件
python run.py file.uasset --verbose        # 调试日志
python run.py file.uasset --full-parse     # 完整解析（含蓝图反编译）
python run.py file.uasset --hex-view       # 十六进制视图调试
python run.py --batch-dir path/to/dir/     # 批量模式
python run.py file.uasset --strict         # 严格模式（默认容错）
python run.py --list-formats               # 列出所有可用格式
```

所有参数同样适用于 `python -m uasset_read`。

## Python API

### 推荐 API

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
print(list_formats())  # ['json', 'markdown']
```

### 底层 API

```python
from uasset_read import parse_uasset
result = parse_uasset("path/to/MyBlueprint.uasset")
print(result.exports)      # 导出列表
print(result.blueprint)    # 蓝图数据
print(result.graphs)       # 图结构
```

## PAK 解析

```python
from uasset_read import parse_package
from uasset_read.pak import PakFileReader
reader = PakFileReader("game.pak")
result = parse_package("Game/Content/MyAsset.uasset", provider=reader)
```