# 单张 WebP 底层编码接口

## 概述

在 `FXGSampleWebPLib`（第二层：纯 C++ 封装）和 `FXGSampleWebPCore`（第三层：UEC++ 封装）中实现单张静态 WebP 图片的编码生成。

## 第二层：纯 C++ 接口

代码：[XGSampleWebPLib.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPLib.h)

```cpp
static bool GenerateWebpByRGBA(
    const char* InWebpSavePath,        // 输出路径
    const unsigned char* InRGBAData,    // RGBA 像素数据
    int InWidth,                        // 图片宽度
    int InHeight,                       // 图片高度
    float InQualityFactor = 100);       // 质量 0~100
```

### 实现流程

1. **参数校验**：质量因子裁剪到 [0, 100]
2. **调用 libwebp API**：`WebPEncodeRGBA()` 执行编码
   - 返回压缩后的数据指针 `uint8_t*`
   - 返回数据大小 `size_t`
3. **写入文件**：将压缩数据通过 `<fstream>` 写入本地路径
4. **释放内存**：调用 `WebPFree()` 释放编码返回的数据
5. **返回成功/失败**：size > 0 且文件写入成功为 `true`

### API 签名解读

`WebPEncodeRGBA()` 的参数：

| 参数 | 含义 |
|------|------|
| `InRGBAData` | 指向 RGBA 像素数组的指针 |
| `InWidth × 4` | stride（步幅），每行字节数 = 宽 × 4（因为 RGBA 每像素 4 字节） |
| `InWidth`, `InHeight` | 图片尺寸 |
| `InQualityFactor` | 0~100 浮点数，100 最佳质量 |

**为什么 stride = width × 4？**
因为每个像素占 4 字节（RGBA），一行的数据量 = 像素宽 × 4。这是 row stride 的概念。

## 第三层：UEC++ 封装

代码：[XGSampleWebPCore.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPCore.h)

```cpp
static bool GenerateStaticWebpPicture(
    const FString& InPicturePath,                // UE 字符串路径
    const TArray<FColor>& InPictureColors,       // UE 像素数组
    const FVector2D& InPictureSize,              // UE 二维向量
    int32 InQualityFactor = 100);
```

### 类型转换

| UE 类型 | C++ 类型 | 转换方式 |
|---------|----------|---------|
| `FString` | `const char*` | `TCHAR_TO_ANSI(*InPicturePath)`（有风险，见下文） |
| `TArray<FColor>` | `unsigned char*` | 逐像素复制到 `new` 分配的内存 |
| `FVector2D` | `int, int` | `.X`, `.Y` 取值 |

### 关键处理

1. **路径校验**：调用 `CheckWebpPicturePath()` 检查路径后缀为 `.webp` 且目录存在
2. **尺寸校验**：`InPictureColors.Num()` == `Width × Height`
3. **A 通道反转**：遍历每个像素，`FColor` 的 A 通道与 libwebp 预期方向可能相反，执行 `255 - A` 反转
4. **内存管理**：
   - `new unsigned char[总数 × 4]` 分配临时缓冲区
   - 无论成功失败都必须 `delete[]` 释放
   - 释放后将指针置 `nullptr`

### TCHAR_TO_ANSI 的风险

`TCHAR_TO_ANSI` 转换存在以下风险：
- 返回的指针生命周期极短（过了作用域即回收）
- 路径过长会被截断
- 不能包含中文路径

**标注"外部必须在其他线程使用该接口"**：WebP 编码是耗时操作（几十毫秒），同步调用会阻塞主线程。

## 质量因子说明

| 质量值 | 效果 |
|--------|------|
| 0 | 最差质量，最小文件 |
| 50 | 中等质量 |
| 100 | 最佳质量（无损/近无损），最大文件 |
