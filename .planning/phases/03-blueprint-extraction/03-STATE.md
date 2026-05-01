---
phase: 03
slug: blueprint-extraction
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 3: 蓝图提取 - 状态

**已规划：** 2026-05-01

---

## 当前阶段状态

**阶段 3：蓝图提取**

- **状态：** ● 已规划（3 个计划，10 个任务）
- **目标：** 检测蓝图资产并提取蓝图特定元数据（变量、父类）
- **需求覆盖：** BLUE-01, BLUE-02, BLUE-03, BLUE-04, BLUE-05, BLUE-06

---

## 计划摘要

| 计划 | 对象 | 任务 | 文件 | 要求 |
|------|------|------|------|------|
| 03-01-PLAN.md | core | 4 | uasset_read.py | BLUE-01, BLUE-02 |
| 03-02-PLAN.md | extraction | 3 | uasset_read.py | BLUE-03, BLUE-05 |
| 03-03-PLAN.md | integration | 3 | uasset_read.py | BLUE-06 |

---

## 波结构

| 波 | 计划 | 自主 | 任务 |
|------|-------|------------|------|
| 1 | 03-01 | 是 | detect_blueprint(), resolve_parent_class() |
| 1 | 03-02 | 是 | read_ed_graph_pin_type(), read_blueprint_variable() |
| 1 | 03-03 | 是 | extract_blueprint_metadata() |

**说明：** 所有计划在波 1 中并行执行，因为它们是模块化的，只依赖于 Phase 1/2 的结构（FArchive、ObjectExport、PackageIndex）。

---

## 必须完成项

### BLUE-01: 蓝图资产检测
- 从 ExportMap 的 ClassIndex 检测蓝图资产
- 类名包含 "Blueprint" 关键字
- 检测失败时添加到 ParseResult.errors

### BLUE-02: 父类解析
- 提取蓝图父类（ParentClass 引用）
- 仅解析直接父类（无继承链）
- FPackageIndex 解析为 ImportMap/ExportMap 中的对象名

### BLUE-03: 变量定义提取
- 从 FBPVariableDescription 提取变量定义
- 变量名称、类型、默认值
- DefaultValue 字符串解析为 Python 原生类型

### BLUE-05: FEdGraphPinType 解析
- 完整 FEdGraphPinType 结构解析
- PinCategory、PinSubCategory、PinSubCategoryObject
- ContainerType (None/Array/Set/Map)

### BLUE-06: 变量元数据提取
- Category、PropertyFlags 提取
- MetaDataArray（延迟到 v2）

---

## 测试计划

### Wave 0 - 测试基础设施
- [ ] `tests/test_blueprint_extraction.py` - Blue-01 至 Blue-06 的存根
- [ ] `tests/conftest.py` - Mock 蓝图 .uasset 数据夹具

### Wave 1 - 单元测试
- [ ] test_blueprint_detection
- [ ] test_parent_class_resolution  
- [ ] test_variable_parsing
- [ ] test_pin_type_parsing
- [ ] test_variable_metadata

---

## 依赖关系

- **阶段 1：** 需要 PackageFileSummary、NameMap、ExportMap、ImportMap
- **阶段 2：** 需要属性解析来获取变量值

---

## 关键数据结构

```python
@dataclass
class FEdGraphPinType:
    pin_category: str = ""  # FName
    pin_sub_category: str = ""  # FName
    pin_sub_category_object: int = 0  # FPackageIndex
    container_type: int = 0  # EPinContainerType
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False

@dataclass
class BlueprintVariable:
    var_name: str
    var_type: FEdGraphPinType
    category: str
    property_flags: int
    default_value: any = None
    friendly_name: str = ""

@dataclass
class BlueprintMetadata:
    is_blueprint: bool
    parent_class: Optional[str] = None
    variables: List[BlueprintVariable] = field(default_factory=list)
    detection_warning: Optional[str] = None
```

---

## 风险和缓解

| 风险 | 缓解 |
|------|------|
| 蓝图序列化变体 | 从 UE 5.7 源码验证序列化顺序 |
| 变量类型复杂性 | D-06：ContainerType + 元素类型格式 |
| 默认值解析 | D-13：基本类型解析，失败 fallback |

---

## 下一步动作

```
/gsd-execute-phase 3  —— 执行 Phase 3 计划
```

---

## 元数据

- **创建日期：** 2026-05-01
- **最后更新：** 2026-05-01（规划完成）
- **状态：** 待执行
