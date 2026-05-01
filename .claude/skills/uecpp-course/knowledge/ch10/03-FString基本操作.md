# FString 基本操作

## 比较

```cpp
FString Str1 = TEXT("Test");
FString Str2 = TEXT("test");

// == 运算符：默认不区分大小写
bool bEqual = Str1 == Str2; // true

// Equals()：可指定是否区分大小写
bool bEqualCase = Str1.Equals(Str2, ESearchCase::CaseSensitive); // false
```

## 查找

```cpp
FString Str = TEXT("UnrealEngine5");

// Contains()：返回 bool，是否包含子串
bool bContainStart = Str.Contains(TEXT("Engine"), ESearchCase::IgnoreCase, ESearchDir::FromStart);
bool bContainEnd = Str.Contains(TEXT("Engine"), ESearchCase::IgnoreCase, ESearchDir::FromEnd);

// Find()：返回 int32 索引，未找到返回 INDEX_NONE
int32 StartIndex = Str.Find(TEXT("real"), ESearchCase::IgnoreCase, ESearchDir::FromStart);
int32 EndIndex = Str.Find(TEXT("real"), ESearchCase::IgnoreCase, ESearchDir::FromEnd);
```

两个函数都支持 `ESearchCase::IgnoreCase` / `CaseSensitive` 和 `ESearchDir::FromStart` / `FromEnd`。

## 截取

```cpp
FString MyStr = TEXT("This is my good code !");

FString LeftStr = MyStr.Left(5);   // "This "
FString MidStr  = MyStr.Mid(5);    // "is my good code !"
FString RightStr = MyStr.Right(6); // "code !"
```

## 追加

```cpp
FString Str = TEXT("This is my good code !");

// += 运算符（创建新FString再拷贝）
Str += TEXT("What is your code?");

// + 运算符（返回新FString）
FString NetString = Str + TEXT("Today is a good day");

// AppendChar() 追加单个字符
TCHAR MYChar = *TEXT("A");
NetString.AppendChar(MYChar);

// Append() 追加字符串
NetString.Append(TEXT("BCD"));
```

## 替换

```cpp
FString NetString = TEXT("...BCD...");

// Replace()：返回新的 FString，不修改原字符串
FString AnotherNetString = NetString.Replace(TEXT("BCD"), TEXT("BCDEF"));

// ReplaceInline()：原地修改，返回替换次数
int32 ReplaceNum = AnotherNetString.ReplaceInline(TEXT("Today"), TEXT("Tomorrow"));
```

## 大小写转换

```cpp
FString MyStr = TEXT("MyLife");

FString UpperStr = MyStr.ToUpper(); // "MYLIFE"
FString LowerStr = MyStr.ToLower(); // "mylife"
```

## 格式化输出

```cpp
// FString::Printf - 类似 C 风格 printf
float TimeSeconds = 1802.456f;
const FString TimeDesc = FString::Printf(TEXT("%02d:%02d"), NumMinutes, NumSeconds);

// UE_LOG 中使用
UE_LOG(LogTemp, Warning, TEXT("Data:[%.2f]==>%02d:%02d"), TimeSeconds, NumMinutes, NumSeconds);
```

## 调试显示

```cpp
// 在屏幕上打印调试信息
GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Red, MyString);
```

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的：
- `ModifyString()` — Compare/Contains/Find
- `ModifyString2()` — Append/Replace/ReplaceInline
- `OperateString()` — Left/Mid/Right
- `LogString()` — Printf/UE_LOG
