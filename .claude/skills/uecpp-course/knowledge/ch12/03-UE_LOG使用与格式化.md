# UE_LOG 使用与格式化

## 基本语法

```cpp
UE_LOG(CategoryName, Verbosity, TEXT("Format String"), Arg1, Arg2, ...);
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `CategoryName` | 已声明的日志类别 | `LogXGSample`、`LogXGLogActor` |
| `Verbosity` | 日志级别枚举 | `Error`、`Warning`、`Display`、`Log`、`Verbose`、`VeryVerbose` |
| `TEXT("...")` | 格式化字符串（必须用 `TEXT()` 包裹） | `TEXT("int32: %d")` |
| `Arg1, Arg2, ...` | 可变参数，与格式说明符匹配 | `MyInt`、`*MyString` |

## 格式说明符（printf 风格）

| 说明符 | 对应类型 | 示例 |
|--------|---------|------|
| `%d` | int32 | `UE_LOG(LogTemp, Log, TEXT("%d"), MyInt)` |
| `%s` | FString（需解引用） | `UE_LOG(LogTemp, Log, TEXT("%s"), *MyString)` |
| `%f` | float | `UE_LOG(LogTemp, Log, TEXT("%f"), MyFloat)` |
| `%.Nf` | float（保留 N 位小数） | `UE_LOG(LogTemp, Log, TEXT("%.2f"), MyFloat)` |
| `%hs` | const char*（ANSI） | `UE_LOG(LogTemp, Log, TEXT("%hs"), AnsiStr)` |

**关键注意事项**：

- **FString 必须解引用**：`FString` 类型变量必须使用 `*MyString` 传入，否则编译不通过或输出乱码
- **格式说明符不匹配会崩溃**：如 `%s` 传入了 `int32`，运行时打印会访问非法内存
- **`TEXT()` 包裹是必须的**：UE_LOG 的格式化字符串必须是 `TCHAR` 字符串

## FString::Printf 中间格式化

当需要创建格式化后的 FString 字符串（不立即打印，或用于拼接）时，使用 `FString::Printf`：

```cpp
int32 MyInt = 32;
FString MyString = TEXT("Test");
float MyFloat = 32.2f;

FString MyNewString = FString::Printf(
    TEXT("New---int32: [%d] ,FString:[%s],float:[%.2f]"),
    MyInt, *MyString, MyFloat
);

UE_LOG(LogXGSample, Error, TEXT("[%s]"), *MyNewString);
```

`FString::Printf` 的格式说明符规则与 `UE_LOG` 完全相同。

## `__FUNCTION__` 与函数名打印

```cpp
UE_LOG(LogXGSample, Error, TEXT("[%s]"), *FString(__FUNCTION__));
```

`__FUNCTION__` 是 C++ 预定义宏，展开为当前函数名的 ANSI 字符串。上述写法将函数名转为 FString 后打印，是调试时快速确认执行路径的常用手法。

## 完整级别演示

以下演示了所有日志级别的使用（Fatal 被注释，避免崩溃）：

```cpp
void AXGLogActor::XGLog()
{
    UE_LOG(LogXGLogActor, Log, TEXT("This is Log"));
    UE_LOG(LogXGSample, Error, TEXT("This is Error"));
    UE_LOG(LogXGSample, Warning, TEXT("This is Warning"));
    UE_LOG(LogXGSample, Display, TEXT("This is Display"));
    UE_LOG(LogXGSample, Log, TEXT("This is Log"));
    UE_LOG(LogXGSample, Verbose, TEXT("This is Verbose"));
    UE_LOG(LogXGSample, VeryVerbose, TEXT("This is VeryVerbose"));
    // UE_LOG(LogXGSample, Fatal, TEXT("This is Fatal"));
}
```

代码中 `LogXGLogActor` 和 `LogXGSample` 是两个不同的日志类别，分别用于演示文件级和模块级类别的用法。

## 配套代码

- [XGLogActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/XGLogActor.cpp) — `XGLog()` 和 `XGLogString()` 函数
