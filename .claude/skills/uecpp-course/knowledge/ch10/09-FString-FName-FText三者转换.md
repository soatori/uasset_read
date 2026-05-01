# FString / FName / FText 三者转换

## 转换关系图

```
FString ─────────→ FName
   │                   │
   │                   ▼
   │               FName ──→ FText (FText::FromName)
   ▼                   │
  FText ←── FString ───┤
                        │
                        ▼
                   FText ──/──→ FName (不能直接转换)
```

## 各方向转换

### FString → FName

```cpp
FString TestString = TEXT("This is a str test");
FName TestName = FName(*TestString);
```

需要 `*FString` 解引用为 TCHAR 数组指针。

### FString → FText

```cpp
FString TestString = TEXT("This is a str test");
FText TestText = FText::FromString(TestString);
```

注意：从 FString 转换到 FText 会丢失本地化能力，原 FString 内容成为 FText 的固定显示文本。

### FName → FString

```cpp
FName TestName = FName(TEXT("OnlyTest"));
FString BackString = TestName.ToString();
```

### FName → FText

```cpp
FName TestName = FName(TEXT("OnlyTest"));
FText BackText = FText::FromName(TestName);
```

### FText → FString

```cpp
FText TestText = FText::FromString(TestString);
FString BackString2 = TestText.ToString();
```

注意：转换会丢失本地化信息，只保留当前文化下的显示文本。

### FText → FName（不能直接转换）

```cpp
// 错误：不能直接转换
// FName BackName = FName(TestText); // 编译错误

// 正确：需要经过 FString 中间过渡
FName BackName = FName(TestText.ToString());
// 或：
FName BackName = FName(*TestText.ToString());
```

## 转换总结

| 方向 | 方法 | 备注 |
|------|------|------|
| FString → FName | `FName(*Str)` | 解引用获得 TCHAR* |
| FString → FText | `FText::FromString(Str)` | 丢失本地化 |
| FName → FString | `Name.ToString()` | 直接转换 |
| FName → FText | `FText::FromName(Name)` | 直接转换 |
| FText → FString | `Text.ToString()` | 丢失本地化 |
| FText → FName | `FName(Text.ToString())` | 需经过 FString 过渡 |

## 其他转换途径

```cpp
// UObject 名称相关
GetName()        // 返回 FName
GetDisplayName() // 返回 FText（编辑器可用）

// 使用 Cast 模式（适用于特定类型）
FString ObjName = Cast<AActor>(SomeObject)->GetName();
```

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的 `InitString()`。
