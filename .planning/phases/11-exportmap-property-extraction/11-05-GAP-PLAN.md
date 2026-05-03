---
phase: 11-exportmap-property-extraction
plan: 05
type: execute
wave: 1
depends_on: []
files_modified:
  - uasset_read.py
requirements_addressed:
  - EXTR-01
gap_closure: true
autonomous: true
user_setup: []
must_haves:
  truths:
    - "ExportMap条目的serial_offset值小于文件大小"
    - "ExportMap条目的serial_size值为合理的正数或0"
    - "parse_properties_from_export能正确seek到serial_offset位置"
  artifacts:
    - path: "uasset_read.py"
      provides: "PKG_UnversionedProperties常量和ScriptSerialization正确条件"
      contains: "PKG_UnversionedProperties = 0x2000"
  key_links:
    - from: "read_export_map()"
      to: "ScriptSerialization字段"
      via: "!uses_unversioned && ue5_version >= 1010"
      pattern: "PKG_UnversionedProperties"
---

# Plan 11-05: 修复ExportMap ScriptSerialization读取条件

**Objective:** 修正read_export_map函数中ScriptSerialization字段的读取条件，使用正确的PKG_UnversionedProperties标志而非PKG_Cooked

**Purpose:** 修复Phase 6遗留的ExportMap解析bug，使serial_offset/serial_size值正确，为Phase 11属性解析提供正确基础

## Gap分析

**VERIFICATION.md发现的gap:**
- ExportMap条目serial_offset值异常（如1099511625984 > 文件大小308880）
- 所有properties为ParseError/Error类型，无实际属性值
- 根本原因：ScriptSerialization字段未正确读取导致数据错位

**UE源码正确条件**（ObjectResource.cpp:212）:
```cpp
if (!BaseArchive.UseUnversionedPropertySerialization() && 
    BaseArchive.UEVer() >= EUnrealEngineObjectUE5Version::SCRIPT_SERIALIZATION_OFFSET)
```

其中UseUnversionedPropertySerialization()基于`PKG_UnversionedProperties (0x2000)`判断。

**当前代码错误条件**（uasset_read.py:1949-1952）:
```python
is_cooked_pkg = (summary.package_flags & PKG_Cooked) != 0  # 错误！
if is_ue5_file and is_cooked_pkg and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
```

**问题：**
- 测试资产package_flags=0，PKG_UnversionedProperties未设置（应读取ScriptSerialization）
- 但PKG_Cooked也未设置（当前代码不读取）
- 结果：每个Export条目少读16字节（2个i64），导致后续条目全部错位

## Context

@E:/Develop/uasset_read/.planning/STATE.md
@E:/Develop/uasset_read/.planning/phases/11-exportmap-property-extraction/11-VERIFICATION.md
@E:/Develop/uasset_read/.planning/phases/11-exportmap-property-extraction/11-RESEARCH.md

<interfaces>
<!-- 关键常量和函数位置 -->

From uasset_read.py:63:
```python
PKG_Cooked = 0x200                     # Package is cooked
```

From uasset_read.py:101:
```python
VER_UE4_64BIT_EXPORTOFFSETS = 508              # Phase 6: 64-bit export offsets
```

From uasset_read.py:1949-1952:
```python
is_cooked_pkg = (summary.package_flags & PKG_Cooked) != 0
if is_ue5_file and is_cooked_pkg and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    script_serial_size = archive.read_i64()
    script_serial_offset = archive.read_i64()
```

From UE ObjectResource.cpp:212:
```cpp
if (!BaseArchive.UseUnversionedPropertySerialization() && 
    BaseArchive.UEVer() >= EUnrealEngineObjectUE5Version::SCRIPT_SERIALIZATION_OFFSET)
```

From UE ObjectMacros.h:143:
```cpp
PKG_UnversionedProperties = 0x00002000,  // Uses unversioned property serialization
```

From UE AsyncLoading2.cpp:7885:
```cpp
Ar.SetUseUnversionedPropertySerialization(
    (LinkerRoot->GetPackageFlags() & PKG_UnversionedProperties) != 0
);
```
</interfaces>

## Tasks

<task type="auto">
  <name>Task 1: 添加PKG_UnversionedProperties常量定义</name>
  <files>uasset_read.py</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (lines 60-70: PKG_*常量定义区域)
    - E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectMacros.h (line 143: PKG_UnversionedProperties定义)
  </read_first>
  <behavior>
    - Test: grep检查PKG_UnversionedProperties常量不存在
    - Test: 添加后grep检查常量存在且值正确(0x2000)
  </behavior>
  <action>
在uasset_read.py的PKG_*常量定义区域（约line 63附近），添加PKG_UnversionedProperties常量：

1. 定位到现有PKG_Cooked定义位置：
```python
PKG_Cooked = 0x200                     # Package is cooked
```

