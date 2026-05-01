# 第二十四章：商业化 Json 读写使用

## 字幕资源

- 来源：`subtitles/024第二十四章商业化Json的读写使用/`
- 共 7 个字幕文件（001~007）

---

## 本章概述

本章是课程的**案例 3**，全面讲解 UE C++ 中 JSON 的三种读写方式（原始拼接→TJsonWriter/Reader→FJsonObjectConverter 反射），以及商业化开发中遇到的特殊 JSON 设计模式。JSON 是后续所有网络通讯章节（HTTP/WebSocket 共 5 章）的前置基础。

## 知识文档索引

| 序号 | 文档 | 覆盖字幕 | 核心内容 |
|------|------|----------|----------|
| 01 | [JSON基础规范与三种写法概述](ch24/01-JSON基础规范与三种写法概述.md) | 001, 002 | JSON 五大数据类型、协议报文结构、FString::Printf 原始拼接（NotGoodJson） |
| 02 | [TJsonWriter与TJsonReader底层读写](ch24/02-TJsonWriter与TJsonReader底层读写.md) | 003, 004 | 写入流创建、对象/数组/嵌套写入、反序列化流程、3 种读取方式、ToString/FromString 封装 |
| 03 | [商业化嵌套读写与糟糕设计模式](ch24/03-商业化嵌套读写与糟糕设计模式.md) | 005, 006 | BadMessage（JSON 字符串嵌套）、VeryBadJson（动态 Key 名反模式）、二次反序列化 |
| 04 | [FJsonObjectConverter反射序列化](ch24/04-FJsonObjectConverter反射序列化.md) | 007 | USTRUCT 自动序列化、UPROPERTY 过滤机制、复杂嵌套、FDateTime 支持、JsonArrayStringToUStruct |

## 关键类/API 速查

| 类/API | 头文件 | 用途 |
|--------|--------|------|
| `TJsonWriterFactory<T>::Create` | `Serialization/JsonWriter.h` | 创建 JSON 写入流 |
| `TJsonReaderFactory<T>::Create` | `Serialization/JsonReader.h` | 创建 JSON 读取流 |
| `FJsonSerializer::Deserialize` | `Serialization/JsonSerializer.h` | 字符串 → FJsonObject |
| `FJsonObject::TryGetField` | `Dom/JsonObject.h` | 安全获取字段值 |
| `FJsonObject::TryGetNumberField` | `Dom/JsonObject.h` | 安全获取数值字段 |
| `FJsonObject::GetStringField` | `Dom/JsonObject.h` | 获取字符串字段 |
| `FJsonObject::GetObjectField` | `Dom/JsonObject.h` | 获取嵌套对象 |
| `FJsonObject::GetArrayField` | `Dom/JsonObject.h` | 获取数组字段 |
| `FJsonObject::Values` | `Dom/JsonObject.h` | 遍历所有键值对（TMap） |
| `FJsonObjectConverter::UStructToJsonObjectString` | `JsonObjectConverter.h` | USTRUCT → JSON 字符串 |
| `FJsonObjectConverter::JsonObjectStringToUStruct` | `JsonObjectConverter.h` | JSON 字符串 → USTRUCT |
| `FJsonObjectConverter::JsonArrayStringToUStruct` | `JsonObjectConverter.h` | JSON 数组 → TArray\<USTRUCT\> |
| `FFileHelper::SaveStringToFile` | `Misc/FileHelper.h` | 字符串存本地 |
| `FFileHelper::LoadFileToString` | `Misc/FileHelper.h` | 读本地文件 |
| `TCondensedJsonPrintPolicy` | `Policies/CondensedJsonPrintPolicy.h` | 紧凑输出（无空格） |

## 代码工程关联

| 目录 | 说明 |
|------|------|
| [code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/](ch24/../code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/) | 本章主代码（XGSampleJson.h/.cpp） |
| [code/004_Json/](ch24/../code/004_Json/) | JSON 示例数据文件（Message.json / Character.json / BadMessage.json 等） |

## 与前序/后续章节的关联

| 关系 | 章节 | 说明 |
|------|------|------|
| 前置依赖 | 第3章 USTRUCT/UPROPERTY | FJsonObjectConverter 依赖反射宏 |
| 前置依赖 | 第10章 字符串 FString::Printf | 原始拼接方式基于 Printf |
| 后续使用 | 第25~28章 HTTP 系列 | 所有 HTTP 通讯均依赖 JSON |
| 后续使用 | 第29~31章 WebSocket 系列 | WebSocket 消息格式为 JSON |
