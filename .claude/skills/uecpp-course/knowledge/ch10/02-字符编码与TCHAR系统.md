# 字符编码与 TCHAR 系统

## TCHAR 定义

TCHAR 是 UE 的字符类型抽象层，在 Windows 平台解析为 `wchar_t`（UTF-16），在其他平台可能不同。所有字符串操作都基于 TCHAR 数组。

## 三种编码类型

在 UE 字符串处理中，三种编码需要清晰区分：

| 编码 | 说明 | UE 表示 |
|------|------|---------|
| ANSI/MBCS | 本地系统编码（Windows 为 GBK） | `ANSICHAR` / `char` |
| UTF-8 | 通用网络传输编码 | `UTF8CHAR` / `ANSICHAR` |
| TCHAR (UTF-16) | UE 内部编码 | `TCHAR` / `wchar_t`（Windows）|

## TEXT() 宏

- `TEXT("...")`：将字符串字面量编译为 TCHAR 数组
- `"..."`（无宏）：编译为 ANSI char 数组，与 FString 的隐式转换可能产生警告或编码错误
- 始终使用 `TEXT()` 包裹字符串字面量

## 与外部系统交互的编码挑战

当 UE 与外部系统（Unity、Java 后端、第三方 SDK、Web 服务）通信时，编码转换是一个常见陷阱：
- 外部系统通常使用 UTF-8 或 ANSI
- UE 内部使用 UTF-16
- 发送前需要将 FString 转换为外部系统的编码
- 接收后需要将外部数据转回 FString

## FString 的三种创建方式

```cpp
FString TestString = FString(TEXT("This is a test")); // 显式构造
FString TestString2 = TEXT("This is a test");          // 隐式转换（推荐）
FString TestString32 = "This is a test";                // ANSI 字面量（不推荐）
```
