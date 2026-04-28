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

# Phase 01: Code Review Report

**Reviewed:** 2026-04-28
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed core uasset parser implementation and test suite. Found 2 critical bugs and several quality issues. The most severe issues are: (1) byte swapping incorrectly reverses UTF-8 string bytes, corrupting string data for big-endian files, and (2) script serialization fields are always read regardless of UE version, causing UE4 file parsing to fail. The test suite has insufficient coverage for byte-swapped file content validation.

## Critical Issues

### CR-01: Byte Swapping Corrupts UTF-8 String Data

**File:** `uasset_read.py:100-102`
**Issue:** The `FArchive.read()` method reverses bytes for all multi-byte reads when byte swapping is enabled. This is correct for integer/float values but **incorrect for UTF-8 string data**. UTF-8 encoding is byte-order independent; reversing string bytes corrupts the data.

When parsing a big-endian file:
1. `read_i32()` correctly reverses the 4-byte length integer
2. `read(length)` for string data **incorrectly reverses** the UTF-8 bytes

For example, string "TestName\x00" (9 bytes) becomes "\x00emanTseT" after reversal, producing garbage output.

The `test_byte_swapping_detection` test only validates header parsing succeeds but does not check that `name_map` content is correct, so this bug goes undetected.

**Fix:**
```python
def read(self, size: int) -> bytes:
    """Base read method - NO byte swapping for raw byte reads."""
    # ... boundary validation ...
    data = self._file.read(size)
    # Do NOT reverse bytes here - let type-specific methods handle swapping
    return data

def read_i32(self) -> int:
    """Read signed 32-bit integer with proper byte order handling."""
    if self._byte_swapping:
        # Use big-endian format for swapped files
        return struct.unpack('>i', self.read(4))[0]
    return struct.unpack('<i', self.read(4))[0]

# Similarly update all other type-specific read methods
# read_u32, read_i64, read_u64, read_f32 should use '>' when byte_swapping

def read_fstring(self) -> str:
    """Read FString - length needs swapping, string data does NOT."""
    length = self.read_i32()  # Properly swapped via type-specific method
    # ... rest unchanged, string bytes are NOT swapped ...
```

### CR-02: Script Serialization Fields Always Read for All Files

**File:** `uasset_read.py:639-644`
**Issue:** The condition `if summary.file_version_ue5 >= UE5_VERSION_MIN` is always True since `UE5_VERSION_MIN = 0`. This causes the parser to always read 16 extra bytes (`script_serial_size` and `script_serial_offset`) per export entry, even for UE4 files where these fields don't exist.

For UE4 files (legacy_file_version > -8), `file_version_ue5` remains at default 0, and the condition evaluates to True. The parser then reads garbage data or fails with boundary errors.

**Fix:**
```python
def read_export_map(...) -> List[ObjectExport]:
    # ...
    # Script serialization fields only exist for UE5 files (legacy <= -8)
    # Check if file is actually UE5, not just if ue5_version >= 0
    is_ue5_file = summary.legacy_file_version <= -8
    
    for _ in range(summary.export_count):
        # ... read base fields ...
        
        if is_ue5_file:
            script_serial_size = archive.read_i64()
            script_serial_offset = archive.read_i64()
        else:
            script_serial_size = 0
            script_serial_offset = 0
```

## Warnings

### WR-01: No Bounds Validation on Array Counts (DoS Risk)

**File:** `uasset_read.py:430-437, 446, 463, 467, 471`
**Issue:** Counts read from file (`custom_versions_count`, `name_count`, `soft_object_paths_count`, `import_count`, `export_count`) are used directly in loops without validation. A malicious file with huge count values could cause memory exhaustion or denial of service.

**Fix:**
```python
# Define reasonable maximums
MAX_NAME_COUNT = 10_000_000
MAX_IMPORT_COUNT = 1_000_000
MAX_EXPORT_COUNT = 1_000_000
MAX_CUSTOM_VERSIONS = 10_000

def read_package_summary(archive: FArchive) -> PackageFileSummary:
    # ...
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count {custom_versions_count} exceeds maximum {MAX_CUSTOM_VERSIONS}")
    # Similarly for name_count, import_count, export_count
```

### WR-02: Integer Overflow Potential in UTF-16 String Length

**File:** `uasset_read.py:459-460`
**Issue:** When handling legacy UTF-16 strings (`slen < 0`), the calculation `-slen * 2` could produce a very large value if `slen` is INT_MIN (-2147483648). While Python handles big integers, the resulting 4GB read would likely fail, but an explicit check would be clearer.

**Fix:**
```python
elif slen < 0:
    utf16_len = -slen * 2
    if utf16_len > 10_000_000:  # Sanity check
        raise ParseError(f"UTF-16 string length {utf16_len} too large")
    archive.read(utf16_len)
```

### WR-03: Unused Variables in PackageFileSummary

**File:** `uasset_read.py:498-499`
**Issue:** `payload_toc_offset` and `data_resource_offset` are set to 0 but never used. These appear to be placeholder fields for future implementation.

**Fix:** Either implement the parsing for these fields or add a TODO comment explaining they're reserved for future use:
```python
# UE5+ trailer fields (reserved for future implementation)
payload_toc_offset: int = 0  # TODO: Parse from file trailer
data_resource_offset: int = 0  # TODO: Parse from file trailer
```

### WR-04: Incomplete Test for SavedHash Parsing

**File:** `tests/test_uasset_read.py:568-642`
**Issue:** The test `test_saved_hash_ue5_package_saved_hash_version` is convoluted and doesn't properly verify SavedHash parsing. Lines 608-636 contain confusing logic with a test that may pass regardless of whether SavedHash is correctly read. The test should verify actual byte content of `saved_hash` field.

**Fix:**
```python
def test_saved_hash_ue5_package_saved_hash_version():
    """Test SavedHash reading for UE5 >= PACKAGE_SAVED_HASH (1004)."""
    # Create a minimal valid UE5 >= 1004 file with known SavedHash bytes
    # Then verify saved_hash contains exactly those 20 bytes
    # Use a simpler, more direct test approach
```

## Info

### IN-01: FArchive Lacks Context Manager Support

**File:** `uasset_read.py:59-128`
**Issue:** `FArchive` doesn't implement `__enter__`/`__exit__` for context manager support. While `parse_uasset` handles cleanup in `finally`, users of `FArchive` directly could leak file handles.

**Fix:**
```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
```

### IN-02: Silent Data Loss in UTF-8 Decode

**File:** `uasset_read.py:191`
**Issue:** `decode('utf-8', errors='replace')` silently replaces invalid bytes with the Unicode replacement character. Corrupted string data would not raise an error.

**Fix:** Consider logging a warning when replacement occurs, or using `errors='strict'` with exception handling:
```python
try:
    return data.decode('utf-8').rstrip('\x00')
except UnicodeDecodeError as e:
    # Log warning and use replacement
    return data.decode('utf-8', errors='replace').rstrip('\x00')
```

### IN-03: Magic Number for SavedHash Size

**File:** `uasset_read.py:426`
**Issue:** The value 20 for SavedHash size is a magic number. While it's defined in a comment, a named constant would be clearer.

**Fix:**
```python
SAVED_HASH_SIZE = 20  # FIoHash structure size

saved_hash = archive.read(SAVED_HASH_SIZE)
```

---

_Reviewed: 2026-04-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_