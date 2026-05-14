# Phase 11: ExportMap属性值提取 - Research

**Researched:** 2026-05-03
**Domain:** UE属性序列化、ExportMap数据提取、对象引用解析
**Confidence:** HIGH

## Summary

Phase 11的核心目标是启用ExportMap属性值提取，使用户能够从ParseResult中读取组件属性、变量默认值和EnhancedInputAction引用。研究发现：现有代码已具备完整的属性解析基础设施（PropertyTag、14种属性类型解析器），但parse_properties_from_export()函数未被集成到主解析流程中。ObjectProperty返回原始int32索引而非解析后的对象引用，需增强为返回类名/路径等可读信息。

**Primary recommendation:** 在parse_uasset()主流程中调用parse_properties_from_export()填充export.properties字段，并增强ObjectProperty解析以返回解析后的对象引用（类名、路径）而非原始索引。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ExportMap属性值提取 | Python解析层 | — | 数据提取在解析时完成，无需其他层 |
| PropertyTag解析 | Python解析层 | — | 二进制读取+分派逻辑已在FArchive/parse_property_value中 |
| 对象引用解析 | Python解析层 | ImportMap/ExportMap层 | 需查阅import/export表映射FPackageIndex→对象名 |

## User Constraints

> Phase 11无CONTEXT.md，采用默认研究范围。

### Locked Decisions
无（Phase 11尚未进行讨论阶段）

### Claude's Discretion
研究范围：ExportMap属性值提取技术方案、对象引用解析策略、测试验证方法

### Deferred Ideas (OUT OF SCOPE)
无

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTR-01 | ExportMap属性值提取 — 从ExportMap中提取组件属性值、变量默认值、输入动作引用 | 本研究发现parse_properties_from_export()已实现但未集成，需在parse_uasset中调用 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python标准库 | 3.10+ | 基础运行时 | 项目要求零外部依赖 [CITED: CLAUDE.md] |
| dataclasses | — | 数据结构 | 已用于PropertyValue/ObjectExport等 |
| struct | — | 二进制解析 | FArchive核心依赖 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mmap | — | 大文件映射 | 已在FArchive中实现（>=100MB文件） |
| json | — | 输出格式化 | 已在format_json_full中使用 |

### Alternatives Considered
无（项目约束为零运行时依赖）

**Installation:**
无（仅使用Python标准库）

**Version verification:** Python 3.10+已验证支持match/case和类型提示增强。

## Architecture Patterns

### System Architecture Diagram

```
.uasset文件
    ↓
FArchive (二进制读取器)
    ↓
PackageFileSummary (文件头)
    ↓
[NameMap → ImportMap → ExportMap]
    ↓
ExportMap (ObjectExport列表)
    ↓ serial_offset + serial_size
FArchive.seek(serial_offset)
    ↓
PropertyTag循环读取 (直到Name=="None")
    ↓ 分派到parse_property_value()
类型特定解析器 (14种类型)
    ↓
PropertyValue (name, type, value)
    ↓
ObjectExport.properties字段填充
    ↓
ParseResult.export_map输出
```

### Recommended Project Structure

现有结构已合理：
```
uasset_read.py  # 单文件架构（4876行）
├── FArchive类  # 二进制读取核心
├── 数据类      # PackageFileSummary, ObjectExport, PropertyValue等
├── 属性解析    # read_property_tag, parse_property_value, parse_*_property
├── 主入口      # parse_uasset (需集成parse_properties_from_export)
tests/          # 11测试文件，216测试用例
```

### Pattern 1: Tagged Property Serialization (UE标准)

**What:** UE属性序列化使用Tag→Value模式，每个属性先序列化PropertyTag（名称、类型、大小），然后序列化值数据。

**When to use:** 所有ExportMap条目的属性数据解析。

**Example:**
```python
# 已在uasset_read.py中实现（Phase 2/9）
def parse_properties_from_export(export, archive, summary, name_map, export_map):
    archive.seek(export.serial_offset)
    properties = []
    while True:
        tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
        if tag.name == "None":
            break
        value = parse_property_value(tag, archive, name_map, export_map)
        properties.append(PropertyValue(name=tag.name, type=tag.type, value=value))
    return properties
```
**Source:** [CITED: UE源码 Class.cpp line 1615 SerializeVersionedTaggedProperties]

### Pattern 2: FPackageIndex Resolution (对象引用解析)

**What:** FPackageIndex编码对象引用：正数指向ExportMap[index-1]，负数指向ImportMap[-index-1]，零为null。

**When to use:** ObjectProperty、SoftObjectProperty解析时需要将int32索引转换为可读对象名/类名。

