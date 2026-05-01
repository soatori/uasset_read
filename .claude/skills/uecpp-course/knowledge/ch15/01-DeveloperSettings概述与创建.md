# DeveloperSettings 概述与创建

## 什么是 DeveloperSettings

DeveloperSettings 是 UE 提供的一种**可在 Project Settings UI 中直接编辑的配置类**。继承 `UDeveloperSettings` 并配合 `UPROPERTY(Config)` 标记的属性，会自动在 Project Settings > 对应分类中生成可视化编辑界面，修改后自动持久化到 INI 文件。

典型用途：存储项目级全局配置（AppKey、版本号、功能开关等），让策划和配置人员无需接触代码即可调整参数。

## 创建 DeveloperSettings 子类

### 头文件声明

```cpp
#pragma once
#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "XGSampleSettings.generated.h"

UCLASS(Config = XGSampleSettings, defaultconfig)
class XGSAMPLEDEMO_API UXGSampleSettings : public UDeveloperSettings
{
    GENERATED_BODY()

public:
    UXGSampleSettings(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
    virtual ~UXGSampleSettings();

public:
    virtual FName GetContainerName() const;
    virtual FName GetCategoryName() const;
    virtual FName GetSectionName() const;

public:
    static UXGSampleSettings* GetXGXunFeiCoreSettings();

public:
    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "XG")
    FString ProjectSimpleName;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "XG")
    FString XGAppID;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category = "XG")
    FString XGAppKey;
};
```

### UCLASS 关键参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `Config = XGSampleSettings` | 指定此类配置存储的 INI 段名 | 生成 `DefaultXGSampleSettings.ini`，段头为 `[/Script/XGSampleDemo.XGSampleSettings]` |
| `defaultconfig` | 标记为默认配置类 | 配置写入 Default 层级的 INI 文件 |

### UPROPERTY(Config)

标记 `Config` 的属性会被引擎自动加载和保存。配置变更时，引擎自动将属性值写入对应的 INI 文件。

### 三个覆盖方法——控制 UI 分类层级

```cpp
FName UXGSampleSettings::GetContainerName() const
{
    return TEXT("Project");  // 容器：Project / Editor / Engine
}

FName UXGSampleSettings::GetCategoryName() const
{
    return TEXT("XG");       // 分类名：Project Settings 左侧导航栏的分类
}

FName UXGSampleSettings::GetSectionName() const
{
    return TEXT("XGSampleSettings");  // 节名：分类下的具体节
}
```

| 方法 | 作用 | 常见值 |
|------|------|--------|
| `GetContainerName()` | 顶层容器 | `Project`、`Editor`、`Engine` |
| `GetCategoryName()` | 侧边栏分类名 | `Game`、`Plugins`、`XG` 等 |
| `GetSectionName()` | 节名，默认返回类名 | 自定义节名 |

### 配套结构体

DeveloperSettings 的属性可以嵌套结构体：

```cpp
USTRUCT(BlueprintType)
struct FXGSampleDescriber
{
    GENERATED_USTRUCT_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "XGProjectInfo")
    FString AuthorName = TEXT("XG");

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "XGProjectInfo")
    bool bExperiment = false;
};
```

然后在 Settings 类中直接声明为属性：

```cpp
UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "XG")
FXGSampleDescriber SampleDescriber;
```

### 构造函数与析构函数

```cpp
UXGSampleSettings::UXGSampleSettings(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
}

UXGSampleSettings::~UXGSampleSettings()
{
}
```

构造函数通常用于为属性设置默认值，也可在头文件属性声明处直接初始化。

## 使用效果

创建完成后，在 Project Settings 界面中：

1. 侧边栏出现 "XG" 分类（由 `GetCategoryName()` 决定）
2. "XG" 分类下出现 "XGSampleSettings" 节（由 `GetSectionName()` 决定）
3. 标签内显示所有 `EditAnywhere` 的 Config 属性
4. 修改后自动保存到 `Config/DefaultXGSampleSettings.ini`

## 配套代码

- [XGSampleSettings.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGSampleSettings.h) — DeveloperSettings 子类完整声明
- [XGSampleSettings.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/018_Config/XGSampleSettings.cpp) — GetContainerName/GetCategoryName/GetSectionName 实现
