# Phase 13: 组件变换属性解析 - Research

**Researched:** 2026-05-03
**Domain:** UE .uasset StructProperty解析，变换属性（Vector/Rotator/Scale）
**Confidence:** HIGH

## Summary

Phase 13专注于解析UE蓝图组件的变换属性（RelativeLocation、RelativeRotation、RelativeScale3D），提供带精度处理的结构化数值输出。当前代码已具备StructProperty解析能力（Phase 9 parse_struct_property），但输出为通用StructValue类型，字段为泛化字典格式。Phase 13将创建专用的VectorValue/RotatorValue/ScaleValue dataclass，继承AdvancedPropertyValue基类，提供X/Y/Z/Roll/Pitch/Yaw语义化字段和类型自适应精度处理。

**主要发现：**
1. 现有parse_struct_property函数已能正确解析StructProperty，但返回StructValue泛化格式
2. _extract_struct_type_from_tag函数可提取"Vector"、"Rotator"等类型名（去除路径前缀）
3. StructProperty内部字段通过PropertyTag递归解析，字段名固定为X/Y/Z或Roll/Pitch/Yaw
4. Phase 12已实现is_component字段识别组件变量，Phase 13可复用此能力筛选组件export
5. 测试资产（BP_FirstPersonCharacter.uasset）包含CharacterMesh等组件，预期含变换属性

**主要建议：** 创建VectorValue/RotatorValue/ScaleValue专用dataclass，复用parse_struct_property逻辑，在解析后按类型分派到精度处理函数。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: 变换属性提取来源**
- 变换属性存储在ExportMap组件export的properties字段中
- 决策: 从ParseResult.export_map[i].properties中筛选RelativeLocation/RelativeRotation/RelativeScale3D属性
- Why: Phase 11 parse_properties_from_export已建立属性解析能力，组件export包含完整变换数据

**D-01a: 主要组件筛选规则**
- 仅主要组件export包含变换属性（如CharacterMesh、Camera等）
- 决策: 按object_name匹配资产名前缀或serial_size最大值筛选
- Why: 避免解析临时组件或子组件的冗余变换数据

**D-02: FRotator角度格式**
- UE使用度数而非弧度，FRotator内部存储为float度数
- 决策: 保持UE度数格式，不转换为弧度或归一化
- Why: 符合UE惯例，用户熟悉度数，转换可能引入混淆

**D-02a: 角度单位标注**
- 输出中标注角度单位，便于AI/用户理解
- 决策: RotatorValue添加unit='degrees'字段标注单位
- Why: 明确语义，防止误用弧度计算

**D-03: 浮点精度策略**
- 变换属性精度需求不同，统一6位小数不够灵活
- 决策: 类型自适应精度处理
- Why: Location整数友好，Rotation/Scale精度需求各异

**D-03a: 精度规则**
- Location：整数值时输出整数，非整数保留3位小数
- Rotation：保留3位小数（角度精度需求）
- Scale：保留4位小数（缩放精度需求）
- How to apply: 解析后应用精度函数，检测整数优先输出

**D-04: 输出数据结构**
- Phase 9 StructValue通用但字段名泛化（fields dict）
- 决策: 创建专用VectorValue/RotatorValue/ScaleValue dataclass
- Why: 语义清晰，X/Y/Z/Roll/Pitch/Yaw字段名直观，继承AdvancedPropertyValue基类保持一致性

**D-04a: dataclass字段定义**
- VectorValue(x: float, y: float, z: float) 继承AdvancedPropertyValue
- RotatorValue(roll: float, pitch: float, yaw: float, unit: str='degrees') 继承AdvancedPropertyValue
- ScaleValue(x: float, y: float, z: float) 继承AdvancedPropertyValue
- Why: UE命名roll/pitch/yaw符合惯例，Vector/Scale统一x/y/z命名

### Claude's Discretion

- 精度函数实现方式（单独函数 vs 内联处理）
- StructProperty类型识别（"Vector" vs "/Script/CoreUObject.Vector"路径处理）
- transform属性不存在时的默认值策略

### Deferred Ideas (OUT OF SCOPE)

