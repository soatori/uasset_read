# 项目结构文档

**更新时间:** 2026-05-01

## 核心文件

```
uasset_read/
├── uasset_read.py           # 主解析器实现 (2104 行, 零依赖)
├── CLAUDE.md                # Claude Code 项目指导
├── VERIFICATION-REPORT.md   # 校验报告 (临时)
├── PROJECT-STRUCTURE.md     # 本文件
├── .gitignore               # Git 排除配置
│
├── tests/                   # 测试套件
│   ├── __init__.py
│   ├── test_uasset_read.py           # 阶段 1: 核心解析 (1310 行)
│   ├── test_property_parsing.py      # 阶段 2: 属性解析 (673 行)
│   ├── test_blueprint_extraction.py  # 阶段 3: 蓝图提取 (173 行)
│   └ test_output_formatting.py       # 阶段 4: 输出格式 (脚手架)
│
└── .planning/               # GSD 规划文档
    ├── PROJECT.md           # 项目定义
    ├── ROADMAP.md           # 5阶段路线图
    ├── STATE.md             # 当前状态
    ├── REQUIREMENTS.md      # 需求映射
    ├── config.json          # GSD 配置
    │
    ├── phases/              # 阶段执行记录
    │   ├── 01-core-parsing/         # ✓ 已完成 (8 个计划)
    │   ├── 02-property-parsing/     # ✓ 已完成 (3 个计划)
    │   ├── 03-blueprint-extraction/ # ✓ 已完成 (4 个计划)
    │   ├── 04-output-and-cli/       # ○ 已规划 (4 个计划)
    │   └── 05-optimization-security/ # ○ 待定
    │
    ├── research/            # 研究产物
    └── templates/           # GSD 模板
│
└── .claude/                 # Claude Code 配置
    ├── memory/              # 记忆系统
    └── skills/              # 技能插件
```

## 已排除目录

以下目录已从版本控制排除（见 .gitignore）:

- `UnrealEngine/` - UE 5.7 源码参考（只读）
- `LyraStarterGame/` - 示例游戏资产（只读）
- `src/` - 早期废弃的多文件结构
- `__pycache__/` - Python 缓存
- `.pytest_cache/` - pytest 缓存

## 测试统计

| 阶段 | 测试文件 | 测试数 | 状态 |
|------|----------|--------|------|
| 1 | test_uasset_read.py | 28 | ✓ 通过 |
| 2 | test_property_parsing.py | 35 | ✓ 通过 |
| 3 | test_blueprint_extraction.py | 21 | ✓ 通过 |
| 4 | test_output_formatting.py | 11 | 脚手架 |
| **总计** | - | **95** | 84 passed |

## API 导出

`uasset_read.py` 导出 14 个公共 API：

```python
from uasset_read import (
    parse_uasset,           # 主解析函数
    ParseResult,            # 解析结果容器
    PackageFileSummary,     # 文件头
    ObjectImport,           # 导入条目
    ObjectExport,           # 导出条目
    PropertyValue,          # 属性值
    BlueprintMetadata,      # 蓝图元数据
    BlueprintVariable,      # 蓝图变量
    FEdGraphPinType,        # 类型信息
    PackageIndex,           # 包索引
    FArchive,               # 二进制读取器
    UAssetError,            # 错误基类
    VersionError,           # 版本错误
    ParseError,             # 解析错误
)
```

## 下一步

执行阶段 4 实现：
```
/gsd-execute-phase 4
```
