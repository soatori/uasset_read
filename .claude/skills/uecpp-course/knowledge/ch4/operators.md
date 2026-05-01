# TArray 运算符

## 拷贝与赋值

```cpp
TArray<int32> Source = {1, 2, 3, 4, 5};

// 拷贝构造
TArray<int32> Dest1 = Source;   // 深拷贝

// 拷贝赋值
TArray<int32> Dest2;
Dest2 = Source;                 // 深拷贝
```

两个数组完全独立，修改其中一个不会影响另一个。

## 连接运算符 `+=`

```cpp
TArray<int32> Arr = {1, 2, 3};
Arr += TArray<int32>{4, 5, 6};  // {1, 2, 3, 4, 5, 6}
```

等价于 `Append()`。

## 移动语义（MoveTemp）

```cpp
TArray<int32> Source = {1, 2, 3, 4, 5};
TArray<int32> Dest = MoveTemp(Source);  // Source 变为空，Dest 获取其内存

// 或使用赋值
TArray<int32> Dest;
Dest = MoveTemp(Source);
```

使用 `MoveTemp()`（UE 封装的 `std::move`）将源数组的内存直接转移给目标数组，避免深拷贝。转移后源数组为空。

## 比较运算符 `==` / `!=`

```cpp
TArray<int32> A = {1, 2, 3};
TArray<int32> B = {1, 2, 3};
TArray<int32> C = {3, 2, 1};

if (A == B)  // true——元素顺序、数量全部一致
if (A == C)  // false——顺序不同
```

比较规则：
- 要求元素类型有 `operator==`
- 逐个元素比较
- 元素**顺序**必须一致
- 元素**数量**必须一致
- 字符串比较（FString）默认**不区分大小写**

## Exchange()

```cpp
TArray<int32> A = {1, 2, 3};
TArray<int32> B = {4, 5, 6};
Exchange(A, B);  // A = {4, 5, 6}, B = {1, 2, 3}
```

交换两个数组的值。

> **代码位置**：[XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGCopyArray()`, `XGSwapArray()`, `XGConnectArray()`, `XGCompareArray()`
