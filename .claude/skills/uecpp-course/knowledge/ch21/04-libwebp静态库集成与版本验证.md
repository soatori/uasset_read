# libwebp 静态库集成与版本验证

## 概述

将 libwebp 的 6 个头文件和 3 个静态库集成到 UE 插件中，并通过 `WebPGetDecoderVersion()` 等 API 验证集成是否成功。同时实现授权控制机制。

## 第三方库资源

位置：[code/012_第三方库资源/libwebp/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/012_第三方库资源/)

| 文件类型 | 文件列表 | 说明 |
|---------|---------|------|
| 头文件 | `decode.h`, `encode.h`, `demux.h`, `mux.h`, `mux_types.h`, `types.h` | API 声明，共 6 个 |
| 静态库 | `libwebp.lib`, `libwebpdemux.lib`, `libwebpmux.lib` | Windows x64 Release，共 3 个 |

插件中的存放位置：[XGSampleWebPLibrary/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/ThirdParty/XGSampleWebPLibrary/)

## 导入步骤

1. 将 6 个头文件放入 `Source/ThirdParty/XGSampleWebPLibrary/Public/`
2. 将 3 个 `.lib` 静态库放入 `Source/ThirdParty/XGSampleWebPLibrary/x64/Release/`
3. 在 `XGSampleWebPLibrary.Build.cs` 中配置 `PublicAdditionalLibraries`
4. 在 `XGSampleWebP.Build.cs` 中添加 `XGSampleWebPLibrary` 为依赖模块

## 版本验证

libwebp 提供了三个版本获取函数：

| 函数 | 头文件 | 返回 |
|------|--------|------|
| `WebPGetDecoderVersion()` | `decode.h` | 解码器版本（int） |
| `WebPGetEncoderVersion()` | `encode.h` | 编码器版本 |
| `WebPGetMuxVersion()` | `mux.h` | 复用器版本 |
| `WebPGetDemuxVersion()` | `demux.h` | 解复用器版本 |

在 BPLibrary 中暴露版本查询：

```cpp
// [XGSampleWebPBPLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/XGSampleWebPBPLibrary.h)
UFUNCTION(BlueprintPure, meta = (...), Category = "XGSampleWebp")
static bool GetXGSampleWebpVersion(FString& OutVersionInfo);
```

实现中拼接四个版本号为一个字符串返回。

## 头文件包含方式

头文件放在第三方模块的 `Public/` 目录下后，可以通过相对路径直接包含：

```cpp
#include "encode.h"
#include "decode.h"
#include "mux.h"
```

注意：确保文件编码为 **UTF-8**，否则中文注释/日志可能出现乱码。

## 授权控制机制

插件内置了一个简单的授权开关：

- 静态变量 `static bool bAuth = false`（默认未授权）
- 在 BPLibrary 中暴露 `SetXGWebpAuth()` 设置授权
- 所有对外接口在执行实际逻辑前检查 `bAuth`，未授权时打日志提示

```cpp
// [XGSampleWebPBPLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/XGSampleWebPBPLibrary.h)
UFUNCTION(BlueprintCallable, meta = (...), Category = "XGSampleWebp")
static void SetXGWebpAuth();
```

这种模式可以扩展为：
- HTTP 请求验证在线授权
- CDK/加密密钥验证
- 游戏时长限制

## 常见问题

### 编译错误：cannot open file 'xxx.lib'

原因：`.lib` 文件路径拼写错误或文件未放入正确目录。
排查：检查 `XGSampleWebPLibrary.Build.cs` 中的 `ModuleDirectory` 路径，确认 `x64/Release/` 下确实有 `.lib` 文件。

### Link 2019 错误

原因通常有二：
1. 模块未正确导入 → 检查 Build.cs 的 `PrivateDependencyModuleNames`
2. 函数只有声明没有实现 → 检查 `.cpp` 文件是否正确生成

排查方法（"小黄鸭调试法"）：
1. 注释掉报错函数 → 编译通过 → 问题在函数内部
2. 逐个取消注释子功能 → 定位到具体的缺失实现

### UTF-8 编码问题

如果日志输出乱码，检查源码文件的编码格式：
- VS → 文件 → 高级保存选项 → 编码 → UTF-8
- 所有新创建的 `.h`/`.cpp` 文件都应设为 UTF-8
