---
title: 常量与配置
section: constants
---

# Constants 常量与配置

**模块路径**: `src/uasset_read/constants.py`

> 定义所有版本号、属性类型阈值、边界验证常量、PropertyTag 标志位、CPF 标志位等。从 UE 源码迁移而来，禁止猜测二进制行为。

## 包文件魔术标签

| 常量 | 值 | 说明 |
|------|-----|------|
| `PACKAGE_FILE_TAG` | `0x9E2A83C1` | UE 包文件魔术标签（正确字节序） |
| `PACKAGE_FILE_TAG_SWAPPED` | `0xC1832A9E` | UE 包文件魔术标签（交换字节序） |

## 边界验证常量

防御性编程常量，用于防止恶意或损坏文件导致的无限循环/内存耗尽。

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_NAME_COUNT` | 10,000,000 | 名称表最大条目数 |
| `MAX_IMPORT_COUNT` | 1,000,000 | 导入表最大条目数 |
| `MAX_EXPORT_COUNT` | 1,000,000 | 导出表最大条目数 |
| `MAX_CUSTOM_VERSIONS` | 10,000 | 自定义版本最大条目数 |
| `MMAP_THRESHOLD` | 50 MB | 启用 mmap 的文件大小阈值 |
| `MAX_PROPERTY_COUNT` | 10,000 | 属性循环上限 |
| `MAX_ARRAY_COUNT` | 1,000,000 | 数组元素上限 |
| `MAX_FSTRING_LENGTH` | 10 MB | FString 最大长度（UTF-8/UTF-16） |
| `MAX_PINS_PER_NODE` | 1,000 | 单节点最大引脚数 |
| `MAX_NODES_PER_GRAPH` | 5,000 | 单图最大节点数 |
| `MAX_LINKEDTO_PER_PIN` | 100 | 单引脚最大连接数 |
| `MAX_TYPENODE_NODES` | 20 | FPropertyTypeName 最大节点数 |

## PropertyTag 标志位

| 标志 | 值 | 说明 |
|------|-----|------|
| `PROP_TAG_NONE` | `0x00` | 无标志 |
| `PROP_TAG_HAS_ARRAY_INDEX` | `0x01` | 有数组索引 |
| `PROP_TAG_HAS_PROPERTY_GUID` | `0x02` | 有属性 GUID |
| `PROP_TAG_HAS_EXTENSIONS` | `0x04` | 扩展数据 |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | `0x08` | 二进制/本地化序列化 |
| `PROP_TAG_BOOL_TRUE` | `0x10` | 布尔值为真 |
| `PROP_TAG_SKIPPED_SERIALIZE` | `0x20` | 跳过序列化 |

## PropertyTag 版本阈值

| 常量 | 值 | 说明 |
|------|-----|------|
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | UE5 格式切换阈值 |

## UE5 版本常量

对应 `EUnrealEngineObjectUE5Version`。

| 常量 | 值 | 说明 |
|------|-----|------|
| `UE5_VERSION_MIN` | 0 | UE5 版本最低值 |
| `UE5_LEGACY_VERSION` | -9 | UE5.6+ 文件的 LegacyFileVersion 固定值 |
| `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` | 1001 | 导出数据引用名称 |
| `UE5_PAYLOAD_TOC` | 1002 | 载荷目录表 |
| `UE5_OPTIONAL_RESOURCES` | 1003 | 可选资源 |
| `UE5_LARGE_WORLD_COORDINATES` | 1004 | 大世界坐标（LWC） |
| `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` | 1005 | 移除对象导出包 GUID |
| `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` | 1006 | 追踪对象导出继承 |
| `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` | 1007 | 移除资产路径 FName |
| `UE5_ADD_SOFTOBJECTPATH_LIST` | 1008 | 添加软对象路径列表 |
| `UE5_DATA_RESOURCES` | 1009 | 数据资源 |
| `UE5_SCRIPT_SERIALIZATION_OFFSET` | 1010 | 脚本序列化偏移 |
| `UE5_PROPERTY_TAG_EXTENSION` | 1011 | PropertyTag 扩展 |
| `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | 完整类型名称（别名） |
| `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` | 1013 | 资产注册表包构建依赖 |
| `UE5_METADATA_SERIALIZATION_OFFSET` | 1014 | 元数据序列化偏移 |
| `UE5_VERSE_CELLS` | 1015 | Verse 单元格 |
| `UE5_PACKAGE_SAVED_HASH` | 1016 | 包保存哈希 |
| `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` | 1017 | 子对象阴影序列化 |
| `UE5_IMPORT_TYPE_HIERARCHIES` | 1018 | 导入类型层次 |

## UE4 版本常量

对应 `EUnrealEngineObjectUE4Version`。

