# 多张动态 WebP 底层编码接口

## 概述

在第二层和第三层实现多张图片合成动态 WebP（动画 WebP）的编码接口。核心差异在于使用 `WebPAnimEncoder` API 替代单张的 `WebPEncodeRGBA`。

## 第二层：纯 C++ 接口

代码：[XGSampleWebPLib.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPLib.h)

```cpp
static bool GenerateDymaicWebpByRGBA(
    const char* InWebpSavePath,                      // 输出路径
    std::vector<const unsigned char*>& InRGBADatas,   // 多张图片的像素数据
    std::vector<int> InTimestamps_ms,                 // 每张图片的时间戳（毫秒）
    int InWidth,                                      // 图片宽度
    int InHeight,                                     // 图片高度
    float InQualityFactor = 100);                     // 质量因子
```

### 与单张接口的差异

| 维度 | 单张 (`GenerateWebpByRGBA`) | 多张 (`GenerateDymaicWebpByRGBA`) |
|------|---------------------------|----------------------------------|
| 像素数据 | `const unsigned char*`（一张） | `std::vector<const unsigned char*>`（多张） |
| 时间戳 | 无 | `std::vector<int>`（毫秒） |
| 底层 API | `WebPEncodeRGBA()` | `WebPAnimEncoder` 系列 |
| 用途 | 生成 `.webp` 静态图 | 生成 `.webp` 动态图（动画） |

### 实现流程

1. **初始化编码器**：`WebPAnimEncoderOptionsInit(&enc_options)` + `WebPAnimEncoderNew()`
2. **逐帧添加**：对每一帧调用 `WebPAnimEncoderAdd()` 传入像素数据和时间戳
3. **完成编码**：`WebPAnimEncoderAssemble()` 组装为完整 WebP 数据
4. **写入文件**：将 `WebPData` 写入本地路径
5. **清理**：`WebPAnimEncoderDelete()` 释放编码器

### 为什么使用 std::vector 而非原生指针数组？

- 多张图片的数量在编译时不确定（可能是 10 张、100 张）
- `std::vector` 管理动态数组更安全，避免手动内存管理
- 可以与 C++ 容器生态互操作

## 第三层：UEC++ 封装

代码：[XGSampleWebPCore.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPCore.h)

```cpp
static bool GenerateDynamicWebpPicture(
    FString& InPicturePath,
    TSharedPtr<FXGSampleWebpPictureInformation> InWebpPictureInformation,
    TArray<TArray<FColor>>& InPicturesColors,         // 多张图片的像素数据
    TArray<int32>& WebpTimestepMillisecond,           // 时间戳数组
    int32 InQualityFactor = 100);
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `InPicturePath` | `FString&` | 输出路径（引用传递，可被修改） |
| `InWebpPictureInformation` | `TSharedPtr<FXGSampleWebpPictureInformation>` | 图片裁剪信息（四角坐标） |
| `InPicturesColors` | `TArray<TArray<FColor>>&` | 每张图的完整像素数组 |
| `WebpTimestepMillisecond` | `TArray<int32>&` | 每张图的时间戳（毫秒） |
| `InQualityFactor` | `int32` | 质量因子 |

### 类型转换挑战

从 UE 类型到 C++ 类型的多层转换：

```
TArray<TArray<FColor>>  →  std::vector<const unsigned char*>
TArray<int32>           →  std::vector<int>
FString                 →  const char*
```

转换时需要逐张图片、逐个像素处理，并在完成后释放临时分配的内存。

## 时间戳含义

- 单位：**毫秒**（ms）
- 表示该帧在动画时间轴上的位置
- 例如：`[16, 40, 100]` 表示第 1 帧在 16ms 显示，第 2 帧在 40ms，第 3 帧在 100ms
- 来源：UE 中通过 `GetWorld()->GetTimeSeconds()` 或 `GetGameTimeSinceCreation()` 获取

## 内存与性能注意事项

- N 张 1920×1080 图片 = N × 8.3 MB 内存
- 编码过程是 CPU 密集型操作，耗时与图片数量、尺寸成正比
- 必须放在**异步线程**中执行，否则阻塞主线程导致卡死
