# UE 源码参考索引

**目的：** 快速查找 UE 5.x .uasset 格式关键结构，无需每次阅读源码
**更新日期：** 2026-04-28
**源码路径：** `D:/Program Files/Epic Games/Engine/UE_5.7`

---

## 1. 核心文件路径

| 文件 | 路径 | 内容 |
|------|------|------|
| PackageFileSummary.h | CoreUObject/Public/UObject/PackageFileSummary.h | 文件头结构定义 |
| PackageFileSummary.cpp | CoreUObject/Private/UObject/PackageFileSummary.cpp | 文件头序列化 |
| ObjectResource.h | CoreUObject/Public/UObject/ObjectResource.h | Import/Export 结构 |
| Archive.h | Core/Public/Serialization/Archive.h | FArchive 抽象 |
| NameTypes.h | Core/Public/UObject/NameTypes.h | FName 结构 |
| UnrealString.h | Core/Public/Containers/UnrealString.h | FString 序列化 |

---

## 2. PackageFileSummary 结构

### 2.1 魔术标签

```cpp
#define PACKAGE_FILE_TAG         0x9E2A83C1  // 正确字节序
#define PACKAGE_FILE_TAG_SWAPPED 0xC1832A9E  // 交换字节序
```

### 2.2 文件头序列化顺序（PackageFileSummary.cpp line 80-200）

**核心顺序：**
```
Tag (u32)
LegacyFileVersion (i32)  // -2 到 -9

// LegacyFileVersion != -4 时：
LegacyUE3Version (i32)   // UE3 遗留版本

FileVersionUE4 (i32)     // UE4 版本号

// LegacyFileVersion <= -8 时：
FileVersionUE5 (i32)     // UE5 版本号

FileVersionLicenseeUE (i32)
CustomVersionsCount (u32)
[CustomVersion: GUID(16 bytes) + Version(i32)] × Count

PackageFlags (u32)

// 名称表
NameCount (i32)
// LegacyFileVersion >= -5: NameOffset (i32)
// LegacyFileVersion < -5: 名称数据 inline

// 其他偏移...
```

### 2.3 LegacyFileVersion 版本差异

| 版本值 | 含义 | 结构差异 |
|--------|------|----------|
| **-2** | 枚举型自定义版本 | 无 LegacyUE3Version，名称表有 NameOffset |
| **-3** | GUID 型自定义版本 | 无 LegacyUE3Version，名称表有 NameOffset |
| **-4** | 移除 UE3 版本 | **无 LegacyUE3Version**，名称表有 NameOffset |
| **-5** | 替换 UE3 版本写入 | 有 LegacyUE3Version，名称表有 NameOffset |
| **-6** | 自定义版本优化 | 有 LegacyUE3Version，名称表有 NameOffset |
| **-7** | 纹理分配信息移除 | 有 LegacyUE3Version，名称表有 NameOffset |
| **-8** | UE5 版本添加 | 有 LegacyUE3Version，**有 FileVersionUE5**，名称表有 NameOffset |
| **-9** | 提前退出约定变更 | 有 LegacyUE3Version，有 FileVersionUE5，名称表有 NameOffset |

### 2.4 关键条件判断

```cpp
// PackageFileSummary.cpp line 130-134
if (LegacyFileVersion != -4) {
    int32 LegacyUE3Version = 0;
    Record << SA_VALUE(TEXT("LegacyUE3Version"), LegacyUE3Version);
}

// line 138-141
if (LegacyFileVersion <= -8) {  // 注意：<= 而非 >=
    Record << SA_VALUE(TEXT("FileVersionUE5"), Sum.FileVersionUE.FileVersionUE5);
}
```

---

## 3. 名称表结构

### 3.1 FNameEntry 序列化（NameTypes.h）

```cpp
// FNameEntry 序列化格式：
Length (i32)           // 字符串长度（含 null 终止符）
StringBytes (Length)   // UTF-8 或 UTF-16 字符串
Number (i32)           // 实例编号（用于编号名如 "Material_0"）
```

### 3.2 名称表位置

