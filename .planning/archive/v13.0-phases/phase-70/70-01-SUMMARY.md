---
phase: 70-n2cstruct-schema
plan: 01
subsystem: n2c
tags: [dataclass, json-schema, id-mapping, token-compression]

# Dependency graph
requires:
  - phase: 69-processor-architecture
    provides: N2CNodeDefinition.extra_data key names and processor infrastructure
provides:
  - N2CPin/N2CNode/N2CGraph/N2CStruct dataclass hierarchy with to_dict() serialization
  - N2CIdMapper GUID-to-short-ID bidirectional mapping (N1, N2...)
  - Public n2c module exports (N2CStruct, N2CGraph, N2CNode, N2CPin, N2CIdMapper)
affects:
  - 70-02 N2CStruct serializer
  - 71 execution flow chain expression

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "dataclass with to_dict() for JSON serialization"
    - "Python 3.10+ union types (str | None)"
    - "field(default_factory=list) for mutable defaults"

key-files:
  created:
    - src/uasset_read/n2c/schema.py
    - src/uasset_read/n2c/id_mapper.py
    - tests/n2c/test_schema.py
    - tests/n2c/test_id_mapper.py
  modified:
    - src/uasset_read/n2c/__init__.py

key-decisions:
  - "Used Python 3.10+ union types (str | None) instead of Optional[str] for consistency with project style"
  - "N2CNode.id uses str type for short IDs (N1, N2...) rather than int, for JSON serialization compatibility"
  - "N2CGraph.flows defaults to {'execution': [], 'data': {}} to match existing flow_builder output shape"

patterns-established:
  - "Schema dataclasses with to_dict() for JSON serialization"
  - "IdMapper pattern for GUID compression with bidirectional lookup"

requirements-completed: [SCHEMA-01]

# Metrics
duration: 15min
completed: 2026-05-22
---

# Phase 70 Plan 01: N2CStruct Schema Summary

**N2CStruct 数据模型层：N2CPin/N2CNode/N2CGraph/N2CStruct 四级 dataclass 层次结构 + GUID→短 ID 双向映射器**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-22T12:15:00Z
- **Completed:** 2026-05-22T12:30:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- 创建 N2CPin/N2CNode/N2CGraph/N2CStruct 四级 dataclass 层次结构，支持完整 Blueprint graph 数据表示
- 每个 dataclass 提供 to_dict() 方法用于 JSON 序列化
- 实现 N2CIdMapper 提供 GUID→短 ID（N1, N2...）双向映射，支持幂等注册
- 更新 n2c/__init__.py 导出公共符号
- 28 个单元测试全部通过，82 个 n2c 模块总测试通过

## Task Commits

1. **Task 1: N2CStruct/N2CGraph/N2CNode/N2CPin dataclass** - `acb31b1` (feat)
2. **Task 2: N2CIdMapper GUID ↔ 短 ID 双向映射** - `acb31b1` (feat, same commit)

## Files Created/Modified

- `src/uasset_read/n2c/schema.py` - N2CPin/N2CNode/N2CGraph/N2CStruct dataclass 定义
- `src/uasset_read/n2c/id_mapper.py` - N2CIdMapper 双向映射器
- `src/uasset_read/n2c/__init__.py` - 更新导出列表
- `tests/n2c/test_schema.py` - schema dataclass 测试（15 tests）
- `tests/n2c/test_id_mapper.py` - id_mapper 测试（13 tests）

## Decisions Made

None - followed plan as specified

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

None

## Known Stubs

- `N2CStruct.structs` and `N2CStruct.enums` are placeholder `list[dict]` - reserved for future struct/enum definition support

## Next Phase Readiness

- N2CStruct 数据模型已就绪，可为 70-02 serializer 提供类型基础
- N2CIdMapper 已就绪，可为后续 flow_extractor 提供 GUID 压缩能力

---
*Phase: 70-n2cstruct-schema*
*Completed: 2026-05-22*
