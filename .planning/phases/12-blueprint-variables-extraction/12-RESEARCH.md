# Phase 12: BlueprintVariables完整提取 - Research

**Researched:** 2026-05-03
**Domain:** Unreal Engine蓝图变量序列化与解析
**Confidence:** HIGH (UE源码验证 + 现有代码分析)

## Summary

Phase 12的目标是从蓝图资产中提取完整的变量信息，包括名称、类型、默认值、元数据，并区分组件变量和普通变量。本研究基于UE 5.7源码中的FBPVariableDescription结构和BlueprintGeneratedClass序列化机制，结合Phase 11已实现的ExportMap属性提取能力。

**关键发现：**
- 变量定义存储在UBlueprint资产的NewVariables数组中（编辑器数据）
- BlueprintGeneratedClass是编译后的类定义，变量属性作为UClass的属性列表
- Phase 3已实现FBPVariableDescription解析，但跳过了MetaDataArray和is_component字段
- Phase 11属性解析器已覆盖EXTR-05需求的所有类型

**主要挑战：**
- Phase 3变量提取返回空列表，需要诊断extract_blueprint_metadata函数
- BlueprintGeneratedClass export的识别需要正确的class_index解析
- PropertyFlags解析需要转换为用户可读的标签列表

**Primary recommendation:** 增强Phase 3的read_blueprint_variable()函数，添加MetaDataArray解析和is_component字段；修复extract_blueprint_metadata()的定位逻辑。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 变量信息来自ExportMap中BlueprintGeneratedClass类型的export条目，需解析该export的properties以提取变量定义
- **D-02:** 组件变量通过类型名称识别（类型名包含"Component"），添加is_component布尔字段
- **D-03:** 变量元数据（Category、BlueprintReadWrite等）存储在PropertyTag的property_flags中，需解析EPropertyFlags标志位
- **D-04:** 类型完整显示使用现有pin_type解析逻辑，增强为完整类型字符串
- **D-05:** 验证Phase 11属性解析器覆盖度，确保Float/Bool/Str/Struct/ObjectProperty覆盖

### Claude's Discretion
- 变量列表构建时机：parse_uasset()结尾或作为独立函数
- 多个蓝图export的处理：如何确定主蓝图Class
- 元数据格式：字段列表vs字典结构

### Deferred Ideas (OUT OF SCOPE)
- 变量分组显示（按Category组织）
- 变量依赖图构建（变量间引用关系）
- 动态变量识别（RunTime变量vs编辑器变量）

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTR-02 | 提取蓝图变量名称、类型、默认值、元数据（Category、BlueprintReadWrite等） | FBPVariableDescription结构完整定义（Blueprint.h L201-254） + Phase 3 read_blueprint_variable()已实现 |
| EXTR-03 | 区分组件变量（SkeletalMeshComponent等）和普通变量 | D-02已决策：类型名contains("Component")判断 + EPropertyFlags CPF_InstancedReference标志位 |
| EXTR-05 | 支持数值、字符串、布尔、向量、对象引用等类型默认值 | Phase 11 parse_property_value支持17种类型，覆盖所有需求类型 |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Blueprint变量定义存储 | Asset/Package | — | UBlueprint资产的NewVariables数组存储编辑器变量定义 |
| 变量类型信息解析 | Parse Layer | — | FEdGraphPinType结构需完整解析（Phase 3已实现） |
| PropertyFlags标志位解析 | Parse Layer | Output Layer | 解析为标志列表，输出层格式化为用户可读标签 |
| 默认值解析 | Parse Layer | — | Phase 11属性解析器已覆盖多种类型 |
| 组件变量识别 | Parse Layer | — | 类型名判断 + CPF_InstancedReference标志位双重验证 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | 3.10+ | BlueprintVariable数据结构 | 标准库，Phase 3已使用 |
| FEdGraphPinType解析 | Phase 3 | 变量类型结构解析 | 已实现read_ed_graph_pin_type()函数 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| EPropertyFlags枚举 | UE 5.7 | 标志位解析 | 从ObjectMacros.h提取CPF_*常量 |
| parse_property_value | Phase 11 | 默认值解析 | 复用已实现的属性值解析器 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FBPVariableDescription解析 | BlueprintGeneratedClass CDO属性读取 | 编辑器数据更完整（含DefaultValue字符串），CDO是编译后状态 |

