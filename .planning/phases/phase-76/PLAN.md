# Phase 76: FArchive 补齐 + PackageSummary + COR 修复

**Milestone:** v14.0 — CUE4Parse 核心对齐
**Requirements:** COR-01, COR-02
**Status:** Planned
**Date:** 2026-05-26

---

## 目标

实现 CUE4Parse 核心 FArchive 层补齐和 StructProperty 深度解析修复：

1. **COR-01**: StructProperty 内部字段完整提取（FVector/FRotator/FBodyInstance 等复杂结构体）
2. **COR-02**: FCustomVersion 体系（GUID→Version 映射表）+ VersionContainer 统一管理

---

## 当前状态分析

### COR-01: StructProperty 深度解析

**已有基础** (`parsers/property_types.py:157`):
- Vector/LinearColor/Rotator/Quat/Plane 的 fast-path raw read ✅
- Transform fast-path（UE5 LWC FVector → double）✅
- 通用 PropertyTag loop fallback（读取子属性 → 递归 parse_property_value）✅
- BodyInstance 已在 fast-path 但字段不完整 ⚠️

**问题** (对照 `docs/CUE4Parse-对照索引.md` 113 行 🔧 标记):
- Box/Sphere/Guid/Matrix/IntPoint/IntVector 等常见 struct 缺失 fast-path
- 通用 loop fallback 中 struct 内嵌 struct 的递归深度处理可能有边界问题
- 缺少 struct 类型从 FPropertyTypeName 链式节点中的提取逻辑（嵌套类型名）

### COR-02: FCustomVersion / VersionContainer

**已有基础** (`serializers/package_summary.py`):
- `CustomVersion` dataclass（guid + version）✅
- `PackageFileSummary.custom_versions` 列表 ✅
- `PackageFileSummary.get_custom_version(guid)` 方法 ✅
- 常量文件中多个 GUID 定义（FFRAMEWORK/FUE5Mainstream/FRelease/FUE5ReleaseStream）✅
- 各 GUID 对应的版本阈值常量 ✅

**问题** (对照索引 49 行 ❌ 标记):
- 版本常量分散在 `constants.py`，没有统一的 VersionContainer 管理
- 没有 `if (Ar.Ver >= EUEVersion.UE4_23)` 风格的版本查询接口
- GUID→版本→阈值的三层映射没有封装为可复用组件
- 各个读取函数（package_summary、object_resources、property_tags）各自 hardcode 版本判断

---

## 任务分解

### Task 1: VersionContainer 统一版本管理 (COR-02)

**文件**: `src/uasset_read/versioning.py`（新）

```python
class VersionContainer:
    def __init__(self, custom_versions: List[CustomVersion], file_version_ue5: int): ...
    def get_version(self, guid: str, default: int = 0) -> int: ...
    def is_at_least(self, threshold: int, stream: str = "framework") -> bool: ...
```

**设计**:
- GUID 常量集中在 `constants.py`（已有）
- VersionContainer 提供统一查询入口
- `EUEVersion` 枚举（UE4_23, UE4_24, UE4_27, UE5_0, UE5_1, ...）
- 预置 CustomVersion GUID 映射

**验收**:
- `container.get_version("CFFC743F43B04480939114DF171D2073")` 返回正确版本
- `container.is_at_least(15, "framework")` 正确比较
- 单元测试覆盖 GUID 查询、版本比较、缺失默认值

### Task 2: PackageSummary 版本集成 (COR-02)

**文件**: `src/uasset_read/serializers/package_summary.py`

新增 `build_version_container(summary) -> VersionContainer` 快捷函数，从已有的 CustomVersion 列表和 file_version_ue5 构建。

### Task 3: StructProperty 深度解析修复 (COR-01)

**文件**: `src/uasset_read/parsers/property_types.py` — `parse_struct_property()`

**补充 fast-path struct 类型**:

| Struct | 字段 |
|--------|------|
| `Box` / `Box2D` | Min, Max, bValid |
| `BoxSphereBounds` | Origin, BoxExtent, SphereRadius |
| `Sphere` | Center, W |
| `Guid` | A, B, C, D (4x uint32) |
| `Matrix` | 4x4 float[4][4] |
| `IntPoint` | X(i32), Y(i32) |
| `IntVector` | X(i32), Y(i32), Z(i32) |
| `Vector2D` | X(f32), Y(f32) |
| `Vector4` | X(f32), Y(f32), Z(f32), W(f32) |
| `TwoVectors` | E1, E2 (Vector) |
| `OrientedBox` | AxisX/Y/Z, Extent, Center |

**BodyInstance 修复**: 补充完整字段序列或降级为通用 PropertyTag loop 模式。

### Task 4: 管线集成 (COR-01/COR-02)

**文件**: `src/uasset_read/parse_uasset.py`

- `parse_uasset()` 返回结果中包含 version_container
- `parse_uasset_with_linker()` 将 version_container 传入 PackageLinker

### Task 5: 测试

- `tests/test_versioning.py` — VersionContainer 单元 + E2E
- `tests/test_struct_property.py` — StructProperty fast-path 单元 + E2E
- 现有 1339 测试全部通过

---

## 文件变更计划

| 文件 | 操作 |
|------|------|
| `src/uasset_read/versioning.py` | 新建 |
| `src/uasset_read/serializers/package_summary.py` | 修改 |
| `src/uasset_read/parsers/property_types.py` | 修改 |
| `src/uasset_read/parse_uasset.py` | 修改 |
| `src/uasset_read/serializers/__init__.py` | 修改 |
| `src/uasset_read/__init__.py` | 修改 |
| `tests/test_versioning.py` | 新建 |
| `tests/test_struct_property.py` | 新建 |

---

## 验收标准

### COR-01
- [ ] StructProperty 内部字段（FVector/FRotator/FBodyInstance + Box/Guid/Matrix/IntPoint/Vector2D/Vector4）完整提取
- [ ] 现有测试全部通过
- [ ] BP_FirstPersonCharacter 测试资产输出完整

### COR-02
- [ ] VersionContainer 支持 get_version/is_at_least 查询
- [ ] CustomVersion GUID 集中管理，按 stream 分类
- [ ] 至少 1 个序列化函数使用 VersionContainer 版本判断
- [ ] 测试覆盖 GUID 查询/版本比较/缺失默认值

---

*Created: 2026-05-26*
