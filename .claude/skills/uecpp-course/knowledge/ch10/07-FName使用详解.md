# FName 使用详解

## 声明方式

```cpp
// 基本声明（字符串存在时复用已有条目）
FName MyFName1 = FName(TEXT("OnlyTest"));

// 从 FString 构造
FString SomeString = TEXT("TestName");
FName NameFromString = FName(*SomeString);
```

## 比较操作

```cpp
FName MyFName1 = FName(TEXT("OnlyTest"));
FName MyFName2 = FName(TEXT("NotTest"));

// == 运算符：比较索引（O(1)），非常快
bool bEqual = MyFName1 == MyFName2;

// Compare()：返回 int32，0 表示相等
int32 CompareResult = MyFName1.Compare(MyFName2);
```

FName 的比较基于全局 Name Table 索引，而非逐字符比较，因此速度极快。命名不区分大小写，但大小写格式会被保留。

## FNAME_Find 查找模式

`FNAME_Find` 是一种特殊的构造模式，用于检测 FName 是否已存在于 Name Table 中：

```cpp
// FNAME_Find：只在表中查找，不存在则返回 NAME_None
if (FName(TEXT("pelvis"), FNAME_Find) != NAME_None)
{
    // 该 FName 已存在于 Name Table 中
}

if (FName(TEXT("OnlyTest"), FNAME_Find) != NAME_None)
{
    // "OnlyTest" 已注册
}

if (FName(TEXT("OnlyTest22"), FNAME_Find) != NAME_None)
{
    // "OnlyTest22" 不存在，不会进入
}
```

## 典型使用场景

| 场景 | 示例 |
|------|------|
| 网格体 Socket 名称 | `GetSocketByName(FName("headSocket"))` |
| 材质参数名称 | `DynamicMaterial->SetScalarParameterValue(FName("Roughness"), 0.5f)` |
| GameplayTag | FName 是 GameplayTag 的底层存储 |
| 资源键值 | 资产路径、对象名称 |
| 枚举/标识符 | 需要快速比较的标识 |

## 注意事项

- **不可变**：FName 一旦创建不能修改内容
- **不用于网络同步**：不同客户端/服务器的 Name Table 不一致
- **不用于 UI 显示**：FName 不是本地化文本，应用 FText
- **不用于大量动态字符串**：FName 在 Name Table 中永久存在

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的 `FNameTest()`。
