# HTTP 基础概念与 UE Http 模块入门

## HTTP 请求的基本结构

HTTP 请求由以下几个部分组成：

- **URL**：请求的目标地址，可附带查询参数（`?key=value`）
- **Verb（请求方法）**：GET（获取资源）、POST（提交数据）、PUT（更新）、DELETE（删除）
- **Header（请求头）**：键值对形式，携带元信息如 `Content-Type`、`XGGuid` 等
- **Body（请求体）**：POST/PUT 时携带的数据，通常为 JSON 格式字符串

响应结构类似：状态码 + Header + Body。

## 常见 HTTP 状态码

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 302 | Found | 临时重定向 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |
| 304 | Not Modified | 缓存有效，无需重新传输 |

## GET 与 POST 的核心区别

| 特性 | GET | POST |
|------|-----|------|
| 参数位置 | URL 查询字符串 | Body |
| 数据大小 | 受 URL 长度限制（约 2KB） | 无限制 |
| 安全性 | 参数明文在 URL 中 | 参数在 Body 中 |
| 幂等性 | 幂等（重复请求结果相同） | 非幂等 |
| 缓存 | 可缓存 | 不可缓存 |

## 开发者工具与调试

浏览器开发者工具（F12）的 Network 面板可查看所有 HTTP 请求的详细信息：

- **Headers**：请求和响应的所有头信息
- **Payload / Request**：请求体内容
- **Preview / Response**：响应体预览和原始内容
- **Status**：响应状态码

Postman 是独立于浏览器的 HTTP 调试工具，支持构造和发送各类 HTTP 请求、管理请求集合、生成代码片段。

## UE Http 模块集成

在 `Build.cs` 中添加 Http 模块依赖：

```cpp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core",
    "CoreUObject",
    "Engine",
    "InputCore",
    "Http"   // 必须大写 H
});
```

> **注意**：模块名必须写作 `"Http"`（首字母大写），写成 `"HTTP"` 会导致模块解析失败。

## UE HTTPS 注意事项

Unreal Engine 的 HTTPS 请求在编辑器环境下正常工作，但在**打包后的游戏中**需要附带 SSL 证书。如果 SSL 证书打包配置未正确处理，HTTPS 请求会在打包后失败。项目中建议：

- 开发和测试阶段可使用 HTTP
- 需要发布时确保 SSL 证书正确嵌入
- 若不处理 SSL 证书问题，建议使用 HTTP 替代 HTTPS

> **代码位置**：[XGSampleHttpTime.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.h) — 完整的异步 HTTP 请求节点定义
>
> **字幕位置**：025 第二十五章 001
