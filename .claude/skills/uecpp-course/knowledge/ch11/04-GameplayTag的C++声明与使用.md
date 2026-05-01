# GameplayTag 的 C++ 声明与使用

## 模块依赖配置

在 `Build.cs` 中添加模块依赖：

```cpp
PublicDependencyModuleNames.AddRange(new string[] {
    "GameplayTags"
});
```

## 头文件包含

```cpp
#include "NativeGameplayTags.h"
#include "GameplayTagsManager.h"
```

## 声明模式

采用与 `UE_LOG` 分类声明一致的**头文件声明 + 实现文件定义**模式。

### 模块级可见（推荐）

适用于跨模块访问的标签。

头文件（`.h`）：

```cpp
// XGTagType.h
#include "NativeGameplayTags.h"

UE_DECLARE_GAMEPLAY_TAG_EXTERN(XG_Mode_Coding);
UE_DECLARE_GAMEPLAY_TAG_EXTERN(XG_Mode_Working);
```

实现文件（`.cpp`）：

```cpp
// XGTagType.cpp
#include "XGTagType.h"

UE_DEFINE_GAMEPLAY_TAG_COMMENT(XG_Mode_Coding, "XG.Mode.Coding", "Coding tag");
UE_DEFINE_GAMEPLAY_TAG_COMMENT(XG_Mode_Working, "XG.Mode.Working", "Working tag");
```

### 文件级可见

适用于仅在单个文件中使用的标签。

```cpp
// XGTagActor.cpp
UE_DEFINE_GAMEPLAY_TAG_STATIC(XG_Mode_Idle, "XG.Mode.Idle");
UE_DEFINE_GAMEPLAY_TAG_STATIC(XX_Mode_Idle, "XX.Mode.Idle");
```

### 宏对照表

| 宏 | 作用范围 | 位置 |
|---|---------|------|
| `UE_DECLARE_GAMEPLAY_TAG_EXTERN` | 模块级（声明） | `.h` |
| `UE_DEFINE_GAMEPLAY_TAG` | 模块级（定义） | `.cpp` |
| `UE_DEFINE_GAMEPLAY_TAG_COMMENT` | 模块级（带注释） | `.cpp` |
| `UE_DEFINE_GAMEPLAY_TAG_STATIC` | 文件级 | `.cpp` |

## 运行时获取 Tag

```cpp
// 通过字符串查找已注册的 Tag（运行时）
FGameplayTag Tag = FGameplayTag::RequestGameplayTag(TEXT("XG"));

// 使用静态定义的宏变量（编译期）
FGameplayTag Tag = XX_Mode_Idle;
```

## 代码示例对应

课程代码位于 [XGTagType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagType.h) 和 [XGTagType.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagType.cpp)，演示了完整的声明模式：

- 头文件：使用 `UE_DECLARE_GAMEPLAY_TAG_EXTERN` 声明 `XG_Mode_Coding` 和 `XG_Mode_Working`
- 实现文件：使用 `UE_DEFINE_GAMEPLAY_TAG_COMMENT` 定义带注释的标签
