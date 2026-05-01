---
phase: 01-core-parsing
plan: 08
subsystem: core-parsing
tags: [gap-closure, ue4, localization, name-hash, bug-fix]
requires: [CORE-01, CORE-04, CORE-05]
provides: [UE4-file-parsing, Lyra-file-support]
affects: [uasset_read.py, tests/test_uasset_read.py]
tech-stack:
  added:
    - LocalizationId FString field in PackageFileSummary
    - GatherableTextData Count/Offset fields in PackageFileSummary
    - Name hash bytes（4 bytes）after each FString for UE4 >= 502
    - SoftObjectPaths conditional（UE5 only）
  patterns:
    - UE4 version-gated field reading
    - FNameEntrySerialized format（FString + hash bytes）
key-files:
  created: []
  modified:
    - uasset_read.py: PackageFileSummary fields, read_package_summary(), read_name_table()
    - tests/test_uasset_read.py: create_test_uasset helper, test_ue4_total_header_size_at_correct_position, test_real_lyra_character_default_file
decisions:
  - LocalizationId/GatherableTextData 仅用于 UE4 文件（legacy > -8）
  - SoftObjectPaths 仅用于 UE5 文件（legacy <= -8）
  - UE4 >= VER_UE4_NAME_HASHES_SERIALIZED（502）的 Name hash bytes
metrics:
  duration: ~45 minutes
  tasks_completed: 5
  files_modified: 2
  tests_added: 3
  tests_passed: 28
completed_date: 2026-04-28T06:00:00Z
---

# 阶段 1 计划 08：LocalizationId 和 GatherableTextData 缺口填补摘要

**一句话概述：** 修复 UE4 文件解析，添加 LocalizationId、GatherableTextData 字段、SoftObjectPaths 条件和名称表哈希字节 - Lyra Character_Default.uasset 现在成功解析。

## 背景

VERIFICATION.md 识别到 Lyra Character_Default.uasset（UE4 文件, legacy=-7, UE4 v521）解析失败，原因是文件头缺失 LocalizationId 和 GatherableTextData 字段。解析器读取垃圾值作为 ImportOffset（910241842 而非 4776），阻塞 ImportMap/ExportMap 解析。

## 已完成任务

| 任务 | 名称 | 状态 | 提交 |
|------|------|--------|--------|
| 1 | 向 PackageFileSummary 添加 LocalizationId 和 GatherableTextData 字段 | COMPLETE | 817e412 |
| 2 | 在 read_package_summary() 中读取 LocalizationId 和 GatherableTextData | COMPLETE | 5f4e2eb |
| 3 | 更新 create_test_uasset helper 以对 UE4 文件输出字段 | COMPLETE | 5f4e2eb |
| 4 | 添加 UE4 LocalizationId 字段解析测试 | COMPLETE | 5f4e2eb |
| 5 | 添加真实 Lyra 文件解析测试 | COMPLETE | 5c5cafa |

## 与计划的偏差

### 自动修复的问题

**1. [规则 1 - Bug] SoftObjectPaths 被 UE4 文件读取（应仅限 UE5）**
- **发现时机：** 任务 2 - Lyra 文件测试失败报 UTF-16 错误
- **问题：** 解析器为 UE4 文件读取 SoftObjectPaths（8 bytes），偏移位置
- **修复：** 添加条件 - 仅 UE5 文件（legacy <= -8）读取 SoftObjectPaths
- **修改文件：** uasset_read.py lines 488-496
- **提交：** 5c5cafa

**2. [规则 1 - Bug] UE4 >= 502 的名称表哈希字节未读取**
- **发现时机：** 任务 5 - Lyra 文件解析显示 position 487 有 UTF-16 错误
- **问题：** UE4 >= VER_UE4_NAME_HASHES_SERIALIZED（502）在每个 FString 后有 4-byte 哈希后缀
- **修复：** read_name_table 现在对 UE4 >= 502 每个 FString 后读取 4 哈希字节
- **修改文件：** uasset_read.py read_name_table function
- **提交：** 5c5cafa

