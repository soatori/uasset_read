# Phase 30: 属性解析模块 - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

## Phase Boundary

从旧版 `uasset_read.py` 中提取所有属性解析逻辑到独立的 `parsers/` 模块。覆盖范围：
- `read_property_tag()` (第 5186-5282 行) — PropertyTag 结构读取
- 14 种 `parse_*_property()` 函数 (第 5289-6004 行) — 属性值解析器
- `parse_properties_from_export()` (第 6007-6158 行) — 属性循环读取
- 蓝图变量提取逻辑 — 独立 `blueprint/` 模块

依赖：Phase 29b (PropertyTag/PropertyValue dataclass 定义)。

## Implementation Decisions

### 模块组织

- **D-01 (目录结构):** `parsers/` 目录包含属性解析相关模块：
  - `parsers/property_parser.py` — read_property_tag + parse_property_value 分派逻辑
  - `parsers/property_types.py` — 14 种 parse_*_property 具体实现
  - `blueprint/` 目录（独立）— 蓝图变量提取逻辑
- **D-02 (蓝图归属):** 蓝图变量提取放在独立 `blueprint/` 模块，因为 Phase 31 图解析也可能用到。与属性解析器同级但独立。
- **D-03 (扁平导入):** 所有解析器通过 `parsers/__init__.py` 统一导出，调用者使用 `from uasset_read.parsers import parse_property_value` 等。

### 分派策略

- **D-04 (类型分派表):** 保持现有 `type_dispatch` 字典模式，通过 `tag.type` 字符串分派到对应解析函数。简单直观，易扩展。
- **D-05 (未知类型处理):** 未知类型返回 None（D-26 跳过策略），不抛出异常。

### 循环导入处理

- **D-06 (类型注解):** 使用 `TYPE_CHECKING` + `'ModelName'` 字符串类型注解，避免运行时循环导入。现有项目已采用此模式。
- **D-07 (依赖方向):** parsers → models（单向），models 的 `from_archive` 方法使用延迟导入或字符串注解引用 parsers 类型。

### 序列化策略

- **D-08 (参数传递):** parse_property_value 保持现有签名：`(tag, archive, name_map, export_map, summary=None, depth=0)`，支持递归深度控制。
- **D-09 (版本检查):** read_property_tag 使用 `use_complete_type_name(legacy_version, ue5_version)` 判断 UE4/UE5 格式。

### Claude's Discretion

- 具体模块内部函数组织方式由规划阶段确定
- 蓝图变量提取的精确边界（哪些函数归属 blueprint/）由规划阶段确定
- 是否需要 PropertyParser 类封装或保持函数式风格由规划阶段确定

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 旧版源码参考

- `uasset_read.py` §5186-5282 — read_property_tag() 完整实现
- `uasset_read.py` §5289-5304 — parse_bool_property()
- `uasset_read.py` §5306-5332 — parse_int_property()
- `uasset_read.py` §5334-5354 — parse_float_property()
- `uasset_read.py` §5356-5370 — parse_str_property()
- `uasset_read.py` §5372-5387 — parse_name_property()
- `uasset_read.py` §5389-5406 — parse_object_property()
- `uasset_read.py` §5408-5439 — parse_soft_object_property()
- `uasset_read.py` §5441-5645 — parse_array_property()
- `uasset_read.py` §5647-5725 — parse_struct_property()
- `uasset_read.py` §5727-5842 — parse_map_property()
- `uasset_read.py` §5844-5888 — parse_set_property()
- `uasset_read.py` §5890-5929 — parse_enum_property()
- `uasset_read.py` §5931-5968 — parse_text_property()
- `uasset_read.py` §5970-6004 — parse_delegate_property()
- `uasset_read.py` §6007-6158 — parse_properties_from_export()
- `uasset_read.py` §6161-6220 — parse_property_value() 分派逻辑

### UE 源码参考

- `PropertyTag.cpp` — PropertyTag 序列化格式
- `PropertyTypeName.cpp` — FPropertyTypeName 格式

### 现有模块模式

- `src/uasset_read/archive.py` — FArchive 读取接口
- `src/uasset_read/constants.py` — PROPERTY_TAG_COMPLETE_TYPE_NAME 等常量
- `src/uasset_read/exceptions.py` — ParseError, UAssetError
- `src/uasset_read/serializers/` — 已建立的 dataclass + from_archive 模式

### 需求与范围

- `.planning/ROADMAP.md` §Phase 30 — Phase 30 目标、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — MOD-06, MOD-07, MOD-09, TEST-01 需求定义

## Existing Code Insights

### Reusable Assets

- **FArchive (archive.py):** read_u32/read_i32/read_u8/read_fstring/read_bytes/read_guid 等方法可直接用于属性解析
- **PropertyTag dataclass:** Phase 29b 将定义，本阶段消费
- **常量模块 (constants.py):** PROPERTY_TAG_COMPLETE_TYPE_NAME=1012 阈值

### Established Patterns

- **函数式解析:** 现有 serializers 采用独立函数 + dataclass 模式，parsers 保持一致
- **类型分派字典:** 旧版 type_dispatch 模式成熟稳定，直接迁移
- **分层架构依赖方向:** Output → Models → Parsers → Serializers → FArchive，单向依赖
- **零运行时依赖:** pyproject.toml 中 `dependencies = []`

### Integration Points

- **parsers/__init__.py 需要更新:** 新增所有解析器函数的导出
- **Phase 29b 依赖:** PropertyTag dataclass 必须先定义，parsers 消费它
- **Phase 31 依赖:** 蓝图图解析依赖属性解析结果
- **测试适配:** 现有测试中使用属性解析的地方需要更新导入路径

## Specific Ideas

无特定要求 — 采用上述讨论的架构设计。

## Deferred Ideas

- UberGraph/事件分发图增强 — 属于 Phase 31 或 Phase 42
- 自定义节点类型处理器 — 游戏特定，超出范围
- JSON Schema 验证 — 属于 v9.0

---

*Phase: 30-属性解析模块*
*Context gathered: 2026-05-11*