- **LegacyFileVersion >= -5:** NameOffset 指向名称数据起始位置
- **LegacyFileVersion < -5:** 名称数据紧跟 NameCount（无 NameOffset）

---

## 4. Import/Export 结构

### 4.1 FObjectImport (ObjectResource.h)

```cpp
struct FObjectImport {
    FName ClassPackage;    // 来源包名
    FName ClassName;       // 类名
    FPackageIndex OuterIndex;  // Outer 引用（有符号）
    FName ObjectName;      // 对象名
};
```

### 4.2 FObjectExport (ObjectResource.h)

```cpp
struct FObjectExport {
    FPackageIndex ClassIndex;      // 类引用
    FPackageIndex SuperIndex;      // 父类引用
    FPackageIndex OuterIndex;      // Outer 引用
    FName ObjectName;              // 对象名
    EObjectFlags ObjectFlags;      // 对象标志 (u32)
    int64 SerialSize;              // 序列化数据大小
    int64 SerialOffset;            // 序列化数据偏移
    
    // UE5+ 字段（取决于版本）：
    int64 ScriptSerialSize;        // 脚本序列化大小
    int64 ScriptSerialOffset;      // 脚本序列化偏移
};
```

### 4.3 FPackageIndex 编码

```cpp
struct FPackageIndex {
    int32 Index;  // 有符号编码
    
    // Index > 0: ExportMap[Index - 1]
    // Index < 0: ImportMap[-Index - 1]
    // Index = 0: null
    
    bool IsImport() const { return Index < 0; }
    bool IsExport() const { return Index > 0; }
    bool IsNull() const { return Index == 0; }
    
    int32 ToImport() const { return -Index - 1; }
    int32 ToExport() const { return Index - 1; }
};
```

---

## 5. CustomVersion 结构

```cpp
struct FCustomVersion {
    FGuid Key;      // 16 bytes GUID
    int32 Version;  // 版本号
};
```

---

## 6. FString 序列化

```cpp
// UnrealString.h 序列化格式：
int32 Length;           // 字符串长度
if (Length == 0) return "";
if (Length > 0) {
    // UTF-8 编码
    char[] Data = read(Length);
    return Data.rstrip('\x00');
} else if (Length < 0) {
    // UTF-16 编码（UE4 风格）
    wchar[] Data = read(-Length * 2);
    return Data.rstrip(L'\x00');
}
```

---

## 7. 已知问题与陷阱

### 7.1 版本条件方向错误

**错误代码：**
```python
if legacy_file_version >= -8:  # 错误！
    file_version_ue5 = archive.read_i32()
```

**正确代码：**
```python
if legacy_file_version <= -8:  # 正确（UE 源码使用 <=）
    file_version_ue5 = archive.read_i32()
```

### 7.2 Python dataclass 字段顺序

Python 要求无默认值字段在有默认值字段之前：
```python
@dataclass
class PackageFileSummary:
    tag: int                    # 无默认值 → 必须在前
    legacy_file_version: int     # 无默认值 → 必须在前
    file_version_ue4: int        # 无默认值 → 必须在前
    legacy_ue3_version: int = 0  # 有默认值 → 必须在后
    file_version_ue5: int = 0    # 有默认值 → 必须在后
```

---

## 8. 测试案例

### 8.1 合成测试文件（legacy=-8）

```
LegacyFileVersion: -8 (< -5)
格式: NameCount + inline names (FString) + SoftObjectPaths...
状态: 解析成功
```

### 8.2 Lyra Character_Default.uasset（legacy=-7）

```
文件大小: 20154 bytes
Tag: 0x9e2a83c1
LegacyFileVersion: -7 (>= -5)
LegacyUE3Version: 864
FileVersionUE4: 521
NameCount: 5

问题:
- Pos 208-212: NameCount = 5 ✓
- Pos 212-216: 值为 1701736270 (ASCII "None")
- 预期应为 NameOffset，但实际是 name data 起始
- 这意味着 legacy=-7 文件也使用 inline names 格式？

状态: 解析失败（NameOffset 读取导致错位）
待研究: UE5 legacy=-7 格式是否与 -8 不同
```

---

*索引创建日期: 2026-04-28*
*源码版本: UE 5.7*