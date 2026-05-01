# 第三十二章·案例 11：SMTP 协议状态机实现

## 概述

本章核心业务逻辑是基于 SMTP 协议的邮件发送状态机。SMTP（Simple Mail Transfer Protocol）基于 TCP 通信，服务端主动发信息、客户端被动回应，采用一问一答的交互模式。

## 完整交互流程

```
Client                                      Server
  │                                           │
  │  ──── TCP Connect ──────────────────────► │
  │  ◄─── 220（服务就绪）──────────────────── │
  │  ──── EHLO XIAOGANG ────────────────────► │
  │  ◄─── 250（请求完成）──────────────────── │
  │  ──── AUTH LOGIN ───────────────────────► │
  │  ◄─── 334（base64"用户名"提示）────────── │
  │  ──── base64(用户名) ───────────────────► │
  │  ◄─── 334（base64"密码"提示）──────────── │
  │  ──── base64(授权令牌) ─────────────────► │
  │  ◄─── 235（认证成功）──────────────────── │
  │  ──── MAIL FROM:<sender@qq.com> ────────► │
  │  ◄─── 250 ─────────────────────────────── │
  │  ──── RCPT TO:<receiver@qq.com> ────────► │
  │  ◄─── 250 ─────────────────────────────── │
  │  ──── DATA ─────────────────────────────► │
  │  ◄─── 354（开始发送数据）──────────────── │
  │  ──── 邮件内容 + \r\n.\r\n ────────────► │
  │  ◄─── 250 ─────────────────────────────── │
  │  ──── QUIT ─────────────────────────────► │
  │  ◄─── 221（服务关闭）──────────────────── │
```

任何阶段接收到非预期响应码，立即执行阶段关闭（StageClose）并回调错误信息。

## 状态枚举定义

状态枚举 `EXGSampleEMailStatus` 直接映射 SMTP 协议阶段：

| 枚举值 | 含义 | 触发时机 |
|--------|------|----------|
| `None` | 无状态 | 初始默认值 |
| `Init` | 初始态 | Activate 后、连接前 |
| `Connected` | 已连接 | TCP 连接成功 |
| `ConnectedSuccess` | 连接成功确认 | 收到 220 |
| `ConnectedError` | 连接失败 | 未收到 220 |
| `EHLO` | 等待 EHLO 回复 | 发送 EHLO 后 |
| `AuthLogin_UserName` | 等待用户名提示 | 发送 AUTH LOGIN 后 |
| `AuthLogin_Password` | 等待密码提示 | 发送用户名后 |
| `AuthLogin_Result` | 等待认证结果 | 发送密码后 |
| `SetMailFrom` | 等待发件人确认 | 发送 MAIL FROM 后 |
| `SetEmailTo` | 等待收件人确认 | 发送 RCPT TO 后 |
| `DataPrepare` | 等待 DATA 确认 | 发送 DATA 后 |
| `Data` | 等待数据发送确认 | 发送邮件内容后 |
| `Quit` | 等待退出确认 | 发送 QUIT 后 |
| `Finished` | 正常完成 | 收到 221 |
| `Closed` | 已关闭 | 连接关闭 |
| `UnKnowedError` | 未知错误 | 异常状态 |

## 状态机实现（AsyncAction::OnMessage）

`OnMessage()` 是 AsyncAction 中 SMTP 状态机的核心，根据当前 Status 枚举值和收到的服务端响应码，决定下一步操作：

```
OnMessage(response)
  ├── Status == Connected + 220 → ConnectedSuccess，发 EHLO
  ├── Status == EHLO + 250 → AuthLogin_UserName，发 AUTH LOGIN
  ├── Status == AuthLogin_UserName + 334 → AuthLogin_Password，发 Base64(用户名)
  ├── Status == AuthLogin_Password + 334 → AuthLogin_Result，发 Base64(授权令牌)
  ├── Status == AuthLogin_Result + 235 → SetMailFrom，发 MAIL FROM:<from>
  ├── Status == SetMailFrom + 250 → SetEmailTo，发 RCPT TO:<to>
  ├── Status == SetEmailTo + 250 → DataPrepare，发 DATA
  ├── Status == DataPrepare + 354 → Data，发邮件内容
  ├── Status == Data + 250 → Quit，发 QUIT
  ├── Status == Quit + 221 → Finished → 关闭连接
  └── 其他 → 异常状态 → StageClose + 回调错误
```

关键行为：
- 每个阶段根据当前状态决定**发什么内容**而非收什么内容——状态表示"我刚才发了什么"，收到服务端回复后推进到下一状态
- 异常响应统一由 `else` 分支捕获，执行 `StageClose` 关闭 TCP
- `StageClose` 在关闭前通过反射获取当前状态的枚举名称，拼接错误信息

## 邮件内容格式

DATA 阶段发送的邮件正文格式：

```
From: =?UTF-8?B?{Base64(FromName)}?= <{FromEmail}>
To: =?UTF-8?B?{Base64(ToName)}?= <{ToEmail}>
Subject: =?UTF-8?B?{Base64(Subject)}?=
Content-Type: text/plain;charset="utf-8"

{Body}
```

- 中文字符需通过 Base64 编码后以 `=?UTF-8?B?{encoded}?=` 格式传输
- 正文结束标志：`\r\n.\r\n`（CRLF + 点 + CRLF）

## 授权认证

- 使用 QQ 邮箱 SMTP 服务（`smtp.qq.com:25`）
- 认证方式：AUTH LOGIN（Base64 编码的用户名和密码）
- 密码字段填写的是 **QQ 邮箱 SMTP 授权码**（非 QQ 密码），需在 QQ 邮箱「设置→账户→POP3/SMTP 服务」中开启并获取

## 文件索引

| 文件路径 | 说明 |
|----------|------|
| [XGSampleEMailType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Type/XGSampleEMailType.h) | 状态枚举 + 邮件内容结构体 |
| [XGSampleEMailAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Private/AsyncAction/XGSampleEMailAsyncAction.cpp) | OnMessage 状态机实现 |
