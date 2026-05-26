# UE 加载方式修正分析报告

**日期：** 2026-05-14
**目的：** 分析当前 Python 直接字节读取与 UE 编辑器 FLinkerLoad 加载机制的差异，制定修正计划
**源码参考：** `E:/Develop/lib/UnrealEngine/Engine/Source` (UE 5.7)

---

## 1. 执行摘要

当前项目采用**直接字节读取**模式解析 .uasset 文件，功能上能够提取大部分数据，但与 UE 编辑器的实际加载机制存在**系统性偏移**。这些偏移导致：

1. **Pin 连接读取失败**（linked_to_raw 为空）— 4 字节偏移问题
2. **版本条件判断错误**（LegacyFileVersion <= -8 误用为 >= -8）
3. **缺失 UE5 新增字段**（bSerializeAsSinglePrecisionFloat、bIsUObjectWrapper 等）
4. **布尔值序列化差异**（UE4 用 4-byte uint32，UE5 用 1-byte uint8）

**根本原因：** 当前实现基于对 UE 文件格式的**静态理解**，而非模拟 UE 的**动态加载流程**。UE 不是"直接读取字节"，而是通过 FLinkerLoad 重建对象图。

---

## 2. 当前字节读取部分分类

### 2.1 文件头读取（PackageFileSummary）

**文件：** `src/uasset_read/serializers/package_summary.py`（483 行）

| 操作 | 行号 | 读取方式 | UE 对照 | 状态 |
|------|------|---------|---------|------|
| 魔数检测 | 124-129 | `read_u32()` + 字节交换 | PackageFileSummary.cpp:80 | ✓ 正确 |
| LegacyFileVersion | 131 | `read_i32()` | PackageFileSummary.cpp:85 | ✓ 正确 |
| **FileVersionUE5 条件** | 142-145 | `if legacy_file_version <= -8` | PackageFileSummary.cpp:138 | ⚠️ **正确但曾错误** |
| SavedHash | 157-158 | `read(20)` | PackageFileSummary.cpp:110 | ✓ 正确 |
| CustomVersions | 162-177 | `read(16)` + `read_i32()` | PackageFileSummary.cpp:95-105 | ✓ 正确 |
| NameCount/Offset | 188-194 | `read_i32()` × 2 | PackageFileSummary.cpp:145-150 | ✓ 正确 |
| ExportCount/Offset | 224-230 | `read_i32()` × 2 | PackageFileSummary.cpp:165-170 | ✓ 正确 |
| ImportCount/Offset | 233-239 | `read_i32()` × 2 | PackageFileSummary.cpp:175-180 | ✓ 正确 |

**问题：** 曾存在 `legacy_file_version >= -8` 错误（应为 `<= -8`），已修复。

### 2.2 Import/Export Map 读取

**文件：** `src/uasset_read/serializers/object_resources.py`

| 操作 | 读取方式 | UE 对照 | 状态 |
|------|---------|---------|------|
| FObjectImport | `read_name()` × 3 + `read_i32()` + `read_bool()` | ObjectResource.h:150-154 | ✓ 正确 |
| FObjectExport (UE4<517) | `read_i32()` for SerialSize/Offset | ObjectResource.h:206-207 | ✓ 正确 |
| FObjectExport (UE4>=517) | `read_i64()` for SerialSize/Offset | ObjectResource.h:206-207 | ✓ 正确 |
| **ScriptSerialOffset/Size** | `read_i64()` (UE5>=1010) | ObjectResource.h:215-216 | ✓ 正确 |

**问题：** 无明显偏移问题，但缺少 bIsInheritedInstance 等 UE5 新增字段的完整处理。

### 2.3 PropertyTag 读取

**文件：** `src/uasset_read/serializers/property_tags.py`

| 操作 | 读取方式 | UE 对照 | 状态 |
|------|---------|---------|------|
| Name | `read_name()` | PropertyTag.cpp:50 | ✓ 正确 |
| **TypeName** | `read_name()` | PropertyTag.cpp:55 | ⚠️ **UE5 使用 CompleteTypeName** |
| Size | `read_i32()` | PropertyTag.cpp:60 | ✓ 正确 |
| Flags | `read_u8()` | PropertyTag.cpp:65 | ✓ 正确 |
| **Extensions** | `read_u8()` (条件) | PropertyTag.cpp:80 | ⚠️ **UE5 >= 1011 新增** |

**问题：** UE5 的 CompleteTypeName 包含嵌套类型信息，当前实现可能丢失类型层次。

### 2.4 Blueprint Graph 读取（**核心问题区域**）

