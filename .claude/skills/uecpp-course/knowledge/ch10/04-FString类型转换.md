# FString 类型转换

## 数值类型 → FString

```cpp
// float → FString
float MyFloat = 109.3f;
FString FloatFString = FString::SanitizeFloat(MyFloat);

// int32 → FString
int32 MyInt = 99;
FString IntString = FString::FromInt(MyInt);

// bool → FString（无直接方法，使用三元表达式）
bool bMyBool = true;
FString BoolString = bMyBool ? TEXT("true") : TEXT("false");
```

## 结构体类型 → FString

UE 核心结构体都提供了 `ToString()` 方法：

```cpp
// FVector → FString（输出格式 "X=100.000 Y=20.000 Z=30.000"）
FVector MyLocation(100.0f, 20.f, 30.f);
FString MyVectorString = MyLocation.ToString();

// FVector2D → FString
FVector2D MyVector2D(100.0f, 20.f);
FString MyVector2DString = MyVector2D.ToString();

// FRotator → FString（输出格式 "P=40.000 Y=50.000 R=60.000"）
FRotator MyRotator(40.f, 50.f, 60.f);
FString MyRotatorString = MyRotator.ToString();

// FLinearColor → FString（输出格式 "R=0.000 G=0.000 B=1.000 A=1.000"）
FLinearColor MyColor = FLinearColor::Blue;
FString MyColorString = MyColor.ToString();
```

## UObject → FString

```cpp
AActor* MyActor = this;

// GetName() 返回 FName，再 ToString()
FString MyActorString = MyActor->GetName().ToString();

// GetDisplayName() 返回 FText（编辑器可用，显示友好名称）
// GetPathName() 返回完整路径
```

## FString → 数值类型

```cpp
// FString → int32
int32 MyBackint = FCString::Atoi(*IntString);

// FString → float
float MyFloatBool = FCString::Atof(*FloatFString);

// FString → bool（直接成员方法）
bool MyBackBool = BoolString.ToBool();

// 通用转换（模板方式）
float Result;
LexTryParseString(Result, *SomeString); // 安全 TryParse
```

## 注意事项

- `*FString` 运算符获取底层 TCHAR 数组指针（C 风格字符串）
- `FCString::Atoi`/`Atof` 等函数需要 `*FString` 解引用
- 浮点数转换不是无损的：`SanitizeFloat` 由于浮点精度可能导致期望之外的位数
- `LexToString`/`LexTryParseString` 是模板化通用方案

## 对应代码

[XGStringActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/013_String/XGStringActor.cpp) 中的 `PropertyString()`。