| 常量 | 值 | 说明 |
|------|-----|------|
| `UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID` | 516 | 添加包摘要本地化 ID |
| `UE4_ADD_STRING_ASSET_REFERENCES_MAP` | 516 | 添加字符串资产引用映射 |
| `UE4_SERIALIZE_TEXT_IN_PACKAGES` | 517 | 包中序列化文本 |
| `UE4_ADDED_SEARCHABLE_NAMES` | 518 | 添加可搜索名称 |
| `UE4_ADDED_PACKAGE_OWNER` | 519 | 添加包所有者 |
| `UE4_NON_OUTER_PACKAGE_IMPORT` | 520 | 非外部包导入 |

## CustomVersion GUIDs

| GUID | 名称 |
|------|------|
| `CFFC743F-43B04480-939114DF-171D2073` | `FFRAMEWORK_OBJECT_VERSION_GUID` |
| `697DD581-E64F41AB-AA4A51EC-BEB7B628` | `FUE5_MAINSTREAM_VERSION_GUID` |
| `9C54D522-A8264FBE-94210746-61B482D0` | `FRELEASE_OBJECT_VERSION_GUID` |
| `D89B5E42-24BD4D46-8412ACA8-DF641779` | `FUE5RELEASESTREAM_OBJECT_VERSION_GUID` |
| `B0D832E4-1F89-4D06-B39A-8F1B5E1B2A4B` | `FBLUEPRINTS_OBJECT_VERSION_GUID` |
| `371EC2EE-4CD7-4C38-AEB1-B7D6F539A54B` | `FCORE_OBJECT_VERSION_GUID` |
| `E4B068ED-F494-42E9-A231-DA0B0E4C5E56` | `FEDITOR_OBJECT_VERSION_GUID` |
| `29E575DD-E0A3-4682-9C20-D1CF1B5E8DEF` | `FANIM_OBJECT_VERSION_GUID` |
| `78F01B33-BEA0-46A0-8BAF-6C4F4E23F8C1` | `FPHYSICS_OBJECT_VERSION_GUID` |
| `645F75DB-7F54-4C64-A1E2-2F6F3B4B8A5E` | `FRENDERING_OBJECT_VERSION_GUID` |

## 子系统版本阈值

### FrameworkObjectVersion

| 常量 | 值 | 说明 |
|------|-----|------|
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | 15 | 图引脚容器类型 |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | 19 | 引脚存储 FName |

### FUE5MainStreamObjectVersion

| 常量 | 值 | 说明 |
|------|-----|------|
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | 50 | 图引脚源索引 |

### FReleaseObjectVersion

| 常量 | 值 | 说明 |
|------|-----|------|
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | 10 | 引脚类型 UObject 包装器 |

### FUE5ReleaseStreamObjectVersion

| 常量 | 值 | 说明 |
|------|-----|------|
| `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION` | 36 | 浮点引脚默认单精度序列化 |

## Package 标志位

| 常量 | 值 | 说明 |
|------|-----|------|
| `PKG_Cooked` | `0x200` | 包已烘焙 |
| `PKG_UnversionedProperties` | `0x2000` | 使用无版本属性序列化 |
| `PKG_FilterEditorOnly` | `0x80000000` | 过滤编辑器专属对象 |

## CPF_* 属性标志位

Class Property Flags，用于属性元数据。

