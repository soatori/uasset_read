# INI 配置系统与层级关系

## UCLASS(config) 与 UPROPERTY(Config)

除了 DeveloperSettings，普通 UObject/AActor 子类也可以参与 INI 配置系统。通过 `UCLASS(config = Game)` 和 `UPROPERTY(Config)` 标记，属性可以自动从 INI 加载。

```cpp
UCLASS(config = Game)
class AXGINIActor : public AActor
{
    GENERATED_BODY()

    UPROPERTY(Config)
    int32 MyConfigVariable;
};
```

| 标记 | 说明 |
|------|------|
| `UCLASS(config = Game)` | 指定此类的配置存储到 Game.ini 中 |
| `UPROPERTY(Config)` | 标记此属性参与自动加载/保存 |

引擎启动时自动从 `DefaultGame.ini` 读取 `MyConfigVariable` 的值并赋给 CDO。

## INI 文件层级

UE 的 INI 配置系统由多层文件组成，**高层覆盖低层**的同名属性：

```
层级 1: Engine/Base.ini            ← 引擎基准配置
层级 2: Engine/Platform/Base.ini   ← 引擎平台配置
层级 3: Project/Default.ini        ← 项目默认配置
层级 4: Project/Platform.ini       ← 项目平台配置
层级 5: Saved/User.ini             ← 用户本地配置（运行时写入）
层级 6: Packaged INI               ← 打包后的固化配置
```

### 层级合并规则

以 `MyConfigVariable` 为例：

1. UE 启动时从层 1 读到层 6，逐层加载
2. 同一个属性在多个层级中出现时，**高层的值覆盖低层的值**
3. 如果用户在 Saved/User.ini 中修改了值，这个值会覆盖 Default 中的值
4. 打包时，INI 文件被冻结到打包产物中

### config = Game 对应的文件

`UCLASS(config = Game)` 对应的 INI 文件为：

- **默认配置**：`Config/DefaultGame.ini`
- **平台覆盖**：`Config/Windows/WindowsGame.ini`（Windows 平台）
- **用户本地**：`Saved/Config/Windows/Game.ini`（Windows 平台运行时）

## 代码中的路径常量

| 全局变量/宏 | 对应路径 | 说明 |
|-------------|---------|------|
| `GGameIni` | `Game.ini`（自动选择当前层） | 最常用的 INI 文件句柄 |
| `GEngineIni` | `Engine.ini` | 引擎配置 |
| `GEditorIni` | `Editor.ini` | 编辑器配置 |
| `FPaths::SourceConfigDir()` | `Project/Config/` | 默认配置目录（Source 层级） |

## 在 BeginPlay 中读取自动加载的变量

```cpp
void AXGINIActor::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Warning, TEXT("MyConfigVariable: %d"), MyConfigVariable);
}
```

引擎在 CDO 创建时已经完成 INI 值的加载，因此 `BeginPlay` 中可以直接读取 `MyConfigVariable`，此时它已经包含了 INI 中的值。

## 配套代码

- [XGINIActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGINIActor.h) — UCLASS(config = Game) 与 UPROPERTY(Config) 声明
- [XGINIActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGINIActor.cpp) — BeginPlay 中读取自动加载的变量
