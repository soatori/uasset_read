# Phase 16: Bool 序列化修复 - Research

**研究日期:** 2026-05-03
**域:** UE 二进制序列化，FArchive 模式，Bool 序列化标准
**置信度:** HIGH (UE 源码直接验证)

---

## 研究摘要

通过 UE 5.7 源码分析确认：**所有 bool 字段在 UE 序列化中使用 4-byte uint32**，而非 1-byte uint8。当前解析器在 16 个位置错误使用 `read_u8()` 读取 bool 字段，导致导出表条目大小计算错误（每条目少读 21 bytes），进而使 serial_offset 出现无效负值，属性解析完全失败。

**核心修复方案：** 在 FArchive 类添加 `read_bool()` 方法，返回 `self.read_u32() != 0`，并替换所有 `bool(archive.read_u8())` 和 `archive.read_u8() != 0` 为 `archive.read_bool()`。

**UE 源码证据：** 
- `Archive.h:1535` — "Serialize bool as if it were UBOOL (legacy, 32 bit int)"
- `ObjectResource.cpp:171-200` — 所有 FObjectExport bool 字段通过 SERIALIZE_BIT_TO_RECORD 宏序列化
- `EdGraphPin.cpp:248-283` — FEdGraphPinType 的 bool 字段转换为临时 bool 变量后序列化

---

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Bool 应使用 4-byte uint32（UE 标准，自 UE3 起）[VERIFIED: Archive.h:1535]
- 修复文件：`uasset_read.py` [VERIFIED: 当前主解析器]
- 需求 ID：FIX-01, FIX-02, FIX-03

### Claude's Discretion
- 是否同时修复其他位置的 bool 序列化（经研究发现共 16 个位置）
- 测试验证策略（使用 BP_FirstPersonCharacter.uasset）

### Deferred Ideas (OUT OF SCOPE)
- 无

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID | 描述 | 研究支持 |
|----|------|----------|
| FIX-01 | Bool 序列化使用 4-byte uint32 | UE 源码 Archive.h:1535 直接验证，所有 bool 字段通过 operator<<(bool) 序列化为 uint32 |
| FIX-02 | 导出表解析正确读取所有字段 | 发现 7 个导出表 bool 字段 + 1 个导入表 bool 字段需要修复，共 16 个位置全量发现 |
| FIX-03 | 测试覆盖 UE 5.7 格式资产 | BP_FirstPersonCharacter.uasset (UE 5.7, version_ue5=1017) 已验证存在，当前解析失败可作为测试基准 |

</phase_requirements>

---

## Architectural Responsibility Map

| 能力 | 主要层 | 辅助层 | 原因 |
|------|--------|--------|------|
| Bool 序列化读取 | FArchive (解析层) | — | 二进制读取器应提供类型特定方法 |
| ExportMap/ImportMap 解析 | Deserializer (解析层) | — | 调用 FArchive 方法读取结构字段 |
| 蓝图节点解析 | GraphParser (扩展组件) | Deserializer | 依赖 FArchive.bool 读取方法 |
| 测试验证 | Tests (测试层) | — | 使用真实 UE 5.7 资产验证修复 |

---

## 标准栈

### 核心组件

| 组件 | 版本 | 用途 | 为什么是标准 |
|------|------|------|-------------|
| FArchive | 现有 | 二进制读取器 | UE 镜像模式，添加 `read_bool()` 方法 |
| struct.unpack | '<I' | uint32 解包 | 标准 Python 库，字节序感知 |
| UE 源码参考 | 5.7 | 序列化验证 | 官方实现确认 bool 序列化标准 |

### 修改方法

```python
# 在 FArchive 类添加（line ~341 后）
def read_bool(self) -> bool:
    """
    读取 UE bool 值（序列化为 uint32，4 bytes）。
    
    UE 源码参考：Archive.h line 1535
    "Serialize bool as if it were UBOOL (legacy, 32 bit int)"
    """
    return self.read_u32() != 0
```

---

## 需要修复的位置（16 个 Bool 字段）

### 1. ExportMap (read_export_map) — 7 个字段

**文件:** `uasset_read.py` line 2128-2160

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_forced_export | 2128 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_not_for_client | 2129 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_not_for_server | 2130 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_is_inherited_instance | 2140 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_not_always_loaded_for_editor_game | 2152 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_is_asset | 2156 | `bool(archive.read_u8())` | `archive.read_bool()` |
| b_generate_public_hash | 2160 | `bool(archive.read_u8())` | `archive.read_bool()` |

**UE 源码验证:**
- `ObjectResource.cpp:171-200` — SERIALIZE_BIT_TO_RECORD 宏，内部调用 `Ar << bool`
- 每个条目影响：7 bools × (4-1) bytes = 21 bytes 偏移累积错误

