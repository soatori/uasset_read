# TArray 索引

## [] 操作符

```cpp
TArray<FString> Arr = {TEXT("A"), TEXT("B"), TEXT("C")};

// 读取——返回引用
FString Elem = Arr[1];    // 拷贝，Elem = "B"
FString& Ref = Arr[1];    // 引用，Ref 就是 Arr[1] 的别名
const FString& ConstRef = Arr[1];  // const 引用，只读

// 修改
Arr[1] = TEXT("X");       // 直接修改数组
```

**索引越界会导致崩溃**，访问前应检查范围。

## IsValidIndex()

```cpp
if (Arr.IsValidIndex(5))
{
    // 安全访问
    FString Elem = Arr[5];
}
```

## Last()

```cpp
FString& LastElem = Arr.Last();       // 最后一个元素
const FString& LastElem = Arr.Last(); // const 版本

FString& SecondLast = Arr.Last(1);    // 倒数第二个（索引 1 从末尾起算）
FString& ThirdLast = Arr.Last(2);     // 倒数第三个
```

## Top()

```cpp
FString& TopElem = Arr.Top();  // 等价于 Last()
```

在标准库中 `top()` 通常用于栈操作（栈顶），在 TArray 中语义等价于 `Last()`。

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGArrayIndex()`
