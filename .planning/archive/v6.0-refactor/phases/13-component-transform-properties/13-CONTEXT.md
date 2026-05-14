# Phase 13: 组件变换属性解析 - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Source:** ROADMAP.md definition + Phase 12 completion

<domain>
## Phase Boundary

Phase 13专注于解析组件的变换属性（Location、Rotation、Scale），提供准确的浮点数值输出。

**输入:** ExportMap中主要组件export的properties（Phase 11 parse_properties_from_export已工作）
**输出:** VectorValue/RotatorValue/ScaleValue专用dataclass，带精度处理和单位标注

**关键依赖:**
- Phase 11的parse_properties_from_export功能（已验证工作）
- Phase 12的is_component组件识别能力（已实现）
- Phase 9的AdvancedPropertyValue基类设计（可继承）

</domain>

<decisions>
## Implementation Decisions

### D-01: 变换属性提取来源
- 变换属性存储在ExportMap组件export的properties字段中
- **决策:** 从ParseResult.export_map[i].properties中筛选RelativeLocation/RelativeRotation/RelativeScale3D属性
- **Why:** Phase 11 parse_properties_from_export已建立属性解析能力，组件export包含完整变换数据

### D-01a: 主要组件筛选规则
- 仅主要组件export包含变换属性（如CharacterMesh、Camera等）
- **决策:** 按object_name匹配资产名前缀或serial_size最大值筛选
- **Why:** 避免解析临时组件或子组件的冗余变换数据

### D-02: FRotator角度格式
- UE使用度数而非弧度，FRotator内部存储为float度数
- **决策:** 保持UE度数格式，不转换为弧度或归一化
- **Why:** 符合UE惯例，用户熟悉度数，转换可能引入混淆

### D-02a: 角度单位标注
- 输出中标注角度单位，便于AI/用户理解
- **决策:** RotatorValue添加unit='degrees'字段标注单位
- **Why:** 明确语义，防止误用弧度计算

### D-03: 浮点精度策略
- 变换属性精度需求不同，统一6位小数不够灵活
- **决策:** 类型自适应精度处理
- **Why:** Location整数友好，Rotation/Scale精度需求各异

### D-03a: 精度规则
- **决策:** 
  - Location：整数值时输出整数，非整数保留3位小数
  - Rotation：保留3位小数（角度精度需求）
  - Scale：保留4位小数（缩放精度需求）
- **How to apply:** 解析后应用精度函数，检测整数优先输出

### D-04: 输出数据结构
- Phase 9 StructValue通用但字段名泛化（fields dict）
- **决策:** 创建专用VectorValue/RotatorValue/ScaleValue dataclass
- **Why:** 语义清晰，X/Y/Z/Roll/Pitch/Yaw字段名直观，继承AdvancedPropertyValue基类保持一致性

### D-04a: dataclass字段定义
- **决策:**
  - VectorValue(x: float, y: float, z: float) 继承AdvancedPropertyValue
  - RotatorValue(roll: float, pitch: float, yaw: float, unit: str='degrees') 继承AdvancedPropertyValue
  - ScaleValue(x: float, y: float, z: float) 继承AdvancedPropertyValue
- **Why:** UE命名roll/pitch/yaw符合惯例，Vector/Scale统一x/y/z命名

### Claude's Discretion
- 精度函数实现方式（单独函数 vs 内联处理）
- StructProperty类型识别（"Vector" vs "/Script/CoreUObject.Vector"路径处理）
- transform属性不存在时的默认值策略

</decisions>

<canonical_refs>
## Canonical References

**Phase 11成果（前置依赖）:**
- `.planning/phases/11-exportmap-property-extraction/11-06-GAP-SUMMARY.md` — ExportMap解析修复完成
- `uasset_read.py:3829` — parse_properties_from_export函数
- `uasset_read.py:3719-3796` — parse_struct_property函数（Phase 9）

**需求定义:**
- `.planning/REQUIREMENTS.md` — EXTR-04定义

**代码参考:**
- `uasset_read.py:830-855` — AdvancedPropertyValue基类 + StructValue定义
- `uasset_read.py:3593-3623` — _extract_struct_type_from_tag函数
- `uasset_read.py:4930-4950` — __all__导出列表

</canonical_refs>

<specifics>
## Specific Ideas

**VectorValue dataclass示例:**
```python
@dataclass
class VectorValue(AdvancedPropertyValue):
    """Vector struct property value (Phase 13)."""
    x: float
    y: float
    z: float
    # property_type inherited: "StructProperty"
```

**RotatorValue dataclass示例:**
```python
@dataclass
class RotatorValue(AdvancedPropertyValue):
    """Rotator struct property value (Phase 13)."""
    roll: float   # UE FRotator.Roll (degrees)
    pitch: float  # UE FRotator.Pitch (degrees)
    yaw: float    # UE FRotator.Yaw (degrees)
    unit: str = 'degrees'  # Unit annotation
```

**精度处理函数示例:**
```python
def format_transform_value(value: float, precision_type: str) -> float:
    """Format transform value with adaptive precision."""
    if precision_type == 'location':
        # Integer check
        if value == int(value):
            return int(value)
        return round(value, 3)
    elif precision_type == 'rotation':
        return round(value, 3)
    elif precision_type == 'scale':
        return round(value, 4)
    return value
```

**StructProperty类型识别:**
- Vector: "/Script/CoreUObject.Vector" → "Vector"
- Rotator: "/Script/CoreUObject.Rotator" → "Rotator"

</specifics>

<deferred>
## Deferred Ideas

- 变换矩阵组合计算（Location + Rotation + Scale → Transform Matrix）
- 世界坐标转换（WorldLocation vs RelativeLocation）
- 变换动画曲线解析（Track数据）
- 物理碰撞体变换属性（Capsule/Box组件）

None for Phase 13 scope.

</deferred>

---

*Phase: 13-component-transform-properties*
*Context gathered: 2026-05-03 via discuss-phase workflow*