### 2. ImportMap (read_import_map) — 1 个字段

**文件:** `uasset_read.py` line 1912

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_import_optional | 1912 | `bool(archive.read_u8())` | `archive.read_bool()` |

### 3. FEdGraphPinType (read_ed_graph_pin_type) — 4 个字段

**文件:** `uasset_read.py` line 2538-2555

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| is_reference | 2538 | `archive.read_u8() != 0` | `archive.read_bool()` |
| is_weak_pointer | 2539 | `archive.read_u8() != 0` | `archive.read_bool()` |
| is_const | 2550 | `archive.read_u8() != 0` | `archive.read_bool()` |
| is_uobject_wrapper | 2555 | `archive.read_u8() != 0` | `archive.read_bool()` |

**UE 源码验证:**
- `EdGraphPin.cpp:248-283` — `bool bIsReferenceBool = bIsReference; Ar << bIsReferenceBool;`
- 位域字段在结构定义中为 `uint8 bIsReference:1`，但序列化时转换为标准 bool (4 bytes)

### 4. FMemberReference (read_member_reference) — 1 个字段

**文件:** `uasset_read.py` line 2823

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_self_context | 2823 | `archive.read_u8() != 0` | `archive.read_bool()` |

**UE 源码验证:**
- `MemberReference.h:91` — `mutable bool bSelfContext;` 标准 bool 字段
- USTRUCT() 反射系统自动序列化为 4 bytes

### 5. K2NodeCallFunction (read_k2node_call_function) — 1 个字段

**文件:** `uasset_read.py` line 2864

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_defaults_to_pure | 2864 | `archive.read_u8() != 0` | `archive.read_bool()` |

### 6. K2NodeEvent (read_k2node_event) — 1 个字段

**文件:** `uasset_read.py` line 2903

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_override_function | 2903 | `archive.read_u8() != 0` | `archive.read_bool()` |

### 7. UEdGraph (read_ue_graph) — 1 个字段

**文件:** `uasset_read.py` line 3078

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| b_editable | 3078 | `archive.read_u8() != 0` | `archive.read_bool()` |

### 8. UEdGraphPin (read_ue_graph_pin) — 1 个字段

**文件:** `uasset_read.py` line 2650

| 字段名 | 行号 | 当前实现 | 修正实现 |
|--------|------|----------|----------|
| has_parent | 2650 | `archive.read_u8() != 0` | `archive.read_bool()` |

**UE 源码验证:**
- `EdGraphPin.cpp:2137` — `bool bNullPtr = PinRef == nullptr; Ar << bNullPtr;`

---

## 不需要修复的位置

| 位置 | 原因 | UE 源码证据 |
|------|------|------------|
| PropertyTag.bool_val (line 3570) | UE4旧格式使用 uint8 存储 BoolVal，UE5新格式使用位标志 | PropertyTag.cpp — UE4: uint8 BoolVal, UE5: flags & PROP_TAG_BOOL_TRUE |
| PropertyTag.flags (line 3548) | uint8 位域，非 bool | PropertyTag.cpp — uint8 Flags bitfield |
| UEdGraphPin.direction (line 2603) | enum，非 bool | EdGraphPin.h — TEnumAsByte<EEdGraphPinDirection> |
| UEdGraphPin.flags (line 2657) | uint8 位域，非 bool | EdGraphPin.cpp:1902-1923 — uint32 BitField |

---

## 常见陷阱

### Pitfall 1: 位域字段的序列化大小混淆

**错误假设:** 结构定义为 `uint8 bIsReference:1`，因此序列化大小为 1 byte。

**实际情况:** 位域字段在序列化时转换为临时 bool 变量，通过 `operator<<(bool)` 序列化为 4 bytes。

**UE 源码证据:** `EdGraphPin.cpp:248-249`
```cpp
bool bIsReferenceBool = bIsReference;  // 位域转标准 bool
Ar << bIsReferenceBool;                 // 序列化为 uint32
```

**教训:** 结构定义的位域不代表序列化大小。必须检查 Serialize() 实现。

### Pitfall 2: PropertyTag.BoolVal 的特殊处理

**错误假设:** BoolProperty 的值也是标准 bool 序列化。

**实际情况:** PropertyTag 有两种格式：
- UE4: `uint8 BoolVal` 字段（1 byte）
- UE5: `flags & PROP_TAG_BOOL_TRUE` 位标志（0 bits）

**验证:** 当前代码正确，无需修改。

### Pitfall 3: 仅修复 ExportMap/ImportMap

**风险:** 如果只修复导出表和导入表（8 个字段），蓝图图解析会继续失败。

**原因:** FEdGraphPinType、FMemberReference、K2Node 等结构也有 bool 字段，同样使用错误的 read_u8()。

