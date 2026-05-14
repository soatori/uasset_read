---
phase: 01-core-parsing
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - uasset_read.py
  - tests/test_uasset_read.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# 阶段 01：代码审查报告

**审查日期：** 2026-04-28
**深度：** standard
**审查文件数：** 2
**状态：** issues_found

## 摘要

审查核心 uasset 解析器实现和测试套件。发现 2 个严重 bug 和若干质量问题。最严重的问题是：（1）字节交换错误反转 UTF-8 字符串字节，损坏大端序文件字符串数据；（2）script serialization 字段总是读取，忽略 UE 版本，导致 UE4 文件解析失败。测试套件字节交换文件内容验证覆盖不足。

## 严重问题

### CR-01：字节交换损坏 UTF-8 字符串数据

**文件：** `uasset_read.py:100-102`
**问题：** `FArchive.read()` 方法启用字节交换时反转所有多字节读取。这对整数/浮点值正确但**对 UTF-8 字符串数据不正确**。UTF-8 编码与字节序无关；反转字符串字节损坏数据。

解析大端序文件时：
1. `read_i32()` 正确反转 4-byte length 整数
2. 字符串数据的 `read(length)` **错误反转** UTF-8 bytes

例如，字符串 "TestName\x00"（9 bytes）反转后变成 "\x00emanTseT"，产生垃圾输出。

`test_byte_swapping_detection` 测试仅验证文件头解析成功，不检查 `name_map` 内容正确，所以此 bug 未被发现。

**修复：**
```python
def read(self, size: int) -> bytes:
    """基础读取方法 - 原始字节读取不进行字节交换。"""
    # ... boundary validation ...
    data = self._file.read(size)
    # 不要在此反转字节 - 类型特定方法处理交换
    return data

def read_i32(self) -> int:
    """读取有符号 32 位整数，正确处理字节序。"""
    if self._byte_swapping:
        # 大端序文件使用大端序格式
        return struct.unpack('>i', self.read(4))[0]
    return struct.unpack('<i', self.read(4))[0]

# 同样更新所有其他类型特定读取方法
# read_u32、read_i64、read_u64、read_f32 应在 byte_swapping 时使用 '>'

def read_fstring(self) -> str:
    """读取 FString - length 需交换，字符串数据不交换。"""
    length = self.read_i32()  # 通过类型特定方法正确交换
    # ... 其余不变，字符串字节不交换 ...
```

### CR-02：Script Serialization 字段对所有文件总是读取

**文件：** `uasset_read.py:639-644`
**问题：** 条件 `if summary.file_version_ue5 >= UE5_VERSION_MIN` 因 `UE5_VERSION_MIN = 0` 总是 True。这导致解析器每个导出条目多读 16 bytes（`script_serial_size` 和 `script_serial_offset`），即使 UE4 文件这些字段不存在。

UE4 文件（legacy_file_version > -8），`file_version_ue5` 保持默认 0，条件评估为 True。解析器读取垃圾数据或边界错误失败。

**修复：**
```python
def read_export_map(...) -> List[ObjectExport]:
    # ...
    # Script serialization 字段仅对 UE5 文件存在（legacy <= -8）
    # 检查文件是否为 UE5，而非仅 ue5_version >= 0
    is_ue5_file = summary.legacy_file_version <= -8
    
    for _ in range(summary.export_count):
        # ... 读取基础字段 ...
        
        if is_ue5_file:
            script_serial_size = archive.read_i64()
            script_serial_offset = archive.read_i64()
        else:
            script_serial_size = 0
            script_serial_offset = 0
```

## 警告

### WR-01：数组计数无边界验证（DoS 风险）

**文件：** `uasset_read.py:430-437, 446, 463, 467, 471`
**问题：** 从文件读取的计数（`custom_versions_count`、`name_count`、`soft_object_paths_count`、`import_count`、`export_count`）直接用于循环无验证。巨大计数的恶意文件可能导致内存耗尽或拒绝服务。

