# TTS 异步节点架构

## 类继承

`UXGSampleTTSAsyncAction` 继承自 `UBlueprintAsyncActionBase`，采用标准异步蓝图节点模式（与第二十七章/二十八章相同）：

```cpp
UCLASS()
class UXGSampleTTSAsyncAction : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()
    // ...
};
```

## 工厂方法

```cpp
static UXGSampleTTSAsyncAction* XGXunFeiTextToSpeech(
    UObject* WorldContextObject,
    FString InAppID,
    FString InAPISecret,
    FString InAPIKey,
    FString InText,
    bool bSaveToLocal,
    FString SaveFileFullPath
);
```

| 参数 | 类型 | 说明 |
|------|------|------|
| InAppID | FString | 讯飞应用 ID |
| InAPISecret | FString | 讯飞 API Secret（用于签名） |
| InAPIKey | FString | 讯飞 API Key |
| InText | FString | 要合成语音的文本 |
| bSaveToLocal | bool | 是否同时保存为 WAV 文件 |
| SaveFileFullPath | FString | WAV 保存路径（需以 .wav 结尾） |

工厂方法调用 `RegisterWithGameInstance` 注册到 GameInstance，防止被 GC 回收：

```cpp
UXGSampleTTSAsyncAction* UXGSampleTTSAsyncAction::XGXunFeiTextToSpeech(
    UObject* WorldContextObject, ...)
{
    UXGSampleTTSAsyncAction* Action = NewObject<UXGSampleTTSAsyncAction>();
    Action->RegisterWithGameInstance(WorldContextObject);
    // 保存参数...
    return Action;
}
```

## 四输出引脚

```cpp
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnSoundWaveSuccess, USoundWave*, SoundWave);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnSoundWaveFail, FString, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWavFileSuccess, FString, SavePath);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWavFileFail, FString, ErrorMessage);

UPROPERTY(BlueprintAssignable)
FOnSoundWaveSuccess OnSoundWaveSuccess;

UPROPERTY(BlueprintAssignable)
FOnSoundWaveFail OnSoundWaveFail;

UPROPERTY(BlueprintAssignable)
FOnWavFileSuccess OnWavFileSuccess;

UPROPERTY(BlueprintAssignable)
FOnWavFileFail OnWavFileFail;
```

四个引脚覆盖两种输出路径的成败：
| 引脚 | 触发时机 |
|------|---------|
| OnSoundWaveSuccess | USoundWave 创建成功 |
| OnSoundWaveFail | USoundWave 创建失败 |
| OnWavFileSuccess | WAV 文件保存成功（含路径） |
| OnWavFileFail | WAV 文件保存失败 |

## Activate 流程

```cpp
void UXGSampleTTSAsyncAction::Activate()
{
    Super::Activate();
    Activate_Internal();
}

void UXGSampleTTSAsyncAction::Activate_Internal()
{
    // 1. 参数校验
    if (bSaveToLocal && !SaveFileFullPath.EndsWith(TEXT(".wav"), ESearchCase::IgnoreCase))
    {
        OnSoundWaveFail.Broadcast(TEXT("文件路径必须以.wav结尾"));
        return;
    }
    if (InText.IsEmpty())
    {
        OnSoundWaveFail.Broadcast(TEXT("文本不能为空"));
        return;
    }

    // 2. 创建 WebSocket 连接
    CreateWebSocket();
}
```

## 生命周期

```
蓝图创建节点
   ↓ RegisterWithGameInstance（防止 GC）
   ↓ Activate → Activate_Internal
       ↓ 参数校验
       ↓ 创建 WebSocket → Connect
           ↓ OnConnected → 发送 JSON
           ↓ OnMessage → 累积音频（可多次）
           ↓ status==2 → 创建 SoundWave + 可选存 WAV
               ↓ 回调蓝图引脚
               ↓ RealeaseResources → SetReadyToDestroy
```

## 资源释放

```cpp
void UXGSampleTTSAsyncAction::RealeaseResources()
{
    if (Socket.IsValid())
    {
        Socket->Close();
        Socket.Reset();
    }
    AllAudioData.Empty();
    OnSoundWaveSuccess.Clear();
    OnSoundWaveFail.Clear();
    OnWavFileSuccess.Clear();
    OnWavFileFail.Clear();
    SetReadyToDestroy();
}
```
