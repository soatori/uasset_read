---
phase: 02-property-parsing
plan: 04
type:WaveStructure
wave: 0
depends_on: []
files_modified: []
autonomous: false
requirements_addressed: []
---

# Phase 2 Wave 结构

## 概览

Phase 2 由 **3 个执行计划** 分布在 **3 个 wave** 中，以实现最优并行化。

| Wave | 计划 | 描述 | 自动执行 |
|------|------|------|----------|
| 1 | 02-01 | PropertyTag 解析 + 基本类型解析器 | 是 |
| 2 | 02-02 | ObjectProperty + ArrayProperty + 导出循环 | 是 |
| 3 | 02-03 | 版本感知解析 + 标志处理 | 是 |

## 依赖关系

```
02-01 (Wave 1)
├── PropertyTag dataclass
├── PropertyValue dataclass
├── read_property_tag (UE5 格式)
├── parse_int_property
├── parse_float_property
├── parse_bool_property
├── parse_str_property
├── parse_name_property
└── PropertyTag 标志常量

02-02 (Wave 2) ──────┐
├── parse_object_property            │
├── parse_array_property (需要 02-01)───┘
├── parse_property_value (分派)
└── parse_properties_from_export

02-03 (Wave 3) ──────┐
├── read_property_tag (UE4 格式)   │
├── 版本阈值检查                    │
├── HasPropertyGuid 标志处理        │
├── HasArrayIndex 标志处理          │
└── 集成测试
```

## Wave 1 详情 (02-01)

**独立计划:** FArchive 设置后的所有自包含内容

**修改文件:** uasset_read.py, tests/test_property_parsing.py

**任务:**
1. PropertyTag 和 PropertyValue dataclasses
2. read_property_tag (UE5 格式)
3. parse_bool_property
4. parse_int_property / parse_float_property
5. parse_str_property / parse_name_property
6. PropertyTag 标志常量
7. 单元测试 (test_property_parsing.py)

**Wave 要求:** 无依赖 - 可并行运行

## Wave 2 详情 (02-02)

**依赖:** 02-01 必须先完成

**原因:** parse_array_property, parse_properties_from_export 需要:
- PropertyTag dataclass (02-01)
- 所有基本类型解析器 (02-01)

**修改文件:** uasset_read.py, tests/test_property_parsing.py

**任务:**
1. parse_object_property
2. parse_array_property
3. parse_properties_from_export
4. PROPERTY_PARSERS 分派表
5. ObjectProperty 测试
6. ArrayProperty 测试

**Wave 要求:** 02-01 完成后开始

## Wave 3 详情 (02-03)

**依赖:** 02-02 必须先完成

**原因:** 完整 PropertyTag 解析需要:
- 完整导出属性循环 (02-02)
- 所有类型特定解析器 (02-01, 02-02)

**修改文件:** uasset_read.py, tests/test_property_parsing.py

**任务:**
1. 版本阈值辅助函数 (use_complete_type_name)
2. read_property_tag (UE4 格式)
3. read_property_tag (UE5 格式) - 完整标志处理
4. PropertyTag 标志常量
5. 集成测试 (版本检测, 标志)

**Wave 要求:** 02-01, 02-02 完成后开始

## 执行顺序

```
/gsd-execute-phase 02-01  # Wave 1 - 属性基础设施
   ↓
/gsd-execute-phase 02-02  # Wave 2 - 高级属性类型
   ↓
/gsd-execute-phase 02-03  # Wave 3 - 版本感知解析
```

## 测试策略

| Wave | 测试 | 触发时机 |
|------|------|----------|
| 1 | test_property_tag_*, test_*_property | 每个解析器添加后 |
| 2 | test_object_property, test_array_property* | ArrayProperty 添加后 |
| 3 | 集成测试 (真实资产) | 所有解析器完成 |

## 各 Wave Grep 检查点

**Wave 1:**
```bash
grep -c "@dataclass" uasset_read.py >= 10  # PropertyTag, PropertyValue
grep -c "def parse_.*_property" uasset_read.py >= 7  # 基本类型解析器
grep -c "def read_property_tag" uasset_read.py >= 1
```

**Wave 2:**
```bash
grep -c "def parse_array_property\|def parse_object_property" uasset_read.py >= 2
grep -c "PROPERTY_PARSERS\[" uasset_read.py >= 1
grep -c "def parse_properties_from_export" uasset_read.py >= 1
```

**Wave 3:**
```bash
grep -c "def use_complete_type_name" uasset_read.py >= 1
grep -c "def read_property_tag_ue" uasset_read.py >= 2
grep -c "PROP_TAG_" uasset_read.py >= 7  # 所有标志常量
```

## 成功标准

| Wave | 交付物 | 验证 |
|------|--------|------|
| 1 | PropertyTag + 基本类型 | test_property_parsing.py: 7+ 测试通过 |
| 2 | ObjectProperty + ArrayProperty | 所有数组子类型测试通过 |
| 3 | 版本处理 + 标志 | 版本检测测试通过 |

---

*Wave 结构创建: 2026-05-01*