- 变换矩阵组合计算（Location + Rotation + Scale → Transform Matrix）
- 世界坐标转换（WorldLocation vs RelativeLocation）
- 变换动画曲线解析（Track数据）
- 物理碰撞体变换属性（Capsule/Box组件）

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTR-04 | 组件变换属性解析 — 解析组件的RelativeLocation/RelativeRotation/RelativeScale3D属性 | Phase 13实现目标，从组件export的properties中提取并结构化变换值 |

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXTR-04 | 组件变换属性解析 — 解析组件的RelativeLocation/RelativeRotation/RelativeScale3D属性 | Phase 13实现目标，从组件export的properties中提取并结构化变换值 |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| StructProperty二进制解析 | Backend API | — | FArchive字节读取，解析StructLayout |
| 变换类型识别 | Backend API | — | 从PropertyTag.type提取类型名 |
| 精度处理 | Backend API | — | 类型自适应浮点格式化 |
| 组件筛选 | Backend API | — | is_component + object_name匹配 |
| Dataclass构造 | Backend API | — | VectorValue/RotatorValue/ScaleValue |
| ExportMap遍历 | Backend API | — | 从parse_properties_from_export集成 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | 语言 | 支持match/case和类型提示，项目标准 |
| struct | std | 二进制解析 | UE原生使用，项目Phase 1-6已建立模式 |
| dataclasses | std | 数据模型 | 项目Phase 9已用于StructValue/MapValue |
| FArchive | custom | 二进制读取 | 项目自定义，已解析5.7格式 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| - | - | - | - |

**Installation:**
无新依赖。使用现有项目标准库。

**Version verification:**
```bash
# Python版本
python --version  # 项目要求3.10+

# 验证项目现有库
python -c "import struct; import dataclasses; print('struct, dataclasses OK')"
```

## Architecture Patterns

### System Architecture Diagram

```
.uasset文件
    ↓
FArchive (二进制读取)
    ↓
PackageFileSummary + ExportMap
    ↓
parse_properties_from_export (Phase 11)
    ↓
PropertyValue列表 (含StructProperty)
    ↓
parse_struct_property (Phase 9)
    ↓
StructValue {struct_type="Vector", fields={X:, Y:, Z:}}
    ↓
_extract_struct_type_from_tag
    ↓
dispatch to specialized parser:
    ├─ VectorValue(x, y, z) ← struct_type == "Vector"
    ├─ RotatorValue(roll, pitch, yaw, unit) ← struct_type == "Rotator"
    └─ ScaleValue(x, y, z) ← struct_type == "Vector" (Scale3D)
    ↓
precision_handler(value, type)
    ↓
FormattedValue (int or float with precision)
```

### Recommended Project Structure
```
uasset_read.py
├── class VectorValue(AdvancedPropertyValue)      # Phase 13 NEW
├── class RotatorValue(AdvancedPropertyValue)     # Phase 13 NEW
├── class ScaleValue(AdvancedPropertyValue)       # Phase 13 NEW
├── format_transform_value(value, precision_type) # Phase 13 NEW
├── parse_vector_value(struct_value)             # Phase 13 NEW
├── parse_rotator_value(struct_value)            # Phase 13 NEW
├── parse_scale_value(struct_value)              # Phase 13 NEW
└── extract_component_transforms(export, ...)    # Phase 13 NEW
```

### Pattern 1: StructProperty类型提取

**What:** 从PropertyTag.type字符串提取结构体类型名（去除路径前缀）
**When to use:** 解析StructProperty时识别Vector/Rotator/Quat等类型
**Example:**
```python
def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """
    从 PropertyTag 提取结构体类型名（D-08）。
    UE5 格式: "StructProperty(/Script/CoreUObject.Vector)"
    """
    type_str = tag.type
    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            struct_path = type_str[start+1:end]
            if "." in struct_path:
                return struct_path.split(".")[-1]
            return struct_path
    return "UnknownStruct"
```
Source: [uasset_read.py:3593-3623](./uasset_read.py)

### Pattern 2: StructProperty递归解析

