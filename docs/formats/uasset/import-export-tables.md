# Import/Export 表结构

## 概述

Import 表存储本包引用的外部对象（其他包中的对象），Export 表存储本包导出的对象（可以被其他包引用）。FPackageIndex 是引用的统一表示：正数指向 Export，负数指向 Import，0 表示空引用。

ImportCount/ImportOffset 和 ExportCount/ExportOffset 在 PackageFileSummary 中记录。详见 [file-header.md](file-header.md) 中 FPackageFileSummary 的 Import/Export 表字段。

## Import 表 (FObjectImport)

### 结构体定义

```cpp
struct FObjectImport {
    FPackageIndex ClassPackage;    // 类所在的包引用
    FPackageIndex ClassIndex;      // 类对象引用
    FPackageIndex OuterIndex;      // 外部对象引用
    FName ObjectName;              // 对象名称
    bool bOptional;                // 是否为可选导入
};
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| ClassPackage | FPackageIndex | 类所在的包引用（负数指向其他 Import 条目） |
| ClassIndex | FPackageIndex | 类对象引用（如 UClass） |
| OuterIndex | FPackageIndex | 外部对象引用，定义对象的层级关系 |
| ObjectName | FName | 对象名称 |
| bOptional | bool | 是否为可选导入 |

## Export 表 (FObjectExport)

### 结构体定义

```cpp
struct FObjectExport {
    FPackageIndex ClassIndex;        // 类引用
    FPackageIndex SuperIndex;        // 父类引用
    FPackageIndex TemplateIndex;     // 模板对象引用
    FPackageIndex OuterIndex;        // 外部对象引用
    FName ObjectName;                // 对象名称
    uint32 ObjectFlags;              // 对象标志
    int64 SerialSize;                // 序列化数据大小
    int64 SerialOffset;              // 序列化数据在文件中的偏移
    // ... 更多字段取决于版本
};
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| ClassIndex | FPackageIndex | 类引用 |
| SuperIndex | FPackageIndex | 父类引用 |
| TemplateIndex | FPackageIndex | 模板对象引用（Archetype） |
| OuterIndex | FPackageIndex | 外部对象引用 |
| ObjectName | FName | 对象名称 |
| ObjectFlags | uint32 | 对象标志位 |
| SerialSize | int64 | 序列化数据大小（UE4.26+ 为 64 位） |
| SerialOffset | int64 | 序列化数据在文件中的偏移（UE4.26+ 为 64 位） |

## FPackageIndex

### 编码规则

FPackageIndex 是有符号整数，编码规则如下：

| 值范围 | 含义 |
|--------|------|
| 0 | 空引用 (None) |
| > 0 | 指向 Export 表，索引为 `value - 1` |
| < 0 | 指向 Import 表，索引为 `abs(value) - 1` |

### 序列化

```cpp
// FPackageIndex 序列化为单个 int32
Ar << Index;
```

## 源码引用

- `Runtime/CoreUObject/Public/UObject/ObjectResource.h` — FObjectImport、FObjectExport、FPackageIndex 定义
- `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` — Import/Export 表加载实现
