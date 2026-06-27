---
title: FArchive Binary Reader
section: archive
---

# FArchive Binary Reader

`archive.py` implements UE's `FArchive`, which serves as the foundation for all binary reading.

## Core API

<!-- data-api="FArchive" -->
```python
FArchive(path: str, tolerant: bool = False) -> FArchive
```

## Key Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `read(size)` | `bytes` | Read a specified number of bytes |
| `seek(pos)` | `None` | Move the file pointer |
| `tell()` | `int` | Get the current position |
| `total_size()` | `int` | Get the total file size |
| `read_u8() / read_i16() / read_u16()` | `int` | 8/16-bit integers |
| `read_i32() / read_u32()` | `int` | 32-bit integers |
| `read_i64() / read_u64()` | `int` | 64-bit integers |
| `peek_i32()` | `int` | Peek ahead (does not move the position) |
| `read_f32() / read_f64()` | `float` | 32/64-bit floating point |
| `read_freal(use_double=False)` | `float` | LWC double-precision coordinates |
| `read_bool()` | `bool` | 4-byte boolean (UE standard) |
| `read_bool_1byte()` | `bool` | 1-byte boolean (UE5) |
| `read_fstring()` | `str` | UTF-8/UTF-16 string |
| `read_name(name_map)` | `str` | FName index lookup |
| `read_array(count, reader)` | `list` | Read an array |
| `set_byte_swapping(bool)` | `None` | Toggle byte order swapping |
| `validate_offset(offset, context="")` | `None` | Boundary validation (with context) |
| `validate_size(size)` | `None` | Size validation |

## Key Design

- **Large file mmap**: Automatically switches when exceeding 50MB, with graceful fallback on failure
- **Byte-order transparent**: Controlled via `set_byte_swapping()`
- **Tolerant mode**: The `tolerant` flag controls validation strictness
- **FString boundary protection**: Automatically seeks back to the entry point on failure

## Dependencies

```
archive.py -> exceptions.py(ParseError), constants.py(MMAP_THRESHOLD, MAX_FSTRING_LENGTH)
```

> [!TIP]
> FArchive corresponds to `Core/Public/Serialization/Archive.h` in the UE source code and is the binary reading foundation of the parsing pipeline.

**Related Sections**: [[Parsing Pipeline]] · [[Constants and Configuration]]
