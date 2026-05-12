# Requirements - v6.0 模块化重构

**里程碑:** v6.0
**目标:** 将单文件 uasset_read.py 重构为多模块 Python 包
**创建日期:** 2026-05-06
**更新日期:** 2026-05-13

---

## 已完成需求（v6.0 主线）

### MOD - 模块化重构

| ID | 需求 | 状态 | 模块 |
|----|------|------|------|
| MOD-01 | 拆分 FArchive 二进制读取器 | ✓ | `archive.py` |
| MOD-02 | 常量和阈值模块 | ✓ | `constants.py` |
| MOD-03 | 异常类定义 | ✓ | `exceptions.py` |
| MOD-04 | PackageFileSummary 序列化 | ✓ | `serializers/package_summary.py` |
| MOD-05 | ImportMap/ExportMap 序列化 | ✓ | `serializers/object_resources.py` |
| MOD-06 | PropertyTag 拆分 | ✓ | `serializers/property_tags.py` |
| MOD-07 | 属性解析器拆分 | ✓ | `parsers/property_parser.py` |
| MOD-08 | 核心数据模型 | ✓ | `models/` (dataclasses) |
| MOD-09 | 避免循环导入 | ✓ | 分层依赖单向 |
| STRUCT-01 | src 目录结构 | ✓ | `src/uasset_read/` |
| STRUCT-02 | pyproject.toml 配置 | ✓ | 零依赖安装 |

### SCHEMA - JSON Schema 定义

| ID | 需求 | 状态 | 说明 |
|----|------|------|------|
| SCHEMA-01 | JSON Schema 结构定义 | ⏭️ | 延后至 v7.0 |
| SCHEMA-02 | Schema 验证功能 | ⏭️ | 延后至 v7.0 |
| SCHEMA-03 | Schema 文档 | ⏭️ | 延后至 v7.0 |

### TEST - 测试兼容性

| ID | 需求 | 状态 |
|----|------|------|
| TEST-01 | 所有现有测试通过 | ✓ | 373 passed, 71 skipped, 0 failed |
| TEST-02 | 新模块单元测试 | ✓ | 每个模块有对应测试 |

---

## 活跃需求

当前唯一未完成需求：**Phase 35b - Pin 连接深度调试与修复**

- 目标：修复 `linked_to_raw` 返回空列表、`pins_offset` 定位不准、UE5 序列化差异问题
- 详情：参见 `.planning/phases/35b-pin-connection-debug/`

---

## Out of Scope

| 需求 | 原因 |
|------|------|
| 向后兼容层 | 用户选择不保留旧入口 |
| 保留根级别 `uasset_read.py` | 已删除，完全模块化 |
| 测试框架迁移 | pytest 可直接运行 |
| MCP Server 封装 | 延后至 v7.x |
| C++ 代码生成 | 仅做解析，生成延后 |

---

## 需求追溯

**覆盖率:** 16/16 需求已映射到阶段 ✓  
**完成度:** 11/11 v6.0 主线需求已完成 ✓  
**剩余:** 1 个调试任务（Phase 35b）

---

## 决策理由

1. **先基础设施后扩展**: FArchive/常量/异常是基础，风险可控，渐进降低复杂度
2. **不向后兼容**: 完全拥抱新架构，不做技术妥协
3. **零运行时依赖**: 减少环境配置复杂度，符合项目定位

---

*最后更新: 2026-05-13 — v6.0 主线需求全部完成，仅剩余 Phase 35b*
