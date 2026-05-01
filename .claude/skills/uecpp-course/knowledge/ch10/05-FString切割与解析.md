# FString 切割与解析

## Split 分割

`Split()` 方法按分隔符将 FString 分为左右两部分：

```cpp
FString MyStr = TEXT("MyLife=998");

FString MyLeftKey = TEXT("");
FString MyRightKey = TEXT("");

MyStr.Split(TEXT("="), &MyLeftKey, &MyRightKey);
// MyLeftKey  = "MyLife"
// MyRightKey = "998"
```

## ParseIntoArray 数组化

`ParseIntoArray()` 将字符串按分隔符拆分为字符串数组：

```cpp
FString MyArrayStr = TEXT("MyLife,MyMoney,MyHealth,MyMana");

TArray<FString> MyStrArray;
MyArrayStr.ParseIntoArray(MyStrArray, TEXT(","));
// 结果：["MyLife", "MyMoney", "MyHealth", "MyMana"]
```

第二个参数为 `bool bCullEmpty`（默认为 false），设为 true 时会过滤空白条目：
```cpp
// 当分隔符连续出现时，设为 true 可过滤空字符串
MyStr.ParseIntoArray(Parts, TEXT(","), true);
```

## URL 解析实战

```cpp
FString iFlyTekURL = TEXT("ws://spark-api.xf-yun.com/v4.0/chat");

TArray<FString> URLParts;
iFlyTekURL.ParseIntoArray(URLParts, TEXT("/"), true);

// URLParts[0] = "ws:"
// URLParts[1] = "spark-api.xf-yun.com"  ← 域名
// URLParts[2] = "v4.0"
// URLParts[3] = "chat"

// 提取路径部分
FString URLPath = TEXT("");
for (int32 Index = 0; Index < URLParts.Num(); Index++)
{
    if (Index > 1)
    {
        URLPath += TEXT("/");
        URLPath += URLParts[Index];
    }
}
// URLPath = "/v4.0/chat"
```

## KismetStringLibrary

UE 提供 `UKismetStringLibrary`（蓝图中的字符串工具库），包含丰富的 FString 辅助方法：
- `Contains` / `Find` / `Left` / `Right` / `Mid` / `Trim`
- `Split` / `ParseIntoArray`
- `ToUpper` / `ToLower`
- `Replace` / `ReplaceInline`
- `Len` / `StartsWith` / `EndsWith`

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的：
- `OperateString2()` — Split + ParseIntoArray + ToUpper/ToLower
- `OperateURL()` — URL 解析实战
