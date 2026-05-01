# TJsonWriter 与 TJsonReader 底层读写

## 概述

TJsonWriter / TJsonReader 是 UE 原生提供的 JSON 流式读写 API。相比 FString::Printf 原始拼接，它提供了完整的类型安全、嵌套支持和错误检查。本章覆盖对象/数组/嵌套对象的完整写与读。

## 头文件依赖

```cpp
#include "Serialization/JsonWriter.h"       // 写入流
#include "Serialization/JsonReader.h"       // 读取流
#include "Policies/CondensedJsonPrintPolicy.h"  // 紧凑输出策略（无空格缩进）
```

## 写 JSON — TJsonWriter

### 创建写入流

```cpp
FString GoodJsonString;
TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> GoodJsonWriter
    = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&GoodJsonString);
```

- `TCondensedJsonPrintPolicy`：紧凑输出，不添加空格/缩进（适合网络传输）
- 另一个策略 `TPrettyJsonPrintPolicy`：带缩进的人类可读格式
- **网络注意事项**：部分后端对空格/缩进敏感，多一个空格可能导致校验失败

### 写简单对象

```cpp
GoodJsonWriter->WriteObjectStart();                        // 输出 {
GoodJsonWriter->WriteValue(TEXT("Code"), MyInfo.UECode);   // "Code": 998
GoodJsonWriter->WriteValue(TEXT("Message"), MyInfo.Message); // "Message": "..."
GoodJsonWriter->WriteValue(TEXT("Data"), MyInfo.UEData);
GoodJsonWriter->WriteValue(TEXT("Sid"), MyInfo.Sid);
GoodJsonWriter->WriteObjectEnd();                          // 输出 }
GoodJsonWriter->Close();   // 关闭流 → GoodJsonString 被填充
```

`WriteValue` 是泛型方法，自动识别 int/float/bool/FString 类型，不需要手动 `%d`/`%s`。

### 写嵌套对象

```cpp
GoodJsonWriter->WriteObjectStart(TEXT("XG"));      // "XG": {
GoodJsonWriter->WriteValue(TEXT("ServerName"), ...); //   "ServerName": "..."
GoodJsonWriter->WriteValue(TEXT("ServerVersion"), ...);
GoodJsonWriter->WriteObjectEnd();                    // }
```

- `WriteObjectStart()` 无参 = 匿名对象 `{}`
- `WriteObjectStart(TEXT("key"))` = 具名对象 `"key": {` （用于对象内部的子对象）
- **代码可读性技巧**：用显式 `{}` 作用域包裹子对象写入代码，对应 JSON 的一层嵌套

### 写数组

```cpp
// 简单类型数组：[1, 3, 5]
GoodJsonWriter->WriteArrayStart(TEXT("WorkerIDs"));    // "WorkerIDs": [
for (auto& TmpID : MyInfo.WorkerIDs)
    GoodJsonWriter->WriteValue(TmpID);                  //   1, 3, 5
GoodJsonWriter->WriteArrayEnd();                        // ]

// 对象数组：[{"Name": "...", "WorkYear": 3.2}, ...]
GoodJsonWriter->WriteArrayStart(TEXT("Coders"));        // "Coders": [
for (auto& TmpCoder : MyInfo.Coders)
{
    GoodJsonWriter->WriteObjectStart();                 //   {
    GoodJsonWriter->WriteValue(TEXT("Name"), TmpCoder.Name);
    GoodJsonWriter->WriteValue(TEXT("WorkYear"), TmpCoder.WorkYear);
    GoodJsonWriter->WriteObjectEnd();                   //   }
}
GoodJsonWriter->WriteArrayEnd();                        // ]
```

- 数组中的对象 `WriteObjectStart()` **不传参**（因为数组元素没有键名）

## 读 JSON — TJsonReader

### 反序列化流程

```cpp
TSharedPtr<FJsonObject> JsonObject;
TSharedRef<TJsonReader<TCHAR>> JsonReader = TJsonReaderFactory<TCHAR>::Create(JsonString);

bool bOk = FJsonSerializer::Deserialize(JsonReader, JsonObject);
if (!bOk) return;  // 不是合法 JSON
```

`FJsonSerializer::Deserialize` 将字符串解析为 `TSharedPtr<FJsonObject>`，其内部是一个 TMap 键值对结构。

