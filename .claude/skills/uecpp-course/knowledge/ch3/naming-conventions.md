# UE 命名规范

## 前缀规则

| 前缀 | 用途 | 示例 |
|------|------|------|
| U | UObject 子类 | `UXGBaseObject` |
| A | Actor 子类 | `AXGClassActor` |
| S | Slate 控件 | `SMyWidget` |
| I | 接口类（原接口类） | `IXGHealthInterface` |
| F | 结构体/其他（非 UObject/Actor/Slate 类型） | `FXGBaseStruct` |
| E | 枚举 | `EMYUENUM` |
| T | 模板类 | `TArray`、`TSubclassOf`、`TWeakPtr` |
| b | bool 变量 | `bIsHungry`、`bCanEverTick` |

## 命名风格

- 使用 **PascalCase**（每个单词首字母大写）
- 违反此命名规则可能导致编译错误或运行时反射异常
- Typedefs 的前缀通常与所指向的类型一致（例如指向 UObject 的类型用 U 前缀）

## 三点说明

1. 前缀是命名约定而非语言强制，但 UE 的编辑器集成和部分工具链依赖这些约定来正确识别类型
2. `b` 前缀只用于 bool 成员变量，函数参数和局部变量可以不遵守
3. 接口类遵循双类命名：`U` 前缀用于反射元数据类，`I` 前缀用于实现类

## 配套代码

| 类/类型 | 代码文件 |
|---------|----------|
| `UXGBaseObject`（U 前缀示例） | [XGBaseObject.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseObject.h) |
| `AXGClassActor`（A 前缀示例） | [XGClassActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.h) |
| `IXGHealthInterface`（I 前缀示例） | [InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h) |
| `FXGBaseStruct`（F 前缀示例） | [XGBaseStruct.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStruct.h) |
| `FXGPropertyStruct2`（F 前缀示例） | [XGBaseStruct.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStruct.h) |
| `EMYUENUM`（E 前缀示例） | [XGBaseStructEnum.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStructEnum.h) |
| `AXGBaseActor`（Actor 基类示例） | [XGBaseActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseActor.h) |
| `EXGActorType`（E 前缀示例） | [InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h) |