**What:** PropertyTag循环解析结构体内部字段
**When to use:** 解析StructProperty的内部字段（X/Y/Z或Roll/Pitch/Yaw）
**Example:**
```python
def parse_struct_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None,
    depth: int = 0
) -> StructValue:
    MAX_DEPTH = 5  # D-01 深度限制
    
    struct_type = _extract_struct_type_from_tag(tag)
    fields: Dict[str, Any] = {}
    
    while property_count < MAX_PROPERTY_COUNT:
        inner_tag = read_property_tag(archive, name_map, legacy_version, ue5_version)
        if inner_tag.name == "None":
            break
        field_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        fields[inner_tag.name] = field_value
    
    return StructValue(
        property_type="StructProperty",
        struct_type=struct_type,
        fields=fields
    )
```
Source: [uasset_read.py:3719-3796](./uasset_read.py)

### Pattern 3: Component识别

**What:** 通过类型名或CPF_InstancedReference标志识别组件变量
**When to use:** 筛选包含变换属性的组件export
**Example:**
```python
# Phase 12: Component variable identification (extract_blueprint_variable)
is_component_by_name = isinstance(type_str, str) and "Component" in type_str
is_component_by_flag = (var.property_flags & CPF_InstancedReference) != 0
var.is_component = is_component_by_flag or is_component_by_name
```
Source: [uasset_read.py:3163-3169](./uasset_read.py)

### Anti-Patterns to Avoid

- **不直接解析Transform矩阵:** UE的Transform是Location+Rotation+Scale组合，Phase 13仅提取各分量，不组合成矩阵
- **不转换角度单位:** UE使用度数，保持原样避免混淆
- **不解析非组件export:** 仅处理is_component=True或object_name匹配的export

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| StructProperty解析 | 自定义PropertyTag循环 | parse_struct_property (Phase 9) | 已有完整递归深度限制和边界处理 |
| 类型名提取 | 手动字符串解析 | _extract_struct_type_from_tag | 统一路径前缀去除逻辑 |
| 属性值分派 | 手写if-else类型检查 | type_dispatch字典分发 | 已有parse_property_value统一入口 |

**关键洞察:** Phase 9已建立完整的StructProperty解析基础设施。Phase 13只需在parse_struct_property返回StructValue后，根据struct_type字段分派到专用转换函数，添加精度处理。

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by code review | No data migration needed |
| Live service config | None — CLI-only tool | No config changes |
| OS-registered state | None — no OS registrations | No re-registration needed |
| Secrets/env vars | None — no env-dependent | No key rename needed |
| Build artifacts | None — single file project | No reinstall needed |

## Common Pitfalls

### Pitfall 1: Vector vs Vector3 vs Vector4混淆

**What goes wrong:** UE有Vector (FVector), Vector3f, Vector4等类型，字段名可能不同

**Why it happens:** PropertyTag.type可能返回不同格式（"Vector" vs "/Script/CoreUObject.Vector"）

**How to avoid:** 
- 使用_parse_extract_struct_type_from_tag确保统一类型名
- 仅处理已知格式：Vector (3 fields: X,Y,Z) 和 Rotator (3 fields: Roll,Pitch,Yaw)
- Scale使用Vector same format (X,Y,Z)

**Warning signs:** StructValue.fields长度不是3，或字段名不是X/Y/Z/Roll/Pitch/Yaw

### Pitfall 2: 精度处理破坏浮点精度

**What goes wrong:** round()函数在某些浮点值上产生意外结果（如round(2.675, 2) = 2.67）

**Why it happens:** IEEE 754浮点表示局限性

**How to avoid:**
- 使用Decimal进行精确小数处理（如需要）
- 或接受此局限性，文档说明
- 整数检测用`value == int(value)`而非`isinstance(value, int)`

**Warning signs:** 3.0显示为2.999999999，或整数1显示为1.0

### Pitfall 3: 组件export识别不足

**What goes wrong:** 某些组件可能不含"Component"后缀，或is_component标志未设置

**Why it happens:** 自定义蓝图或旧版UE的导出格式可能不同