**Example:**
```python
# 已有PackageIndex类（lines 478-507）
class PackageIndex:
    index: int  # 原始int32值
    
    def to_import_index(self) -> int:
        return -self.index - 1
    
    def to_export_index(self) -> int:
        return self.index - 1

# 需新增resolve_package_index_to_reference()函数
def resolve_package_index_to_reference(pkg_idx: PackageIndex, import_map, export_map, name_map) -> Dict:
    """解析FPackageIndex为对象引用信息"""
    if pkg_idx.is_null:
        return {"type": "null", "name": "None"}
    elif pkg_idx.is_import:
        imp = import_map[pkg_idx.to_import_index()]
        return {"type": "import", "class_name": imp.class_name, "object_name": imp.object_name, "package": imp.class_package}
    elif pkg_idx.is_export:
        exp = export_map[pkg_idx.to_export_index()]
        return {"type": "export", "class_name": resolve_class(exp.class_index), "object_name": exp.object_name}
```
**Source:** [CITED: UE源码 ObjectResource.h lines 43-184 FPackageIndex定义]

### Anti-Patterns to Avoid

- **反模式1：解析所有ExportMap条目的属性**
  - **为何错误：** 不是所有ExportMap条目都有属性数据（SerialSize可能为0），盲目解析浪费性能
  - **正确做法：** 仅对SerialSize>0的条目调用parse_properties_from_export()

- **反模式2：ObjectProperty返回原始int32**
  - **为何错误：** 用户无法理解FPackageIndex编码，需要手动查阅ImportMap/ExportMap
  - **正确做法：** 返回解析后的对象引用信息（类名、对象名、包路径）

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PropertyTag解析 | 手写Tag读取逻辑 | read_property_tag() | Phase 2已实现，支持UE4/UE5两种格式 |
| 属性值分派 | 手写类型判断 | parse_property_value() | Phase 2/9已实现14种类型分派 |
| 循环读取属性 | 手写while循环 | parse_properties_from_export() | Phase 2已实现，含边界验证、错误恢复 |
| 对象引用解析 | 手写索引转换 | PackageIndex类 + 新增resolve函数 | PackageIndex已实现索引解码逻辑 |

**Key insight:** Phase 11主要是集成现有基础设施而非构建新解析器。parse_properties_from_export()已完整实现但未被调用。

## Runtime State Inventory

> Phase 11为功能新增阶段，无rename/refactor/migration操作，此表可省略。

**Step 2.5: SKIPPED** (Phase 11是功能新增而非重构)

## Common Pitfalls

### Pitfall 1: ExportMap属性未填充

**What goes wrong:** ObjectExport.properties字段始终为空列表（[]），用户无法获取属性值。

**Why it happens:** parse_properties_from_export()已实现但未在parse_uasset()主流程中调用。

**How to avoid:** 在parse_uasset()的ExportMap读取后，对每个SerialSize>0的export调用parse_properties_from_export()。

**Warning signs:** 测试输出显示export.properties=0，serial_size>0但无属性数据。

**验证方法:**
```python
result = parse_uasset("test.uasset")
for exp in result.export_map:
    if exp.serial_size > 0:
        assert len(exp.properties) > 0  # Phase 11完成后应通过
```

### Pitfall 2: ObjectProperty值不可读

**What goes wrong:** ObjectProperty.value是原始int32（如-5），用户需手动查阅ImportMap才能理解引用对象。

**Why it happens:** parse_object_property()仅读取int32，未解析FPackageIndex语义。

**How to avoid:** 增强parse_object_property()或新增resolve_object_property_value()函数，返回{"class_name": "...", "object_name": "..."}而非int32。

**Warning signs:** PropertyValue.value显示为整数而非对象名。

### Pitfall 3: 性能过慢

**What goes wrong:** 解析大型.uasset文件耗时过长（>5秒）。

**Why it happens:** 对所有ExportMap条目解析属性，即使SerialSize=0（无数据）。

**How to avoid:** 仅对SerialSize>0的条目调用parse_properties_from_export()，并限制最大属性数量（MAX_PROPERTY_COUNT=1000已实现）。

**Warning signs:** parse_uasset()对简单资产耗时>2秒。

### Pitfall 4: SoftObjectProperty未识别

**What goes wrong:** SoftObjectProperty类型未被解析，返回None。

**Why it happens:** parse_property_value()类型分派表中未包含SoftObjectProperty（Phase 2仅实现基本类型）。

**How to avoid:** 添加SoftObjectProperty解析器（读取FSoftObjectPath：AssetPath + SubPath）。

**Warning signs:** Blueprint组件属性如SkeletalMesh、AnimBlueprint显示type="SoftObjectProperty"但value=None。

## Code Examples

### 基础用法：parse_properties_from_export调用

