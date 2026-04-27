# 架构模式

**领域：** Unreal Engine .uasset 文件二进制解析器
**研究日期：** 2026-04-27

## 推荐架构

推荐架构遵循 **分层管道** 模式，镜像 Unreal Engine 自身序列化架构，同时适配 Python 习惯。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              输出层                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   TextOutput    │  │   JsonOutput    │  │      SummaryOutput         │  │
│  │  (人类可读)     │  │ (Agent 可解析)  │  │  (精简概览)                │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              模型层                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   UObject       │  │   UBlueprint    │  │      FProperty             │  │
│  │   (基类)        │  │   (蓝图)        │  │   (属性类型)               │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   FPackageIndex │  │   NameTable     │  │      ExportMap/ImportMap   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           反序列化层                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         AssetDeserializer                            │   │
│  │  - 读取 NameTable、ImportMap、ExportMap                            │   │
│  │  - 分发到类型特定处理器                                             │   │
│  │  - 解析交叉引用（FPackageIndex）                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │ BlueprintHandler  │  │  TextureHandler   │  │    ...其他类型        │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              读取层                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           BinaryReader                               │   │
│  │  - 低级字节操作（read_u8、read_u32、read_f32 等）                   │   │
│  │  - 字节序处理                                                        │   │
│  │  - 流位置管理                                                        │   │
│  │  - 内存映射文件支持                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │   FileReader      │  │   MemoryReader    │  │    PakReader          │   │
│  │  (文件流)         │  │  (字节缓冲)       │  │   (pak 归档)          │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            输入层                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           .uasset 文件                               │   │
│  │  [PackageFileSummary][NameTable][ImportMap][ExportMap][Payload]     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 组件边界

| 组件 | 职责 | 与谁通信 |
|------|------|----------|
| **BinaryReader** | 低级字节读取、字节序、定位 | 输入层（读取）、反序列化器（服务） |
| **AssetDeserializer** | 协调解析、类型分发、引用解析 | Reader（读取）、模型（创建）、处理器（分发） |
| **TypeHandlers** | 类型特定解析逻辑（Blueprint、Texture 等） | 反序列化器（接收上下文）、模型（创建） |
| **Models** | 结构化数据表示 | 反序列化器（创建）、输出（服务） |
| **OutputFormatters** | 将模型转换为文本/JSON/概要 | 模型（读取） |

### 数据流

```
.uasset 文件
    │
    ▼
BinaryReader.open(path)
    │
    ├─► read_package_summary() ─► PackageSummary 模型
    │
    ├─► read_name_table() ─► List[str] (NameMap)
    │
    ├─► read_import_map() ─► List[ObjectImport]
    │
    ├─► read_export_map() ─► List[ObjectExport]
    │
    ▼
AssetDeserializer.parse_exports()
    │
    ├─► resolve_export_type() ─► "Blueprint"、"Texture" 等
    │
    ├─► dispatch_to_handler(export_type)
    │       │
    │       └─► BlueprintHandler.parse(reader, context)
    │               │
    │               └─► Blueprint 模型（带节点、属性等）
    │
    ▼
OutputFormatter.format(model, format="text"|"json"|"summary")
    │
    ▼
结构化输出（text/JSON/概要）
```

## 遵循的模式

### 模式 1：Archive/Reader 抽象（源于 UE FArchive）

**概念：** 二进制读取操作的抽象基类，灵感来自 UE 的 `FArchive` 模式。

**时机：** 整个解析系统的基础。

**示例：**

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from dataclasses import dataclass

@dataclass
class ArchiveState:
    """跟踪解析状态，镜像 UE 的 FArchiveState。"""
    position: int = 0
    is_error: bool = False
    engine_version: int = 0
    custom_versions: dict[int, int] = None