**Installation:**
无需额外安装，所有功能基于现有代码增强。

## Architecture Patterns

### System Architecture Diagram

```
.uasset文件
    ↓
FArchive二进制读取
    ↓
ExportMap解析
    ↓
    ├─ UBlueprint export → NewVariables数组 → FBPVariableDescription解析
    │   ↓
    │   ├─ VarName (FName)
    │   ├─ VarType (FEdGraphPinType)
    │   ├─ PropertyFlags (uint64) → EPropertyFlags解析 → 标签列表
    │   ├─ MetaDataArray → 元数据字典
    │   └─ DefaultValue (FString) → Phase 11 parse_property_value
    │
    └─ BlueprintGeneratedClass export → 属性列表 → 变量运行时状态
        ↓
    组件变量识别：类型名 + CPF_InstancedReference
    ↓
ParseResult.blueprint.variables
```

### Recommended Project Structure

现有结构无需调整，增强以下函数：
```
uasset_read.py
├── read_blueprint_variable()      # 增强MetaDataArray解析
├── extract_blueprint_metadata()   # 修复定位逻辑
├── parse_property_flags()         # 新增：EPropertyFlags解析
└── format_variable_type()         # 新增：完整类型字符串格式化
```

### Pattern 1: FBPVariableDescription解析

**What:** 从Blueprint.h L201-254定义的结构，完整解析蓝图变量定义。

**When to use:** 处理UBlueprint资产的NewVariables数组时。

**Example:**
```python
# Source: Blueprint.h L201-254 [VERIFIED]
# 序列化顺序：
# 1. VarName (FName)
# 2. VarGuid (FGuid - 16 bytes)
# 3. VarType (FEdGraphPinType)
# 4. FriendlyName (FString)
# 5. Category (FText - simplified to FString)
# 6. PropertyFlags (uint64)
# 7. RepNotifyFunc (FName)
# 8. ReplicationCondition (uint8)
# 9. MetaDataArray (TArray<FBPVariableMetaDataEntry>)
# 10. DefaultValue (FString)

@dataclass
class BlueprintVariable:
    var_name: str
    var_type: FEdGraphPinType
    category: str
    property_flags: int              # uint64
    default_value: any = None
    friendly_name: str = ""
    is_component: bool = False       # Phase 12新增
    metadata: Dict[str, str] = {}    # Phase 12新增：从MetaDataArray解析
```

### Pattern 2: EPropertyFlags解析

**What:** 从uint64 flags解析为用户可读的标签列表。

**When to use:** 解析PropertyFlags字段时。

**Example:**
```python
# Source: ObjectMacros.h L415-480 [VERIFIED]
# 关键标志位：
CPF_Edit = 0x0000000000000001           # EditAnywhere
CPF_BlueprintVisible = 0x0000000000000004  # BlueprintReadWrite
CPF_BlueprintReadOnly = 0x0000000000000010 # BlueprintReadOnly
CPF_Protected = 0x0000080000000000      # Protected
CPF_InstancedReference = 0x0000000000080000  # 组件引用标志
CPF_ExposeOnSpawn = 0x0001000000000000  # ExposeOnSpawn
CPF_Config = 0x0000000000004000         # Config
CPF_Transient = 0x0000000000002000      # Transient
CPF_SaveGame = 0x0000000001000000       # SaveGame
CPF_Deprecated = 0x0000000020000000     # Deprecated

def parse_property_flags(flags: int) -> List[str]:
    """解析PropertyFlags为标签列表"""
    labels = []
    if flags & CPF_Edit:
        labels.append("EditAnywhere")
    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")
    if flags & CPF_Protected:
        labels.append("Protected")
    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")  # 组件变量标志
    if flags & CPF_ExposeOnSpawn:
        labels.append("ExposeOnSpawn")
    # ... 其他标志位
    return labels
```

### Anti-Patterns to Avoid