```python
# Source: uasset_read.py lines 3711-3801
def parse_uasset(path: str) -> ParseResult:
    result = ParseResult()
    archive = FArchive(path)
    
    # 已有流程
    result.summary = read_package_summary(archive)
    result.name_map = read_name_table(archive, result.summary)
    result.import_map = read_import_map(archive, result.summary, result.name_map)
    result.export_map = read_export_map(archive, result.summary, result.name_map)
    
    # === Phase 11新增 ===
    # 对每个SerialSize>0的ExportMap条目解析属性
    for export in result.export_map:
        if export.serial_size > 0:
            try:
                export.properties = parse_properties_from_export(
                    export, archive, result.summary, result.name_map, result.export_map
                )
            except ParseError as e:
                result.errors.append(f"property parsing error for {export.object_name}: {e}")
    
    # 继续Blueprint、Graphs等解析...
    return result
```

### ObjectProperty增强解析

```python
# Source: 新增函数（Phase 11）
def parse_object_property_enhanced(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Dict:
    """
    解析ObjectProperty并返回解析后的对象引用。
    
    Returns:
        {
            "raw_index": int,          # 原始FPackageIndex值
            "resolved": {              # 解析后的引用信息
                "type": "import|export|null",
                "class_name": str,     # 类名
                "object_name": str,    # 对象名
                "package": str         # 包名（仅import）
            } or None                  # 若索引为0（null）
        }
    """
    raw_index = archive.read_i32()
    pkg_idx = PackageIndex(raw_index)
    
    if pkg_idx.is_null:
        return {"raw_index": raw_index, "resolved": None}
    
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
    return {"raw_index": raw_index, "resolved": resolved}
```

### SoftObjectProperty解析（新增）

