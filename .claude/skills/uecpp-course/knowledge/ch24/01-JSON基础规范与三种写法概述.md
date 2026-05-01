# JSON 基础规范与三种写法概述

## 概述

JSON（JavaScript Object Notation）是网络通讯中最通用的数据交换格式。它在 UE C++ 中有三种使用方式，从原始到高级依次递进。本章是课程**案例 3**（商业化 Json 读写），后续章节（HTTP/WebSocket 共 5 章）均依赖本章知识。

## JSON 五大数据类型

| 类型 | JSON 示例 | C++ 对应 |
|------|----------|----------|
| 对象 (object) | `{"key": "value"}` | `FJsonObject` / 自定结构体 |
| 整数 (int) | `998` | `int32` |
| 浮点 (float) | `3.2` | `float` / `double` |
| 布尔 (bool) | `true` / `false` | `bool` |
| 字符串 (string) | `"hello"` | `FString` |
| 数组 (array) | `[1, 3, 5]` | `TArray` |
| 空值 | `null` | 特殊处理 |

- **对象**：用 `{}` 括起，内含 `"key": value` 键值对
- **数组**：用 `[]` 括起，元素逗号分隔
- JSON 对象 ≠ UE 的 `UObject` — 只是数据格式概念

## 通讯协议报文结构

后端通信的典型 JSON 报文规范（以讯飞等厂商为例）：

```json
{
  "Code": 0,          // 状态码（0=成功，非0=失败，值与后端约定）
  "Message": "Success", // 消息描述（成功为空或默认，失败时说明原因）
  "Data": "...",      // 业务数据（可字符串/对象/数组）
  "Sid": "753415"     // 会话 ID（标识本次请求唯一性）
}
```

**设计约束**：
- 不要设计递归自引用结构（对象套自身），自动化工具难以解析
- 不要设计"可选字段"（有时有有时无），应始终包含该字段并给默认值
- 嵌套层级不要太深（建议不超过 3 层）

## 三种写法对比

| 方式 | API | 适用场景 | 复杂度 |
|------|-----|----------|--------|
| 原始字符串拼接 | `FString::Printf` | ❌ 不推荐 | 低→高（嵌套后极难维护） |
| TJsonWriter/TJsonReader | `FJsonSerializer` | 第三方接口适配、灵活控制 | 中 |
| FJsonObjectConverter | `UStructToJsonObjectString` | 自有前后端、快速开发 | 低 |

### 方式一：原始 FString::Printf（NotGoodJson）

```cpp
FString NotGooDJson = FString::Printf(
    TEXT("{\"Code\":%d,\"Message\":\"%s\",\"Data\":\"%s\",\"Sid\":\"%s\"}"),
    Code, *Message, *Data, *Sid);
```

**问题**：
- 需要手动转义引号 `\"`，极易出错
- 布尔值需三目运算符自己转换
- 嵌套对象/数组几乎无法手写
- 前后端联调时编码不一致（空格/缩进/引号）会导致校验不通过
- 反序列化需手写 `Find/Split` 解析，代码量巨大且不健壮

### 方式二：TJsonWriter/TJsonReader（GoodJson）

UE 底层原生 JSON 工厂 API，精确控制每个字段。详见[第 2 篇](02-TJsonWriter与TJsonReader底层读写.md)。

### 方式三：FJsonObjectConverter（GoodStructJson）

基于 UE 反射系统自动序列化 USTRUCT。详见[第 4 篇](04-FJsonObjectConverter反射序列化.md)。

## 联调建议

- VS Code 安装 **Prettify JSON** 插件，格式化查看 JSON
- 联调时不要比对最终的字符串结果（编码/空格可能不同），应比对**二进制值**
- 后端已定好格式时，前端只能用方式二适配；自建前后端时推荐方式三

## 配套代码

| 文件 | 路径 |
|------|------|
| XGSampleJson.h | [code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.h) |
| XGSampleJson.cpp | [code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp) |
| JSON 示例文件 | [code/004_Json/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/004_Json/) — Message.json / Character.json / BadMessage.json 等 |
