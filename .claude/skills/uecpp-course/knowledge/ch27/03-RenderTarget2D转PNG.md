# RenderTarget2D 转 PNG 二进制数据

将 `UTextureRenderTarget2D` 的像素数据读取并压缩为 PNG 格式的二进制数据。代码见 [XGSamplePictureAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSamplePicture/Source/XGSamplePicture/Private/XGSamplePictureActionAction.cpp#L56-L142)。

## 实现步骤

### 1. 空指针检查

```cpp
if (RenderTarget2DPtr == nullptr)
{
    CallOnFail(TEXT("UTextureRenderTarget2D is nullptr"));
    RealeaseResources();
    return;
}
```

### 2. 获取渲染资源并读取像素

```cpp
FTextureRenderTargetResource* RenderTargetResource = RenderTarget2DPtr->GameThread_GetRenderTargetResource();
int32 Height = RenderTarget2DPtr->GetSurfaceHeight();
int32 Wide = RenderTarget2DPtr->GetSurfaceWidth();
int32 PixelNum = Height * Wide;

FReadSurfaceDataFlags readPixelFlags(RCM_UNorm);
readPixelFlags.SetLinearToGamma(true);

TArray<FColor> OutColors;
OutColors.AddUninitialized(PixelNum);

bool bRead = RenderTargetResource->ReadPixels(OutColors, readPixelFlags);
```

- `FReadSurfaceDataFlags(RCM_UNorm)` — 线性伽马模式读取
- `SetLinearToGamma(true)` — 将线性空间转为 Gamma 空间
- `ReadPixels()` 返回 bool，失败时走 Fail 路径

### 3. Alpha 预乘修正

```cpp
for (auto& TmpColor : OutColors)
{
    TmpColor.A = 255 - TmpColor.A;
}
```

UE 的 `ReadPixels` 读取的 Alpha 通道通常为 0，通过将 A 通道取反（255 - A）修复 PNG 的透明问题。这是 UE 纹理读取与 PNG 格式之间的兼容性处理。

### 4. 异步 PNG 压缩

```cpp
AsyncTask(ENamedThreads::AnyThread, [Wide, Height, OutColors, this]()
{
    TArray<uint8> OutPictureData;
    TArray64<uint8> PictureData;
    FImageUtils::PNGCompressImageArray(Wide, Height, OutColors, PictureData);
    
    OutPictureData = PictureData;
    
    if (bSaveLocalTempPNG)
    {
        FString FilePath = FPaths::ConvertRelativePathToFull((FPaths::ProjectSavedDir())) / TEXT("TestVideo.png");
        FFileHelper::SaveArrayToFile(OutPictureData, *FilePath);
    }
    
    AsyncTask(ENamedThreads::GameThread, [OutPictureData, this]()
    {
        CallOnSuccess(TEXT("Generate Succeed"), OutPictureData);
        RealeaseResources();
    });
});
```

- `FImageUtils::PNGCompressImageArray()` — UE 内置的 PNG 压缩函数，需要在后台线程执行防止卡主 GameThread
- `Async(EAsyncExecution::ThreadPool)` 或 `AsyncTask(ENamedThreads::AnyThread)` — 两种后台线程执行方式
- `bSaveLocalTempPNG` — 可选的本机保存调试开关，保存到 `ProjectSavedDir/TestVideo.png`
- PNG 压缩完成后通过 `AsyncTask(ENamedThreads::GameThread)` 回到 GameThread 广播结果

## 涉及模块依赖

Build.cs 中需要以下依赖：
- `RHI`（Public） — 用于 `FTextureRenderTargetResource`、`FReadSurfaceDataFlags`
- `CoreUObject` / `Engine`（Private） — 基础 UE 类型
- `ImageUtils.h` — PNG 压缩
- `Async/Async.h` — 异步任务