**修复：**
```python
# 定义合理最大值
MAX_NAME_COUNT = 10_000_000
MAX_IMPORT_COUNT = 1_000_000
MAX_EXPORT_COUNT = 1_000_000
MAX_CUSTOM_VERSIONS = 10_000

def read_package_summary(archive: FArchive) -> PackageFileSummary:
    # ...
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count {custom_versions_count} exceeds maximum {MAX_CUSTOM_VERSIONS}")
    # 同样处理 name_count、import_count、export_count
```

### WR-02：UTF-16 字符串长度整数溢出可能

**文件：** `uasset_read.py:459-460`
**问题：** 处理 legacy UTF-16 字符串（`slen < 0`）时，计算 `-slen * 2` 若 `slen` 为 INT_MIN（-2147483648）可能产生极大值。虽然 Python 处理大整数，但结果 4GB 读取可能失败，但显式检查更清晰。

**修复：**
```python
elif slen < 0:
    utf16_len = -slen * 2
    if utf16_len > 10_000_000:  # Sanity check
        raise ParseError(f"UTF-16 string length {utf16_len} too large")
    archive.read(utf16_len)
```

### WR-03：PackageFileSummary 中未使用变量

**文件：** `uasset_read.py:498-499`
**问题：** `payload_toc_offset` 和 `data_resource_offset` 设为 0 但从未使用。这些似乎是未来实现的占位符字段。

**修复：** 实现这些字段的解析或添加 TODO 注释说明保留供未来使用：
```python
# UE5+ trailer 字段（保留供未来实现）
payload_toc_offset: int = 0  # TODO: 从文件 trailer 解析
data_resource_offset: int = 0  # TODO: 从文件 trailer 解析
```

### WR-04：SavedHash 解析测试不完整

**文件：** `tests/test_uasset_read.py:568-642`
**问题：** 测试 `test_saved_hash_ue5_package_saved_hash_version` 复杂且未正确验证 SavedHash 解析。Lines 608-636 包含混淆逻辑，测试可能不管 SavedHash 是否正确读取都通过。测试应验证 `saved_hash` 字段的实际字节内容。

**修复：**
```python
def test_saved_hash_ue5_package_saved_hash_version():
    """测试 UE5 >= PACKAGE_SAVED_HASH（1004）的 SavedHash 读取。"""
    # 创建含已知 SavedHash bytes 的最小有效 UE5 >= 1004 文件
    # 然后验证 saved_hash 精确包含这 20 bytes
    # 使用更简单、直接的测试方法
```

## 信息

### IN-01：FArchive 缺少上下文管理器支持

**文件：** `uasset_read.py:59-128`
**问题：** `FArchive` 未实现 `__enter__`/`__exit__` 上下文管理器支持。虽然 `parse_uasset` 在 `finally` 处理清理，但直接使用 `FArchive` 用户可能泄漏文件句柄。

**修复：**
```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
```

### IN-02：UTF-8 解码静默数据丢失

**文件：** `uasset_read.py:191`
**问题：** `decode('utf-8', errors='replace')` 静默用 Unicode 替换字符替换无效字节。损坏字符串数据不会抛错误。

**修复：** 考虑替换发生时记录警告，或使用 `errors='strict'` 配异常处理：
```python
try:
    return data.decode('utf-8').rstrip('\x00')
except UnicodeDecodeError as e:
    # Log warning and use replacement
    return data.decode('utf-8', errors='replace').rstrip('\x00')
```

### IN-03：SavedHash 大小魔术数字

**文件：** `uasset_read.py:426`
**问题：** SavedHash 大小值 20 是魔术数字。虽然注释中定义，命名常量更清晰。

**修复：**
```python
SAVED_HASH_SIZE = 20  # FIoHash structure size

saved_hash = archive.read(SAVED_HASH_SIZE)
```

---

_审查日期：2026-04-28_
_审查者：Claude（gsd-code-reviewer）_
_深度：standard_