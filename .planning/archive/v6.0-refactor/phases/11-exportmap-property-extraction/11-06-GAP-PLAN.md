---
phase: 11-exportmap-property-extraction
plan: 06
type: execute
wave: 2
depends_on:
  - 11-05
files_modified:
  - uasset_read.py
  - tests/test_exportmap_properties.py
requirements_addressed:
  - EXTR-01
gap_closure: true
autonomous: true
user_setup: []
must_haves:
  truths:
    - "parse_properties_from_export成功解析ExportMap条目的属性"
    - "properties字段包含非Error类型的PropertyValue"
    - "ObjectProperty返回解析后的对象引用（raw_index + resolved）"
    - "SoftObjectProperty返回asset_path和sub_path"
  artifacts:
    - path: "tests/test_exportmap_properties.py"
      provides: "端到端验证EXTR-01成功标准"
      exports: ["test_extr_01_success_criterion_*"]
  key_links:
    - from: "parse_uasset()"
      to: "export.properties"
      via: "parse_properties_from_export(export)"
      pattern: "for export in result.export_map"
---

# Plan 11-06: 验证ExportMap属性解析功能完整

**Objective:** 确认修复ScriptSerialization条件后，parse_properties_from_export能正确解析属性值，验证EXTR-01成功标准达成

**Purpose:** 端到端验证Phase 11核心功能，确保ExportMap属性值可读取

## Gap分析

**VERIFICATION.md发现的gap:**
- ExportMap属性解析代码存在，单元测试通过
- 但实际资产解析失败，所有properties为Error类型
- 原因：serial_offset异常导致parse_properties_from_export无法seek

**修复后预期:**
- 11-05修复后serial_offset正常
- parse_properties_from_export能seek到正确位置
- 属性值能正确解析

## Context

@E:/Develop/uasset_read/.planning/STATE.md
@E:/Develop/uasset_read/.planning/phases/11-exportmap-property-extraction/11-05-GAP-PLAN.md
@E:/Develop/uasset_read/.planning/phases/11-exportmap-property-extraction/11-RESEARCH.md

<interfaces>
<!-- 属性解析关键函数 -->

From uasset_read.py:3829:
```python
def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None
) -> List[PropertyValue]:
```

From uasset_read.py:513:
```python
def resolve_package_index_to_reference(
    pkg_idx: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str]
) -> Optional[Dict[str, Any]]:
```

From uasset_read.py:3230:
```python
def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, str]:
```

From uasset_read.py:4045:
```python
# Phase 11: 解析ExportMap属性
for export in result.export_map:
    if export.serial_size > 0:
        try:
            export.properties = parse_properties_from_export(...)
```
</interfaces>

## Tasks

<task type="auto">
  <name>Task 1: 验证parse_properties_from_export功能正常</name>
  <files>uasset_read.py (验证)</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (lines 3829-3919: parse_properties_from_export函数)
    - E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset
  </read_first>
  <behavior>
    - Test: parse_properties_from_export返回非空列表
    - Test: PropertyValue类型正确（非ParseError）
    - Test: 属性名和类型正确识别
  </behavior>
  <action>
验证修复后属性解析功能正常工作：

```python
# 验证脚本
from uasset_read import FArchive, read_package_summary, read_name_table, read_import_map, read_export_map, parse_properties_from_export

path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'

archive = FArchive(path)
summary = read_package_summary(archive)
name_map = read_name_table(archive, summary)
import_map = read_import_map(archive, summary, name_map)
export_map = read_export_map(archive, summary, name_map)

print(f'文件大小: {archive._file_size}')
print(f'ExportMap条目数: {len(export_map)}')

# 查找有serial_size的export
for i, exp in enumerate(export_map):
    if exp.serial_size > 0 and exp.serial_offset <= archive._file_size:
        print(f'解析 Export #{i}: {exp.object_name}')
        print(f'  serial_offset: {exp.serial_offset}')
        print(f'  serial_size: {exp.serial_size}')
        
        try:
            props = parse_properties_from_export(exp, archive, summary, name_map, export_map, import_map)
            print(f'  properties数量: {len(props)}')
            for p in props[:3]:
                print(f'    {p.name}: {p.type}')
                if not isinstance(p.value, (Exception, str)) and 'Error' not in str(type(p.value)):
                    print(f'      value: {str(p.value)[:80]}')
        except Exception as e:
            print(f'  解析错误: {e}')
        break
```