class FArchive(ABC):
    """
    二进制读取抽象基类，镜像 UE 的 FArchive 模式。
    提供序列化无关接口。
    """
    def __init__(self):
        self._state = ArchiveState(custom_versions={})

    @abstractmethod
    def read(self, size: int) -> bytes: ...
    @abstractmethod
    def seek(self, pos: int) -> None: ...
    @abstractmethod
    def tell(self) -> int: ...
    @abstractmethod
    def total_size(self) -> int: ...

    # 类型读取便捷方法
    def read_u8(self) -> int:
        return int.from_bytes(self.read(1), 'little')

    def read_u32(self) -> int:
        return int.from_bytes(self.read(4), 'little')

    def read_u64(self) -> int:
        return int.from_bytes(self.read(8), 'little')

    def read_f32(self) -> float:
        return struct.unpack('<f', self.read(4))[0]

    def read_fstring(self) -> str:
        """读取 UE FString（带长度前缀的 UTF-16 或 UTF-8）。"""
        length = self.read_i32()
        if length == 0:
            return ""
        if length < 0:
            # UTF-16 编码
            data = self.read(-length * 2)
            return data.decode('utf-16-le').rstrip('\x00')
        else:
            # UTF-8 编码
            data = self.read(length)
            return data.decode('utf-8').rstrip('\x00')

    def read_name(self, name_map: list[str]) -> str:
        """读取 FName（名称表索引）。"""
        index = self.read_u32()
        number = self.read_u32()  # 实例编号
        if 0 <= index < len(name_map):
            base = name_map[index]
            return f"{base}_{number}" if number > 0 else base
        return "None"

class FFileArchive(FArchive):
    """文件后端归档实现。"""

    def __init__(self, path: str):
        super().__init__()
        self._file = open(path, 'rb')

    def read(self, size: int) -> bytes:
        return self._file.read(size)

    def seek(self, pos: int) -> None:
        self._file.seek(pos)

    def tell(self) -> int:
        return self._file.tell()

    def total_size(self) -> int:
        pos = self._file.tell()
        self._file.seek(0, 2)
        size = self._file.tell()
        self._file.seek(pos)
        return size

class FMemoryArchive(FArchive):
    """内存后端归档，用于测试和嵌套归档。"""

    def __init__(self, data: bytes):
        super().__init__()
        self._data = data
        self._pos = 0

    def read(self, size: int) -> bytes:
        result = self._data[self._pos:self._pos + size]
        self._pos += size
        return result

    def seek(self, pos: int) -> None:
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def total_size(self) -> int:
        return len(self._data)
```

### 模式 2：模型优先使用 Dataclasses

**概念：** 使用 Python dataclasses 表示结构化数据。

**时机：** 所有模型类（PackageSummary、ObjectImport、ObjectExport 等）。

**示例：**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FPackageFileSummary:
    """镜像 UE 的 FPackageFileSummary —— 包文件头。"""
    tag: int  # PACKAGE_FILE_TAG = 0x9E2A83C1
    file_version_ue: int
    file_version_licensee: int
    custom_versions: dict[int, int]
    package_flags: int
    name_count: int
    name_offset: int
    export_count: int
    export_offset: int
    import_count: int
    import_offset: int
    total_header_size: int
    # ... 其他字段

@dataclass
class FObjectImport:
    """镜像 UE 的 FObjectImport —— 外部引用。"""
    class_package: str  # 包名
    class_name: str     # 类名
    outer_index: int    # FPackageIndex 到 outer
    object_name: str    # 对象名

@dataclass
class FObjectExport:
    """镜像 UE 的 FObjectExport —— 包内对象定义。"""
    class_index: int       # FPackageIndex 到类
    super_index: int       # FPackageIndex 到超类
    outer_index: int       # FPackageIndex 到 outer
    object_name: str       # 对象名
    object_flags: int      # EObjectFlags
    serial_size: int       # 序列化数据大小
    serial_offset: int     # 序列化数据偏移

@dataclass
class FPackageIndex:
    """
    镜像 UE 的 FPackageIndex。
    Index > 0: ExportMap[index - 1]
    Index < 0: ImportMap[-index - 1]
    Index = 0: null
    """
    index: int

    @property
    def is_import(self) -> bool:
        return self.index < 0

    @property
    def is_export(self) -> bool:
        return self.index > 0

    @property
    def is_null(self) -> bool:
        return self.index == 0

    def to_import_index(self) -> int:
        return -self.index - 1

    def to_export_index(self) -> int:
        return self.index - 1
```

### 模式 3：处理器/插件注册