- **跳过MetaDataArray解析：** Phase 3跳过了，但元数据包含Category、DisplayName等重要信息
- **仅依赖类型名判断组件变量：** 应同时检查CPF_InstancedReference标志位，双重验证
- **忽略DefaultValue的字符串解析：** DefaultValue是FString，可能包含结构体、数组等复杂值

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PropertyFlags解析 | 自定义bit位解析 | ObjectMacros.h CPF_*常量 | UE标准定义，64个标志位覆盖全面 |
| 默认值类型解析 | 自定义类型分派 | Phase 11 parse_property_value() | 已支持17种类型，验证充分 |
| FEdGraphPinType解析 | 自定义类型格式化 | Phase 3 read_ed_graph_pin_type() | 已实现完整结构解析 |

**Key insight:** Phase 11和Phase 3已建立完整的基础设施，Phase 12主要是集成和增强工作。

## Common Pitfalls

### Pitfall 1: BlueprintGeneratedClass识别失败

**What goes wrong:** Phase 3的detect_blueprint()检测UBlueprint而非BlueprintGeneratedClass，导致变量提取定位错误。

**Why it happens:** UBlueprint是编辑器资产定义，BlueprintGeneratedClass是编译后的类定义，两者class_index不同。

**How to avoid:** 
- 检查export的class_index是否指向BlueprintGeneratedClass（ImportMap或ExportMap）
- 主BlueprintGeneratedClass的object_name通常匹配蓝图资产名（如"BP_FirstPersonCharacter_C"）

**Warning signs:** ParseResult.blueprint.variables为空列表，但ExportMap中有BlueprintGeneratedClass export。

### Pitfall 2: 组件变量识别不准确

**What goes wrong:** 仅依赖类型名判断组件变量，误判普通变量或漏判组件变量。

**Why it happens:** 某些组件类型名不以"Component"结尾（如ChildActor），某些类型名包含"Component"但不是组件。

**How to avoid:**
- 双重验证：类型名contains("Component") + CPF_InstancedReference标志位
- 优先使用CPF_InstancedReference标志位判断（更可靠）

**Warning signs:** is_component字段误判，组件变量数量与预期不符。

### Pitfall 3: MetaDataArray解析遗漏

**What goes wrong:** Phase 3跳过了MetaDataArray，导致Category、DisplayName等元数据丢失。

**Why it happens:** Phase 3设计决策简化实现，推迟元数据解析。

**How to avoid:**
- 完整解析MetaDataArray（TArray<FBPVariableMetaDataEntry>）
- 转换为Dict[str, str]格式供用户访问

**Warning signs:** Category字段为空或显示为"FText"，BlueprintReadWrite等标签缺失。

### Pitfall 4: ExportMap解析错位（Phase 11遗留）

**What goes wrong:** ExportMap的class_index解析返回Unknown，serial_size显示异常值。

**Why it happens:** 版本常量错误或ImportMap解析问题，导致ExportMap定位错位。

**How to avoid:**
- 使用Phase 11 gap closure修正的版本常量（UE5_OPTIONAL_RESOURCES = 1003）
- 验证ImportMap的class_package/class_name解析正确

**Warning signs:** ExportMap条目的class_name显示为Unknown或None，serial_size为负数或超大值。

## Code Examples

Verified patterns from official sources:

### FBPVariableDescription完整解析

```python
# Source: Blueprint.h L201-254 [VERIFIED]
def read_blueprint_variable_enhanced(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> BlueprintVariable:
    """完整解析FBPVariableDescription（Phase 12增强版）"""
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )
    
    # VarGuid (16 bytes)
    archive.read(16)
    
    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)
    
    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()
    
    # Category (FText - simplified to FString)
    var.category = archive.read_fstring()
    
    # PropertyFlags (uint64)
    var.property_flags = archive.read_u64()
    
    # RepNotifyFunc (FName)
    archive.read_name(name_map)
    
    # ReplicationCondition (uint8)
    archive.read_u8()
    
    # MetaDataArray (TArray<FBPVariableMetaDataEntry>) - Phase 12新增
    meta_count = archive.read_i32()
    var.metadata = {}
    for _ in range(meta_count):
        key = archive.read_name(name_map)
        value = archive.read_fstring()
        var.metadata[key] = value
    
    # DefaultValue (FString)
    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)
    
    # 组件变量识别（Phase 12新增）
    # 双重验证：类型名 + CPF_InstancedReference标志位
    type_str = var.var_type.pin_sub_category or var.var_type.pin_category
    is_component_by_name = isinstance(type_str, str) and "Component" in type_str
    is_component_by_flag = (var.property_flags & 0x0000000000080000) != 0  # CPF_InstancedReference
    var.is_component = is_component_by_flag or is_component_by_name
    
    return var
```