### 读取字段的三种方式

| 方式 | API | 安全性 | 使用场景 |
|------|-----|--------|----------|
| TryGet → As | `TryGetField→IsValid→AsNumber()` | 最高 | 不确定字段是否存在 |
| TryGetXxxField | `TryGetNumberField(key, outValue)` | 高 | 需要布尔判断是否读到 |
| GetXxxField | `GetNumberField(key)` | 低（不存在会 assert） | 确定字段一定存在 |

**方式一：TryGetField + 判空 + AsNumber**

```cpp
TSharedPtr<FJsonValue> CodeValue = JsonObject->TryGetField(TEXT("Code"));
if (CodeValue.IsValid())
{
    int32 Code = CodeValue->AsNumber();  // 转为数值
}
```

`FJsonValue` 是字段值的容器，需要 `AsNumber()`/`AsString()`/`AsBool()`/`AsObject()` 转换。

**方式二：TryGetNumberField（推荐）**

```cpp
int32 CodeNum = -1;
bool bFound = JsonObject->TryGetNumberField(TEXT("Code"), CodeNum);
// bFound = true 时 CodeNum 被填充
```

一步完成查找+转换+返回成功标志。同理有 `TryGetStringField`、`TryGetBoolField`。

**方式三：GetNumberField（直接取，失败会断言）**

```cpp
int32 Code = JsonObject->GetNumberField(TEXT("Code"));  // 不存在时崩溃
```

仅用于你能**100% 确定字段存在且类型正确**时。

### 读字符串

```cpp
FString Message = JsonObject->GetStringField(TEXT("Message"));
```

### 读嵌套对象

```cpp
TSharedPtr<FJsonObject> XGObj = JsonObject->GetObjectField(TEXT("XG"));
FString ServerName = XGObj->GetStringField(TEXT("ServerName"));
FString ServerVersion = XGObj->GetStringField(TEXT("ServerVersion"));
```

`GetObjectField` 返回 `TSharedPtr<FJsonObject>`，然后继续读取其内部属性。

### 读数组

```cpp
// 读简单数组
TArray<TSharedPtr<FJsonValue>> WorkerIDs = JsonObject->GetArrayField(TEXT("WorkerIDs"));
for (auto& Val : WorkerIDs)
{
    int32 Id = Val->AsNumber();
    MyInfo.WorkerIDs.Add(Id);
}

// 读对象数组
TArray<TSharedPtr<FJsonValue>> Coders = JsonObject->GetArrayField(TEXT("Coders"));
for (auto& Val : Coders)
{
    TSharedPtr<FJsonObject> CoderObj = Val->AsObject();
    FString Name = CoderObj->GetStringField(TEXT("Name"));
    float WorkYear = CoderObj->GetNumberField(TEXT("WorkYear"));
}
```

## toString / FromString 封装模式

将读写逻辑封装到结构体内部，使用者只需调用两个方法：

```cpp
struct TempMessageInfo
{
    // 属性...
    FString ToString();                                  // 序列化 → JSON 字符串
    static TempMessageInfo FromString(const FString&);  // 反序列化 → 结构体
};
```

- `ToString()`：非静态，输出自身为 JSON（复制 `WriteObjectStart`...`Close` 代码）
- `FromString()`：**静态**，从 JSON 字符串创建新对象（不修改调用者）
  - 必须是静态方法，因为它是"另外构建一个"对象，不是修改自身

这种封装的意义：结构体开发者维护读写逻辑，使用者只关心属性 + `ToString`/`FromString`。

## 注意事项

- `WriteObjectStart` 与 `WriteObjectEnd` 必须配对，漏写会导致 JSON 格式错误
- `Close()` 关闭流后 `GoodJsonString` 才被填充
- 写对象数组中元素时不传参 `WriteObjectStart()`（无键名），区别于子对象 `WriteObjectStart(TEXT("key"))`

## 配套代码

| 函数 | 文件 | 行 |
|------|------|----|
| `AXGSampleJson::GoodJson()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L58) | 58~235 |
| `TempMessageInfo::ToString()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L464) | 464~522 |
| `TempMessageInfo::FromString()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L524) | 524~599 |
| `AXGSampleJson::GoodJson2()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L237) | 237~272 |
