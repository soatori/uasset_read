# USTRUCT 宏

## 基本语法

```cpp
USTRUCT(BlueprintType)
struct FXGBaseStruct
{
    GENERATED_USTRUCT_BODY();

    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    FString StructName;
};
```

## 要点

| 特性 | 说明 |
|------|------|
| `GENERATED_USTRUCT_BODY()` | USTRUCT 专用，非 `GENERATED_BODY()` |
| UPROPERTY 支持 | 字段可以用 UPROPERTY 标记，获得反射、序列化、蓝图可见能力 |
| 非 UObject | 结构体不属于 UObject 生态，**不参与 GC** |
| BlueprintType | 使结构体可在蓝图中作为变量类型 |
| Break/Make 节点 | 只要至少一个字段标记为 `BlueprintReadOnly` 或 `BlueprintReadWrite`，引擎自动生成 Break 和 Make 节点 |
| 适用场景 | 简单数据组合。复杂交互应使用 UObject 或 Actor |

## 完整示例

```cpp
USTRUCT(BlueprintType)
struct FXGPropertyStruct2
{
    GENERATED_USTRUCT_BODY();

    UPROPERTY(BlueprintReadOnly, EditAnywhere)
    FString StructName1;

    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    FString StructName2;

    UPROPERTY(BlueprintReadWrite, EditAnywhere)
    UObject* ObjectPtr = nullptr;
};
```

参考实现：[XGBaseStruct.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/001_BaseType/XGBaseStruct.h) | `FXGPropertyStruct2`（含 UObject* 指针的结构体）位于同文件

## 关于 UObject* 指针

结构体可以包含 `UObject*` 指针，但需要注意：
- 结构体自身不参与 GC，不会被自动追踪
- 如果结构体中持有 UObject 指针，需要在外部确保该对象的生命周期有效性
- 这是 USTRUCT 和 UCLASS 在内存管理上的关键区别
