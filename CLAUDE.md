# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言设置

请使用中文进行所有回复和编写文件。

## 项目概述

解析 Unreal Engine .uasset 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

## 当前状态

**v2.0 (蓝图图解析): 已完成** — 10个阶段全部完成。
**v6.0 (模块化重构): 进行中** — Phase 27/28已完成（archive.py、constants.py、exceptions.py、serializers/），Phase 29数据模型模块待开始。

仓库存在两套代码：
- `uasset_read.py` — 旧版单文件（~5000行），当前 CLI 入口，包含完整解析管线
- `src/uasset_read/` — 新版模块化包（v6.0重构中），目前仅包含序列化基础模块

## 常用命令

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 解析 .uasset 文件（使用旧版入口）
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# 运行测试（简要输出）
python -m pytest tests/ --tb=short

# 查看特定解析结果
python -c "
from uasset_read import parse_uasset
import json
r = parse_uasset('BP_FirstPersonCharacter.uasset')
print(json.dumps(r.to_dict(), indent=2))
"
```

测试资产位于 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ 扩展组件
          GraphParser (Phase 7)
          AdvancedPropParser (Phase 9)
          DependencyGraphBuilder (Phase 10)
```

### 新版模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap、边界验证 |
| 常量 | `constants.py` | 版本号、属性类型阈值、MMAP_THRESHOLD |
| 异常 | `exceptions.py` | UAssetError、VersionError、ParseError、ErrorContext |
| 序列化 | `serializers/` | PackageFileSummary、ObjectImport/Export、PackageIndex |

待迁移模块（Phase 29-32）：models、properties、graph、formatters。

### 旧版单文件 (`uasset_read.py`)

完整解析管线，包含所有组件（ParseResult、UEdGraph/Node/Pin、PropertyParser、OutputFormatter、CLI入口等）。Phase 33完成后将被删除。

## 技术栈

- **语言**: Python 3.10+（match/case，类型提示）
- **依赖**: 零运行时依赖 — 仅使用标准库（struct、mmap、dataclasses、json、argparse）
- **构建**: setuptools（src layout），pyproject.toml 配置
- **测试**: pytest（可选 dev 依赖）

## 文件组织

```
uasset_read.py              # 旧版单文件主入口（待删除）
src/uasset_read/            # 新版模块化包（v6.0重构中）
tests/                      # 测试目录（18个测试文件）
uasset_read_cpp/            # C++移植参考（请勿修改）
.planning/                  # GSD工作流文件（路线图、状态、需求）
```

外部目录（Git排除）：
- `UnrealEngine/` — UE引擎源码参考
- `LyraStarterGame/` — 示例游戏资产
- `E:\Develop\lib\UnrealEngine\` — UE 5.7完整源码（只读参考）

## API 导出

当前公共API（通过 `src/uasset_read/__init__.py`）：

```python
from uasset_read import (
    # 常量
    PACKAGE_FILE_TAG, MMAP_THRESHOLD, PROPERTY_TAG_COMPLETE_TYPE_NAME, ...
    # 异常
    UAssetError, VersionError, ParseError, ErrorContext,
)

# 序列化模块
from uasset_read.serializers import (
    PackageFileSummary, PackageIndex, ObjectImport, ObjectExport,
    read_package_summary, read_name_table,
    read_import_map, read_export_map, detect_blueprint, ...
)

# FArchive（基础读取器）
from uasset_read.archive import FArchive
```

完整解析入口仍在旧版 `uasset_read.py`：

```python
from uasset_read import parse_uasset, ParseResult
```

## 规划文档

- `.planning/ROADMAP.md` — 版本路线图（48 phases）
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯表
- `.planning/PROJECT.md` — 项目概览
- `.planning/MILESTONES.md` — 已发布里程碑历史