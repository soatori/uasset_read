# Phase 16: Bool 序列化修复

**里程碑:** v3.1 解析器兼容性修复
**创建日期:** 2026-05-03
**状态:** Context gathered，待规划

---

## 问题背景

### 发现过程

2026-05-03 在解析 `BP_FirstPersonCharacter.uasset` (UE 5.7, version_ue5=1017) 时发现：
- 解析器返回 `status: fail`
- 错误信息：`Invalid offset -5629499534213120 (negative) at seek`
- 导出表解析完全失败，无法读取蓝图内容

### 根本原因

**Bool 序列化大小错误**

| 项目 | 解析器实现 | UE 实际实现 |
|------|-----------|-------------|
| Bool 大小 | 1 byte (`read_u8`) | 4 bytes (`uint32`) |
| 参考 | `uasset_read.py` | `Archive.h:1535` |

UE 源码注释明确说明：
```cpp
// Archive.h line 1535
// Serialize bool as if it were UBOOL (legacy, 32 bit int).
```

### 影响范围

1. **导出表解析失败**
   - `read_export_map()` 中所有 bool 字段错误
   - 条目大小计算错误：原假设 ~75 bytes，实际 112 bytes
   
2. **后续解析连锁失败**
   - `SerialOffset` 出现无效负值
   - 属性解析无法开始（偏移无效）
   
3. **影响字段列表**
   - `bForcedExport`
   - `bNotForClient`
   - `bNotForServer`
   - `bIsInheritedInstance` (UE5 >= 1006)
   - `bNotAlwaysLoadedForEditorGame`
   - `bIsAsset`
   - `bGeneratePublicHash`

---

## UE 源码参考

### Bool 序列化实现

**文件:** `Engine/Source/Runtime/Core/Public/Serialization/Archive.h`

```cpp
// Line 1533-1552
inline friend FArchive& operator<<( FArchive& Ar, bool& D )
{
    // Serialize bool as if it were UBOOL (legacy, 32 bit int).
    uint32 OldUBoolValue = 0;
    if (!Ar.IsLoading())
    {
        OldUBoolValue = D ? 1 : 0;
    }
    Ar << OldUBoolValue;
    if (Ar.IsLoading())
    {
        D = !!OldUBoolValue;
    }
    return Ar;
}
```

### FObjectExport 序列化

**文件:** `Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp`

```cpp
// Line 165-173
#define SERIALIZE_BIT_TO_RECORD(bValue) { \
    bool b = E.bValue; \
    Record << SA_VALUE(TEXT(#bValue), b); \
    E.bValue = b; \
}

SERIALIZE_BIT_TO_RECORD(bForcedExport);
SERIALIZE_BIT_TO_RECORD(bNotForClient);
SERIALIZE_BIT_TO_RECORD(bNotForServer);
```

每个 bool 通过 `operator<<` 序列化为 4 bytes。

---

## 验证数据

### 手动解析验证

使用修正后的 4-byte bool 解析 `BP_FirstPersonCharacter.uasset`：

| 导出索引 | 对象名 | SerialOffset | SerialSize | 状态 |
|----------|--------|--------------|------------|------|
| 0 | Arrow | 74868 | 46 | ✓ 有效 |
| 1 | BP_FirstPersonCharacter | 74914 | 2015 | ✓ 有效 |
| 2 | BP_FirstPersonCharacter_C | 76929 | 817 | ✓ 有效 |
| 3 | Default__BP_FirstPersonCharacter_C | 77746 | 306 | ✓ 有效 |

### 条目大小验证

- **错误实现:** 75 bytes/条目（使用 1-byte bool）
- **正确实现:** 112 bytes/条目（使用 4-byte bool）

差异：37 bytes = 7 bools × (4-1) bytes + 其他偏移修正

---

## 修复方案

### 核心修改

**文件:** `.claude/skills/uasset-read/scripts/uasset_read.py`

```python
# 当前实现（错误）
def read_u8(self):
    return struct.unpack('<B', self.read(1))[0]

# 在 read_export_map 中使用
b_forced_export = bool(archive.read_u8())  # WRONG: 1 byte

# 修正实现
def read_bool(self):
    """UE bool serialized as uint32 (4 bytes)"""
    return self.read_u32() != 0

# 使用
b_forced_export = archive.read_bool()  # CORRECT: 4 bytes
```

### 替换位置

1. `FArchive` 类添加 `read_bool()` 方法
2. `read_export_map()` 中所有 `read_u8()` bool 替换为 `read_bool()`
3. `read_import_map()` 检查是否有类似问题
4. 其他使用 bool 序列化的位置（如有）

---

## 测试验证

### 测试资产

- `BP_FirstPersonCharacter.uasset` (UE 5.7, version_ue5=1017)
- 文件大小: 138,384 bytes
- ExportCount: 69
- ImportCount: 73

### 验证标准

1. 解析返回 `status: success`
2. 所有 `serial_offset` 在有效范围 [0, file_size]
3. 可以正确读取导出对象名和类名
4. 属性解析可以正常开始

---

## 依赖关系

**依赖:** Phase 15 (Skill 封装完成，API 稳定)

**阻塞:** 无（独立修复）

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 其他位置使用 1-byte bool | 中 | 全面 grep 搜索 `read_u8` |
| 版本兼容性 | 低 | Bool 4-byte 从 UE3 开始就是标准 |
| 测试覆盖 | 中 | 添加 UE5.7 专门测试用例 |

---

## 需求映射

| 需求 ID | 描述 | 来源 |
|---------|------|------|
| FIX-01 | Bool 序列化使用 4-byte uint32 | UE 源码 Archive.h |
| FIX-02 | 导出表解析正确读取所有字段 | 用户报告解析失败 |
| FIX-03 | 测试覆盖 UE 5.7 格式资产 | BP_FirstPersonCharacter.uasset |

---

## 下一步

**运行 `/gsd-plan-phase 16` 开始规划修复方案**

---

*Context gathered: 2026-05-03*