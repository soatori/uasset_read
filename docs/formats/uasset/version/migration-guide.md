# 版本迁移指南

## 概述

版本迁移指南帮助开发者理解 UE4/UE5 资产版本变更，处理跨版本资产加载问题。本文档覆盖常见迁移问题、各资产类型迁移注意事项和版本检测逻辑。

## 版本枚举体系

### EUnrealEngineObjectUE5Version

UE5 版本枚举，从 `INITIAL_VERSION = 1000` 开始，与 UE4 版本号分离。

| 版本号 | 枚举名 | 新增内容 |
|--------|--------|----------|
| 1000 | INITIAL_VERSION | UE5 初始版本 |
| 1001 | NAMES_REFERENCED_FROM_EXPORT_DATA | Export 数据引用的名称排序优化 |
| 1002 | PAYLOAD_TOC | Payload TOC 支持 |
| 1003 | OPTIONAL_RESOURCES | 可选资源支持 |
| 1004 | LARGE_WORLD_COORDINATES | 大世界坐标支持 |
| 1005 | REMOVE_OBJECT_EXPORT_PACKAGE_GUID | 移除 ObjectExport 包 GUID |
| 1006 | TRACK_OBJECT_EXPORT_IS_INHERITED | 跟踪 ObjectExport 继承关系 |
| 1007 | FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES | FSoftObjectPath 资产路径 FName 移除 |
| 1008 | ADD_SOFTOBJECTPATH_LIST | 软对象路径列表 |
| 1009 | DATA_RESOURCES | 数据资源表 |
| 1010 | SCRIPT_SERIALIZATION_OFFSET | 脚本序列化偏移 |
| 1011 | PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | PropertyTag 扩展 |
| 1012 | PROPERTY_TAG_COMPLETE_TYPE_NAME | PropertyTag 完整类型名 |
| 1013 | ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES | 资产注册表包构建依赖 |
| 1014 | METADATA_SERIALIZATION_OFFSET | 元数据序列化偏移 |
| 1015 | VERSE_CELLS | Verse Cell 支持 |
| 1016 | PACKAGE_SAVED_HASH | 包保存哈希（FGuid → FIoHash） |
| 1017 | OS_SUB_OBJECT_SHADOW_SERIALIZATION | OS 子对象阴影序列化 |
| 1018 | IMPORT_TYPE_HIERARCHIES | 导入类型层级 |

## 迁移注意事项

### UE4 → UE5 迁移

1. **版本号分离**: UE5.0 起 FileVersionUE 从单一 int32 拆分为 FileVersionUE4 + FileVersionUE5
2. **名称引用优化**: NAMES_REFERENCED_FROM_EXPORT_DATA (1001) 改变了名称表的组织方式
3. **64 位导出表**: SerialSize/SerialOffset 在 UE4.26+ 升级为 64 位
4. **SoftObjectPath 变更**: FSoftObjectPath 序列化格式在 UE5 中有变更

### 资产类型特定迁移

#### 蓝图资产

- 检查 Blueprint 变量序列化格式变更
- 注意 Graph/Node/Pin 结构在不同版本中的差异
- 验证 Transform 和 Component 数据兼容性

#### 网格资产

- 静态网格索引缓冲从 16 位升级到 32 位（版本 235）
- 骨骼网格蒙皮影响数量变更（版本 263/265）
- 导航碰撞数据序列化方式变更

#### 材质资产

- 材质属性重排序（版本 219）
- 纹理坐标数量增加（版本 225）

## 版本检测逻辑

### 加载器版本检查

```cpp
// 检查包是否可加载
bool IsLoadable(int32 packageVersion) {
    return packageVersion >= VER_UE4_OLDEST_LOADABLE_PACKAGE;
}

// 确定序列化格式
ESerializationFormat DetermineFormat(int32 legacyFileVersion) {
    if (legacyFileVersion <= -8) return UE5_Format;
    if (legacyFileVersion <= -2) return UE4_CustomVersion;
    return UE4_Legacy;
}
```

## 源码引用

- `Runtime/Core/Public/UObject/ObjectVersion.h` — 版本枚举定义
- `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` — 加载器版本检查逻辑