### PropertyFlags解析为标签列表

```python
# Source: ObjectMacros.h L415-480 [VERIFIED]
def parse_property_flags_to_labels(flags: int) -> List[str]:
    """解析PropertyFlags为用户可读标签列表"""
    # EPropertyFlags常量定义
    CPF_Edit = 0x0000000000000001
    CPF_BlueprintVisible = 0x0000000000000004
    CPF_BlueprintReadOnly = 0x0000000000000010
    CPF_Protected = 0x0000080000000000
    CPF_InstancedReference = 0x0000000000080000
    CPF_ExposeOnSpawn = 0x0001000000000000
    CPF_Config = 0x0000000000004000
    CPF_Transient = 0x0000000000002000
    CPF_SaveGame = 0x0000000001000000
    CPF_Deprecated = 0x0000000020000000
    CPF_EditConst = 0x0000000000020000
    CPF_AdvancedDisplay = 0x0000040000000000
    
    labels = []
    
    # Edit相关
    if flags & CPF_Edit:
        if flags & CPF_EditConst:
            labels.append("EditConst")
        else:
            labels.append("EditAnywhere")
    
    # Blueprint相关
    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")
    
    # 其他重要标志
    if flags & CPF_Protected:
        labels.append("Protected")
    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")
    if flags & CPF_ExposeOnSpawn:
        labels.append("ExposeOnSpawn")
    if flags & CPF_Config:
        labels.append("Config")
    if flags & CPF_Transient:
        labels.append("Transient")
    if flags & CPF_SaveGame:
        labels.append("SaveGame")
    if flags & CPF_Deprecated:
        labels.append("Deprecated")
    if flags & CPF_AdvancedDisplay:
        labels.append("AdvancedDisplay")
    
    return labels
```

### BlueprintGeneratedClass识别

