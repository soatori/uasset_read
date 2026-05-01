# 编辑器定制

## ULyraEditorEngine

[ULyraEditorEngine](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.h) 继承自 `UUnrealEdEngine`，负责编辑器环境下的 Lyra 定制。位于 `LyraEditor` 模块。

### FirstTickSetup

在编辑器首次 Tick 时执行的初始化逻辑：

```cpp
void ULyraEditorEngine::FirstTickSetup()
{
    if (bFirstTickSetup)
    {
        return;
    }
    bFirstTickSetup = true;

    // 强制在内容浏览器中显示插件文件夹
    GetMutableDefault<UContentBrowserSettings>()->SetDisplayPluginFolders(true);
}
```

## SPathView 的 bDisplayPluginFolders

### 背景

`SPathView::CreateCompiledFolderFilter()` 是内容浏览器路径视图的筛选器创建方法。

### UE 5.0 vs 5.6 差异

**UE 5.0**：直接从 `ContentBrowserSettings->GetDisplayPluginFolders()` 读取设置。

**UE 5.6**：增加了实例配置覆写逻辑，优先检查 `FContentBrowserInstanceConfig`：

```cpp
bool bDisplayPluginFolders = ContentBrowserSettings->GetDisplayPluginFolders();
if (FContentBrowserInstanceConfig* EditorConfig = GetContentBrowserConfig())
{
    bDisplayPluginFolders = EditorConfig->bShowPluginContent;
}
```

### LyraEditorEngine 的补丁

`FirstTickSetup()` 强制调用 `SetDisplayPluginFolders(true)`，确保项目加载后内容浏览器总是显示插件文件夹。这是一种轻量的编辑器定制方式，在无需重写编辑器模块代码的前提下改变编辑器行为。
