# TArray 创建与初始化

## 基本声明

```cpp
TArray<int32> IntArray;
TArray<FString> StrArray;
TArray<FMyStruct> StructArray;
```

声明时不做任何初始化，数组为空（Num = 0, Max = 0）。

## 使用 Init() 填充

```cpp
TArray<int32> IntArray;
IntArray.Init(0, 5);  // 填充 5 个 0：{0, 0, 0, 0, 0}
```

## 初始值设定项列表

```cpp
TArray<int32> IntArray = {1, 2, 3, 4, 5};
TArray<FString> StrArray = {TEXT("Hello"), TEXT("World")};
```

## 复制构造

```cpp
TArray<int32> Source = {1, 2, 3};
TArray<int32> Dest = Source;  // 深拷贝
```

> **代码位置**：[XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h) / [XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp) — 函数 `XGCreateTArray()`