**教训:** 必须全局搜索所有 `bool(.*read_u8())` 和 `read_u8() != 0` 模式。

---

## UE 源码参考

### Archive.h:1535 — Bool 序列化定义

```cpp
inline friend FArchive& operator<<( FArchive& Ar, bool& D )
{
    // Serialize bool as if it were UBOOL (legacy, 32 bit int).
    uint32 OldUBoolValue = 0;
    if (!Ar.IsLoading())
    {
        OldUBoolValue = D ? 1 : 0;
    }
    Ar.Serialize(&OldUBoolValue, sizeof(OldUBoolValue));  // 4 bytes!
    if (Ar.IsLoading())
    {
        D = !!OldUBoolValue;
    }
    return Ar;
}
```

**关键注释:** "Serialize bool as if it were UBOOL (legacy, 32 bit int)" — 自 UE3 开始的标准。

### ObjectResource.cpp:171-200 — FObjectExport 序列化

```cpp
#define SERIALIZE_BIT_TO_RECORD(bValue) { \
    bool b = E.bValue; \
    Record << SA_VALUE(TEXT(#bValue), b); \
    E.bValue = b; \
}

SERIALIZE_BIT_TO_RECORD(bForcedExport);
SERIALIZE_BIT_TO_RECORD(bNotForClient);
SERIALIZE_BIT_TO_RECORD(bNotForServer);
// ... 所有 7 个 bool 字段
```

每个 bool 通过 `Record << bool` 序列化，最终调用 operator<<(bool)，即 4 bytes。

### EdGraphPin.cpp:248-283 — FEdGraphPinType 序列化

```cpp
bool bIsReferenceBool = bIsReference;
bool bIsWeakPointerBool = bIsWeakPointer;

Ar << bIsReferenceBool;  // 4 bytes
Ar << bIsWeakPointerBool; // 4 bytes

// ... 版本检查后
bool bIsConstBool = bIsConst;
if (Ar.UEVer() >= VER_UE4_SERIALIZE_PINTYPE_CONST)
{
    Ar << bIsConstBool;  // 4 bytes
}

bool bIsUObjectWrapperBool = bIsUObjectWrapper;
if (Ar.CustomVer(...) >= ...)
{
    Ar << bIsUObjectWrapperBool;  // 4 bytes
}
```

---

## 验证数据

### 当前解析错误

使用 `BP_FirstPersonCharacter.uasset` (UE 5.7, version_ue5=1017):

```
Is success: True
Errors (17):
  - Property parse error in /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter: 
    Invalid offset -5629499534213120 (negative) at seek
  - Property parse error in None: 
    Offset 68679911499956224 exceeds file size 138384 at seek
  ...

Export entries:
0: Arrow
   Serial offset: 74868  ✓ 有效
   Serial size: 46       ✓ 有效
1: /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter_4294962432
   Serial offset: 14080  ✓ 有效
   Serial size: 0        ✓ 有效
2: /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter
   Serial offset: -5629499534213120  ✗ 无效负值
   Serial size: 566046178165129216   ✗ 无效超大值
```

### 条目大小验证

| 项目 | 计算 | 结果 |
|------|------|------|
| 错误实现 | 各 bool 1 byte | 条目大小 ~75 bytes (错误注释) |
| 正确实现 | 各 bool 4 bytes | 条目大小 ~112 bytes |
| 差异 | 7 bools × 3 bytes + 其他偏移修正 | 37 bytes |

每条目少读 21 bytes (7 × 3)，累积导致后续字段偏移错误。

---

## 测试覆盖

### 当前测试状态

```
350 passed, 49 skipped in 1.23s
```

所有测试使用**合成数据**，不使用真实 UE 5.7 资产，因此测试通过但实际解析失败。

### Wave 0 测试缺口

| 测试文件 | 缺失内容 | 覆盖需求 |
|----------|----------|----------|
| `test_uasset_read.py` | 真实 UE 5.7 资产测试 | 使用 BP_FirstPersonCharacter.uasset 验证导出表解析 |
| `test_graph_parsing.py` | 真实蓝图节点测试 | 验证 FEdGraphPinType bool 字段 |
| `test_bool_serialization.py` | 专门 bool 序列化测试 | 新增文件，覆盖所有 16 个位置 |

---

## 环境可用性

| 依赖 | 需求方 | 可用 | 版本 | 备注 |
|------|--------|------|------|------|
| Python 3.10+ | 解析器 | ✓ | 3.14.3 | match/case 支持 |
| pytest | 测试框架 | ✓ | 9.0.3 | 350 测试通过 |
| BP_FirstPersonCharacter.uasset | 测试资产 | ✓ | UE 5.7 | E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/ |

**无缺失依赖。**

---

## 验证架构

### 测试框架

