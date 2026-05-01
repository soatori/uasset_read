# UEC++ 层解码封装与蓝图展示入口

## 概述

在第三层和第四层实现解码后的像素数据 → 动态纹理展示的完整链路：从 `FXGSampleWebPCore::LoadDynamicWebpPicture()` 拿到像素数据，到 `UXGSampleWebpShowMultiSubsystem` 中创建 `UTexture2D` 并逐帧更新纹理。

## UXGSampleWebpShowMultiSubsystem

代码：[XGSampleWebpShowMultiSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Subsystem/XGSampleWebpShowMultiSubsystem.h)

### 继承关系

```cpp
class UXGSampleWebpShowMultiSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
```

与 `MultiShotSubsystem` 一样，需要 `FTickableGameObject` 来实现逐帧纹理切换。

### 状态机

```cpp
// [XGSampleWebPType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Type/XGSampleWebPType.h)
enum class EXGSampleWebpLoadAndShowType : uint8
{
    None,      // 空闲
    Loading,   // 正在加载（解码）
    Showing,   // 正在展示（逐帧更新纹理）
    Max
};
```

状态转换：

```
None ──LoadWebp──→ Loading ──解码完成──→ Showing ──Release──→ None
```

### 核心成员变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `WebpTexture` | `UTexture2D*` (UPROPERTY) | 动态纹理对象 |
| `LoadAndShowStatus` | `EXGSampleWebpLoadAndShowType` | 当前状态 |
| `PicturesColors` | `TArray<TArray<FColor>>` | 解码后的所有帧像素 |
| `WebpTimestepMillisecond` | `TArray<int32>` | 解码后的所有帧时间戳 |
| `WebpWidth` / `WebpHeight` | `int32` | 图片尺寸 |
| `WebpShowIndex` | `int32` | 当前展示的帧索引 |
| `CurrentMillisecond` | `int32` | 当前已播放的毫秒数 |
| `XGWebpLoadAndShowWebp` | `FXGWebpLoadAndShowWebp` | 蓝图回调委托 |

## 核心流程

### LoadWebp（加载）

1. 检查状态，如在 Loading 或 Showing 则返回
2. 异步调用 `FXGSampleWebPCore::LoadDynamicWebpPicture()` 解码 WebP 文件
3. 解码完成后：
   - 保存像素数据、时间戳、宽高
   - 创建 `UTexture2D`：`NewObject<UTexture2D>()`，设置尺寸和格式
   - 设置状态为 `Showing`
   - 触发蓝图回调 `XGWebpLoadAndShowWebp`，传递纹理对象和尺寸

### Tick 驱动的纹理更新

每帧 `Tick()` 中：

1. 检查是否处于 `Showing` 状态
2. 累计 `DeltaTime` 到 `CurrentMillisecond`
3. 根据 `CurrentMillisecond` 查找对应的帧索引
4. 如果帧索引变化（`WebpShowIndex` 改变），更新纹理：
   - 通过 `UpdateTextureRegions()` 将当前帧像素数据写入 `UTexture2D`
5. 如果播放完所有帧，保持最后一帧

### ReleaseLoadedWebp（释放）

1. 设置状态为 `None`
2. 将 `WebpTexture` 置 `nullptr`
3. 清理像素数据数组

## 创建 UTexture2D

```cpp
// 创建动态纹理
WebpTexture = NewObject<UTexture2D>(GetTransientPackage(), NAME_None, RF_Transient);
WebpTexture->PlatformData = new FTexturePlatformData();
WebpTexture->PlatformData->SizeX = WebpWidth;
WebpTexture->PlatformData->SizeY = WebpHeight;
WebpTexture->PlatformData->PixelFormat = EPixelFormat::PF_B8G8R8A8;
// 分配 Mip 0 数据...
WebpTexture->UpdateResource();
```

关键点：
- `RF_Transient` 标志表示不持久化到磁盘
- 使用 `PF_B8G8R8A8` 与 `TArray<FColor>` 的内存布局兼容
- 调用 `UpdateResource()` 初始化纹理

## 蓝图暴露接口

### FXGWebpLoadAndShowWebp 委托

```cpp
// [XGSampleWebPType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Type/XGSampleWebPType.h)
DECLARE_DYNAMIC_DELEGATE_FourParams(FXGWebpLoadAndShowWebp, bool, bLoad, UTexture2D*, OutWebpPicture, int32, WebpWidth, int32, WebpHeight);
```

四个参数：
| 参数 | 说明 |
|------|------|
| `bLoad` | 是否加载成功 |
| `OutWebpPicture` | 纹理对象（成功时非空） |
| `WebpWidth` | 图片宽度 |
| `WebpHeight` | 图片高度 |

### BPLibrary 接口

| 蓝图函数 | 说明 |
|---------|------|
| `LoadWebp(WorldContext, Delegate, FilePath)` | 加载 WebP 文件 |
| `ReleaseLoadedWebp(WorldContext)` | 释放已加载的 WebP |

## 材质与展示

要将 `UTexture2D` 显示在场景中：
1. 创建一个 `Plane` Actor
2. 创建一个动态材质实例（`UMaterialInstanceDynamic`）
3. 将 `WebpTexture` 设置为材质的纹理参数
4. 将材质实例应用到 Plane 的 Mesh 上