**概念：** 类型特定反序列化器的注册表模式。

**时机：** 扩展支持新资产类型。

**示例：**

```python
from typing import Protocol, TypeVar, Callable
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class ParseContext:
    """解析时传递给所有处理器的上下文。"""
    archive: FArchive
    name_map: list[str]
    import_map: list[FObjectImport]
    export_map: list[FObjectExport]
    summary: FPackageFileSummary

class TypeHandler(Protocol[T]):
    """类型特定处理器协议。"""

    @staticmethod
    def can_handle(class_name: str, package_path: str) -> bool: ...

    def parse(self, ctx: ParseContext, export: FObjectExport) -> T: ...

# 全局注册表
_handler_registry: dict[str, type[TypeHandler]] = {}

def register_handler(asset_type: str):
    """装饰器：为资产类型注册处理器。"""
    def decorator(cls: type[TypeHandler]) -> type[TypeHandler]:
        _handler_registry[asset_type] = cls
        return cls
    return decorator

def get_handler(class_name: str) -> Optional[type[TypeHandler]]:
    """根据类名获取处理器。"""
    # 直接匹配
    if class_name in _handler_registry:
        return _handler_registry[class_name]
    # 模式匹配（如 "BlueprintGeneratedClass" -> "Blueprint"）
    for pattern, handler in _handler_registry.items():
        if pattern.lower() in class_name.lower():
            return handler
    return None

# 处理器实现示例
@register_handler("Blueprint")
class BlueprintHandler:
    """处理蓝图资产反序列化。"""

    @staticmethod
    def can_handle(class_name: str, package_path: str) -> bool:
        return "Blueprint" in class_name or package_path.endswith("_BP.uasset")

    def parse(self, ctx: ParseContext, export: FObjectExport) -> 'Blueprint':
        ctx.archive.seek(export.serial_offset)
        # 解析蓝图特定数据
        return Blueprint(...)
```

### 模式 4：大文件流式处理

**概念：** 内存映射文件访问和大文件分块读取。

**时机：** 文件 > 100MB 或处理多个文件。

**示例：**

```python
import mmap
from contextlib import contextmanager

class FMappedArchive(FArchive):
    """大文件内存映射归档。"""

    def __init__(self, path: str):
        super().__init__()
        self._file = open(path, 'rb')
        self._mmap = mmap.mmap(
            self._file.fileno(),
            0,
            access=mmap.ACCESS_READ
        )

    def read(self, size: int) -> bytes:
        result = self._mmap[self._pos:self._pos + size]
        self._pos += size
        return result

    def seek(self, pos: int) -> None:
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def total_size(self) -> int:
        return len(self._mmap)

    def read_at(self, offset: int, size: int) -> bytes:
        """随机访问不影响位置。"""
        return self._mmap[offset:offset + size]

    def close(self):
        self._mmap.close()
        self._file.close()

# 工厂函数
def create_archive(path: str, use_mmap: bool = True) -> FArchive:
    """根据文件大小创建合适归档。"""
    import os
    file_size = os.path.getsize(path)
    if use_mmap and file_size > 50 * 1024 * 1024:  # > 50MB
        return FMappedArchive(path)
    return FFileArchive(path)
```

### 模式 5：版本感知反序列化

**概念：** 处理多个 UE 版本，使用版本特定解析分支。

**时机：** 解析不同 UE 版本的 .uasset。

**示例：**