**文件：** `src/uasset_read/serializers/graph.py`

| 操作 | 读取方式 | UE 对照 (EdGraphPin.cpp) | 状态 |
|------|---------|------------------------|------|
| **FEdGraphPinType 字段顺序** | 自定义顺序 | EdGraphPin.cpp:200-245 | 🔴 **4 字节偏移根源** |
| **bSerializeAsSinglePrecisionFloat** | **缺失** | EdGraphPin.cpp:240 | 🔴 **缺失字段** |
| **bIsUObjectWrapper** | **缺失** | EdGraphPin.cpp:245 | 🔴 **缺失字段** |
| **布尔值序列化** | `read_bool()` (4-byte) | EdGraphPin.cpp:225-245 | 🔴 **UE5 用 1-byte** |
| **位字段压缩** | 分别读取 | EdGraphPin.cpp:370-400 | ⚠️ **UE 打包为 uint8** |
| FText 读取 | `read_ftext_with_history()` | TextProperty.cpp:100 | ⚠️ **部分实现** |
| LinkedTo 数组 | `read_pin_array()` | EdGraphPin.cpp:345 | ⚠️ **偏移错误导致空列表** |

**核心问题：**
1. **缺失字段导致偏移累积：** bSerializeAsSinglePrecisionFloat (1 byte) + bIsUObjectWrapper (1 byte) + 其他布尔差异 = 约 4 字节偏移
2. **布尔值序列化差异：** UE4 用 `read_bool()` (4-byte uint32)，UE5 用 `read_bool_ue5()` (1-byte uint8)
3. **位字段压缩：** UE 将多个 editor-only bool 打包为单个 uint8，Python 分别读取

---

## 3. UE 加载机制与 Python 实现的根本差异

### 3.1 架构差异

| 维度 | Python 当前实现 | UE FLinkerLoad |
|------|----------------|----------------|
| **加载模式** | 直接字节读取（线性） | 对象图重建（两阶段） |
| **版本处理** | 手动 FileVersion 检查 | CustomVersion 系统 |
| **属性读取** | 假设固定布局 | PropertyTag 标签系统 |
| **引用解析** | 存储索引，不解析 | ImportMap/ExportMap 解析 |
| **对象创建** | 无，只提取数据 | StaticConstructObject_Internal() |
| **序列化方式** | 手动 struct.unpack | Object->Serialize(*this) |

### 3.2 关键差异详解

#### 差异 1：对象图重建

**UE 方式：**
```cpp
// FLinkerLoad::CreateExport()
UObject* Object = StaticConstructObject_Internal(Class);
Export.Object = Object;  // 建立对象引用
LoadedObjects.Add(Object);

// FLinkerLoad::Preload()
Object->Serialize(*this);  // 对象自身知道如何序列化
```

**Python 当前方式：**
```python
properties = parse_properties_from_export(archive, export, summary, name_map)
# 没有对象创建，只有数据提取
```

**影响：** Python 无法正确解析跨对象引用，只能存储索引。

#### 差异 2：PropertyTag 系统

**UE 方式：**
```cpp
// UE5 使用 CompleteTypeName
Slot << SA_ATTRIBUTE("Type", Tag.CompleteTypeName);  // 包含嵌套类型
```

**Python 当前方式：**
```python
type_name = archive.read_name(name_map)  # 只读简单类型名
```

**影响：** UE5 的 StructProperty 可能丢失内部类型信息。

#### 差异 3：EdGraphPin 序列化

**UE 方式（EdGraphPin.cpp）：**
```cpp
// Editor-only 数据使用位字段压缩
if (Ar.IsPersistent() && !Ar.IsSaving())
{
    uint8 Flags = 0;
    Flags |= bAdvancedView ? 0x01 : 0;
    Flags |= bHidden ? 0x02 : 0;
    Flags |= bNotConnectable ? 0x04 : 0;
    // ... 更多位字段
    Ar << Flags;
}
```

**Python 当前方式：**
```python
bAdvancedView = archive.read_bool()  # 4 bytes!
bHidden = archive.read_bool()  # 4 bytes!
bNotConnectable = archive.read_bool()  # 4 bytes!
```

**影响：** 每个 bool 多读 3 bytes，累积导致严重偏移。

---

## 4. 修正方案

### 4.1 修正原则

1. **对齐 UE 源码：** 严格对照 UE 5.7 源码修正字段顺序和类型
2. **最小侵入：** 保持现有架构，只修正偏移问题
3. **版本兼容：** 同时支持 UE4 和 UE5 格式
4. **可验证：** 每个修正都有测试用例验证

