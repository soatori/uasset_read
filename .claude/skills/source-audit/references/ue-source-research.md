# UE Source Research

## Overview

针对解析器实现中的具体问题，快速定位 UE 引擎 C++ 源码中的对应序列化逻辑，返回文件路径、函数名、字段顺序。

## 触发场景

- "UE 里这个结构体怎么序列化的？"
- "FString 的编码方式是什么？"
- "PackageIndex 在 UE 里是什么格式？"
- 需要对照源码确认二进制格式

## UE 源码路径

基础路径：`E:\Develop\lib\UnrealEngine`

常用模块：

| 模块 | 路径 |
|------|------|
| Core 序列化 | `Engine/Source/Runtime/Core/Private/Serialization/` |
| UObject 序列化 | `Engine/Source/Runtime/CoreUObject/Private/Serialization/` |
| 属性系统 | `Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h` |
| Linker 加载 | `Engine/Source/Runtime/CoreUObject/Private/Serialization/LinkerLoad.cpp` |
| 蓝图节点 | `Engine/Source/Runtime/Engine/Classes/Engine/EngineTypes.h` |
| Kismet 字节码 | `Engine/Source/Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h` |

## 工作流

```
问题 → 定位 UE 源码文件 → 读取序列化函数 → 提取字段顺序 → 对照解析器 → 输出参考
```

### Step 1: 定位源码

```bash
# 搜索特定结构体
find "E:/Develop/lib/UnrealEngine" -name "*.cpp" -exec grep -l "FString::Serialize" {} \;

# 搜索特定函数
find "E:/Develop/lib/UnrealEngine" -name "*.cpp" -exec grep -l "operator<<.*FArchive.*FName" {} \;
```

### Step 2: 读取序列化逻辑

关注模式：
- `operator<<(FArchive& Ar, ...)` — 序列化入口
- `Ar << member` — 字段读取顺序
- `if (Ar.IsLoading())` — 加载时分支
- `Ar.Ver() >= VER_XXX` — 版本门控

### Step 3: 输出参考

```markdown
## UE 源码参考：FString 序列化

文件: `Engine/Source/Runtime/Core/Private/Serialization/Archive.cpp`
函数: `operator<<(FArchive& Ar, FString& S)`

字段顺序:
1. int32 Length（字节数，含终止符）
2. if Length > 0: ANSICHAR* Data（UTF-8 或 TCHAR）
3. if Ar.IsUnicode(): wchar_t* WideData（UTF-16）

版本差异:
- UE4: 仅 ANSI
- UE5: 根据 Ar.IsUnicode() 决定编码

解析器对照: `archive.py:read_fstring()` 已对齐
```

## 常见查询

| 问题 | UE 源码位置 |
|------|------------|
| FName 格式 | `Core/UObjectBase.cpp` — `FName::Serialize()` |
| FString 编码 | `Core/Serialization/Archive.cpp` — `operator<<(FArchive&, FString&)` |
| PackageIndex | `CoreUObject/Serialization/ObjectResource.cpp` |
| FPropertyTag | `CoreUObject/Serialization/PropertyTag.cpp` |
| CustomVersion | `Core/Serialization/CustomVersion.cpp` |

## 注意事项

- 仅读取源码，不修改 UE 引擎
- UE 源码版本需与资产版本匹配（UE5.7 / UE5.8）
- 结论必须包含具体文件路径和行号