```python
# Source: BlueprintGeneratedClass.h L432-435 [VERIFIED]
def detect_blueprint_generated_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """检测BlueprintGeneratedClass export"""
    if export.class_index.is_import:
        idx = export.class_index.to_import_index()
        if 0 <= idx < len(import_map):
            class_name = import_map[idx].class_name
            # BlueprintGeneratedClass或其子类（如AnimBlueprintGeneratedClass）
            return "BlueprintGeneratedClass" in class_name
    return False

def find_main_blueprint_generated_class(
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    asset_name: str  # 如"BP_FirstPersonCharacter"
) -> Optional[ObjectExport]:
    """找到主BlueprintGeneratedClass export"""
    for export in export_map:
        if detect_blueprint_generated_class(export, import_map, export_map):
            # 主BPGC的object_name通常为蓝图名+"_C"
            # 如 BP_FirstPersonCharacter_C
            if export.object_name.startswith(asset_name):
                return export
    return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 3跳过MetaDataArray | Phase 12完整解析 | 2026-05-03 | 用户可访问完整元数据 |
| Phase 3仅解析DefaultValue字符串 | Phase 11 parse_property_value | 2026-05-02 Phase 11 | 支持多种类型默认值解析 |
| Phase 3无is_component字段 | Phase 12添加组件变量识别 | 2026-05-03 | 用户可区分组件和普通变量 |

**Deprecated/outdated:**
- Phase 3的read_blueprint_variable()跳过MetaDataArray逻辑：Phase 12需要完整解析
- 仅依赖类型名判断组件变量：应使用CPF_InstancedReference标志位双重验证

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 11属性解析器覆盖EXTR-05所有需求类型 | Phase Requirements | 如有遗漏类型，需补充解析器 |
| A2 | BlueprintGeneratedClass export的object_name为蓝图名+"_C" | BlueprintGeneratedClass识别 | 如命名规则变化，识别失败 |
| A3 | Phase 3变量提取返回空列表是定位逻辑问题 | Pitfall 1 | 可能是其他根本问题，需诊断 |

## Open Questions

1. **Phase 3变量提取为何返回空列表？**
   - What we know: extract_blueprint_metadata()调用read_blueprint_variable()，但variables=[]
   - What's unclear: 是定位错误（找不到NewVariables数组）还是解析错误
   - Recommendation: 添加调试日志，验证archive定位和var_count读取

2. **BlueprintGeneratedClass的CDO属性是否包含变量默认值？**
   - What we know: BlueprintGeneratedClass有SerializeDefaultObject方法
   - What's unclear: CDO属性与NewVariables数组的DefaultValue是否一致
   - Recommendation: 同时解析两种来源，验证一致性

3. **多个BlueprintGeneratedClass export如何选择主Class？**
   - What we know: 一个蓝图资产可能包含多个BPGC export（组件、子对象等）
   - What's unclear: 如何准确识别主蓝图Class
   - Recommendation: 使用object_name匹配资产名 + serial_size最大（主类数据量最大）

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| UE 5.7源码 | Blueprint.h参考 | ✓ | 5.7 | — |
| Phase 3代码 | FBPVariableDescription解析 | ✓ | 已实现 | — |
| Phase 11代码 | parse_property_value | ✓ | 已实现 | — |
| BP_FirstPersonCharacter.uasset | 测试资产 | ✓ | UE Samples | 使用其他蓝图资产 |

**Missing dependencies with no fallback:**
None — 所有依赖已满足。

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 3.10+ |
| Config file | tests/conftest.py (fixtures) |
| Quick run command | `pytest tests/test_phase12_blueprint_variables.py -x -v` |
| Full suite command | `pytest tests/ --tb=short -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTR-02 | 变量名称、类型、默认值提取 | unit | `pytest tests/test_phase12_variables.py::test_variable_extraction -v` | ❌ Wave 0 |
| EXTR-02 | 元数据解析（Category、BlueprintReadWrite等） | unit | `pytest tests/test_phase12_variables.py::test_metadata_extraction -v` | ❌ Wave 0 |
| EXTR-03 | 组件变量识别（is_component字段） | unit | `pytest tests/test_phase12_variables.py::test_component_identification -v` | ❌ Wave 0 |
| EXTR-05 | 默认值类型覆盖验证 | unit | `pytest tests/test_phase12_variables.py::test_default_value_types -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase12_variables.py -x`
- **Per wave merge:** `pytest tests/ --tb=short -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase12_variables.py` — 覆盖EXTR-02, EXTR-03, EXTR-05所有测试
- [ ] `tests/fixtures/blueprint_with_components.uasset` — 包含组件变量的测试资产
- [ ] `tests/fixtures/blueprint_with_metadata.uasset` — 包含完整元数据的测试资产

## Security Domain

> Phase 12为纯解析功能，不涉及运行时安全风险。ASVS安全要求不适用。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | archive.validate_size()边界验证 |
| V6 Cryptography | no | — |

### Known Threat Patterns for uasset_read

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Invalid PropertyTag.Size | Tampering | archive.validate_size()检查 |
| Infinite property loop | Denial of Service | MAX_PROPERTY_COUNT限制 |
| Recursive depth overflow | Denial of Service | depth限制（StructProperty递归） |

## Sources

### Primary (HIGH confidence)
- Blueprint.h L201-254 [VERIFIED] — FBPVariableDescription完整定义
- ObjectMacros.h L415-480 [VERIFIED] — EPropertyFlags枚举定义
- BlueprintGeneratedClass.h L432-435 [VERIFIED] — BlueprintGeneratedClass类定义
- EdGraphPin.h L76-225 [VERIFIED] — FEdGraphPinType结构（Phase 3已参考）

### Secondary (MEDIUM confidence)
- uasset_read.py L2870-3025 — Phase 3 read_blueprint_variable()实现
- uasset_read.py L3945-4005 — Phase 11 parse_property_value()实现
- Phase 11-06-GAP-SUMMARY.md — ExportMap解析验证状态

### Tertiary (LOW confidence)
- WebSearch未使用 — 所有信息来自UE源码和现有代码

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有依赖已实现或UE源码定义明确
- Architecture: HIGH — FBPVariableDescription序列化顺序已验证
- Pitfalls: HIGH — 基于现有代码分析和Phase 11遗留问题

**Research date:** 2026-05-03
**Valid until:** 30 days — UE蓝图结构稳定，变化风险低