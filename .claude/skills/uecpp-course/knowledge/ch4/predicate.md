# 二元谓词与 Lambda

## 二元谓词排序

`Sort()` 可以传入自定义比较函数（二元谓词），决定排序规则：

```cpp
// 降序排列
Arr.Sort([](const int32& A, const int32& B)
{
    return A > B;
});
```

## Lambda 表达式语法

```cpp
[capture](parameters) -> return_type
{
    body
};
```

- **捕获** `[]`：指定外部变量的访问方式
- **参数** `()`：传入的参数
- **返回类型** `->`：可选，可省略由编译器推导
- **函数体** `{}`：具体逻辑

## 捕获方式

| 方式 | 写法 | 说明 |
|------|------|------|
| 值捕获 | `[Val]` | 拷贝外部变量到 Lambda，外部变量后续变化不影响 Lambda |
| 引用捕获 | `[&Val]` | 引用外部变量，Lambda 内修改会影响外部 |
| 全部值捕获 | `[=]` | 所有外部变量按值捕获 |
| 全部引用捕获 | `[&]` | 所有外部变量按引用捕获 |

## 实战案例：结构体排序

```cpp
USTRUCT()
struct FCharacterInfo
{
    GENERATED_BODY()

    UPROPERTY() int32 ID;
    UPROPERTY() int32 Money;
    UPROPERTY() FString Name;
};

TArray<FCharacterInfo> Characters;

// 按 ID 升序
Characters.Sort([](const FCharacterInfo& A, const FCharacterInfo& B)
{
    return A.ID < B.ID;
});

// 按 Money 降序
Characters.Sort([](const FCharacterInfo& A, const FCharacterInfo& B)
{
    return A.Money > B.Money;
});
```

## 应用场景

- 物品栏排序（按品质、类型、ID）
- 怪物图鉴排序（按 ID、HP、攻击力等）
- 排行榜排序（按分数降序）

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGSortArray3()`, `XGSortArray4()`
