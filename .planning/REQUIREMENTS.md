# Requirements - v5.1 模块化重构与C++代码生成准备

**里程碑:** v5.1
**目标:** 模块化重构 + JSON Schema定义
**创建日期:** 2026-05-06

---

## Active Requirements

### MOD - 模块化重构

- [ ] **MOD-01**: 拆分FArchive二进制读取器到独立模块
  - 文件: `src/uasset_read/archive.py`
  - 包含: FArchive类及其所有方法（read_i32, seek, tell等）
  - 零依赖: 仅使用Python标准库（struct, mmap）

- [ ] **MOD-02**: 定义常量和阈值到独立模块
  - 文件: `src/uasset_read/constants.py`
  - 包含: 版本号常量、属性类型阈值、边界常量
  - 示例: PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012

- [ ] **MOD-03**: 定义异常类到独立模块
  - 文件: `src/uasset_read/exceptions.py`
  - 包含: UAssetError, VersionError, ParseError, ErrorContext

- [ ] **MOD-04**: 拆分PackageFileSummary序列化到独立模块
  - 文件: `src/uasset_read/serializers/package_summary.py`
  - 包含: PackageFileSummary, GenerationInfo, EngineVersion, CustomVersion
  - 依赖: MOD-01, MOD-02

- [ ] **MOD-05**: 拆分ImportMap/ExportMap到独立模块
  - 文件: `src/uasset_read/serializers/object_resources.py`
  - 包含: ObjectImport, ObjectExport, PackageIndex, resolve_*
  - 依赖: MOD-01, MOD-02

- [ ] **MOD-06**: 拆分PropertyTag到独立模块
  - 文件: `src/uasset_read/serializers/property_tags.py`
  - 包含: PropertyTag, parse_property_tag
  - 依赖: MOD-01

- [ ] **MOD-07**: 拆分属性解析器到独立模块
  - 文件: `src/uasset_read/parsers/property_parser.py`
  - 包含: parse_property, parse_*_property函数
  - 依赖: MOD-01, MOD-06

- [ ] **MOD-08**: 定义核心数据模型
  - 文件: `src/uasset_read/models/core.py`
  - 包含: ParseResult, StatusInfo
  - 使用dataclass，零依赖

- [ ] **MOD-09**: 避免循环导入
  - 使用分层架构：Output → Models → Parsers → Serializers → FArchive
  - 使用延迟导入、TYPE_CHECKING、字符串类型注解
  - 所有模块依赖单向

### SCHEMA - JSON Schema定义

- [ ] **SCHEMA-01**: 定义JSON Schema结构
  - 文件: `src/uasset_read/schemas/json_schema.py` 或 `schemas/json_schema.json`
  - 目的: 为C++代码生成准备规范化输出结构
  - 包含: ParseResult顶层结构、蓝图图结构、节点类型定义

- [ ] **SCHEMA-02**: Schema验证功能
  - 文件: `src/uasset_read/schemas/validator.py`
  - 功能: 验证输出JSON符合Schema定义
  - 使用: Python标准库json模块（零依赖）

- [ ] **SCHEMA-03**: Schema文档
  - 文件: `docs/JSON_SCHEMA.md` 或 `.planning/research/JSON_SCHEMA.md`
  - 内容: Schema结构说明、字段语义、C++映射关系

### TEST - 测试兼容性

- [ ] **TEST-01**: 所有现有测试通过
  - 运行: `pytest tests/`
  - 要求: 359+ 测试用例通过
  - 验证: 功能性零变更

- [ ] **TEST-02**: 新模块单元测试
  - 为每个新模块创建测试文件
  - 测试模块独立功能
  - 验证: 模块接口正确

### STRUCT - 项目结构

- [ ] **STRUCT-01**: 创建src目录结构
  - 目录: `src/uasset_read/`
  - 包含: `__init__.py` 导出公共API
  - 符合: Python Packaging User Guide src layout

- [ ] **STRUCT-02**: 配置pyproject.toml
  - 文件: `pyproject.toml`
  - 配置: dependencies = [], src layout, 项目元数据
  - 验证: 零依赖安装

---

## Future Requirements

以下需求延后至v5.2或后续里程碑：

- **MOD-10**: 输出模块拆分（JSON/文本格式化器）
- **MOD-11**: CLI模块拆分（命令行接口）
- **MOD-12**: 蓝图模块拆分（Graph/Node/Pin组件）
- **SCHEMA-04**: C++代码生成器实现
- **SCHEMA-05**: TypeScript类型定义生成

---

## Out of Scope

| 需求 | 原因 |
|------|------|
| 向后兼容层 | 用户选择"不考虑兼容"，不保留旧入口 |
| 保留根级别uasset_read.py | 采用新结构，完全模块化 |
| 测试框架迁移 | pytest可直接运行unittest测试 |
| MCP Server封装 | 超出v5.1范围，延后 |
| C++代码生成 | v5.1仅准备JSON Schema，实际生成延后 |

---

## Requirements Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| MOD-01~09 | Phase 27 | Pending |
| SCHEMA-01~03 | Phase 28 | Pending |
| TEST-01~02 | Phase 29 | Pending |
| STRUCT-01~02 | Phase 27 | Pending |

*待路线图创建后更新Phase映射*

---

## Requirements Rationale

### 为什么先实现基础设施和核心模块？

1. **依赖关系**: FArchive和常量/异常是所有其他模块的基础
2. **风险最小**: 基础模块变更影响可控，测试验证简单
3. **渐进式**: 先核心后扩展，降低重构复杂度

### 为什么不考虑向后兼容？

用户明确选择新结构，不保留旧入口。这意味着：
- 导入路径将从 `from uasset_read import *` 变为 `from src.uasset_read import *`
- CLI入口将从 `python uasset_read.py` 变为 `python -m src.uasset_read.cli`
- 完全拥抱新架构，不做技术妥协

### 为什么同时做JSON Schema？

1. **C++代码生成准备**: v5.1目标是为蓝图转C++自动化做准备
2. **模块化并行**: Schema定义不依赖完整模块化
3. **规范化输出**: 确保JSON输出结构稳定，为后续阶段打下基础

---

*最后更新: 2026-05-06*