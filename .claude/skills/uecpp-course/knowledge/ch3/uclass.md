# UCLASS 宏

## 基本语法

```cpp
UCLASS([specifier1, specifier2, ...])
class XGSAMPLEDEMO_API AMyClass : public AActor
{
    GENERATED_BODY()
};
```

## 常用 Specifiers

| Specifier | 说明 |
|-----------|------|
| `BlueprintType` | 可在蓝图中作为变量类型使用 |
| `Blueprintable` | 可在蓝图中继承此类 |
| `MinimalAPI` | 仅导出类型本身，不导出类方法（常用于接口类） |

## XGSAMPLEDEMO_API

- 由 UHT 生成，用于控制 DLL 导出/导入的可见性宏
- 单模块项目可以省略，但 UHT 默认会生成
- 跨模块引用时必须保留

## 要点

1. UCLASS 宏必须写在 class 关键字之前
2. 宏括号内可以同时使用多个 specifier，用逗号分隔
3. `GENERATED_BODY()` 是 UCLASS 类必须包含的宏，UHT 在此处插入反射支持代码

## 配套代码

| 知识点 | 代码文件 |
|--------|----------|
| UCLASS 完整声明示例 | [XGClassActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.h) |
| `BlueprintType` 用法 | [XGBaseObject.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseObject.h) |
| `MinimalAPI` 用法 | [InterfaceActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/003_UInterface/InterfaceActor.h) |
| `XGSAMPLEDEMO_API` 导出宏 | [XGClassActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGClassActor.h) |