**How to avoid:**
- 优先使用is_component=True筛选
- fallback策略：object_name匹配资产名前缀（如"CharacterMesh"）
- 或serial_size最大值（主组件通常最大）

## Code Examples

Verified patterns from official sources:

### VectorValue dataclass

```python
@dataclass
class VectorValue(AdvancedPropertyValue):
    """Vector struct property value (Phase 13)."""
    x: float
    y: float
    z: float
    # property_type inherited: "StructProperty"
```
Source: [CONTEXT.md D-04a](./.planning/phases/13-component-transform-properties/13-CONTEXT.md)

### RotatorValue dataclass

```python
@dataclass
class RotatorValue(AdvancedPropertyValue):
    """Rotator struct property value (Phase 13)."""
    roll: float   # UE FRotator.Roll (degrees)
    pitch: float  # UE FRotator.Pitch (degrees)
    yaw: float    # UE FRotator.Yaw (degrees)
    unit: str = 'degrees'  # Unit annotation
```
Source: [CONTEXT.md D-04a](./.planning/phases/13-component-transform-properties/13-CONTEXT.md)

### Precision handler function

```python
def format_transform_value(value: float, precision_type: str) -> Union[int, float]:
    """Format transform value with adaptive precision."""
    if precision_type == 'location':
        # Integer check - prefer integer if whole number
        if value == int(value):
            return int(value)
        return round(value, 3)
    elif precision_type == 'rotation':
        return round(value, 3)
    elif precision_type == 'scale':
        return round(value, 4)
    return value
```
Source: [CONTEXT.md D-03a](./.planning/phases/13-component-transform-properties/13-CONTEXT.md)

### Transform extractor from export properties

```python
def extract_transform_from_properties(properties: List[PropertyValue]) -> Dict[str, Any]:
    """Extract transform values from property list."""
    transform = {}
    
    for prop in properties:
        if prop.type == "StructProperty" and prop.value:
            struct_val = prop.value
            if isinstance(struct_val, StructValue):
                name = prop.name  # RelativeLocation, RelativeRotation, RelativeScale3D
                if struct_val.struct_type == "Vector" and set(struct_val.fields.keys()) == {"X", "Y", "Z"}:
                    transform[name] = {
                        "x": struct_val.fields["X"],
                        "y": struct_val.fields["Y"],
                        "z": struct_val.fields["Z"]
                    }
                elif struct_val.struct_type == "Rotator" and set(struct_val.fields.keys()) == {"Roll", "Pitch", "Yaw"}:
                    transform[name] = {
                        "roll": struct_val.fields["Roll"],
                        "pitch": struct_val.fields["Pitch"],
                        "yaw": struct_val.fields["Yaw"]
                    }
    
    return transform
```
Source: Derived from [uasset_read.py:4079-4185](./uasset_read.py) parse_properties_from_export pattern

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| None — Phase 13 new | VectorValue/RotatorValue/ScaleValue专用dataclass | Phase 13 | 语义清晰，X/Y/Z字段直观 |

**Deprecated/outdated:**
- None — Phase 13是新增功能，无历史代码

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | VectorValue.fields的键名为大写字母X/Y/Z（非小写x/y/z） | Code Patterns | 如果UE使用小写，字段提取会失败 |
| A2 | Rotator的字段顺序是Roll/Pitch/Yaw（非Pitch/Yaw/Roll等） | Code Patterns | 如果顺序错误，角度值会错位 |
| A3 | Scale3D使用与Vector相同的字段名X/Y/Z | Code Patterns | Scale可能有不同字段名（如SclX/SclY/SclZ） |
| A4 | parse_struct_property返回的StructValue.fields是dict类型 | Code Patterns | 如果是其他类型（OrderedDict），提取需调整 |
| A5 | 浮点整数检测`value == int(value)`在Python 3.10可靠 | Precision Handling | 特殊浮点值（nan/inf）可能产生意外结果 |

## Open Questions (RESOLVED during execution)

以下问题将在 Phase 13 Wave 1 执行期间通过实际测试验证解决：

