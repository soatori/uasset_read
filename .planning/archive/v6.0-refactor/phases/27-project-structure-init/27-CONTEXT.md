# Phase 27: 项目结构初始化 - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

## Phase Boundary

创建项目基础设施（目录结构、配置文件、基础常量和异常模块），为后续模块化重构工作打下基础。

## Implementation Decisions

### 项目结构

- **D-01 (向后兼容):** 不考虑向后兼容 — 用户明确选择，直接采用新结构，不保留旧的 uasset_read.py 入口
- **D-02 (目录布局):** 采用 src layout — 符合 Python Packaging User Guide 最佳实践，防止导入混淆，测试环境一致
- **D-03 (目录范围):** Phase 27 仅创建最小目录结构 — src/uasset_read/ 及其 __init__.py，子目录（serializers/, parsers/, models/）由后续阶段按需创建

### 配置文件

- **D-04 (pyproject.toml):** 零依赖配置 — `dependencies = []`，确保仅使用 Python 标准库
- **D-05 (开发依赖):** 包含可选开发依赖 — `dev = ["pytest>=7.0"]`，用于测试环境
- **D-06 (入口点):** 保留 CLI 入口配置 `[project.scripts]` — 为 Phase 28+ 准备
- **D-07 (版本号):** 在 pyproject.toml 中定义版本为 "5.1.0" — 语义化版本，与里程碑对应

### __init__.py 策略

- **D-08 (初始导出):** Phase 27 的 __init__.py 不导出任何 API — 使用延迟导入和类型注解字符串，避免初始导入加载模块
- **D-09 (API 控制):** 使用 `__all__` 控制公共接口 — Phase 27 的 __all__ 为空列表，后续阶段逐步填充

### 常量模块

- **D-10 (常量组织):** 按现有代码结构扁平分组 — 所有常量定义在 constants.py 单一文件中，不分组为子模块
- **D-11 (内容来源):** 常量从现有 uasset_read.py 提取 — 包括版本号、属性类型阈值、边界常量（如 PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012）

### 异常模块

- **D-12 (异常组织):** 单一模块包含所有异常类 — UAssetError, VersionError, ParseError, ErrorContext 及其子类
- **D-13 (内容来源):** 异常类从现有 uasset_read.py 提取 — 保持现有类结构和功能不变

### Claude's Discretion

无 — 所有实现细节已在研究阶段（ARCHITECTURE.md, STACK.md）明确。

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目架构与结构

- `.planning/research/ARCHITECTURE.md` — 推荐目录结构（src layout）、pyproject.toml 配置示例、模块组织方式
- `.planning/research/STACK.md` — 技术栈选择、常量/异常模块组织建议、零依赖验证方法

### 需求与范围

- `.planning/ROADMAP.md` §Phase 27 — Phase 27 目标、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — STRUCT-01, STRUCT-02, MOD-02, MOD-03 需求定义

### 项目状态

- `.planning/STATE.md` — 当前里程碑进度、关键决策记录、技术债务

## Existing Code Insights

### Reusable Assets

- **uasset_read.py (现有常量):** 7805行单文件包含完整的常量定义（PACKAGE_FILE_TAG, PROPERTY_TAG_COMPLETE_TYPE_NAME, UE5_VERSION_MIN 等），可直接提取到 constants.py
- **uasset_read.py (现有异常):** UAssetError, VersionError, ParseError, ErrorContext 等异常类可直接提取到 exceptions.py

### Established Patterns

- **dataclass for models:** 使用 Python 标准库 dataclasses 定义数据模型，asdict() 自动序列化到 JSON
- **分层架构依赖方向:** Output → Models → Parsers → Serializers → FArchive，单向依赖避免循环导入
- **边界验证常量:** 所有表大小都有 MAX_* 常量限制（MAX_NAME_COUNT, MAX_IMPORT_COUNT 等），防御性编程

### Integration Points

- **导入路径变更:** 所有现有测试的导入路径将从 `from uasset_read import *` 变为 `from src.uasset_read import *`，需要 Phase 30 更新
- **CLI 入口:** CLI 模块将在 Phase 28+ 实现，pyproject.toml 的 `[project.scripts]` 配置为后续阶段准备
- **后续模块依赖:** constants.py 和 exceptions.py 是所有后续模块的基础依赖

## Specific Ideas

No specific requirements — open to standard approaches documented in ARCHITECTURE.md and STACK.md.

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 27-项目结构初始化*
*Context gathered: 2026-05-06*