# GConfig 手动读写 INI

## 概述

除了通过 UPROPERTY(Config) 的自动加载机制，UE 还提供了 `GConfig` 全局接口用于手动读写 INI 文件。手动读写不受 UCLASS/property 反射系统的限制，可以在任意位置对任意段名操作。

## 读取 INI 值

```cpp
int32 XGCustomInt;
GConfig->GetInt(TEXT("XGCustom"), TEXT("XGCustomInt"), XGCustomInt, GGameIni);
UE_LOG(LogTemp, Warning, TEXT("XGCustomInt: %d"), XGCustomInt);
```

| 参数 | 说明 | 示例 |
|------|------|------|
| Section | INI 段名 | `TEXT("XGCustom")` |
| Key | 键名 | `TEXT("XGCustomInt")` |
| Value（输出） | 读取到的值 | `int32` 类型的输出参数 |
| ConfigFile | INI 文件路径/句柄 | `GGameIni`、`GEngineIni`、自定义路径 |

### 其他数据类型

```cpp
float MyFloat;
GConfig->GetFloat(TEXT("Section"), TEXT("Key"), MyFloat, GGameIni);

FString MyString;
GConfig->GetString(TEXT("Section"), TEXT("Key"), MyString, GGameIni);

bool MyBool;
GConfig->GetBool(TEXT("Section"), TEXT("Key"), MyBool, GGameIni);

TArray<FString> MyArray;
GConfig->GetArray(TEXT("Section"), TEXT("Key"), MyArray, GGameIni);
```

## 写入 INI 值

```cpp
XGCustomInt += 10;
GConfig->SetInt(TEXT("XGCustom"), TEXT("XGCustomInt"), XGCustomInt, GGameIni);
```

写入后值暂存于内存中，需要执行 `Flush` 才会真正写入磁盘文件。

## Flush —— 刷入磁盘

```cpp
GConfig->Flush(false, GGameIni);
```

| 参数 | 说明 |
|------|------|
| `false` | 是否强制刷新所有配置（false 只刷新指定文件） |
| `GGameIni` | 要刷新的目标文件句柄 |

如果设置了 `true`，会刷新所有 INI 文件的待写入缓冲区——这通常不需要，推荐指定具体文件。

## 写入指定路径的 INI 文件

GConfig 也支持直接使用文件路径而非 `GGameIni` 句柄：

```cpp
const FString DefaultGamePath = FString::Printf(
    TEXT("%sDefaultGame.ini"), *FPaths::SourceConfigDir());

int32 XGCustomInt2;
GConfig->GetInt(TEXT("XGCustom"), TEXT("XGCustomInt2"), XGCustomInt2, DefaultGamePath);
UE_LOG(LogTemp, Warning, TEXT("XGCustomInt2: %d"), XGCustomInt2);

XGCustomInt2 += 100;
GConfig->SetInt(TEXT("XGCustom"), TEXT("XGCustomInt2"), XGCustomInt2, DefaultGamePath);
GConfig->Flush(false, DefaultGamePath);
```

### 注意：GGameIni 与直接路径的区别

- `GGameIni` 自动选择当前层级（编辑器下通常是 Saved/Config/Windows/Game.ini）
- `FPaths::SourceConfigDir()` 始终指向 `Config/` 目录（Default 层级）
- 写入 `GGameIni` 时，值被写入用户本地层（Saved/），可能不会覆盖 Default 层的值
- 写入 `SourceConfigDir` 路径时，值被写入项目默认层，影响所有开发者

## GConfig 手动读写 vs UPROPERTY(Config) 自动加载

| 方式 | 优点 | 缺点 |
|------|------|------|
| UPROPERTY(Config) 自动加载 | 零代码、反射自动处理、类型安全 | 需要 UCLASS 声明、只支持 UObject 属性 |
| GConfig 手动读写 | 灵活，任意代码位置、任意段名、任意文件路径 | 需要手动管理类型转换、需要显式 Flush |

## 配套代码

- [XGINIActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGINIActor.cpp) — GetINIVariable() 中 GConfig 手动读写 + Flush 完整实现
