# 第二十八章 HTTP 流式传输——大模型通讯（百度文心一言）

## 章节说明

本章讲解如何使用 UE 的 FHttpModule 与百度文心一言（ERNIE Bot）大模型进行 HTTP 通信，覆盖**非流式**（一次性返回）和**流式**（逐 token 实时输出）两种模式。与第二十七章（讯飞接口）形成对比，展示不同云服务商 API 鉴权与数据格式的差异。

## 知识文档

| # | 文档 | 内容 |
|---|------|------|
| 01 | [知识概览](ch28/01-知识概览.md) | 本章概述、文件索引、与第二十七章的关联 |
| 02 | [异步蓝图节点框架](ch28/02-异步蓝图节点框架.md) | BDChat 节点四引脚设计（Then/OnSuccess/OnUpdate/OnFail） |
| 03 | [百度 AKSK 鉴权签名](ch28/03-百度AKSK鉴权签名.md) | BCE v1 签名、HMAC-SHA256 十六进制输出、Header 鉴权 |
| 04 | [请求体构造与 JSON 工厂](ch28/04-请求体构造与JSON工厂.md) | FBDReqUtil 条件写入、messages 数组、manual JSON 构建 |
| 05 | [非流式响应解析](ch28/05-非流式响应解析.md) | HTTP 状态检查、error_code 判断、FJsonObjectConverter 反序列化 |
| 06 | [HTTP 流式数据处理](ch28/06-HTTP流式数据处理.md) | OnStreamReady 绑定、跨线程处理、\n\n 分隔符解析 |
| 07 | [响应类型体系](ch28/07-响应类型体系.md) | 全部响应类型 USTRUCT 定义 |
| 08 | [蓝图节点生命周期与跨线程安全](ch28/08-蓝图节点生命周期与跨线程安全.md) | RegisterWithGameInstance、跨线程委托广播、资源释放 |

## 知识图谱
<!-- 此章节知识图谱节点将在下次重建时自动更新 -->