### 4.2 修正范围

| 修正项 | 影响文件 | 预计工作量 |
|--------|---------|-----------|
| FEdGraphPinType 字段补全 | `serializers/graph.py` | 2 小时 |
| UEdGraphPin 布尔值修正 | `serializers/graph.py` | 2 小时 |
| 位字段压缩实现 | `serializers/graph.py` | 3 小时 |
| PropertyTag CompleteTypeName | `serializers/property_tags.py` | 2 小时 |
| 集成测试验证 | `tests/` | 4 小时 |
| **总计** | | **~13 小时** |

### 4.3 修正策略

#### 策略 A：直接修正（推荐）

**优点：**
- 工作量小，直接修正偏移
- 保持现有架构不变
- 快速解决 linked_to_raw 空列表问题

**缺点：**
- 仍然是"直接字节读取"模式
- 不解决根本的架构差异

**实施步骤：**
1. 对照 EdGraphPin.cpp 修正 FEdGraphPinType 字段顺序
2. 添加缺失字段：bSerializeAsSinglePrecisionFloat、bIsUObjectWrapper
3. 修正布尔值序列化：UE5 使用 read_bool_ue5()
4. 实现位字段压缩/解压缩
5. 编写集成测试验证

#### 策略 B：模拟 FLinkerLoad（长期）

**优点：**
- 根本解决架构差异
- 支持完整对象图重建
- 与 UE 编辑器行为一致

**缺点：**
- 工作量大（预计 40+ 小时）
- 需要重构现有架构
- 超出当前项目范围

**实施步骤：**
1. 实现 PackageLinker 类
2. 建立 ImportMap/ExportMap 引用解析
3. 创建 Python UObject 模拟类
4. 实现 Object->Serialize() 模式
5. 实现惰性加载机制

---

## 5. 里程碑调整建议

### 5.1 当前状态

- **v6.0**：模块化重构（Phase 27-35e）— 进行中
- **v7.0**：BulkData 解析 — 规划中
- **v8.0**：UberGraph 增强/字节码反编译 — 规划中
- **v9.0**：.umap 解析/JSON Schema — 规划中

### 5.2 建议调整

在 v6.0 和 v7.0 之间插入 **v6.5：UE 加载方式对齐修正**

**理由：**
1. 当前 Pin Offset 问题（Phase 35e）只是冰山一角
2. 系统性偏移会影响后续所有扩展功能
3. 在进入 BulkData 等复杂功能前，需要确保基础加载机制正确

**v6.5 范围：**
- Phase 36：UE 源码对照修正（FEdGraphPinType/UEdGraphPin）
- Phase 37：PropertyTag CompleteTypeName 支持
- Phase 38：布尔值序列化统一（UE4/UE5 兼容）
- Phase 39：位字段压缩实现
- Phase 40：集成测试与验证

**预期成果：**
- linked_to_raw 正确填充
- 执行流/数据流完整构建
- UE4/UE5 格式完全兼容
- 373+ 测试全部通过

---

## 6. 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| UE 源码版本差异 | 中 | 中 | 对照 UE 5.7 源码，测试 Lyra 资产 |
| 修正引入回归 | 低 | 高 | 保留现有测试，新增回归测试 |
| 版本条件复杂化 | 中 | 中 | 使用 CustomVersion 系统 |
| 位字段实现错误 | 低 | 高 | 逐字节对比 UE 序列化输出 |

---

## 7. 结论与建议

### 7.1 结论

当前项目的字节读取实现与 UE 编辑器加载机制存在**系统性偏移**，主要体现在：

1. **字段缺失：** FEdGraphPinType 缺少 bSerializeAsSinglePrecisionFloat、bIsUObjectWrapper
2. **序列化差异：** 布尔值在 UE4/UE5 中使用不同大小
3. **位字段压缩：** UE 将多个 bool 打包，Python 分别读取
4. **架构差异：** 直接字节读取 vs 对象图重建

### 7.2 建议

1. **短期（v6.5）：** 采用策略 A，直接修正偏移问题
2. **中期（v7.0）：** 引入 PropertyTag CompleteTypeName 支持
3. **长期（v8.0+）：** 考虑模拟 FLinkerLoad 架构

### 7.3 下一步

1. 创建 v6.5 里程碑规划
2. 制定 Phase 36-40 详细计划
3. 更新 ROADMAP.md 和 STATE.md
4. 开始 Phase 36 实施

---

*报告完成日期: 2026-05-14*
*分析师: Claude Code*
*源码版本: UE 5.7*
