# CLAUDE.md

本文件为Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 语言设置

**请使用中文进行所有回复和编写文件。**

## 项目概述

解析Unreal Engine .uasset文件的Python工具，使AI代理能够在不依赖UE编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

## 当前状态

**v2.0 (蓝图图解析): 完成** — 10个阶段全部完成，支持蓝图图解析、高级属性、依赖分析。

### 已完成功能

| 阶段 | 功能 | 状态 |
|------|------|------|
| 1-5 | v1.0核心 | ✓ 完成 |
| 6 | 导出表修复 | ✓ 完成 |
| 7 | 蓝图图核心解析 | ✓ 完成 |
| 8 | 蓝图图输出增强 | ✓ 完成 |
| 9 | 高级属性类型 | ✓ 完成 |
| 10 | 依赖分析 | ✓ 完成 |

### 解析能力

- ✓ PackageFileSummary (文件头)
- ✓ NameMap (名称表)
- ✓ ImportMap (依赖映射)
- ✓ ExportMap (导出映射)
- ✓ Blueprint检测
- ✓ UEdGraph/Node/Pin解析
- ✓ 高级属性 (Struct/Map/Set/Enum/Text/Delegate)
- ✓ 依赖图构建
- ✓ 循环依赖检测

## UE 5.7 源码参考

UE 5.7源码位于 `E:\Develop\lib\UnrealEngine` (只读参考)。

.uasset解析的关键文件：
- `PackageFileSummary.h` — 文件头部结构
- `ObjectResource.h` — 导入/导出结构
- `Archive.h` — FArchive模式

## 外部目录 (Git排除)

- `UnrealEngine/` — UE引擎源码参考 (请勿修改)
- `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` — 示例蓝图测试资产
- `E:\Develop\lib\UnrealEngine\Samples\FirstPersonC` — C++对照文件
- `LyraStarterGame/` — 示例游戏资产 (请勿修改)

## 技术栈

- **语言**: Python 3.10+ (支持match/case，更好的类型提示)
- **依赖**: 零运行时依赖 — 仅使用标准库
- **解析**: `struct`用于二进制，`mmap`用于大文件
- **模型**: `dataclasses`配合 `asdict()` → JSON
- **CLI**: `argparse`
- **编码**: UTF-8 (UE 5.x标准)

## 架构

采用镜像UE的FArchive管道模式：

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ 扩展组件
          GraphParser (Phase 7)
          AdvancedPropParser (Phase 9)
          DependencyGraphBuilder (Phase 10)
```

`uasset_read.py`核心组件：
- `FArchive`: 二进制读取器，支持字节交换、边界验证
- `PackageFileSummary`: 文件头，包含各表偏移量
- `ParseResult`: 解析结果容器，包含所有提取数据
- `UEdGraph/UEdGraphNode/UEdGraphPin`: 蓝图图结构

## 文件组织

- 源码: `uasset_read.py` (单文件，4901行)
- 测试: `tests/` 目录 (11测试文件，216测试用例)
- C++移植: `uasset_read_cpp/` 目录
- 规划: `.planning/` (GSD工作流文件)
- 测试输出: `test/` (已在.gitignore中)

## 命令

```bash
# 解析.uasset文件
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"

# 运行所有测试
python -m pytest tests/ -v

# 运行测试（简要）
python -m pytest tests/ --tb=short

# 查看解析数据
python -c "
from uasset_read import parse_uasset
import json
r = parse_uasset('BP_FirstPersonCharacter.uasset')
print(json.dumps(r.name_map[:50], indent=2))
"
```

## API导出

```python
from uasset_read import (
    parse_uasset,           # 主解析函数
    ParseResult,            # 解析结果容器
    PackageFileSummary,     # 文件头
    FArchive,               # 二进制读取器
    UAssetError,            # 错误基类
)
```

## 规划文档

- `.planning/ROADMAP.md` — 版本路线图
- `.planning/STATE.md` — 当前状态
- `.planning/REQUIREMENTS.md` — 需求映射
- `.planning/v3_DRAFT.md` — v3.0草案（蓝图转C++自动化）