# TSet DefaultKeyFuncs 与实用工具

## 结构体作为 TSet 键

使用自定义结构体作为 TSet 元素时，必须重载 `operator==` 和 `GetTypeHash`，规则与 TMap 完全一致：

```cpp
USTRUCT()
struct FMyStruct
{
    GENERATED_BODY()
    UPROPERTY()
    int32 ID;
    UPROPERTY()
    FString Name;

    bool operator==(const FMyStruct& Other) const
    {
        return ID == Other.ID;
    }
};

// 必须重载全局 GetTypeHash
FORCEINLINE uint32 GetTypeHash(const FMyStruct& S)
{
    return HashCombine(GetTypeHash(S.ID), GetTypeHash(S.Name));
}
```

> 注意：`operator==` 和 `GetTypeHash` 是 TSet **必需**的，不像 TMap 中仅作为结构体作为键时的要求。TSet 的每个元素都参与哈希和比较。

## DefaultKeyFuncs

TSet 的 DefaultKeyFuncs 比 TMap 更简单，因为没有 TPair 封装，元素本身就是键。

```cpp
template<typename ElementType>
struct DefaultKeyFuncs
{
    // Type definitions
    using KeyInitType = typename TCallTraits<ElementType>::ParamType;
    using ElementInitType = typename TCallTraits<ElementType>::ParamType;

    // GetSetKey — 从元素中提取键（对 TSet 而言就是元素本身）
    static KeyInitType GetSetKey(ElementInitType Element)
    {
        return Element;
    }

    // Matches — 比较两个元素是否相等
    static bool Matches(KeyInitType A, KeyInitType B)
    {
        return A == B;
    }

    // GetKeyHash — 计算元素的哈希值
    static uint32 GetKeyHash(KeyInitType Key)
    {
        return GetTypeHash(Key);
    }
};
```

| Typedef | TSet（本容器） | TMap（参考对比） |
|---------|---------------|-----------------|
| KeyInitType | 元素类型本身（参与哈希的属性） | 键类型 |
| ElementInitType | 元素类型本身 | TPair\<KeyType, ValueType\> |

| 静态方法 | TSet | TMap |
|---------|------|------|
| GetSetKey | 返回元素本身 | 从 TPair 中提取 Key |
| Matches | 比较两个元素是否相等 | 比较两个 key 是否相等 |
| GetKeyHash | 计算元素哈希值 | 计算 key 的哈希值 |

对于 TSet，KeyInitType 和 ElementInitType 都指向元素类型本身（简化了 TMap 中 KeyInitType ≠ KeyType 的复杂关系）。

## 自定义 KeyFuncs

当需要自定义比较和哈希逻辑时，可以实现自己的 KeyFuncs：

```cpp
struct FMyStructKeyFuncs : public DefaultKeyFuncs<FMyStruct>
{
    static uint32 GetKeyHash(const FMyStruct& S)
    {
        // 仅基于 ID 计算哈希
        return GetTypeHash(S.ID);
    }

    static bool Matches(const FMyStruct& A, const FMyStruct& B)
    {
        return A.ID == B.ID;
    }
};

// 使用时作为模板参数传入
TSet<FMyStruct, FMyStructKeyFuncs> MySet;
```

## 内存调试工具

### GetAllocatedSize

返回 TSet 当前分配的总内存大小（字节），包括所有元素和内部结构所占内存：

```cpp
uint32 MemSize = FruitSet.GetAllocatedSize();
```

### Dump

向调试输出打印 TSet 的详细内存布局信息，适合调试时查看内部结构。

### CountBytes

计算 TSet 在指定归档器中占用的字节数，用于序列化场景：

```cpp
uint32 SerSize = FruitSet.CountBytes(Ar);
```

## 代码引用

本章源码未包含 KeyFuncs 和内存调试工具的示例代码。上述 API 为 UE 标准容器接口，可在任意 TSet 实例上调用。

- [SetActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.h)：TSet 声明和蓝图暴露
- [SetActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp)：基础操作实现