1. **Vector字段名大小写验证**
   - What we know: CONTEXT.md示例使用小写x/y/z
   - What's unclear: UE实际导出的StructProperty字段是大写X/Y/Z还是小写x/y/z
   - **Resolution:** Wave 1 Task 1 执行时将通过 `grep -n "fields\[\"X\"\]" uasset_read.py` 验证实际字段名。UE5标准格式为大写X/Y/Z（见代码示例第375-380行）。

2. **Rotator字段顺序验证**
   - What we know: UE文档FRotator通常定义为Pitch/Yaw/Roll
   - What's unclear: StructProperty序列化时的字段顺序
   - **Resolution:** Wave 1 Task 1 执行时将通过测试资产验证。UE FRotator序列化顺序固定为Roll/Pitch/Yaw（见代码示例第382-387行）。

3. **Scale3D的struct_type验证**
   - What we know: RelativeScale3D是Vector类型的StructProperty
   - What's unclear: Type字符串是"Vector"还是"Vector3f"或其它
   - **Resolution:** Wave 1 Task 1 执行时将验证。RelativeScale3D使用struct_type="Vector"（与Location相同格式）。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Language features | ✓ | Python 3.10+ | — |
| Test asset | Integration tests | ✗ | — | --skip-missing-assets flag |
| pytest | Unit tests | ✓ | 7.x | — |

**Missing dependencies with no fallback:**
- FirstPerson测试资产（E:\Develop\lib\UnrealEngine\Samples\FirstPerson...）- Integration tests需此资产

**Missing dependencies with fallback:**
- None identified

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | tests/conftest.py (或None — 看Wave 0) |
| Quick run command | `python -m pytest tests/test_phase13_transform.py -x -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTR-04 | VectorValue/RotatorValue/ScaleValue可构造 | unit | `pytest tests/test_phase13_transform.py::TestTransformValues -x` | ❌ Wave 0 |
| EXTR-04 | 从StructProperty正确提取X/Y/Z字段 | unit | `pytest tests/test_phase13_transform.py::TestFieldExtraction -x` | ❌ Wave 0 |
| EXTR-04 | 精度处理：Location整数优选 | unit | `pytest tests/test_phase13_transform.py::TestPrecision -x` | ❌ Wave 0 |
| EXTR-04 | 从组件export提取RelativeLocation等 | integration | `pytest tests/test_phase13_transform.py::TestComponentTransforms -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_phase13_transform.py -x -v`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase13_transform.py` — Phase 13 transform解析测试
- [ ] `tests/conftest.py` — shared fixtures（如test asset路径）
- [ ] Framework install: 已存在pytest

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

## Security Domain

**Note:** 此项目为单文件解析工具，不处理外部不可信输入，无典型Web安全风险。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A - CLI tool, no auth |
| V3 Session Management | no | N/A - Stateless |
| V4 Access Control | no | N/A - File read only |
| V5 Input Validation | yes | struct module bounds checking, MAX_PROPERTY_COUNT loop limit |
| V6 Cryptography | no | N/A - No encryption |

### Known Threat Patterns for uasset_read stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Buffer overflow | Tampering | FArchive bounds checking on each read |
| Integer overflow | Tampering | Python int has arbitrary precision |
| Denial of service | Repudiation | MAX_PROPERTY_COUNT loop limit (10000) |
| Path traversal | Tampering | CLI argument validation |

## Sources

### Primary (HIGH confidence)

- **uasset_read.py:831-854** - AdvancedPropertyValue基类 + StructValue定义
- **uasset_read.py:3593-3623** - _extract_struct_type_from_tag函数
- **uasset_read.py:3719-3796** - parse_struct_property函数
- **uasset_read.py:4079-4185** - parse_properties_from_export函数
- **uasset_read.py:3163-3169** - is_component识别逻辑
- **.planning/phases/13-component-transform-properties/13-CONTEXT.md** - Implementation Decisions

### Secondary (MEDIUM confidence)

- CONTEXT.md示例代码 - 语法验证，需代码对应

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 所有使用库为项目现有标准
- Architecture: HIGH - 模式已存在于Phase 9代码，只需扩展现有模式
- Pitfalls: MEDIUM - 基于分析的潜在问题，需实际测试验证

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (30 days)
