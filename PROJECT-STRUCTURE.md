# 项目结构文档

**更新时间:** 2026-05-11

## 核心文件

```
uasset_read/
├── uasset_read.py           # 主解析器实现 (旧版单文件，v6.0重构中)
├── pyproject.toml           # 项目配置 (setuptools, src layout)
├── CLAUDE.md                # Claude Code 项目指导
├── PROJECT-STRUCTURE.md     # 本文件
├── SECURITY.md              # 安全审计文档
├── README.md                # 项目说明
├── .gitignore               # Git 排除配置
│
├── src/uasset_read/         # 新版模块化包 (v6.0重构目标)
│   ├── __init__.py          # 公共API导出 (常量、异常)
│   ├── archive.py           # FArchive 二进制读取器
│   ├── constants.py         # 版本号、阈值、边界常量
│   ├── exceptions.py        # 异常类定义
│   └── serializers/         # 序列化模块
│       ├── __init__.py      # 序列化模块导出
│       ├── package_summary.py  # PackageFileSummary
│       └── object_resources.py # ObjectImport/Export
│
├── tests/                   # 测试套件 (18个测试文件)
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
│   ├── test_partial_results.py       # 部分结果测试
│   ├── test_exportmap_properties.py  # ExportMap属性测试
│   ├── test_phase12_blueprint_variables.py
│   ├── test_phase13_transform.py
│   ├── test_phase14_output_formats.py
│   ├── test_phase21_verification.py
│   ├── test_phase26_blueprint_metadata_enhancement.py
│   └── test_skill_integration.py
│
├── uasset_read_cpp/         # C++移植版本 (请勿修改)
│   ├── include/
│   ├── src/
│   └── CMakeLists.txt
│
└── .planning/               # GSD工作流文件
    ├── PROJECT.md           # 项目定义
    ├── ROADMAP.md           # 路线图 (48 phases)
    ├── STATE.md             # 当前状态
    ├── REQUIREMENTS.md      # 需求映射
    ├── MILESTONES.md        # 已发布里程碑历史
    └── phases/              # 阶段执行记录
```

## 已排除目录

以下目录已从版本控制排除（见 .gitignore）:

- `UnrealEngine/` - UE 5.7 源码参考（只读）
- `LyraStarterGame/` - 示例游戏资产（只读）
- `E:\Develop\lib\UnrealEngine\` - UE 5.7完整源码（只读参考）
- `__pycache__/` - Python 缓存
- `.pytest_cache/` - pytest 缓存
- `test/` - 测试分析产物目录

## 开发阶段

项目已完成v1.0-v5.1共28个阶段，当前处于v6.0模块化重构。

| 里程碑 | 阶段 | 名称 | 状态 |
|--------|------|------|------|
| v1.0 | 1-5 | 核心解析、属性、蓝图、输出、安全 | ✓ 完成 |
| v2.0 | 6-10 | 导出表修复、蓝图图、高级属性、依赖分析 | ✓ 完成 |
| v3.x | 11-17 | 属性值提取、输出优化、skill封装、兼容修复 | ✓ 完成 |
| v4.0 | 18-22 | 节点属性深度解析、连接验证 | ✓ 完成 |
| v5.0 | 23-26 | 蓝图编译研究、元数据增强 | ✓ 完成 |
| v5.1 | 27 | 项目结构初始化 (constants.py, exceptions.py) | ✓ 完成 |
| v6.0 | 28 | 核心序列化模块 (FArchive, PackageFileSummary, ObjectResources) | ✓ 完成 |
| v6.0 | 29-32 | 数据模型、属性解析、蓝图图、输出格式化 | 待开始 |
| v6.0 | 33 | 入口与测试适配 + 删除旧文件 | 待开始 |

## API 导出

### 新版模块化包 (`src/uasset_read/`)

```python
# 公共API (通过 src/uasset_read/__init__.py)
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

### 旧版单文件 (`uasset_read.py`) — 当前主要入口

```python
from uasset_read import (
    parse_uasset,           # 主解析函数
    ParseResult,            # 解析结果容器
    PackageFileSummary,     # 文件头
    FArchive,               # 二进制读取器
    UAssetError,            # 错误基类
)
```

> **注意：** v6.0完成后，旧版 `uasset_read.py` 将被删除，所有功能迁移至 `src/uasset_read/`。

## 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# 解析.uasset文件
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"
```

## 项目状态

所有v1.0-v5.1阶段已完成。项目可解析未烘焙的UE .uasset文件，提取蓝图元数据、变量、图表结构等信息。v6.0模块化重构进行中，目标是将单文件重构为多模块Python包。
