# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

Python 工具，用于读取 Unreal Engine .uasset 文件，让 AI agent 能直接解析蓝图内容，无需依赖 UE 编辑器。重点关注未烘焙/编辑器保存的资产（包含完整蓝图数据）。

## UE 5.7 源码参考路径

UE 5.7 源码作为格式参考（只读，不可修改）：
```
D:\Program Files\Epic Games\Engine\UE_5.7
```

.uasset 解析关键文件：
- `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` — 文件头结构
- `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` — Import/Export 结构
- `Engine/Source/Runtime/CoreUObject/Public/Serialization/Archive.h` — FArchive 模式

## 外部引用目录（已排除）

以下目录为外部 UE 内容的副本/符号链接，已从 git 排除：
- `UnrealEngine/` — UE 引擎源码参考
- `LyraStarterGame/` — 示例游戏资产

不要修改这些目录，仅供参考使用。

## 技术栈

- **语言**: Python 3.10+（支持 match/case，类型提示更完善）
- **依赖**: 零运行时依赖 — 仅使用标准库
- **解析**: `struct` 处理二进制，`mmap` 处理大文件
- **模型**: `dataclasses`，通过 `asdict()` 转 JSON
- **CLI**: `argparse`
- **编码**: 仅 UTF-8（UE 5.x 标准）

## 架构模式

分层流水线，模仿 UE 的 FArchive：
```
.uasset → FArchive (读取器) → 反序列化器 → 模型 (dataclasses) → 输出 (JSON/文本)
```

核心组件：
- `FArchive`: 基类，包含 read_u8/u32/u64/f32/fstring 方法
- `PackageFileSummary`: 文件头，包含 NameTable/ImportMap/ExportMap 偏移量
- `FPackageIndex`: 有符号整数编码（>0 导出，<0 导入，0 为空）
- `FName`: NameMap 索引 + 实例编号

## 文件放置规则

- 文档: `docs/` 或 `.planning/`
- 源码: 根目录或 `src/`（Phase 1 使用单文件，后续可模块化）
- 测试: `tests/`

## 文档语言规范

- 简洁清晰
- 中英混合时优先使用中文说明
- 引用 UE 源码路径时使用相对格式

## 当前项目状态

详见 `.planning/STATE.md`。

**Phase 1（核心解析）** 待执行。运行 `/gsd-plan-phase 1` 创建详细计划。

## 常用命令

暂无构建系统。源码创建后：
```bash
python uasset_read.py file.uasset --json      # 输出 JSON
python uasset_read.py file.uasset --text      # 输出可读文本
python -m pytest tests/                       # 运行测试
```