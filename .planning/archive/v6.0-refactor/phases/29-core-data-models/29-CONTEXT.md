# Phase 29: 核心数据模型 - 上下文

**收集日期：** 2026-05-11
**状态：** 已完成 2026-05-11

## 阶段边界

提取并全新设计 UE 蓝图核心数据模型（UEdGraph、UEdGraphNode、UEdGraphPin、ParseResult 及相关节点类型）到 `src/uasset_read/models/` 目录。等价覆盖旧版 uasset_read.py 中第 1878-2074 行的数据类定义，但采用全新架构设计而非 1:1 提取。

## 实现决策

### 命名约定

- **D-01 (命名风格):** 保持 UE 源码命名 — UEdGraph、UEdGraphNode、UEdGraphPin、FMemberReference 等，与 UE 源码一致，方便对照研究和文档引用。

### 模块组织

- **D-02 (目录结构):** models/ 目录包含 3 个文件：
  - `models/core.py` — UEdGraphPin、UEdGraphNode 基类、UEdGraph、FMemberReference
  - `models/node_types.py` — K2NodeCallFunction、K2NodeEvent、K2NodeKnot、EdGraphNodeComment、K2NodeEnhancedInputAction
  - `models/result.py` — ParseResult、StatusInfo
- **D-03 (扁平导入):** 所有模型类通过 `models/__init__.py` 统一导出，调用者使用 `from uasset_read.models import UEdGraph` 等，不需要子模块路径。

### 继承结构

- **D-04 (节点继承):** UEdGraphNode 作为基类，包含所有节点共有的字段（node_guid、node_pos_x/y、node_comment、pins、class_name），具体节点类型（K2NodeCallFunction 等）作为子类继承，各自添加特有字段。
- **D-05 (类型识别):** 子类通过 class_name 字段或 `isinstance()`/`match/case` 进行类型分派。Phase 31 的图解析使用 match/case 判断节点类型。

### 序列化策略

- **D-06 (独立序列化):** 数据类本身只定义字段，序列化逻辑在独立函数/模块中处理（类似现有 serializers 的做法）。数据和逻辑解耦，方便后续重构。
- **D-07 (空值过滤):** 序列化函数默认跳过 None 值和空字符串/空列表字段，减少 JSON 输出噪音。
- **D-08 (EditorOnly 处理):** EditorOnly 字段（persistent_guid、source_index 等）保留在模型中但标记为 exclude，序列化时默认跳过，可通过参数显式包含。
- **D-09 (嵌套结构):** 序列化函数负责处理嵌套结构转换（如 position 转为 `{"x": ..., "y": ...}`、function_reference 提取到顶层等），不在数据类中硬编码。

### 类型系统

- **D-10 (严格类型):** 使用 Python 3.10+ 严格类型提示，包括 Generic、TypeVar、Union 等。子类方法返回 `Self` 类型，from_archive 返回具体子类实例。
- **D-11 (节点多态):** node_data 字段在基类中声明为 `Optional[UEdGraphNode]`（多态），实际运行时为具体子类实例。序列化时通过 isinstance 分派处理。

### 解析职责

- **D-12 (模型自带解析):** 每个数据类附带静态 `from_archive(archive: FArchive) -> Self` 方法，负责从二进制流中读取自身。模型既是数据结构也是解析器。
- **D-13 (UEdGraphPin 解析):** UEdGraphPin 的 from_archive 按 UE 源码 EdGraphPin.cpp L1838-1964 序列化顺序读取。
- **D-14 (UEdGraphNode 解析):** UEdGraphNode 基类的 from_archive 读取公共字段后，由子类重写/扩展读取特有字段。

### AI 自行决定

- 具体字段顺序和默认值由规划阶段确定
- 序列化函数命名（to_dict / format_xxx 等）由规划阶段确定
- 是否需要基类 Model 或 Serializable mixin 由规划阶段确定

## 权威参考

**下游智能体在规划或实现前必须阅读以下内容。**

### 旧版源码参考

- `uasset_read.py` §1878-1920 — UEdGraphPin 完整定义和注释
- `uasset_read.py` §1922-1938 — UEdGraphNode 基类定义
- `uasset_read.py` §1941-1956 — UEdGraph 容器定义
- `uasset_read.py` §1959-1971 — FMemberReference 定义
- `uasset_read.py` §1978-2047 — 5 种节点类型数据类
- `uasset_read.py` §2051-2074 — ParseResult 和 StatusInfo 定义
- `uasset_read.py` §6640-6682 — format_node_to_dict() 序列化逻辑参考
- `uasset_read.py` §6685-6750 — format_graphs_json() 参考

### UE 源码参考

- `EdGraphPin.cpp` L1838-1964 — UEdGraphPin 序列化顺序
- `EdGraphNode.h` + `K2Node.h` — UEdGraphNode 字段定义
- `EdGraph.h` — UEdGraph 容器结构

### 现有模块模式

- `src/uasset_read/serializers/package_summary.py` — 现有 dataclass + from_archive 模式参考
- `src/uasset_read/serializers/object_resources.py` — PackageIndex/ObjectImport/ObjectExport 模式
- `src/uasset_read/archive.py` — FArchive 读取接口
- `src/uasset_read/constants.py` — 已有常量
- `src/uasset_read/exceptions.py` — 已有异常
- `src/uasset_read/__init__.py` — 公共 API 导出模式

### 需求与范围

- `.planning/ROADMAP.md` §Phase 29 — Phase 29 目标、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — MOD-06, MOD-07 需求定义

## 现有代码洞察

### 可复用资产

- **FArchive (archive.py):** 已实现的 read_u32/read_i32/read_u8/read_fstring/read_bytes/read_guid 等方法可直接用于模型解析
- **PackageFileSummary/ObjectImport/ObjectExport (serializers/):** 已建立的 dataclass 模式可作为模型类设计参考
- **常量模块 (constants.py):** 版本号、阈值等常量已就位

### 既定模式

- **dataclass for models:** Phase 27 CONTEXT.md 已锁定 — 使用 Python 标准库 dataclasses
- **from_archive 模式:** serializers 中已建立 — 独立函数读取二进制流返回 dataclass 实例
- **分层架构依赖方向:** Output → Models → Parsers → Serializers → FArchive，单向依赖避免循环导入
- **零运行时依赖:** pyproject.toml 中 `dependencies = []`

### 集成点

- **models/__init__.py 需要更新:** 新增所有模型类的导出，替换 Phase 27 的空 `__all__`
- **Phase 29b 依赖:** PropertyTag、FunctionReference、图连接数据结构将在 Phase 29b 定义，Phase 29 不应包含这些 → **注意：Phase 29b 已合并到 Phase 30 一并实现**
- **Phase 30-33 依赖:** 属性解析、图解析、输出格式化、CLI 入口都依赖这些模型类
- **测试适配:** 现有测试中使用这些数据类的地方需要更新导入路径

## 具体想法

无特定要求 — 采用上述讨论的全新设计方案。

## 延期想法

- 蓝图变量完整元数据增强 — Phase 30 已实现
- PropertyTag/PropertyValue 数据模型 — Phase 30 (30-01) 已实现
- 图连接数据结构 (ExecutionFlow/DataFlow) — 待 Phase 31 蓝图图解析时补充
- FunctionReference/EventReference — 待 Phase 31 蓝图图解析时补充
- MCP Server 封装 — 延后至 v4.x
- JSON Schema 生成 — 延后至 v9.0

---

*阶段：29-核心数据模型 — 已完成 2026-05-11*
*Phase 29b（属性与图数据模型）已合并到 Phase 30 一并实现*
