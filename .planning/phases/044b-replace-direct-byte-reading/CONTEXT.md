# Phase 44b: 替换直接字节读取

## Status
⏳ 待执行

## Goal
消除所有绕过 FArchive 的直接 `struct.unpack` 调用，统一使用 FArchive 方法确保字节序处理一致性。

## Scope

### 涉及位置
| 文件:行 | 当前代码 | 改为 |
|---------|----------|------|
| `src/uasset_read/parsers/property_types.py:59-60` | `struct.unpack('<h', archive.read(2))[0]` | `archive.read_i16()` (需添加) |
| `src/uasset_read/serializers/graph.py:712-715` | 4x `struct.unpack('<f', archive.read(4))[0]` | 4x `archive.read_f32()` |

### archive.py 补充
- 添加 `read_i16()` 方法（如不存在）

### 不变
- `archive.py` 内部的 `struct.unpack` 调用（这是 FArchive 的核心实现，不属于"绕过"）

## Success Criteria
- `grep -rn 'struct.unpack' src/` 仅返回 `archive.py` 内部实现
- 所有测试通过，无回归

## Dependencies
- Phase 44a 完成（避免同时修改重叠文件）

## Notes
执行前先检索当前代码状态，确认哪些直接字节读取仍存在。

*Created: 2026-05-14*