```python
from enum import IntEnum
from typing import Callable

class UEVersion(IntEnum):
    """关键 UE 版本里程碑，对应序列化变更。"""
    VER_4_0 = 400
    VER_4_14 = 414
    VER_4_22 = 422
    VER_4_25 = 425
    VER_4_27 = 427
    VER_5_0 = 500
    VER_5_1 = 510
    VER_5_2 = 520
    VER_5_3 = 530
    VER_5_4 = 540
    VER_5_5 = 550

# 自定义版本（UE 用于特定子系统）
CUSTOM_VERSIONS = {
    0x7E7A3F3E: "CoreObjectVersion",
    0x12E8C3E4: "BlueprintVersion",
    0x4B4B2E28: "NiagaraVersion",
    # ... 来自 UE 源码
}

class VersionedParser:
    """处理版本特定解析逻辑。"""

    def __init__(self, engine_version: int, custom_versions: dict[int, int]):
        self.engine_version = engine_version
        self.custom_versions = custom_versions

    def should_read_fstring_as_utf8(self) -> bool:
        """UE 5.0+ 默认使用 UTF-8。"""
        return self.engine_version >= UEVersion.VER_5_0

    def should_use_new_guid_format(self) -> bool:
        """5.1 GUID 序列化变更。"""
        return self.engine_version >= UEVersion.VER_5_1

    def get_custom_version(self, version_key: int) -> int:
        """获取子系统自定义版本。"""
        return self.custom_versions.get(version_key, 0)

# 解析器中使用
def parse_property(ctx: ParseContext) -> Property:
    parser = VersionedParser(
        ctx.summary.file_version_ue,
        ctx.summary.custom_versions
    )

    # 版本特定逻辑
    if parser.should_read_fstring_as_utf8():
        value = ctx.archive.read_utf8_string()
    else:
        value = ctx.archive.read_utf16_string()
```

## 需避免的反模式

### 反模式 1：全量加载文件到内存

**概念：** `data = open(path, 'rb').read()` 在多 GB 文件上。

**为何不好：** 内存耗尽、启动慢、大文件崩溃。

**替代：** 使用流式或内存映射文件。

```python
# 错误做法
with open(path, 'rb') as f:
    data = f.read()  # 加载整个文件
    process(data)

# 正确做法
with FMappedArchive(path) as archive:
    process_streaming(archive)  # 按需读取
```

### 反模式 2：硬编码偏移

**概念：** `archive.seek(0x1234)` 不先读取文件头。

**为何不好：** UE 格式随版本变化；偏移会失效。

**替代：** 先解析 PackageFileSummary，使用其偏移。

```python
# 错误做法
archive.seek(0x1234)  # 魔术数字 —— 不同文件会崩溃

# 正确做法
summary = read_package_summary(archive)
archive.seek(summary.export_offset)  # 来自实际文件头
```

### 反模式 3：单体解析器

**概念：** 单个 2000 行 `parse_uasset()` 函数。

**为何不好：** 不可维护、难测试、难扩展。

**替代：** 分离关注点到 Reader、Deserializer、Model、Output 层。

```python
# 错误做法
def parse_uasset(path):
    with open(path, 'rb') as f:
        # 2000 行所有内容混在一起
        pass

# 正确做法
def parse_uasset(path):
    with FFileArchive(path) as archive:
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        imports = read_import_map(archive, summary, name_map)
        exports = read_export_map(archive, summary, name_map)

        ctx = ParseContext(archive, name_map, imports, exports, summary)

        for export in exports:
            handler = get_handler(export.class_name)
            if handler:
                yield handler.parse(ctx, export)
```

### 反模式 4：忽略导入解析

**概念：** 只解析导出而不解析导入引用。

**为何不好：** 蓝图引用父类、接口、其他包的类型。不解析则数据不完整。

**替代：** 将导入解析纳入架构。

```python
# 正确做法 —— 内置导入解析
@dataclass
class ResolvedExport:
    export: FObjectExport
    resolved_class: Optional[str]  # 来自 ImportMap 或 ExportMap
    resolved_super: Optional[str]  # 父类
    resolved_outer: Optional[str]  # 包含对象

def resolve_reference(
    index: FPackageIndex,
    imports: list[FObjectImport],
    exports: list[FObjectExport]
) -> Optional[str]:
    if index.is_import:
        imp = imports[index.to_import_index()]
        return f"{imp.class_package}.{imp.object_name}"
    elif index.is_export:
        exp = exports[index.to_export_index()]
        return exp.object_name
    return None
```

### 反模式 5：紧密耦合输出格式

**概念：** 解析器直接返回格式化字符串。

**为何不好：** 无法生成 JSON、无法过滤、无法测试结构。

**替代：** 返回结构化模型，单独格式化。