| 属性 | 值 |
|------|-----|
| Framework | pytest 9.0.3 |
| Config file | 无（使用 pytest.ini 默认） |
| Quick run command | `python -m pytest tests/test_uasset_read.py::test_export_map -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-01 | read_bool() 返回正确 bool 值 | unit | `pytest tests/test_bool_serialization.py::test_read_bool -x` | ❌ Wave 0 新增 |
| FIX-02 | ExportMap 解析所有字段正确 | integration | `pytest tests/test_uasset_read.py::test_ue57_export_map -x` | ❌ Wave 0 新增 |
| FIX-03 | BP_FirstPersonCharacter 解析成功 | integration | `pytest tests/test_ue57_integration.py -x` | ❌ Wave 0 新增 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_bool_serialization.py -x`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green + BP_FirstPersonCharacter 解析无错误

### Wave 0 Gaps

- [ ] `tests/test_bool_serialization.py` — 专门测试 read_bool() 方法
- [ ] `tests/test_ue57_integration.py` — 真实 UE 5.7 资产集成测试
- [ ] `tests/test_uasset_read.py` — 添加 `test_ue57_export_map()` 用例

---

## 安全域

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | 文件大小边界检查 (现有 FArchive.validate_offset) |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 无效偏移导致越界读取 | Tampering | FArchive.validate_offset() 边界检查 (已存在) |
| 累积偏移错误导致解析失败 | Denial of Service | 修复 bool 序列化，恢复正确偏移 |

---

## Sources

### Primary (HIGH confidence)

- `Archive.h:1535` — UE 5.7 源码，bool 序列化定义 [VERIFIED]
- `ObjectResource.cpp:171-200` — UE 5.7 源码，FObjectExport bool 字段序列化 [VERIFIED]
- `EdGraphPin.cpp:248-283` — UE 5.7 源码，FEdGraphPinType bool 字段序列化 [VERIFIED]
- `EdGraphPin.cpp:2132-2137` — UE 5.7 源码，SerializePin has_parent 序列化 [VERIFIED]
- `MemberReference.h:91` — UE 5.7 源码，bSelfContext 定义 [VERIFIED]

### Secondary (MEDIUM confidence)

- `uasset_read.py:2128-2160` — 当前错误实现 [CITED: 代码分析]
- `BP_FirstPersonCharacter_uasset.json` — 解析失败证据 [CITED: 测试输出]

### Tertiary (LOW confidence)

- 无 — 所有发现已通过 UE 源码验证

---

## Metadata

**置信度分析:**
- Standard stack: HIGH — UE 源码直接验证 bool 序列化标准
- Architecture: HIGH — FArchive 模式清晰，添加方法符合设计
- Pitfalls: HIGH — UE 源码明确位域和 PropertyTag 的特殊处理
- 全量位置发现: HIGH — Grep 搜索 + UE 源码验证 16 个位置

**研究日期:** 2026-05-03
**有效期:** 30 天 (UE bool 序列化标准自 UE3 稳定)

---

## RESEARCH COMPLETE

**Phase:** 16 - Bool 序列化修复
**Confidence:** HIGH

### Key Findings

1. **UE bool 序列化标准:** 所有 bool 字段使用 4-byte uint32，自 UE3 开始稳定（Archive.h:1535）
2. **全量位置发现:** 16 个 bool 字段需要修复，覆盖 ExportMap、ImportMap、蓝图图结构
3. **位域陷阱:** FEdGraphPinType 的位域字段（uint8 bIsReference:1）序列化为 4 bytes
4. **PropertyTag 特例:** BoolProperty 在 PropertyTag 中使用 uint8 或位标志，非标准 bool 序列化
5. **测试缺口:** 当前测试使用合成数据，需添加真实 UE 5.7 资产测试

### File Created

`E:\Develop\uasset_read\.planning\phases\16-bool-serialization-fix\16-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | UE 源码直接验证 bool 序列化标准 |
| Architecture | HIGH | FArchive 模式清晰，添加 read_bool() 符合设计 |
| Pitfalls | HIGH | 位域和 PropertyTag 特例通过 UE 源码验证 |
| Locations | HIGH | Grep 全量搜索 + UE 源码验证 16 个位置 |

### Open Questions

无 — 所有疑问已通过 UE 源码验证解决。

### Ready for Planning

研究完成。规划者可以创建 PLAN.md 文件，基于以下修复方案：

**修复方案摘要:**
1. 在 FArchive 类添加 `read_bool()` 方法
2. 替换所有 16 个 `bool(archive.read_u8())` 和 `archive.read_u8() != 0` 为 `archive.read_bool()`
3. 更新错误注释（"各读取 1 byte" → "各读取 4 bytes"）
4. 添加真实 UE 5.7 资产测试用例