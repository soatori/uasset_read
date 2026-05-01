# AsyncMixin 异步加载

## 架构概览

AsyncMixin 是一个不依赖 UObject 的开销极低的异步资源加载工具，允许以链式方式编排异步加载序列，支持预加载 PrimaryAsset、自定义条件和事件。

核心文件：AsyncMixin 插件源码

## FAsyncMixin

```cpp
class FAsyncMixin : public FNoncopyable
{
public:
    // 加载单个软引用
    template <typename T = UObject>
    void AsyncLoad(TSoftClassPtr<T> SoftClass, TFunction<void()>&& Callback);

    // 加载多个资源
    void AsyncLoad(const TArray<FSoftObjectPath>& SoftObjectPaths,
                   const FSimpleDelegate& Callback = FSimpleDelegate());

    // 预加载 PrimaryAsset
    void AsyncPreloadPrimaryAssetsAndBundles(
        const TArray<FPrimaryAssetId>& AssetIds,
        const TArray<FName>& LoadBundles,
        const FSimpleDelegate& Callback = FSimpleDelegate());

    // 自定义条件
    void AsyncCondition(TSharedRef<FAsyncCondition> Condition,
                        const FSimpleDelegate& Callback = FSimpleDelegate());

    // 占位事件
    void AsyncEvent(const FSimpleDelegate& Callback);

    // 生命周期
    void StartAsyncLoading();
    void CancelAsyncLoading();
    bool IsAsyncLoadingInProgress() const;

    // 虚回调
    virtual void OnStartedLoading() {}
    virtual void OnFinishedLoading() {}
};
```

### 设计要点

- `FNoncopyable` — 禁止拷贝，每个 Mixin 唯一持有
- 零内存开销 — 只有调用 `AsyncLoad` 后才分配状态
- 使用静态 `TMap<FAsyncMixin*, TSharedRef<FLoadingState>>` 管理所有加载状态

## 加载状态 FLoadingState

```cpp
class FLoadingState : public TSharedFromThis<FLoadingState>
{
    TArray<TUniquePtr<FAsyncStep>> AsyncSteps;
    int32 CurrentAsyncStep = 0;

    void Start();
    void TryCompleteAsyncLoading();
    void CompleteAsyncLoading();
    void RequestDestroyThisMemory();  // ticker 延迟销毁
};
```

- 维护步骤队列
- 串行执行，完成一个步骤后自动进入下一个
- 所有步骤完成后调用 `OnFinishedLoading` → 通过 ticker 延迟清理内存

## 加载步骤 FAsyncStep

```cpp
class FAsyncStep
{
    FSimpleDelegate UserCallback;
    TSharedPtr<FStreamableHandle> StreamingHandle;
    TSharedPtr<FAsyncCondition> Condition;

    bool IsComplete() const;
    void ExecuteUserCallback();
    bool BindCompleteDelegate(const FSimpleDelegate&);  // 重入保护
};
```

- 每个 `AsyncLoad` / `AsyncCondition` 调用生成一个步骤
- 支持 `StreamingHandle`（资源加载完成）和 `Condition`（自定义条件）两种完成方式
- `BindCompleteDelegate` 防止重复注册完成回调

## FAsyncCondition

```cpp
class FAsyncCondition : public TSharedFromThis<FAsyncCondition>
{
    FTSTicker::FDelegateHandle RepeatHandle;
    FAsyncConditionDelegate UserCondition;
    FSimpleDelegate CompletionDelegate;

    bool TryToContinue(float);  // ticker 轮询
};
```

- 通过 ticker 轮询完成状态（每 0.16 秒）
- 返回 `TryAgain` 继续轮询，返回 `Complete` 触发下一步

```cpp
enum class EAsyncConditionResult : uint8
{
    TryAgain,
    Complete
};
```

## 异步序列执行流程

1. 调用 `AsyncLoad` / `AsyncCondition` / `AsyncEvent` 将步骤加入队列
2. 调用 `StartAsyncLoading()` 启动加载
3. `FLoadingState` 从 `CurrentAsyncStep = 0` 开始
4. 当前步骤的 `IsComplete()` 检查完成状态
5. 完成后执行 `UserCallback`，`CurrentAsyncStep++`
6. 进入下一步骤
7. 所有步骤完成后调用 `OnFinishedLoading`
8. `RequestDestroyThisMemory` 安排 ticker 延迟销毁加载状态

## FAsyncScope

```cpp
class FAsyncScope : public FAsyncMixin {};
```

- 独立封装，不依赖继承
- 适合非 Mixin 场景的直接使用
