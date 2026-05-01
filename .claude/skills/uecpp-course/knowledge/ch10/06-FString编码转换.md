# FString 编码转换

## 背景

UE 内部使用 TCHAR（Windows 为 UTF-16），但外部系统通常使用 UTF-8 或 ANSI。编码转换在以下场景必不可少：
- 与 Web 服务器通信（HTTP JSON）
- 调用第三方 C/C++ SDK（如讯飞 SDK）
- 文件 I/O（跨平台兼容性）
- 网络传输

## 已废弃的宏（不推荐使用）

```cpp
// 以下是 UE 早期版本的转换方式，已废弃（deprecated）
FString Str = TEXT("This is my good code !");
char* MyAnsiChar = TCHAR_TO_ANSI(*Str);     // TCHAR → ANSI
FString MyBackStr = ANSI_TO_TCHAR(MyAnsiChar); // ANSI → TCHAR

char* MyUtf8Char = TCHAR_TO_UTF8(*Str);     // TCHAR → UTF-8
FString MyBackStr2 = UTF8_TO_TCHAR(MyUtf8Char); // UTF-8 → TCHAR
```

### 宏的两大陷阱

**陷阱一：临时指针生命周期**

宏产生的指针指向栈上临时缓冲区，生命周期极短。不能将指针存储后跨作用域使用：

```cpp
void WrongUse(char* InStr)
{
    // InStr 指向的缓冲区可能已经失效！
    // 这是错误用法！
}

// 调用
WrongUse(MyAnsiCharUTF8); // 危险！
```

**陷阱二：长字符串截断**

宏内部使用固定大小的栈缓冲区，当字符串较长时会被静默截断：

```cpp
FString StrLong = TEXT("This is my good code !...（很长的字符串）...");
char* MyAnsiCharLong = TCHAR_TO_ANSI(*StrLong);
// 如果字符串超过缓冲区大小，会被截断
FString MyBackStrLong = ANSI_TO_TCHAR(MyAnsiCharLong);
// MyBackStrLong 与 StrLong 不相等！
```

## 推荐的转换方式

### 方式一：FTCHARToUTF8 / FUTF8ToTCHAR（UE 标准）

```cpp
FString StrLong = TEXT("...（含中文的长字符串）...");

// TCHAR → UTF-8
FTCHARToUTF8 Convert(*StrLong);
TArray<uint8> Data;
Data.Append((uint8*)Convert.Get(), Convert.Length());

// UTF-8 → TCHAR
FUTF8ToTCHAR BackConvert((const ANSICHAR*)Data.GetData(), Data.Num());
FString UTF8Text(BackConvert.Length(), BackConvert.Get());
```

### 方式二：StringCast（通用模板，UE5.4 推荐）

```cpp
FString StrLong = TEXT("...（长字符串）...");

// TCHAR → UTF-8
auto UTF8String = StringCast<UTF8CHAR>(*StrLong);
TArray<uint8> NewMethodData;
NewMethodData.SetNum(UTF8String.Length());
NewMethodData.Add(0);
FMemory::Memcpy(NewMethodData.GetData(), UTF8String.Get(), UTF8String.Length());

// UTF-8 → TCHAR
auto Cnv = StringCast<TCHAR>((const UTF8CHAR*)NewMethodData.GetData(), NewMethodData.Num());
FString FinalStr(Cnv.Get(), Cnv.Length());
```

## 编码转换 "四层境界"

| 层级 | 方式 | 风险 |
|------|------|------|
| Level 1 | TCHAR_TO_ANSI 等宏 | 临时指针 + 长字符串截断 |
| Level 2 | StringCast | 正确处理内存，推荐使用 |
| Level 3 | StringCast + StreamCast + Memcpy | 精细控制内存布局 |
| Level 4 | 处理空终止符、部分编码等边界情况 | 极端场景 |

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的：
- `TransformString()` — 错误示范（使用已废弃宏）
- `WrongUse()` — 演示临时指针陷阱
- `TransformStringRight()` — 正确做法（FTCHARToUTF8 + StringCast）
