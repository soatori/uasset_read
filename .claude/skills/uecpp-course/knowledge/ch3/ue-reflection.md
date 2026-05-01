# UE 反射系统

## 概述

UE 反射系统是 UEC++ 所有宏体系（UCLASS、UPROPERTY、UFUNCTION 等）的底层基础设施。它让 C++ 类在编译时生成元数据，使引擎能在运行时获取类型信息、序列化对象、集成编辑器、追踪 GC 根、执行网络复制。

## UHT（Unreal Header Tool）

- 编译管线中的预处理步骤，在标准 C++ 编译之前运行
- 解析 UCLASS/USTRUCT/UENUM/UINTERFACE/UPROPERTY/UFUNCTION 等宏
- 为每个标记了 UE 宏的类型生成对应的 `.generated.h` 文件
- `.generated.h` 包含反射元数据、`GENERATED_BODY()` 展开所需的支持代码

## GENERATED_BODY

- 必须写在整个类定义体内部
- UHT 在此位置插入反射支持代码（虚函数重写、类型注册、序列化接口等）
- UCLASS 和 USTRUCT 都要求此宏
- USTRUCT 使用专用的 `GENERATED_USTRUCT_BODY()`

## 反射能力

所有继承自 UObject 的类型通过反射获得以下能力：

| 能力 | 说明 |
|------|------|
| 运行时类型识别 | `IsA<T>()`、`Cast<T>()`、`GetClass()` |
| 序列化/反序列化 | SaveGame、网络复制、关卡加载保存 |
| 编辑器集成 | 细节面板属性编辑、蓝图节点自动生成 |
| GC 追踪 | UPROPERTY 标记的引用由 GC 追踪 |
| 元数据访问 | 运行时读取 UCLASS/UPROPERTY/UFUNCTION 上的 specifiers 和 meta |

## 三句要点

1. UHT 不是编译器，是预处理器——它在 C++ 编译前扫描头文件，生成 `.generated.h`
2. `GENERATED_BODY` 是通往反射世界的入口，所有 UEC++ 类型都必须包含
3. 反射的核心收益在编辑器集成、序列化和 GC——这三项是 UE 区别于普通 C++ 的关键

## 配套代码

| 知识点 | 代码文件 |
|--------|----------|
| `GENERATED_BODY()` 在 UCLASS 中的使用 | [XGBaseObject.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseObject.h) |
| `GENERATED_USTRUCT_BODY()` 在 USTRUCT 中的使用 | [XGBaseStruct.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStruct.h) |
| `UCLASS()` / `UPROPERTY()` / `UFUNCTION()` 宏标记 | [XGPropertyActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGPropertyActor.h) |
| `UENUM()` 宏标记 | [XGBaseStructEnum.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStructEnum.h) |
| `UINTERFACE()` 双类模式 | [InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h) |
