# Phase 12: BlueprintVariables完整提取 - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Source:** ROADMAP.md definition + Phase 11 completion

<domain>
## Phase Boundary

Phase 12专注于从Blueprint解析中提取完整的变量信息，建立在Phase 11 ExportMap属性提取能力之上。

**输入:** ParseResult对象（Phase 11已建立export.properties提取）
**输出:** ParseResult.blueprint.variables完整结构，包含is_component标识

**关键依赖:**
- Phase 11的parse_properties_from_export功能（已验证工作）
- ExportMap解析正确（Phase 11 gap closure已修复版本常量）

</domain>

<decisions>
## Implementation Decisions

### D-01: 变量信息来源
- 变量信息来自ExportMap中BlueprintGeneratedClass类型的export条目
- 需要解析该export的properties以提取变量定义
- **决策:** 从export.properties中识别变量属性类型

### D-02: 组件变量识别标准
- 组件变量通过类型名称识别：类型名以"Component"结尾
- 典型组件类型：SkeletalMeshComponent, StaticMeshComponent, CameraComponent等
- **决策:** 添加is_component布尔字段，基于类型名contains("Component")判断

### D-03: 变量元数据来源
- 元数据（Category、BlueprintReadWrite等）存储在PropertyTag的property_flags中
- 需要解析EPropertyFlags标志位
- **决策:** 在PropertyValue中添加flags字段解析

### D-04: 类型显示格式
- 类型完整显示需要处理泛型（TArray、TMap、TSet）
- PinValueType结构已实现，可复用
- **决策:** 使用现有pin_type解析逻辑，增强为完整类型字符串

### D-05: 默认值类型覆盖
- Phase 11已支持多种PropertyType解析
- 需确保FloatProperty、BoolProperty、StrProperty、StructProperty、ObjectProperty覆盖
- **决策:** 验证Phase 11属性解析器覆盖度

### Claude's Discretion
- 变量列表构建时机：parse_uasset()结尾或作为独立函数
- 多个蓝图export的处理：如何确定主蓝图Class
- 元数据格式：字段列表vs字典结构

</decisions>

<canonical_refs>
## Canonical References

**Phase 11成果（前置依赖）:**
- `.planning/phases/11-exportmap-property-extraction/11-06-GAP-SUMMARY.md` — ExportMap解析修复完成
- `uasset_read.py:3829` — parse_properties_from_export函数
- `uasset_read.py:513` — resolve_package_index_to_reference函数

**需求定义:**
- `.planning/REQUIREMENTS.md` — EXTR-02, EXTR-03, EXTR-05定义

**代码参考:**
- `uasset_read.py:930-960` — PropertyTag结构和flags定义
- `uasset_read.py:1000-1100` — PinValueType和类型解析
- `uasset_read.py:4045` — ExportMap属性解析集成点

</canonical_refs>

<specifics>
## Specific Ideas

**蓝图变量典型结构:**
```python
class BlueprintVariable:
    name: str              # 变量名
    type: str              # 完整类型（如"TArray<UObject*>")
    default_value: Any     # 默认值
    is_component: bool     # 是否组件变量
    flags: List[str]       # 元数据标签列表
    category: str          # 分类路径
```

**组件类型识别规则:**
- 类型名.endswith("Component")
- 特殊类型：ChildActorComponent, WidgetComponent等

**元数据flag解析:**
- CPF_Edit → EditAnywhere
- CPF_BlueprintVisible → BlueprintReadWrite
- CPF_Protected → Protected
- CPF_Category → Category字符串

</specifics>

<deferred>
## Deferred Ideas

- 变量分组显示（按Category组织）
- 变量依赖图构建（变量间引用关系）
- 动态变量识别（RunTime变量vs编辑器变量）

None for Phase 12 scope.

</deferred>

---

*Phase: 12-blueprint-variables-extraction*
*Context gathered: 2026-05-03 via ROADMAP derivation*