预期结果：
- parse_properties_from_export成功返回属性列表
- PropertyValue.value非Error类型
- 属性名和类型正确（如FloatProperty、ObjectProperty等）
  </action>
  <verify>
    <automated>python -c "from uasset_read import parse_uasset; r=parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'); has_props=any(len(e.properties)>0 and not any('Error' in str(type(p.value)) for p in e.properties) for e in r.export_map); print('HAS_VALID_PROPS:', has_props)"</automated>
  </verify>
  <done>parse_properties_from_export成功解析MM_Death_Back_01.uasset的ExportMap属性，返回非Error类型PropertyValue</done>
</task>

<task type="auto">
  <name>Task 2: 验证ObjectProperty解析返回解析后引用</name>
  <files>uasset_read.py (验证)</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (lines 3906-3912: ObjectProperty后处理)
    - E:/Develop/uasset_read/uasset_read.py (lines 513-570: resolve_package_index_to_reference函数)
  </read_first>
  <behavior>
    - Test: ObjectProperty返回Dict而非int32
    - Test: Dict包含raw_index和resolved字段
    - Test: resolved包含class_name/object_name或为None
  </behavior>
  <action>
验证ObjectProperty增强解析功能：

```python
from uasset_read import parse_uasset

path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'
r = parse_uasset(path)

# 查找ObjectProperty类型的属性
for exp in r.export_map:
    for prop in exp.properties:
        if prop.type == "ObjectProperty":
            print(f'{exp.object_name}.{prop.name}: {prop.type}')
            print(f'  value类型: {type(prop.value).__name__}')
            if isinstance(prop.value, dict):
                print(f'  raw_index: {prop.value.get("raw_index")}')
                resolved = prop.value.get("resolved")
                if resolved:
                    print(f'  resolved.type: {resolved.get("type")}')
                    print(f'  resolved.class_name: {resolved.get("class_name")}')
                    print(f'  resolved.object_name: {resolved.get("object_name")}')
                else:
                    print(f'  resolved: None (null reference)')
            else:
                print(f'  value: {prop.value} (旧格式，需检查)')
            break
```

预期结果：
- ObjectProperty.value为Dict格式
- 包含raw_index（原始int32）
- 包含resolved（解析后的引用信息或None）
  </action>
  <verify>
    <automated>python -c "from uasset_read import parse_uasset; r=parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'); obj_props=[p for e in r.export_map for p in e.properties if p.type=='ObjectProperty']; has_dict=any(isinstance(p.value, dict) for p in obj_props) if obj_props else True; print('OBJECTPROP_DICT:', has_dict)"</automated>
  </verify>
  <done>ObjectProperty类型属性返回Dict格式包含raw_index和resolved字段</done>
</task>

<task type="auto">
  <name>Task 3: 验证SoftObjectProperty解析返回asset_path</name>
  <files>uasset_read.py (验证)</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (lines 3230-3250: parse_soft_object_property函数)
    - E:/Develop/uasset_read/uasset_read.py (lines 3989: SoftObjectProperty分派注册)
  </read_first>
  <behavior>
    - Test: SoftObjectProperty返回Dict
    - Test: Dict包含asset_path和sub_path字段
    - Test: asset_path为字符串路径格式
  </behavior>
  <action>
验证SoftObjectProperty解析功能：