```python
# 错误做法
def parse_blueprint(archive) -> str:
    return f"蓝图: {name}\n节点: {nodes}"

# 正确做法
def parse_blueprint(archive) -> Blueprint:
    return Blueprint(name=name, nodes=nodes, ...)

# 然后格式化：
class JsonOutput:
    def format(self, blueprint: Blueprint) -> str:
        return json.dumps(asdict(blueprint))

class TextOutput:
    def format(self, blueprint: Blueprint) -> str:
        return f"蓝图: {blueprint.name}\n节点: {len(blueprint.nodes)}"
```

## 可扩展性考量

| 关注点 | 100 导出时 | 10K 导出时 | 100K 导出时 |
|--------|------------|------------|-------------|
| **内存** | 全量加载 | 流式导出 | mmap + 延迟解析 |
| **启动** | 解析所有文件头 | 仅解析 Summary | Summary + 延迟导入 |
| **输出** | 全量序列化 | 分页输出 | 流式写入文件 |
| **解析** | 全量导入解析 | 缓存已解析名称 | 按需延迟解析 |

### 延迟解析策略

超大包（如带大量 Actor 的大地图）：

```python
class LazyExportIterator:
    """迭代导出而不一次性全部解析。"""

    def __init__(self, ctx: ParseContext, exports: list[FObjectExport]):
        self.ctx = ctx
        self.exports = exports
        self._parsed: dict[int, Any] = {}

    def get(self, index: int) -> Any:
        """首次访问时解析导出。"""
        if index not in self._parsed:
            export = self.exports[index]
            handler = get_handler(export.class_name)
            if handler:
                self._parsed[index] = handler.parse(self.ctx, export)
        return self._parsed.get(index)

    def __iter__(self):
        for i, export in enumerate(self.exports):
            yield self.get(i)
```

## 来源

- **Unreal Engine 源码**：`D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/`
  - `Private/UObject/Package.cpp` —— 包处理
  - `Private/Serialization/AsyncLoading.cpp` —— 加载架构
  - `Public/UObject/Linker.h` —— Linker 结构
  - `Public/UObject/LinkerLoad.h` —— 包加载
  - `Public/UObject/PackageFileSummary.h` —— 文件头结构
  - `Public/UObject/ObjectResource.h` —— 导入/导出结构
  - `Public/Serialization/Archive.h` —— Archive 抽象

- **CUE4Parse 架构**：[https://github.com/Fabian-Creostone/CUE4Parse](https://github.com/Fabian-Creostone/CUE4Parse)
  - C# FArchive 模式实现
  - 类型特定处理器注册
  - 版本感知反序列化

- **FModel 架构**：[https://github.com/4sval/FModel](https://github.com/4sval/FModel)
  - 分层架构（Reader -> Deserializer -> Model -> Output）
  - CUE4Parse 集成模式

- **Python 二进制解析**：
  - `struct` 模块用于低级解析（内置）
  - `dataclasses` 用于模型表示（内置）
  - `mmap` 用于高效大文件处理（内置）
  - 生成器模式用于流式处理

## 构建顺序启示

基于架构，推荐构建顺序：

1. **阶段 1：读取层**
   - `FArchive` 基类
   - `FFileArchive` 实现
   - `FMemoryArchive` 用于测试
   - 低级读取方法（u8、u32、fstring、fname）

2. **阶段 2：模型层（核心）**
   - `FPackageFileSummary`
   - `FPackageIndex`
   - `FObjectImport` / `FObjectExport`
   - 名称表结构

3. **阶段 3：反序列化层（核心）**
   - `read_package_summary()`
   - `read_name_table()`
   - `read_import_map()`
   - `read_export_map()`
   - `ParseContext`

4. **阶段 4：模型层（类型）**
   - 基础 `UObject` 模型
   - `Blueprint` 模型
   - 属性类型（`FProperty`、`FArrayProperty` 等）

5. **阶段 5：处理器层**
   - 处理器注册表
   - `BlueprintHandler`
   - 其他类型处理器按需添加

6. **阶段 6：输出层**
   - `TextOutput`
   - `JsonOutput`
   - `SummaryOutput`

7. **阶段 7：性能与优化**
   - `FMappedArchive` 用于大文件
   - 延迟解析
   - 版本处理
   - 错误恢复