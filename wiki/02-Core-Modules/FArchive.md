---
title: FArchive 二进制读取器
section: archive
---

# FArchive 二进制读取器

`archive.py` 实现 UE 的 `FArchive`，是所有二进制读取的基础。

## 核心 API

<!-- data-api="FArchive" -->
```python
FArchive(path: str, tolerant: bool = False) -> FArchive
```

## 主要方法

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `read(size)` | `bytes` | 读取指定大小字节 |
| `seek(pos)` | `None` | 移动文件指针 |
| `tell()` | `int` | 获取当前位置 |
| `total_size()` | `int` | 获取文件总大小 |
| `read_u8() / read_i16() / read_u16()` | `int` | 8/16 位整数 |
| `read_i32() / read_u32()` | `int` | 32 位整数 |
| `read_i64() / read_u64()` | `int` | 64 位整数 |
| `peek_i32()` | `int` | 预读（不移动位置） |
| `read_f32() / read_f64()` | `float` | 32/64 位浮点 |
| `read_freal(use_double=False)` | `float` | LWC 双精度坐标 |
| `read_bool()` | `bool` | 4 字节布尔（UE 标准） |
| `read_bool_1byte()` | `bool` | 1 字节布尔（UE5） |
| `read_fstring()` | `str` | UTF-8/UTF-16 字符串 |
| `read_name(name_map)` | `str` | FName 索引查找 |
| `read_array(count, reader)` | `list` | 读取数组 |
| `set_byte_swapping(bool)` | `None` | 字节序交换 |
| `validate_offset(offset, context="")` | `None` | 边界验证（含上下文） |
| `validate_size(size)` | `None` | 大小验证 |

## 关键设计

- **大文件 mmap**：超过 50MB 自动切换，失败时降级
- **字节序透明**：`set_byte_swapping()` 控制
- **容错模式**：`tolerant` 标志控制验证严格度
- **FString 边界防护**：失败时自动 seek 回入口

## 依赖关系

```
archive.py → exceptions.py(ParseError), constants.py(MMAP_THRESHOLD, MAX_FSTRING_LENGTH)
```

> [!TIP]
> FArchive 对应 UE 源码中的 `Core/Public/Serialization/Archive.h`，是解析管线的二进制读取基础。

**相关章节**: [[解析管线]] · [[常量与配置]]