| 常量 | 值（十六进制） | 说明 |
|------|---------------|------|
| `CPF_Edit` | `0x0000000000000001` | 可编辑 |
| `CPF_ConstParm` | `0x0000000000000002` | 常量参数 |
| `CPF_BlueprintVisible` | `0x0000000000000004` | 蓝图可见 |
| `CPF_ExportObject` | `0x0000000000000008` | 可导出对象 |
| `CPF_BlueprintReadOnly` | `0x0000000000000010` | 蓝图只读 |
| `CPF_BlueprintAuthorityOnly` | `0x0000000000000020` | 仅蓝图授权 |
| `CPF_EditFixedSize` | `0x0000000000000040` | 编辑固定大小 |
| `CPF_Parm` | `0x0000000000000080` | 参数 |
| `CPF_OutParm` | `0x0000000000000100` | 输出参数 |
| `CPF_ZeroConstructor` | `0x0000000000000200` | 零构造函数 |
| `CPF_ReturnParm` | `0x0000000000000400` | 返回参数 |
| `CPF_Net` | `0x0000000000000800` | 网络复制 |
| `CPF_EditAnywhere` | `0x0000000000001000` | 任意位置编辑 |
| `CPF_Transient` | `0x0000000000002000` | 临时 |
| `CPF_Config` | `0x0000000000004000` | 配置 |
| `CPF_DisableEditOnTemplate` | `0x0000000000008000` | 模板上禁用编辑 |
| `CPF_BlueprintReadWrite` | `0x0000000000010000` | 蓝图可读写 |
| `CPF_DuplicateTransient` | `0x0000000000020000` | 复制临时 |
| `CPF_NonPIEDuplicateTransient` | `0x0000000000040000` | 非 PIE 复制临时 |
| `CPF_EditConst` | `0x0000000000080000` | 编辑常量 |
| `CPF_NoClear` | `0x0000000000200000` | 不可清除 |
| `CPF_ReferencePersisted` | `0x0000000000400000` | 引用持久化 |
| `CPF_SaveGame` | `0x0000000001000000` | 存档游戏 |
| `CPF_BlueprintAssignable` | `0x0000000002000000` | 蓝图可分配 |
| `CPF_BlueprintCallable` | `0x0000000004000000` | 蓝图可调用 |
| `CPF_BlueprintPure` | `0x0000000008000000` | 蓝图纯函数 |
| `CPF_BlueprintCompilerGenerated` | `0x0000000010000000` | 蓝图编译器生成 |
| `CPF_NetSerialize` | `0x0000000020000000` | 网络序列化 |
| `CPF_RepNotify` | `0x0000000040000000` | 复制通知 |
| `CPF_RepRetry` | `0x0000000080000000` | 复制重试 |
| `CPF_Interp` | `0x0000000100000000` | 插值 |
| `CPF_Constructed` | `0x0000000200000000` | 已构造 |
| `CPF_Protected` | `0x0000000400000000` | 受保护 |
| `CPF_AdvancedDisplay` | `0x0000000800000000` | 高级显示 |
| `CPF_AssetRegistrySearchable` | `0x0000001000000000` | 资产注册表可搜索 |
| `CPF_ContainsInstancedReference` | `0x0000002000000000` | 包含实例引用 |
| `CPF_Deprecated` | `0x0000004000000000` | 已弃用 |
| `CPF_IsPlainOldData` | `0x0000008000000000` | 简单数据类型 |
| `CPF_NoDestructor` | `0x0000010000000000` | 无析构函数 |
| `CPF_HasGetValueTypeHash` | `0x0000020000000000` | 有 GetValue Hash |
| `CPF_NativeAccessSpecifierPublic` | `0x0000040000000000` | 原生公开访问 |
| `CPF_NativeAccessSpecifierProtected` | `0x0000080000000000` | 原生受保护访问 |
| `CPF_NativeAccessSpecifierPrivate` | `0x0000100000000000` | 原生私有访问 |
| `CPF_SkipSerialization` | `0x0000200000000000` | 跳过序列化 |
| `CPF_TextExportTransient` | `0x0000400000000000` | 文本导出临时 |
| `CPF_NonTransactional` | `0x0000800000000000` | 非事务性 |
| `CPF_Required` | `0x0001000000000000` | 必需 |
| `CPF_ExposeOnSpawn` | `0x0002000000000000` | 生成时暴露 |
| `CPF_PersistentInstance` | `0x0004000000000000` | 持久实例 |
| `CPF_TObjectPtr` | `0x0008000000000000` | TObjectPtr |
| `CPF_UObjectWrapper` | `0x0010000000000000` | UObject 包装器 |
| `CPF_NaturalizePropertyIndex` | `0x0020000000000000` | 自然化属性索引 |
| `CPF_InstancedReference` | `0x0040000000000000` | 实例引用 |

### CPF 别名

| 别名 | 映射到 | 说明 |
|------|--------|------|
| `CPF_EditInstanceOnly` | `CPF_EditAnywhere` | 仅实例编辑（旧 API） |
| `CPF_ReferenceOnly` | `CPF_ReferencePersisted` | 仅引用（旧 API） |
| `CPF_Replicated` | `CPF_Net` | 已复制（旧 API） |

## 蓝图图解析集合

### 控制流节点

```python
CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
})
```

### 开始事件类型

```python
START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent",
    "K2Node_FunctionEntry",
})
```

### 数据流边界节点

```python
DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",
    "K2Node_VariableSet",
})
```

## 映射与配置

### EnhancedInput TriggerEvent 引脚映射

```python
ETRIGGER_EVENT_PIN_MAP = {
    "Started": "Started",
    "Triggered": "Ongoing",
    "Completed": "Completed",
    "Exited": "Exited",
}
```

### 分支类型映射

```python
BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
}
```

### 图类型映射

```python
GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}
```

### 输出格式配置

```python
FORMAT_CONFIG = {
    "pin_reference_mode": "name",
}
```

## CLI 退出代码

| 常量 | 值 | 说明 |
|------|-----|------|
| `EXIT_SUCCESS` | 0 | 成功 |
| `EXIT_PARSE_ERROR` | 1 | 解析错误 |
| `EXIT_FILE_NOT_FOUND` | 2 | 文件未找到 |
| `EXIT_ARGUMENT_ERROR` | 3 | 参数错误 |
