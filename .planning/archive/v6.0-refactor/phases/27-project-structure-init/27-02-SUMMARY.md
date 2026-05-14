# Phase 27-02 Summary

**Plan:** 27-02 - 提取常量和异常到独立模块
**Date:** 2026-05-07
**Status:** Complete

## What was built

### Files Created

1. **src/uasset_read/constants.py** (308 lines)
   - Package文件标签：PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED
   - 版本范围常量：UE5_VERSION_MIN, LEGACY_FILE_VERSION_MIN, LEGACY_FILE_VERSION_MAX
   - 边界验证常量：MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, etc.
   - PropertyTag标志：PROP_TAG_NONE, PROP_TAG_HAS_ARRAY_INDEX, etc.
   - PropertyTag版本阈值：PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012
   - Package Flags：PKG_Cooked, PKG_UnversionedProperties, etc.
   - 蓝图图解析安全常量：MAX_PINS_PER_NODE, MAX_NODES_PER_GRAPH, MAX_LINKEDTO_PER_PIN
   - UE5版本常量（UE5_NAMES_REFERENCED_FROM_EXPORT_DATA等）
   - UE4版本常量（UE4_WORLD_LEVEL_INFO等）
   - CustomVersion GUIDs：FFRAMEWORK_OBJECT_VERSION_GUID, etc.
   - FrameworkObjectVersion阈值：FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE, etc.
   - 调试标志：DEBUG_PIN_PARSING
   - 控制流节点集合：CONTROL_FLOW_NODES（frozenset）
   - 开始事件类型集合：START_EVENT_TYPES（frozenset）
   - 分支类型映射：BRANCH_TYPE_MAP（dict）
   - 输出格式配置：FORMAT_CONFIG（dict）
   - 图类型映射：GRAPH_TYPE_MAP（dict）
   - CLI退出代码：EXIT_SUCCESS, EXIT_PARSE_ERROR, etc.

2. **src/uasset_read/exceptions.py** (42 lines)
   - UAssetError：uasset解析错误基类
   - VersionError：版本不支持错误
   - ErrorContext：dataclass，记录错误发生时的解析状态
   - ParseError：解析错误（可携带部分结果和上下文）

3. **src/uasset_read/__init__.py** (updated)
   - 导出常量模块（from .constants import ...）
   - 导出异常类（from .exceptions import ...）
   - 更新__all__列表，包含常用常量和所有异常类

## Verification

### Automated Checks
```bash
# constants.py验证
test -f src/uasset_read/constants.py  # OK
grep -q "PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012" src/uasset_read/constants.py  # OK
grep -q "PACKAGE_FILE_TAG = 0x9E2A83C1" src/uasset_read/constants.py  # OK
grep -q "CONTROL_FLOW_NODES = frozenset" src/uasset_read/constants.py  # OK

# exceptions.py验证
grep -E "class (UAssetError|VersionError|ErrorContext|ParseError)" src/uasset_read/exceptions.py | wc -l  # 返回4（4个异常类）

# __init__.py验证
test -f src/uasset_read/__init__.py  # OK
grep -q "from \.constants import" src/uasset_read/__init__.py  # OK
grep -q "from \.exceptions import" src/uasset_read/__init__.py  # OK
grep -q "PACKAGE_FILE_TAG" src/uasset_read/__init__.py  # OK
grep -q "UAssetError" src/uasset_read/__init__.py  # OK
```

All verification checks passed.

## Deviations

None.

## Key Decisions

1. **扁平分组**：所有常量在单一文件（constants.py），按功能分组（package标签、版本、边界、PropertyTag等）
2. **从现有代码提取**：保持原有值和注释不变，确保功能性零变更
3. **初始导出**：仅导出常用常量，所有常量可通过`import uasset_read.constants as const`访问
4. **异常类完整保留**：保持原有的异常层次结构和功能（UAssetError → VersionError/ParseError）

## Links to Artifacts

- `src/uasset_read/constants.py`: 常量定义（版本号、阈值、边界常量）
- `src/uasset_read/exceptions.py`: 异常类定义（UAssetError, VersionError, ErrorContext, ParseError）
- `src/uasset_read/__init__.py`: 公共API导出（常量和异常）

## Next Steps

- Phase 28: 核心模块拆分（FArchive、PackageFileSummary、ImportMap/ExportMap）
- Phase 28将导入constants.py和exceptions.py

## Requirements Satisfied

- MOD-02: 常量模块包含所有版本号、属性类型阈值、边界常量
- MOD-03: 异常模块包含所有异常类（UAssetError, VersionError, ParseError, ErrorContext）