```python
from uasset_read import parse_uasset

path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'
r = parse_uasset(path)

# 查找SoftObjectProperty类型的属性
soft_props = []
for exp in r.export_map:
    for prop in exp.properties:
        if prop.type == "SoftObjectProperty":
            soft_props.append((exp.object_name, prop))

if soft_props:
    for obj_name, prop in soft_props[:3]:
        print(f'{obj_name}.{prop.name}: {prop.type}')
        print(f'  value类型: {type(prop.value).__name__}')
        if isinstance(prop.value, dict):
            print(f'  asset_path: {prop.value.get("asset_path")}')
            print(f'  sub_path: {prop.value.get("sub_path")}')
        else:
            print(f'  value: {prop.value} (格式异常)')
else:
    print('当前资产无SoftObjectProperty类型属性（可能需要其他测试资产）')
```

预期结果：
- SoftObjectProperty.value为Dict格式
- 包含asset_path（资产路径字符串）
- 包含sub_path（子路径字符串，可能为空）
  </action>
  <verify>
    <automated>python -c "from uasset_read import parse_uasset; r=parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'); soft_props=[p for e in r.export_map for p in e.properties if p.type=='SoftObjectProperty']; valid=all(isinstance(p.value, dict) and 'asset_path' in p.value for p in soft_props) if soft_props else True; print('SOFTOBJ_VALID:', valid)"</automated>
  </verify>
  <done>SoftObjectProperty类型属性返回Dict格式包含asset_path和sub_path字段（或无此类属性时测试通过）</done>
</task>

<task type="auto">
  <name>Task 4: 创建端到端测试验证EXTR-01成功标准</name>
  <files>tests/test_exportmap_properties.py</files>
  <read_first>
    - E:/Develop/uasset_read/tests/test_exportmap_properties.py (现有测试结构)
    - E:/Develop/uasset_read/.planning/REQUIREMENTS.md (EXTR-01成功标准)
  </read_first>
  <behavior>
    - Test: 用户可读取ExportMap属性值（成功标准1）
    - Test: JSON输出包含完整属性层次结构（成功标准4）
  </behavior>
  <action>
更新tests/test_exportmap_properties.py，确保测试验证EXTR-01成功标准：

1. 确认test_extr_01_success_criterion_1()测试：
   - 解析MM_Death_Back_01.uasset
   - 验证至少一个export.properties非空
   - 验PropertyValue.value非Error类型

2. 确认test_extr_01_success_criterion_4()测试：
   - 验证JSON输出包含export_map[].properties
   - 验属性值正确序列化

3. 若测试不存在，创建新测试：
```python
def test_extr_01_success_criterion_1_exportmap_properties():
    """验证成功标准1：用户可读取ExportMap属性值"""
    path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'
    r = parse_uasset(path)
    
    # 找到有属性的export
    exports_with_props = [e for e in r.export_map if len(e.properties) > 0]
    assert len(exports_with_props) > 0, "至少一个export有properties"
    
    # 验证属性值非Error
    for exp in exports_with_props:
        for prop in exp.properties:
            assert not isinstance(prop.value, Exception), f"{exp.object_name}.{prop.name}值为Error"
            assert 'Error' not in str(type(prop.value)), f"{exp.object_name}.{prop.name}类型包含Error"
```

4. 运行完整测试套件验证：
```bash
pytest tests/test_exportmap_properties.py -v --tb=short
```
  </action>
  <verify>
    <automated>pytest tests/test_exportmap_properties.py -v --tb=short 2>&1 | grep -E "(PASSED|FAILED|ERROR)" | head -20</automated>
  </verify>
  <done>tests/test_exportmap_properties.py端到端测试通过，验证EXTR-01成功标准1和4</done>
</task>

<task type="auto">
  <name>Task 5: 更新ROADMAP.md和STATE.md记录gap修复</name>
  <files>.planning/ROADMAP.md, .planning/STATE.md</files>
  <read_first>
    - E:/Develop/uasset_read/.planning/ROADMAP.md (Phase 11进度)
    - E:/Develop/uasset_read/.planning/STATE.md (当前状态)
  </read_first>
  <behavior>
    - Test: STATE.md Phase 11状态为gap_resolved
    - Test: ROADMAP.md Phase 11计划数为6
  </behavior>
  <action>
