# USoundWave 创建的三种方式

## 概述

收到完整音频数据后，需要创建 `USoundWave` 对象供蓝图播放。课程字幕中探讨了三种方式，最终采用最可靠的方式。

## 方式一：RawPCMData（UE4 经典方式）

```cpp
USoundWave* SoundWave = NewObject<USoundWave>();
SoundWave->SetSampleRate(16000);
SoundWave->NumChannels = 1;
SoundWave->Duration = AllAudioData.Num() / (16000.0f * 2); // 16bit = 2 bytes/sample

// RawPCMData 赋值
SoundWave->RawPCMData = (uint8*)FMemory::Malloc(AllAudioData.Num());
FMemory::Memcpy(SoundWave->RawPCMData, AllAudioData.GetData(), AllAudioData.Num());
SoundWave->RawPCMDataSize = AllAudioData.Num();
```

- `RawPCMData` 是 `USoundWave` 的原始 PCM 数据缓冲区
- 编译器需要手动管理内存（`FMemory::Malloc`）
- **问题**：UE5 中 `RawPCMData` 已被标记为 deprecated，推荐使用 `RawData`

## 方式二：RawData（UE5 推荐方式）

```cpp
USoundWave* SoundWave = NewObject<USoundWave>();
SoundWave->SetSampleRate(16000);
SoundWave->NumChannels = 1;
SoundWave->Duration = AllAudioData.Num() / (16000.0f * 2);

// RawData 使用 FSharedBuffer（UE5 推荐）
SoundWave->RawData = FSharedBuffer::Clone(AllAudioData.GetData(), AllAudioData.Num());
```

- `RawData` 类型为 `FSharedBuffer`，自动管理内存
- 使用 `FSharedBuffer::Clone` 复制数据
- 继承自 UE5 的音频系统更新，`RawPCMData` 的替代方案

## 方式三：FSampleBuffer（最终使用方式）

UE5 的音频管线最终使用方式，也是最可靠的方式：

```cpp
USoundWave* SoundWave = NewObject<USoundWave>();
SoundWave->SetSampleRate(16000);
SoundWave->NumChannels = 1;
SoundWave->Duration = AllAudioData.Num() / (16000.0f * 2);

// 创建音频采样缓冲区
Audio::FSampleBuffer SampleBuffer(
    AllAudioData.GetData(),     // int16 数据
    AllAudioData.Num() / 2,    // 样本数（每个 int16 算一个样本）
    1,                          // 通道数
    16000                       // 采样率
);

// 通过 FAudioSampleBuffer 赋值到 RawData
// ...
```

## 最终选择

项目最终选择了 **方式三（FSampleBuffer）**，因为：
1. `RawPCMData` 在 UE5 中已被标记为 deprecated
2. `RawData` 需要额外处理 UE5 的音频序列化要求
3. `Audio::FSampleBuffer` 是 UE5 音频系统原生的缓冲区类型，最稳定

## 回调蓝图

```cpp
void UXGSampleTTSAsyncAction::ProcessCompleteAudio()
{
    // 创建 USoundWave ...
    // ...

    // 回调蓝图
    if (OnSoundWaveSuccess.IsBound())
    {
        OnSoundWaveSuccess.Broadcast(SoundWave);
    }
}
```

## 注意事项

| 问题 | 说明 |
|------|------|
| 内存管理 | USoundWave 由 GC 管理，但 RawPCMData 需要手动 Free |
| 线程安全 | WebSocket 回调可能不在游戏线程，需注意 |
| 音频格式 | 服务器返回的是 16KHz、16bit、单声道 PCM 数据 |
| Duration 计算 | `数据总字节数 / (采样率 × 字节数每样本 × 通道数)` |