**3. [规则 3 - Blocking] 合成测试需要哈希字节**
- **发现时机：** 名称哈希修复后，合成测试失败
- **问题：** create_test_uasset 未对 UE4 >= 502 输出哈希字节
- **修复：** 更新 helper 以对 UE4 >= 502 每个名称后输出 4-byte 哈希
- **修改文件：** tests/test_uasset_read.py create_test_uasset
- **提交：** 5c5cafa

**4. [规则 3 - Blocking] 手动测试文件缺失 UE4 字段**
- **发现时机：** test_ue4_total_header_size_at_correct_position 失败
- **问题：** 测试中手动文件创建未包含 LocalizationId、GatherableTextData 或哈希字节
- **修复：** 更新测试以正确输出所有 UE4 字段
- **修改文件：** tests/test_uasset_read.py
- **提交：** 5c5cafa

## 关键技术决策

### 发现的 UE 版本常量

来自 UE 5.7 源码 ObjectVersion.h：
- VER_UE4_NAME_HASHES_SERIALIZED = 502（FString 后的名称哈希）
- VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 514
- VER_UE4_SERIALIZE_TEXT_IN_PACKAGES = 457（GatherableTextData）

### 字段读取逻辑

| 字段 | UE4（legacy > -8） | UE5（legacy <= -8） |
|-------|-------------------|--------------------|
| SoftObjectPaths | NO | YES |
| LocalizationId | YES（UE4 >= 514） | NO |
| GatherableTextData | YES（UE4 >= 457） | NO |
| Name Hash Bytes | YES（UE4 >= 502） | NO |

### 名称表格式

UE4 >= 502 使用 FNameEntrySerialized 格式：
- FString（int32 length + UTF-8 data + null terminator）
- 4 bytes hash（NonCasePreservingHash uint16 + CasePreservingHash uint16）

## 验证结果

### Lyra Character_Default.uasset

```
Success: True
NameMap count: 129
ImportMap count: 20
ExportMap count: 35
LocalizationId: 20A614D64ED8D59F9004C9AAB041067E
ImportOffset: 4776
ExportOffset: 3516
```

所有值匹配 VERIFICATION.md 预期值。ImportMap 和 ExportMap 正确填充。

### 测试结果

全部 28 个测试通过包括：
- test_real_lyra_character_default_file（集成测试）
- test_ue4_localization_id_field_reading（字段验证）
- test_ue4_total_header_size_at_correct_position（手动文件测试）

## 修改文件

### uasset_read.py

1. PackageFileSummary dataclass：添加 localization_id、gatherable_text_data_count、gatherable_text_data_offset 字段
2. read_package_summary()：
   - SoftObjectPaths 条件（仅 UE5）
   - UE4 文件的 LocalizationId 读取
   - UE4 文件的 GatherableTextData 读取
3. read_name_table()：UE4 >= 502 添加哈希字节读取

### tests/test_uasset_read.py

1. create_test_uasset：
   - SoftObjectPaths 条件（仅 UE5）
   - UE4 LocalizationId/GatherableTextData 输出
   - UE4 >= 502 的名称哈希字节输出
2. test_ue4_total_header_size_at_correct_position：更新手动文件创建
3. test_real_lyra_character_default_file：新集成测试
4. test_ue4_localization_id_field_reading：新字段验证测试

## 成功标准达成

1. 所有测试通过（现有 + 新） - 28/28 passed
2. Lyra Character_Default.uasset 成功解析 - 已验证
3. LocalizationId 字段填充 GUID 字符串 - "20A614D64ED8D59F9004C9AAB041067E"
4. ImportOffset=4776, ExportOffset=3516（有效值） - 已验证
5. ImportMap 和 ExportMap 正确填充 - 20 imports, 35 exports

## 自检：通过

- 所有文件存在并正确修改
- git log 中所有提交（817e412, 5f4e2eb, 5c5cafa）
- 所有测试通过（28/28）
- Lyra 文件正确解析，值正确

---
*完成时间：2026-04-28T06:00:00Z*
*执行器：Claude（gsd-execute-phase）*