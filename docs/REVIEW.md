# Phase 01: Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed 4 core files for the uasset_read project: archive.py (binary I/O), cli.py (CLI entrypoint), exceptions.py (error definitions), and __main__.py (module entrypoint). Found multiple critical and high-severity issues including resource leaks, ignored CLI flags, missing validation, and inefficient imports.

## Critical Issues

### CR-01: File descriptor leak in FArchive.__init__
**File:** `E:\Develop\uasset_read\src\uasset_read\archive.py:23`
**Category:** bug
**Evidence:** The file handle is opened at line 23 with `open(path, 'rb')` but no cleanup is added for failed initialization. If an error occurs after opening the file (e.g., mmap creation fails, `os.path.getsize` raises an error), the file descriptor is not closed.
**Impact:** File descriptor leaks, especially when processing many files in sequence, leading to resource exhaustion.
**Fix:**
```python
# Add import os at the top of archive.py
import os

# Update __init__ method with proper cleanup
def __init__(self, path: str, tolerant: bool = False):
    self._path = path
    self._byte_swapping: bool = False
    self._file: Optional[BinaryIO] = None
    self._file_size: int = 0
    self._tolerant: bool = tolerant
    self._mmap: Optional[mmap.mmap] = None
    self._use_mmap: bool = False
    self._mmap_warning: Optional[str] = None

    self._file = open(path, 'rb')
    try:
        self._file_size = os.path.getsize(path)

        # mmap branch
        if self._file_size >= MMAP_THRESHOLD:
            try:
                self._mmap = mmap.mmap(
                    self._file.fileno(),
                    0,
                    access=mmap.ACCESS_READ
                )
                self._use_mmap = True
            except (OSError, ValueError, PermissionError) as e:
                self._mmap_warning = f"mmap failed ({type(e).__name__}): {e}"
                self._use_mmap = False
    except:
        # Cleanup file and mmap if initialization fails
        if self._mmap:
            self._mmap.close()
        self._file.close()
        raise
```

### CR-02: Unvalidated FString read in archive.py
**File:** `E:\Develop\uasset_read\src\uasset_read\archive.py:225`
**Category:** security/edge-case
**Evidence:** The `read_fstring` method reads `length` bytes directly without validation when the length is positive. Malicious or malformed uasset files could pass extremely large lengths to trigger OOM errors.
**Impact:** Denial of service via memory exhaustion when parsing malicious uasset files.
**Fix:**
```python
# Add validation before reading positive-length strings
elif length > 0:
    self.validate_size(length, "read_fstring")
    data = self.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')
```

### CR-03: --tolerant CLI flag is non-functional
**File:** `E:\Develop\uasset_read\src\uasset_read\cli.py:63, 99`
**Category:** bug
**Evidence:** The `--tolerant` flag is defined with `action='store_true'` and `default=True`, which makes it redundant — the flag has no effect regardless of whether it's passed. The code also ignores `args.tolerant` entirely, using only `not args.strict`.
**Impact:** Users cannot configure tolerant mode via the CLI as documented; the flag's presence has no impact on parsing behavior.
**Fix:**
```python
# Update flag definition for proper behavior
parser.add_argument('--tolerant', action='store_true', dest='tolerant', default=True,
                    help='Enable tolerant mode for UE5 serialization (default: on)')
parser.add_argument('--strict', action='store_true', dest='strict', default=False,
                    help='Disable tolerant mode: throw ParseError on serialization issues')

# Fix line 99 to use args.tolerant and args.strict correctly
tolerant = args.tolerant and not args.strict
```

## High Issues

### HIGH-01: Missing regular file check in CLI
**File:** `E:\Develop\uasset_read\src\uasset_read\cli.py:94`
**Category:** bug
**Evidence:** The code checks if the file exists but not if the path points to a regular file (e.g., a directory). Attempting to parse a directory will raise an unhandled IOError.
**Impact:** Un graceful failure when passing directories as input files.
**Fix:**
```python
# Add after line 94
if not file_path.is_file():
    print(f"Error: {args.file} is not a regular file", file=sys.stderr)
    sys.exit(EXIT_FILE_NOT_FOUND)
```

### HIGH-02: Inefficient repeated struct imports
**File:** `E:\Develop\uasset_read\src\uasset_read\archive.py:139, 148, 154, 168, 174, 192, 198, 204, 210`
**Category:** quality/performance
**Evidence:** The `struct` module is imported inside nearly every read method, causing repeated module import overhead.
**Impact:** Minor but unnecessary performance degradation, especially for repeated parsing operations.
**Fix:**
```python
# Add struct import at the top of archive.py
import struct

# Remove all `import struct` lines inside individual methods
```

### HIGH-03: Unhandled exceptions from parse_uasset
**File:** `E:\Develop\uasset_read\src\uasset_read\cli.py:100`
**Category:** bug
**Evidence:** The code assumes `parse_uasset` returns a result object with `is_success` and `errors` fields, but does not catch exceptions raised directly by `parse_uasset`.
**Impact:** Unhandled exceptions will crash the CLI instead of exiting gracefully with an error message.
**Fix:**
```python
# Wrap parse_uasset call in try-except
from uasset_read.exceptions import UAssetError

try:
    result = parse_uasset(args.file, tolerant=tolerant)
except UAssetError as e:
    print(f"Parse error: {e}", file=sys.stderr)
    sys.exit(EXIT_PARSE_ERROR)
```

## Info

### INFO-01: Redundant os.path import usage
**File:** `E:\Develop\uasset_read\src\uasset_read\archive.py:25`
**Category:** quality
**Evidence:** The code uses `__import__('os').path.getsize(path)` instead of importing `os` at the top of the file, reducing readability.
**Fix:** Add `import os` at the top of archive.py and replace the call with `os.path.getsize(path)`.

### INFO-02: Hardcoded string length limit
**File:** `E:\Develop\uasset_read\src\uasset_read\archive.py:221`
**Category:** quality
**Evidence:** The UTF-16 string length limit is hardcoded to 10,000,000 bytes without a constant or configuration option.
**Fix:** Add a module-level constant for the limit, e.g., `MAX_STRING_LENGTH = 10_000_000` and use it instead of the literal value.

### INFO-03: Redundant file existence check
**File:** `E:\Develop\uasset_read\src\uasset_read\cli.py:93-96`
**Category:** quality
**Evidence:** The code checks `file_path.exists()` before opening the file, but `open()` will raise a FileNotFoundError anyway if the file doesn't exist. This check is redundant but harmless.
**Fix:** Remove the existence check and rely on the exception handling from open(), or keep it for a more user-friendly error message.