2. 在其后添加新常量：
```python
PKG_Cooked = 0x200                     # Package is cooked
PKG_UnversionedProperties = 0x2000     # Uses unversioned property serialization (Phase 11 GAP-01)
```

3. 添加注释说明用途，用于判断是否读取ScriptSerialization字段

per UE源码 ObjectMacros.h:143 和 ObjectResource.cpp:212
  </action>
  <verify>
    <automated>grep -n "PKG_UnversionedProperties" E:/Develop/uasset_read/uasset_read.py | grep -v "^#" | grep "0x2000"</automated>
  </verify>
  <done>PKG_UnversionedProperties常量存在于uasset_read.py，值为0x2000，位于PKG_Cooked定义之后</done>
</task>

<task type="auto">
  <name>Task 2: 修改read_export_map的ScriptSerialization读取条件</name>
  <files>uasset_read.py</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (lines 1943-1954: ScriptSerialization读取区域)
    - E:/Develop/uasset_read/uasset_read.py (line 63: 新添加的PKG_UnversionedProperties常量)
    - E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp (lines 212-222: 正确条件)
  </read_first>
  <behavior>
    - Test: 解析MM_Death_Back_01.uasset，serial_offset值应小于文件大小
    - Test: 解析FirstPerson资产，ExportMap条目不再错位
  </behavior>
  <action>
修改read_export_map函数中ScriptSerialization字段读取条件（约line 1949-1952）：

**当前错误代码：**
```python
# 19-20. ScriptSerializationStartOffset/EndOffset
# 条件: !UseUnversionedPropertySerialization() && UEVer() >= SCRIPT_SERIALIZATION_OFFSET(1010)
# 未烘焙/编辑器保存的文件 UseUnversionedPropertySerialization()=true，不序列化这些字段
# 烘焙文件 UseUnversionedPropertySerialization()=false，序列化这些字段
script_serial_size = 0
script_serial_offset = 0
is_cooked_pkg = (summary.package_flags & PKG_Cooked) != 0
if is_ue5_file and is_cooked_pkg and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    script_serial_size = archive.read_i64()
    script_serial_offset = archive.read_i64()
```

**修复为正确代码：**
```python
# 19-20. ScriptSerializationStartOffset/EndOffset
# 条件: !UseUnversionedPropertySerialization() && UEVer() >= SCRIPT_SERIALIZATION_OFFSET(1010)
# UseUnversionedPropertySerialization()基于PKG_UnversionedProperties标志判断
# 若PKG_UnversionedProperties未设置，则使用versioned property serialization，需要读取这些字段
script_serial_size = 0
script_serial_offset = 0
uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
if is_ue5_file and not uses_unversioned and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    script_serial_size = archive.read_i64()
    script_serial_offset = archive.read_i64()
```

关键变更：
1. `is_cooked_pkg` → `uses_unversioned`（变量名反映实际含义）
2. `(package_flags & PKG_Cooked)` → `(package_flags & PKG_UnversionedProperties)`
3. `is_cooked_pkg` → `not uses_unversioned`（条件逻辑反转）
4. 更新注释说明PKG_UnversionedProperties的作用

per UE源码 ObjectResource.cpp:212 和 AsyncLoading2.cpp:7885
  </action>
  <verify>
    <automated>grep -n "uses_unversioned" E:/Develop/uasset_read/uasset_read.py | grep -v "^#" | head -5</automated>
  </verify>
  <done>read_export_map使用uses_unversioned变量和PKG_UnversionedProperties标志判断ScriptSerialization读取条件</done>
</task>

<task type="auto">
  <name>Task 3: 验证修复后ExportMap解析正确</name>
  <files>uasset_read.py (验证命令)</files>
  <read_first>
    - E:/Develop/uasset_read/uasset_read.py (修复后的read_export_map函数)
    - E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset
  </read_first>
  <behavior>
    - Test: Export #0 serial_offset正常（小于文件大小）
    - Test: Export #1开始不再错位
    - Test: 所有export条目object_name正确（非乱码）
  </behavior>
  <action>
创建验证脚本确认修复正确：

```python
# 验证脚本
from uasset_read import FArchive, read_package_summary, read_name_table, read_import_map, read_export_map

path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'

archive = FArchive(path)
summary = read_package_summary(archive)
name_map = read_name_table(archive, summary)
import_map = read_import_map(archive, summary, name_map)
export_map = read_export_map(archive, summary, name_map)

print(f'文件大小: {archive._file_size}')
print(f'ExportMap条目数: {len(export_map)}')

all_valid = True
for i, exp in enumerate(export_map):
    if exp.serial_offset > archive._file_size:
        print(f'ERROR: Export #{i} serial_offset={exp.serial_offset} > file_size={archive._file_size}')
        all_valid = False
    elif exp.serial_size < 0:
        print(f'ERROR: Export #{i} serial_size={exp.serial_size} < 0')
        all_valid = False

if all_valid:
    print('SUCCESS: 所有ExportMap条目serial_offset/serial_size值正常')
```

