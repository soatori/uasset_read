# FText 本地化与格式化

## 本地化宏

### LOCTEXT — 文件级命名空间

```cpp
// 文件开头定义命名空间
#define LOCTEXT_NAMESPACE "XGStringActor"

// 使用 LOCTEXT(命名空间内Key, 原文)
FText MyCodeText = LOCTEXT("OwnCode", "MyCode");

// 文件末尾取消定义
#undef LOCTEXT_NAMESPACE
```

LOCTEXT 的三个参数：
1. **Key**（标识符）：在同一命名空间内唯一，用于翻译匹配
2. **Source String**（原字符串）：开发语言的原始文本

### NSLOCTEXT — 单行命名空间

适用于按需定义的场景，不需要定义 LOCTEXT_NAMESPACE：

```cpp
FText MyCodeTypeText = NSLOCTEXT("CodeTypeNamespace", "CodeType", "XiaoGangCode");
```

参数顺序：NSLOCTEXT(命名空间, Key, 原字符串)

## FText::Format 格式化

格式化字符串支持 `{0}`、`{1}` 等占位符：

```cpp
FString PlayerName = TEXT("XG");

FText PlayerText = FText::Format(
    LOCTEXT("PlayerNameFmt", "{0} is really cool"),
    FText::FromString(PlayerName)
);
// 结果：PlayerText = "XG is really cool"
```

## 格式化说明符

FText 提供多种文化感知的格式化说明符：

```cpp
// AsNumber — 数值格式（带千位分隔符）
FText NumText = FText::AsNumber(15689.33f);
// 美式文化下显示：15,689.33

// AsPercent — 百分比格式
FText PercentText = FText::AsPercent(0.33f);
// 显示：33%

// AsMemory — 内存大小格式（使用 KiB/GiB 等二进制前缀）
FText MemoryText = FText::AsMemory(1234);
// 显示：1.21 KiB

// AsCurrencyBase — 货币格式
FText MoneyText = FText::AsCurrencyBase(650, TEXT("EUR"));
// 显示货币金额，使用当地文化格式

// AsDate — 日期格式
FDateTime MyDateTime = FDateTime::Now();
FText DateText = FText::AsDate(MyDateTime);

// AsTime — 时间格式
FText TimeText = FText::AsTime(MyDateTime);
```

## KiB 与 KB 的区别

| 单位 | 进位 | 用途 |
|------|------|------|
| KiB (Kibibyte) | 1024 | 计算机内存/储存（精确二进制） |
| KB (Kilobyte) | 1000 | 硬盘厂商标记（十进制） |

FText::AsMemory 使用 KiB/GiB 标准（带 i 的二进制前缀），这是逐渐明确的行业规范。

## FText 的使用场景

- **Slate UI**：按钮文字、标签、提示框（最常用）
- **蓝图文本节点**：所有显示文本应使用 FText
- **网络同步**：使用 FString 而非 FText
- **日志输出**：使用 FString
- **资源标识**：使用 FName

## 对应代码

[XGStringActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.h) 和 [XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的：
- `FTextTest()` — LOCTEXT/NSLOCTEXT 声明
- `FTextFormat()` — FText::Format + 各种格式化说明符