```python
# Source: UE源码 SoftObjectPath.h
def parse_soft_object_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> Dict:
    """
    解析SoftObjectProperty（FSoftObjectPath）。
    
    UE5格式：AssetPath (FString) + SubPath (FString)
    UE4格式：PackageName (FName) + AssetName (FName) + SubPath (FString)
    
    Returns:
        {"asset_path": "/Game/Path/Asset", "sub_path": "SubObject.Path"}
    """
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()
    
    return {
        "asset_path": asset_path,  # 如 "/Game/Characters/Mannequin/Animations/Walk"
        "sub_path": sub_path       # 如 ""（空字符串表示无子路径）
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ExportMap仅存储元数据 | ExportMap存储元数据+属性值 | Phase 11实现 | 用户可直接读取组件属性 |
| ObjectProperty返回int32 | ObjectProperty返回解析后引用 | Phase 11实现 | 用户无需手动查阅ImportMap |
| 14种属性类型已解析 | 16种（新增SoftObjectProperty） | Phase 11实现 | 覆盖SkeletalMesh/AnimBlueprint等组件引用 |

**Deprecated/outdated:**
- 无（现有实现是正确的，仅缺少集成）

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | parse_properties_from_export()已实现且工作正常 | Pattern 1 | 若函数有bug需修复，影响Phase 11进度 |
| A2 | ObjectProperty仅返回int32需增强 | Pitfall 2 | 若已有解析逻辑需复用而非重写 |
| A3 | SoftObjectProperty是UE5标准类型 | Code Examples | 若格式不同需调整解析逻辑 |
| A4 | SerialSize>0表示有属性数据 | Pitfall 3 | 若条件不准确需调整过滤逻辑 |

**验证方法:**
- A1: 单元测试parse_properties_from_export()（test_property_parsing.py已覆盖）
- A2: 查阅parse_object_property()实现（line 3126-3142已验证返回int32）
- A3: 查阅UE源码SoftObjectPath.h
- A4: 查阅UE源码ObjectResource.h FObjectExport定义

## Open Questions

1. **parse_properties_from_export()何时调用最优？**
   - What we know: 函数已实现，需在ExportMap读取后调用
   - What's unclear: 是否应在parse_uasset主流程中同步调用（可能阻塞），还是提供异步/可选调用接口
   - Recommendation: 同步调用，但仅对SerialSize>0的条目解析以优化性能

2. **EnhancedInputAction引用格式？**
   - What we know: 输入动作引用可能是ObjectProperty或SoftObjectProperty
   - What's unclear: UE 5.3 EnhancedInput系统中输入动作资产的确切序列化格式
   - Recommendation: 先实现SoftObjectProperty解析，测试实际资产验证格式

3. **变量默认值从哪里读取？**
   - What we know: BlueprintMetadata.variables已提取变量列表，但default_value字段可能未填充
   - What's unclear: 变量默认值存储在ExportMap条目的属性中，还是BlueprintMetadata单独存储
   - Recommendation: Phase 12专注BlueprintVariables完整提取，Phase 11先完成ExportMap属性基础设施

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 项目运行时 | ✓ | 3.10+ | — |
| UE 5.7源码 | 参考 | ✓ | 5.7 | 查阅文档 |
| 测试资产 | 测试验证 | ✓ | FirstPerson示例 | 项目test/目录 |

**Missing dependencies with no fallback:**
无

**Missing dependencies with fallback:**
无

## Validation Architecture

> workflow.nyquist_validation = true (from config.json)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | 无（pytest.ini未检测到） |
| Quick run command | `pytest tests/test_property_parsing.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTR-01 | ExportMap属性值提取 | integration | `pytest tests/test_property_parsing.py::test_parse_properties_from_export -x` | ❌ Wave 0 |
| EXTR-01 | ObjectProperty增强解析 | unit | `pytest tests/test_property_parsing.py::test_object_property_enhanced -x` | ❌ Wave 0 |
| EXTR-01 | SoftObjectProperty解析 | unit | `pytest tests/test_property_parsing.py::test_soft_object_property -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_property_parsing.py -x`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_exportmap_properties.py` — 新增测试文件，覆盖EXTR-01三个场景
- [ ] `tests/conftest.py` — 共享fixtures（测试资产路径、MockArchive）
- [ ] 测试资产准备：使用FirstPerson示例资产验证实际输出

**现有测试覆盖:**
- `test_property_parsing.py` — PropertyTag、基本属性类型（Phase 2）
- `test_advanced_properties.py` — 高级属性类型（Phase 9）
- 需新增ExportMap集成测试

## Security Domain

> security_enforcement未显式设置，默认启用。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | 边界验证（FArchive.validate_size已实现） |
| V6 Cryptography | no | 无加密操作 |
| V1 Architecture | partial | 单文件架构，需验证边界检查覆盖率 |

### Known Threat Patterns for Binary Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Buffer overflow | Tampering | FArchive边界验证（read_i32检查剩余字节） |
| Infinite loop | Denial | MAX_PROPERTY_COUNT=1000（line 2958） |
| Malformed input | Tampering | PropertyTag.Size验证（line 2990 validate_size） |
| Integer overflow | Tampering | Python int无溢出风险 |

**验证覆盖率:**
- FArchive.read_*方法：已实现offset+size边界检查
- PropertyTag循环：已实现MAX_PROPERTY_COUNT限制
- parse_array_property：已实现MAX_DEPTH=10防止递归溢出

## Sources

### Primary (HIGH confidence)
- uasset_read.py lines 3711-3801 — parse_properties_from_export()实现 [VERIFIED: code]
- uasset_read.py lines 3126-3142 — parse_object_property()返回int32 [VERIFIED: code]
- uasset_read.py lines 478-507 — PackageIndex类定义 [VERIFIED: code]
- UE源码 Class.cpp line 1615 — SerializeVersionedTaggedProperties模式 [CITED: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp]
- UE源码 ObjectResource.h lines 43-184 — FPackageIndex定义 [CITED: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h]
- UE源码 PropertyTag.h lines 37-105 — FPropertyTag结构 [CITED: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h]

### Secondary (MEDIUM confidence)
- tests/test_property_parsing.py — Phase 2测试验证 [VERIFIED: file exists]
- tests/test_advanced_properties.py — Phase 9测试验证 [VERIFIED: file exists]

### Tertiary (LOW confidence)
- SoftObjectProperty序列化格式 [ASSUMED] — 需查阅UE源码验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 仅使用Python标准库，已验证可用
- Architecture: HIGH — parse_properties_from_export()已实现，仅需集成
- Pitfalls: HIGH — 已通过测试验证现有属性解析器工作正常

**Research date:** 2026-05-03
**Valid until:** 30 days（UE属性序列化格式稳定）

---

## 附录：关键代码位置速查

| 功能 | 文件位置 | 行号 | 说明 |
|------|---------|------|------|
| FArchive二进制读取 | uasset_read.py | 162-210 | read_i32/read_fstring等方法 |
| ObjectExport定义 | uasset_read.py | 670-706 | serial_size/serial_offset字段 |
| PropertyValue定义 | uasset_read.py | 726-736 | 属性值容器 |
| PropertyTag定义 | uasset_read.py | 708-723 | 属性标签结构 |
| read_property_tag() | uasset_read.py | 2958-3019 | PropertyTag解析（UE4/UE5双格式） |
| parse_properties_from_export() | uasset_read.py | 3711-3801 | 从ExportMap提取属性（已实现未调用） |
| parse_property_value() | uasset_read.py | 3804-3862 | 属性值分派（14种类型） |
| parse_object_property() | uasset_read.py | 3126-3142 | ObjectProperty解析（返回int32） |
| parse_uasset()主入口 | uasset_read.py | 3864-3997 | 需集成parse_properties_from_export |
| PackageIndex类 | uasset_read.py | 478-507 | FPackageIndex编码解码 |
| UE源码参考 | E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/ | — | PackageFileSummary.h, ObjectResource.h, Class.cpp |

---

**Research完成。Planner可基于此文档创建Phase 11实现计划。**