预期结果：
- 所有serial_offset < file_size
- 所有serial_size >= 0
- object_name正确（如AnimationSequencerDataModel而非/Script/ControlRig乱码）
  </action>
  <verify>
    <automated>python -c "from uasset_read import FArchive, read_package_summary, read_name_table, read_import_map, read_export_map; a=FArchive('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'); s=read_package_summary(a); n=read_name_table(a,s); i=read_import_map(a,s,n); e=read_export_map(a,s,n); valid=all(x.serial_offset<=a._file_size and x.serial_size>=0 for x in e); print('VALID:', valid)"</automated>
  </verify>
  <done>MM_Death_Back_01.uasset的ExportMap条目serial_offset/serial_size值全部正常（offset <= file_size, size >= 0）</done>
</task>

<task type="auto">
  <name>Task 4: 新增单元测试覆盖ScriptSerialization条件</name>
  <files>tests/test_exportmap_properties.py</files>
  <read_first>
    - E:/Develop/uasset_read/tests/test_exportmap_properties.py (现有测试结构)
    - E:/Develop/uasset_read/tests/test_property_parsing.py (测试模式参考)
  </read_first>
  <behavior>
    - Test: uses_unversioned=False时读取ScriptSerialization字段
    - Test: uses_unversioned=True时不读取ScriptSerialization字段
    - Test: package_flags=0时正确行为（应读取字段）
  </behavior>
  <action>
在tests/test_exportmap_properties.py中新增测试验证ScriptSerialization条件：

1. test_script_serialization_with_unversioned_properties():
   - 模拟package_flags包含PKG_UnversionedProperties (0x2000)
   - 验证ScriptSerialization字段不被读取
   - 验证export_map正确解析无错位

2. test_script_serialization_without_unversioned_properties():
   - 模拟package_flags不含PKG_UnversionedProperties (0x0000)
   - 验证ScriptSerialization字段被读取（ue5_version >= 1010时）
   - 验证export_map正确解析无错位

3. test_script_serialization_version_threshold():
   - 验证ue5_version < 1010时不读取ScriptSerialization（即使uses_unversioned=False）
   - 验证版本条件正确应用

注意：需要创建MockArchive模拟不同package_flags场景，或使用实际资产验证。
  </action>
  <verify>
    <automated>pytest tests/test_exportmap_properties.py::test_script_serialization* -v --tb=short</automated>
  </verify>
  <done>tests/test_exportmap_properties.py包含ScriptSerialization条件测试，全部通过</done>
</task>

## Verification

**核心验证 - ExportMap解析正确：**
```bash
python -c "
from uasset_read import FArchive, read_package_summary, read_name_table, read_import_map, read_export_map
path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset'
archive = FArchive(path)
summary = read_package_summary(archive)
name_map = read_name_table(archive, summary)
import_map = read_import_map(archive, summary, name_map)
export_map = read_export_map(archive, summary, name_map)
for i, exp in enumerate(export_map[:5]):
    print(f'Export #{i}: {exp.object_name}, serial_offset={exp.serial_offset}, serial_size={exp.serial_size}')
    assert exp.serial_offset <= archive._file_size, f'serial_offset异常'
print('SUCCESS: ExportMap解析正确')
"
```

**单元测试验证：**
```bash
pytest tests/test_exportmap_properties.py -v --tb=short
```

**属性解析验证（修复后应成功）：**
```bash
python -c "
from uasset_read import parse_uasset
r = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Characters/Mannequins/Anims/Death/MM_Death_Back_01.uasset')
for exp in r.export_map:
    if len(exp.properties) > 0:
        print(f'{exp.object_name}: {len(exp.properties)} properties')
        for p in exp.properties[:2]:
            print(f'  {p.name}: {p.type} = {str(p.value)[:50]}')
"
```

## Success Criteria

- [ ] PKG_UnversionedProperties常量定义存在（0x2000）
- [ ] read_export_map使用uses_unversioned变量判断条件
- [ ] 测试资产ExportMap条目serial_offset值正常（< file_size）
- [ ] 测试资产ExportMap条目serial_size值正常（>= 0）
- [ ] 单元测试覆盖ScriptSerialization条件
- [ ] parse_properties_from_export能正确seek到serial_offset

## Threat Model

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-11-05-01 | Tampering | ScriptSerialization条件 | mitigate | 使用正确的PKG_UnversionedProperties标志而非PKG_Cooked |
| T-11-05-02 | Tampering | ExportMap数据错位 | mitigate | 修复条件后验证所有条目offset正常 |

## Output

创建 `.planning/phases/11-exportmap-property-extraction/11-05-GAP-SUMMARY.md` 记录修复结果。

---

**Summary:** 修复read_export_map的ScriptSerialization读取条件，从错误的PKG_Cooked标志改为正确的PKG_UnversionedProperties标志，解决ExportMap数据错位问题。