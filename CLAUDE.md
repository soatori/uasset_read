# CLAUDE.md

本文件为Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 语言设置

**请使用中文进行所有回复和编写文件。**

## 项目概述

解析Unreal Engine .uasset文件的Python工具，使AI代理能够在不依赖UE编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

## 当前状态

**Phase 1 (核心解析): 完成** — 解析器读取头部、名称表、导入/导出映射。所有测试通过。

后续阶段 (2-5) 已在 `.planning/ROADMAP.md` 中规划。

## UE 5.7 源码参考

UE 5.7源码位于 `E:\Develop\lib\UnrealEngine` (只读参考)。

.uasset解析的关键文件：
- `PackageFileSummary.h` — 文件头部结构
- `ObjectResource.h` — 导入/导出结构
- `Archive.h` — FArchive模式

## 外部目录 (Git排除)

- `UnrealEngine/` — UE引擎源码参考 (请勿修改)
- `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` `E:\Develop\lib\UnrealEngine\Samples\FirstPersonC` - 示例蓝图/C++测试对照(请勿修改)
- `LyraStarterGame/` — 示例游戏资产 (请勿修改)
- `D:\Program Files\Epic Games\Engine\UE_5.7` — UE 5.7引擎路径 (本地参考请勿修改)
- `D:\Program Files\Epic Games\Engine\UE_4.27` — UE 4.27引擎路径 (本地参考请勿修改)

## 技术栈

- **语言**: Python 3.10+ (支持match/case，更好的类型提示)
- **依赖**: 零运行时依赖 — 仅使用标准库
- **解析**: `struct`用于二进制，`mmap`用于大文件 (计划中)
- **模型**: `dataclasses`配合 `asdict()` → JSON
- **CLI**: `argparse`
- **编码**: 仅UTF-8 (UE 5.x标准)

## 架构

采用镜像UE的FArchive管道模式：

```
.uasset → FArchive (读取器) → 反序列化器 → 数据类 → 输出 (JSON/文本)
```

`uasset_read.py`中的核心组件：
- `FArchive`: 二进制读取器，支持字节交换、边界验证
- `PackageFileSummary`: 包含NameTable/ImportMap/ExportMap偏移量的头部
- `FPackageIndex`: 有符号整数编码 (>0 导出, <0 导入, 0 空)
- `FName`: NameMap索引 + 实例编号
- `ParseResult`: 错误时包含部分结果的容器

## 文件组织

- 源码: `uasset_read.py` (Phase 1单文件)
- 测试: `tests/` 目录
- 文档: `docs/` 或 `.planning/`
- 规划: `.planning/` (GSD工作流文件)

## 命令

```bash
# 解析.uasset文件
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试
python -m pytest tests/test_uasset_read.py::test_package_summary_valid -v
```