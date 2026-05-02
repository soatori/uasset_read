# 项目结构文档

**更新时间:** 2026-05-02

## 核心文件

```
uasset_read/
├── uasset_read.py           # 主解析器实现 (4901 行, 零依赖)
├── CLAUDE.md                # Claude Code 项目指导
├── PROJECT-STRUCTURE.md     # 本文件
├── SECURITY.md              # 安全文档
├── .gitignore               # Git 排除配置
│
├── tests/                   # 测试套件 (11 个测试文件)
│   ├── __init__.py
│   ├── test_uasset_read.py           # 核心解析测试
│   ├── test_property_parsing.py      # 属性解析测试
│   ├── test_blueprint_extraction.py  # 蓝图提取测试
│   ├── test_output_formatting.py     # 输出格式测试
│   ├── test_graph_parsing.py         # 图解析测试
│   ├── test_advanced_properties.py   # 高级属性测试
│   ├── test_dependency_analysis.py   # 依赖分析测试
│   ├── test_mmap_behavior.py         # mmap行为测试
│   ├── test_boundary_validation.py   # 边界验证测试
│   ├── test_loop_limits.py           # 循环限制测试
│   └ test_partial_results.py        # 部分结果测试
│
├── test/                    # 测试资产分析产物
│
├── uasset_read_cpp/         # C++移植版本
│   ├── include/
│   ├── src/
│   ├── tests/
│   └ CMakeLists.txt
│
└── .planning/               # GSD规划文档
    ├── PROJECT.md           # 项目定义
    ├── ROADMAP.md           # 路线图
    ├── STATE.md             # 当前状态
    ├── REQUIREMENTS.md      # 需求映射
    ├── VERIFICATION-REPORT.md # 校验报告
    ├── config.json          # GSD配置
    │
    ├── phases/              # 阶段执行记录 (10个阶段)
    │   ├── 01-core-architecture/     # ✓ 已完成
    │   ├── 01-core-parsing/          # ✓ 已完成
    │   ├── 02-property-parsing/      # ✓ 已完成
    │   ├── 03-blueprint-extraction/  # ✓ 已完成
    │   ├── 04-output-and-cli/        # ✓ 已完成
    │   ├── 05-optimization-security/ # ✓ 已完成
    │   ├── 06-export-table-fix/      # ✓ 已完成
    │   ├── 07-blueprint-graph-core/  # ✓ 已完成
    │   ├── 08-blueprint-graph-output/# ✓ 已完成
    │   ├── 09-advanced-properties/   # ✓ 已完成
    │   └── 10-dependency-analysis/   # ✓ 已完成
    │
    └ research/              # 研究产物
    │
    └── .claude/             # Claude Code配置
        ├── memory/          # 记忆系统
        └── skills/          # 技能插件
            ├── lyra-course/
            ├── uasset-format/
            └── uecpp-course/
```

## 已排除目录

以下目录已从版本控制排除（见 .gitignore）:

- `UnrealEngine/` - UE 5.7 源码参考（只读）
- `LyraStarterGame/` - 示例游戏资产（只读）
- `src/` - 早期废弃的多文件结构
- `__pycache__/` - Python 缓存
- `.pytest_cache/` - pytest 缓存
- `test/` - 测试分析产物目录

## 开发阶段

项目已完成10个阶段：

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| 01 | 核心架构 + 核心解析 | ✓ 完成 | 文件头、名称表、导入/导出映射 |
| 02 | 属性解析 | ✓ 完成 | UObject属性反序列化 |
| 03 | 蓝图提取 | ✓ 完成 | 蓝图元数据、变量、图表 |
| 04 | 输出和CLI | ✓ 完成 | JSON输出、命令行接口 |
| 05 | 优化和安全 | ✓ 完成 | 性能优化、边界验证 |
| 06 | 导出表修复 | ✓ 完成 | UE5条件字段修复 |
| 07 | 蓝图图核心 | ✓ 完成 | 图结构解析 |
| 08 | 蓝图图输出 | ✓ 完成 | 图输出格式化 |
| 09 | 高级属性 | ✓ 完成 | 复杂属性类型 |
| 10 | 依赖分析 | ✓ 完成 | 资产依赖关系 |

## API 导出

`uasset_read.py` 导出多个公共 API：

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

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_uasset_read.py -v

# 解析.uasset文件
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"
```

## 项目状态

所有规划阶段已完成。项目可解析未烘焙的UE .uasset文件，提取蓝图元数据、变量、图表结构等信息。