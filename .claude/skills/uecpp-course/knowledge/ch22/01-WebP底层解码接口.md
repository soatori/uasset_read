# WebP 底层解码接口

## 概述

在第21章编码（生成）的基础上，第22章实现反方向的解码（展示）流程。底层接口负责从 `.webp` 文件中解析出逐帧的像素数据和时间戳。

代码：[XGSampleWebPLib.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPLib.h)

## 第二层：纯 C++ 解码接口

```cpp
static bool LoadDynamicWebpPictureByRGBA(
    const char* InWebpFilePath,                      // WebP 文件路径
    std::vector<const unsigned char*>& OutRGBADatas,  // 输出：每帧像素数据
    std::vector<int>& OutTimestamps_ms,               // 输出：每帧时间戳
    int& OutWidth,                                    // 输出：图片宽度
    int& OutHeight);                                  // 输出：图片高度
```

### 与编码接口的对称性

| 编码 | 解码 |
|------|------|
| `GenerateDymaicWebpByRGBA` | `LoadDynamicWebpPictureByRGBA` |
| 输入：像素数据 + 时间戳 | 输出：像素数据 + 时间戳 |
| 调用 `WebPAnimEncoder` 系列 | 调用 `WebPAnimDecoder` 系列 |
| 最终写入文件 | 从文件读取 |

### 实现流程

1. **打开文件流**：`std::ifstream` 以二进制模式打开 `.webp` 文件
2. **读取文件内容**：将整个文件读入内存缓冲区
3. **创建解复用器**：`WebPDemuxer` + `WebPDemux()` 解析 WebP 数据
4. **获取全局信息**：
   - `WebPDemuxGetI()` 获取 Canvas 宽/高
   - `WebPDemuxGetI()` 获取帧数
5. **逐帧提取**：
   - `WebPDemuxGetFrame()` 遍历每一帧
   - 获取该帧的像素数据和时间戳
   - 将数据拷贝追加到输出容器
6. **清理**：`WebPDemuxDelete()` 释放解复用器

### 关键 API

| libwebp API | 用途 |
|-------------|------|
| `WebPDemuxer` | 解复用器对象 |
| `WebPDemux()` | 从内存数据创建解复用器 |
| `WebPDemuxGetI()` | 获取 WebP 全局信息（宽高、帧数、标志） |
| `WebPDemuxGetFrame()` | 逐帧获取帧信息（像素数据、时间戳、持续时间） |
| `WebPDemuxDelete()` | 释放解复用器 |

## 第三层：UEC++ 解码封装

代码：[XGSampleWebPCore.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Core/XGSampleWebPCore.h)

```cpp
static bool LoadDynamicWebpPicture(
    FString InWebpFilePath,
    TArray<int32>& OutWebpTimestepMillisecond,
    TArray<TArray<FColor>>& OutPicturesColors,
    int32& OutWebpWidth,
    int32& OutWebpHeight);
```

### 类型转换（解码方向）

| C++ 类型 | UE 类型 | 转换方式 |
|----------|---------|---------|
| `const unsigned char*` | `TArray<FColor>` | 逐像素从 raw bytes 构造 `FColor(R, G, B, A)` |
| `std::vector<int>` | `TArray<int32>` | 逐元素 `Add()` |
| `int` | `int32&` | 直接赋值 |

### 路径转换注意事项

与编码路径相同的风险：
- `TCHAR_TO_ANSI` 宏：指针生命周期短、不能有中文路径、长路径可能截断
- 实现中使用 `FPaths::FileExists()` 检查文件是否存在
- 编码阶段建议使用 `FTCHARToUTF8` 或 `StringCast<UTF8CHAR>` 替代裸宏

## 为什么解码也需要异步？

解码同样是 CPU 密集型操作（解复用 + 逐帧像素提取）。对于数十帧 1K 图片的解码，同步调用会导致明显的卡顿。
