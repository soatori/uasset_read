# WAV 文件生成与存储

## 概述

当 `bSaveToLocal = true` 时，除了创建内存中的 `USoundWave`，还会将音频数据保存为 `.wav` 文件到磁盘。

## WAV 文件结构

WAV 文件由三个主要块（Chunk）组成：

```
┌─────────────────────────┐
│ RIFF Header (12 bytes)  │ ← 文件类型标识
├─────────────────────────┤
│ fmt Chunk (24 bytes)    │ ← 音频格式信息
├─────────────────────────┤
│ data Chunk (N bytes)    │ ← PCM 音频数据
└─────────────────────────┘
```

### RIFF Header

```cpp
struct FXGWaveHeard
{
    // RIFF 头部
    uint8 RIFF[4] = { 'R', 'I', 'F', 'F' };
    int32 FileSize;                 // 文件总大小 - 8
    uint8 WAVE[4] = { 'W', 'A', 'V', 'E' };

    // fmt 子块
    uint8 fmt[4] = { 'f', 'm', 't', ' ' };
    int32 fmtSize = 16;             // fmt 块大小（PCM 格式固定 16）
    int16 AudioFormat = 1;          // 1 = PCM（未压缩）
    int16 NumChannels = 1;          // 通道数（单声道）
    int32 SampleRate = 16000;       // 采样率
    int32 ByteRate;                 // 字节率 = SampleRate * NumChannels * BitsPerSample/8
    int16 BlockAlign;               // 块对齐 = NumChannels * BitsPerSample/8
    int16 BitsPerSample = 16;       // 位深（16bit）
};
```

### Data Chunk

```cpp
struct FXGWaveData
{
    uint8 data[4] = { 'd', 'a', 't', 'a' };
    int32 dataSize;                 // PCM 数据大小
    // 后续紧跟原始 PCM 数据
};
```

### 完整的 WAV 头

```cpp
struct FXGWaveFmt
{
    int16 AudioFormat;
    int16 NumChannels;
    int32 SampleRate;
    int32 ByteRate;
    int16 BlockAlign;
    int16 BitsPerSample;
};
```

## 实现代码

### ConvertPCMToWave

```cpp
TArray<uint8> UXGSampleTTSAsyncAction::ConvertPCMToWave(const TArray<uint8>& InPCMData)
{
    TArray<uint8> WaveData;

    // 计算字段值
    int32 PCMDataSize = InPCMData.Num();
    int16 NumChannels = 1;              // 单声道
    int32 SampleRate = 16000;           // 16KHz
    int16 BitsPerSample = 16;           // 16bit
    int16 BlockAlign = NumChannels * (BitsPerSample / 8);      // 2
    int32 ByteRate = SampleRate * BlockAlign;                   // 32000

    // 写入 RIFF Header
    FXGWaveHeard WaveHeard;
    WaveHeard.FileSize = 36 + PCMDataSize;  // 总大小 - 8
    WaveHeard.NumChannels = NumChannels;
    WaveHeard.SampleRate = SampleRate;
    WaveHeard.ByteRate = ByteRate;
    WaveHeard.BlockAlign = BlockAlign;
    WaveHeard.BitsPerSample = BitsPerSample;

    // 追加 Header
    WaveData.Append(reinterpret_cast<uint8*>(&WaveHeard), sizeof(FXGWaveHeard));

    // 追加 Data Chunk 头部
    FXGWaveData WaveDataChunk;
    WaveDataChunk.dataSize = PCMDataSize;
    WaveData.Append(reinterpret_cast<uint8*>(&WaveDataChunk), sizeof(FXGWaveData));

    // 追加 PCM 数据
    WaveData.Append(InPCMData);

    return WaveData;
}
```

### 异步保存到文件

```cpp
void UXGSampleTTSAsyncAction::ProcessCompleteAudio()
{
    // 创建 USoundWave（略）...

    // WAV 文件保存
    if (bSaveToLocal)
    {
        TArray<uint8> WaveFileData = ConvertPCMToWave(AllAudioData);

        // 异步保存到磁盘
        FString SavePath = SaveFileFullPath;
        Async(EAsyncExecution::TaskGraph, [WaveFileData, SavePath]()
        {
            bool bSaved = FFileHelper::SaveArrayToFile(WaveFileData, *SavePath);
            return bSaved;
        }).Then([this, SavePath](bool bSaved)
        {
            if (bSaved)
            {
                OnWavFileSuccess.Broadcast(SavePath);
            }
            else
            {
                OnWavFileFail.Broadcast(TEXT("文件保存失败"));
            }
        });
    }

    // 回调 SoundWave 成功
    if (OnSoundWaveSuccess.IsBound())
    {
        OnSoundWaveSuccess.Broadcast(SoundWave);
    }
}
```

## 字段计算参考

| 字段 | 公式 | 值 | 说明 |
|------|------|----|------|
| BlockAlign | `NumChannels * (BitsPerSample/8)` | 2 | 每样本帧的字节数 |
| ByteRate | `SampleRate * BlockAlign` | 32000 | 每秒字节数 |
| FileSize | `36 + PCMDataSize` | 可变 | RIFF 块大小 |
| dataSize | `PCMDataSize` | 可变 | 音频数据大小 |

## 验证

保存后的 WAV 文件可以用标准音频播放器打开验证：
- 格式：PCM（未压缩）
- 采样率：16000 Hz
- 位深：16 bit
- 声道：单声道