更新规划文档记录gap修复完成：

STATE.md更新：
1. Phase 11状态从"已规划"改为"✓ 完成"
2. 计划数从"4/4"改为"6/6"（增加2个gap closure计划）
3. 进度改为"100%"
4. 添加gap_resolution记录

ROADMAP.md更新：
1. Phase 11行Plans列改为"6/6"
2. 添加gap closure计划说明：
   - 11-05: 修复ScriptSerialization读取条件
   - 11-06: 验证属性解析功能完整
3. Status改为"Complete"
  </action>
  <verify>
    <automated>grep -n "Phase 11" E:/Develop/uasset_read/.planning/STATE.md | grep -E "(完成|Complete|100%)"</automated>
  </verify>
  <done>STATE.md和ROADMAP.md记录Phase 11 gap修复完成，计划数更新为6/6</done>
</task>

## Verification

**端到端验证 - 属性解析成功：**
```bash
python -c "
from uasset_read import parse_uasset, json
r = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset')

# 验证属性解析成功
exports_with_props = [e for e in r.export_map if len(e.properties) > 0]
print(f'Exports with properties: {len(exports_with_props)}')

# 检查第一个有属性的export
if exports_with_props:
    exp = exports_with_props[0]
    print(f'{exp.object_name}: {len(exp.properties)} properties')
    for p in exp.properties[:3]:
        value_type = type(p.value).__name__
        is_error = 'Error' in value_type or isinstance(p.value, Exception)
        print(f'  {p.name}: {p.type} ({value_type}) - Error={is_error}')
        if not is_error:
            print(f'    value preview: {str(p.value)[:50]}')

# 统计非Error属性
non_error_props = []
for exp in r.export_map:
    for p in exp.properties:
        if not isinstance(p.value, Exception) and 'Error' not in str(type(p.value)):
            non_error_props.append(p)

print(f'Non-Error properties: {len(non_error_props)}')
assert len(non_error_props) > 0, '至少一个非Error属性'
print('SUCCESS: ExportMap属性解析正常')
"
```

**单元测试验证：**
```bash
pytest tests/test_exportmap_properties.py tests/test_property_parsing.py -v --tb=short
```

**JSON输出验证：**
```bash
python -c "
from uasset_read import parse_uasset, format_json_full
import json
r = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset')
j = format_json_full(r)
data = json.loads(j)

# 验证层次结构
assert 'export_map' in data, 'JSON包含export_map'
for exp in data['export_map']:
    if 'properties' in exp and len(exp['properties']) > 0:
        for prop in exp['properties']:
            assert 'name' in prop, '属性包含name'
            assert 'type' in prop, '属性包含type'
            assert 'value' in prop, '属性包含value'
print('SUCCESS: JSON层次结构正确')
"
```

## Success Criteria

- [ ] parse_properties_from_export成功解析ExportMap属性
- [ ] 至少一个export.properties包含非Error类型PropertyValue
- [ ] ObjectProperty返回Dict格式（raw_index + resolved）
- [ ] SoftObjectProperty返回Dict格式（asset_path + sub_path）或无此类资产时通过
- [ ] 端到端测试test_extr_01_success_criterion_*通过
- [ ] STATE.md和ROADMAP.md更新记录gap修复完成

## Threat Model

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-11-06-01 | Tampering | 属性值解析 | mitigate | 验证PropertyValue.value非Error类型 |
| T-11-06-02 | Tampering | ObjectProperty引用 | mitigate | 验证resolved字段包含有效引用信息 |

## Output

创建 `.planning/phases/11-exportmap-property-extraction/11-06-GAP-SUMMARY.md` 记录验证结果。

---

**Summary:** 验证11-05修复后ExportMap属性解析功能正常工作，端到端测试确认EXTR-01成功标准达成。