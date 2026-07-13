from __future__ import annotations

"""Usmap 无版本属性映射解析器。

解析 CUE4Parse 兼容的 .usmap 映射文件，提供无版本属性的完整反序列化。
参考 UE 源码中 FPropertyTag 序列化机制和 CUE4Parse 映射格式。

用法::

    from uasset_read.parsers.usmap import parse_usmap, UsmapData

    # 从文件路径
    usmap = UsmapData("path/to/file.usmap")

    # 从 bytes
    usmap = UsmapData(raw_bytes)

    # 便捷函数
    usmap = parse_usmap("path/to/file.usmap")
"""

from dataclasses import dataclass, field
import gzip
import json
import os
import struct
from typing import TYPE_CHECKING, BinaryIO, Dict, List, Optional, Union

from uasset_read.exceptions import ParseError

if TYPE_CHECKING:
    from uasset_read.memory_safety import ResourceBudget


# ============================================================================
# 类型映射表 — 与 CUE4Parse UsmapTypeTag 枚举对齐
# ============================================================================

PROPERTY_TYPE_NAMES: Dict[int, str] = {
    0: "ByteProperty",
    1: "BoolProperty",
    2: "IntProperty",
    3: "FloatProperty",
    4: "ObjectProperty",
    5: "NameProperty",
    6: "DelegateProperty",
    7: "DoubleProperty",
    8: "ArrayProperty",
    9: "StructProperty",
    10: "StrProperty",
    11: "TextProperty",
    12: "InterfaceProperty",
    13: "MulticastDelegateProperty",
    14: "WeakObjectProperty",
    15: "LazyObjectProperty",
    16: "AssetObjectProperty",
    17: "SoftObjectProperty",
    18: "UInt64Property",
    19: "UInt32Property",
    20: "UInt16Property",
    21: "Int64Property",
    22: "Int16Property",
    23: "Int8Property",
    24: "MapProperty",
    25: "SetProperty",
    26: "EnumProperty",
    27: "FieldPathProperty",
    28: "OptionalProperty",
    29: "Utf8StrProperty",
    30: "AnsiStrProperty",
    31: "ClassProperty",
    32: "MulticastInlineDelegateProperty",
    33: "SoftClassProperty",
    34: "VerseStringProperty",
    35: "VerseDynamicProperty",
    36: "VerseFunctionProperty",
    0xFD: "CustomProperty_FD",
    0xFE: "CustomProperty_FE",
    0xFF: "Unknown",
}

MAGIC_USMAP: int = 0x30C4
MAX_SUPPORTED_VERSION: int = 4
MAX_RECURSION_DEPTH: int = 64


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class UsmapProperty:
    """映射文件中的单个属性描述。

    Attributes:
        index: 属性在结构体中的序号
        name: 属性名称
        type_name: 属性类型名（如 "IntProperty"）
        struct_type: 对于 StructProperty，嵌套的结构体名称
        inner_type: 容器类型的内部类型（Array/Set/Optional/Enum/Map 的 key）
        value_type: MapProperty 的 value 类型
        enum_name: 对于 EnumProperty，枚举类型名称
        array_dim: 数组维度大小
    """
    index: int
    name: str
    type_name: str
    struct_type: Optional[str] = None
    inner_type: Optional[UsmapProperty] = None
    value_type: Optional[UsmapProperty] = None
    enum_name: Optional[str] = None
    array_dim: int = 1


@dataclass
class UsmapSchema:
    """映射文件中的类/结构体描述。

    Attributes:
        name: 类/结构体名称
        super_type: 父类名称（如有）
        serializable_count: 可序列化属性数量
        property_count: 属性总数
        properties: 属性字典（key = 属性序号）
    """
    name: str
    super_type: Optional[str] = None
    serializable_count: int = 0
    property_count: int = 0
    properties: Dict[int, UsmapProperty] = field(default_factory=dict)


# ============================================================================
# 二进制读取器
# ============================================================================

class _BytesReader:
    """内部二进制读取器，使用小端序。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    @property
    def remaining(self) -> int:
        return len(self._data) - self._pos

    def read(self, size: int) -> bytes:
        if self._pos + size > len(self._data):
            raise ParseError(
                f"Usmap 读取越界：需要 {size} 字节，剩余 {self.remaining}"
            )
        result = self._data[self._pos:self._pos + size]
        self._pos += size
        return result

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack_from("<H", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack_from("<i", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack_from("<Q", self.read(8))[0]

    def name(self, lut: List[str]) -> Optional[str]:
        """读取名称索引并从 LUT 解析。-1 表示 None。"""
        idx = self.i32()
        if idx == -1:
            return None
        if idx < 0 or idx >= len(lut):
            raise ParseError(f"Usmap 名称索引越界: {idx} (LUT 大小: {len(lut)})")
        return lut[idx]


# ============================================================================
# 解压
# ============================================================================

def _decompress(payload: bytes, method: int, comp_size: int, decomp_size: int,
                 budget: "ResourceBudget | None" = None) -> bytes:
    """根据压缩方法解压 usmap payload。

    支持的方法:
        0: 无压缩
        2: Brotli（可选依赖）
        3: ZStandard（可选依赖）
    """
    if method == 0:
        if comp_size != decomp_size:
            raise ParseError(
                f"Usmap 无压缩模式下大小不一致: {comp_size} != {decomp_size}"
            )
        return payload
    if method == 2:
        try:
            import brotli  # type: ignore
        except ImportError as exc:
            raise ParseError("Usmap Brotli 压缩需要安装 brotli 包") from exc
        if budget is not None:
            budget.reserve(decomp_size, "usmap_brotli_decompress")
        result = brotli.decompress(payload)
        if len(result) > decomp_size:
            raise ParseError(
                f"Usmap Brotli 解压后大小超出预期: {len(result)} > {decomp_size}"
            )
        return result
    if method == 3:
        try:
            import zstandard as zstd  # type: ignore
        except ImportError as exc:
            raise ParseError("Usmap ZStandard 压缩需要安装 zstandard 包") from exc
        if budget is not None:
            budget.reserve(decomp_size, "usmap_zstd_decompress")
        return zstd.ZstdDecompressor().decompress(payload, max_output_size=decomp_size)
    raise ParseError(f"不支持的 Usmap 压缩方式: {method}")


# ============================================================================
# 解析属性类型（递归）
# ============================================================================

def _parse_property_type(reader: _BytesReader, lut: List[str], depth: int = 0) -> UsmapProperty:
    """解析一个属性类型描述（递归处理嵌套类型）。"""
    if depth > MAX_RECURSION_DEPTH:
        raise ParseError(
            f"Usmap 属性类型递归深度超过上限 {MAX_RECURSION_DEPTH}"
        )
    type_id = reader.u8()
    type_name = PROPERTY_TYPE_NAMES.get(type_id, "Unknown")

    # EnumProperty: 内嵌值类型 + 枚举名
    if type_name == "EnumProperty":
        inner = _parse_property_type(reader, lut, depth + 1)
        enum_name = reader.name(lut) or ""
        return UsmapProperty(
            index=0, name="", type_name=type_name,
            inner_type=inner, enum_name=enum_name,
        )

    # StructProperty: 嵌套结构体名
    if type_name == "StructProperty":
        struct_name = reader.name(lut) or ""
        return UsmapProperty(
            index=0, name="", type_name=type_name,
            struct_type=struct_name,
        )

    # Array/Set/Optional: 内嵌值类型
    if type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
        inner = _parse_property_type(reader, lut, depth + 1)
        return UsmapProperty(
            index=0, name="", type_name=type_name,
            inner_type=inner,
        )

    # MapProperty: key + value 类型
    if type_name == "MapProperty":
        inner = _parse_property_type(reader, lut, depth + 1)
        value = _parse_property_type(reader, lut, depth + 1)
        return UsmapProperty(
            index=0, name="", type_name=type_name,
            inner_type=inner, value_type=value,
        )

    # 基本类型
    return UsmapProperty(index=0, name="", type_name=type_name)


# ============================================================================
# 解析 schema
# ============================================================================

def _parse_schema(reader: _BytesReader, lut: List[str]) -> UsmapSchema:
    """解析单个结构体/类 schema。"""
    name = reader.name(lut) or ""
    super_type = reader.name(lut)
    property_count = reader.u16()
    serializable_count = reader.u16()

    properties: Dict[int, UsmapProperty] = {}
    for _ in range(serializable_count):
        index = reader.u16()
        array_dim = reader.u8()
        prop_name = reader.name(lut) or ""
        prop_type = _parse_property_type(reader, lut)

        # 创建带有完整信息的属性
        prop = UsmapProperty(
            index=index,
            name=prop_name,
            type_name=prop_type.type_name,
            struct_type=prop_type.struct_type,
            inner_type=prop_type.inner_type,
            value_type=prop_type.value_type,
            enum_name=prop_type.enum_name,
            array_dim=array_dim,
        )

        # 处理数组展开
        for offset in range(array_dim):
            slot = prop if offset == 0 else UsmapProperty(
                index=index + offset,
                name=prop_name,
                type_name=prop_type.type_name,
                struct_type=prop_type.struct_type,
                inner_type=prop_type.inner_type,
                value_type=prop_type.value_type,
                enum_name=prop_type.enum_name,
                array_dim=array_dim,
            )
            properties[index + offset] = slot

    return UsmapSchema(
        name=name,
        super_type=super_type,
        serializable_count=serializable_count,
        property_count=property_count,
        properties=properties,
    )


# ============================================================================
# 内部解析结果
# ============================================================================

@dataclass
class _UsmapParseResult:
    """内部解析结果容器。"""
    version: int
    name_table: List[str]
    enums: Dict[str, Dict[int, str]]
    schemas: Dict[str, UsmapSchema]


def _parse_usmap_data(data: bytes, budget: "ResourceBudget | None" = None) -> _UsmapParseResult:
    """解析 .usmap 文件二进制数据。"""
    reader = _BytesReader(data)

    # --- Header ---
    magic = reader.u16()
    if magic != MAGIC_USMAP:
        raise ParseError(f"Usmap magic 无效: 0x{magic:04X}（期望 0x{MAGIC_USMAP:04X}）")

    version = reader.u8()
    if version > MAX_SUPPORTED_VERSION:
        raise ParseError(f"Usmap 版本不支持: {version}（最大 {MAX_SUPPORTED_VERSION}）")

    # 版本 1+: PackageFileVersion + CustomVersions + NetCL
    if version >= 1:
        has_versioning = reader.u8()
        if has_versioning:
            reader.read(8)  # PackageFileVersion (int32 x 2)
            custom_count = reader.i32()
            if custom_count < 0:
                raise ParseError(f"Usmap CustomVersion 数量无效: {custom_count}")
            reader.read(custom_count * 20)  # 每个 CustomVersion 20 字节
            reader.read(4)  # NetCL

    # 压缩头
    compression = reader.u8()
    comp_size = reader.u32()
    decomp_size = reader.u32()
    payload = reader.read(comp_size)

    # 解压
    decompressed = _decompress(payload, compression, comp_size, decomp_size, budget=budget)
    ar = _BytesReader(decompressed)

    # --- NameTable ---
    name_count = ar.u32()
    name_table: List[str] = []
    for _ in range(name_count):
        length = ar.u16() if version >= 2 else ar.u8()
        name_bytes = ar.read(length)
        name_table.append(name_bytes.decode("utf-8", errors="replace"))

    # --- EnumTable ---
    enum_count = ar.u32()
    enums: Dict[str, Dict[int, str]] = {}
    for _ in range(enum_count):
        enum_name = ar.name(name_table) or ""
        value_count = ar.u16() if version >= 3 else ar.u8()
        values: Dict[int, str] = {}
        for idx in range(value_count):
            if version >= 4:
                val = int(ar.u64())
            else:
                val = idx
            member_name = ar.name(name_table) or ""
            values[val] = member_name
        enums[enum_name] = values

    # --- SchemaTable ---
    schema_count = ar.u32()
    schemas: Dict[str, UsmapSchema] = {}
    for _ in range(schema_count):
        schema = _parse_schema(ar, name_table)
        schemas[schema.name] = schema

    return _UsmapParseResult(
        version=version,
        name_table=name_table,
        enums=enums,
        schemas=schemas,
    )


# ============================================================================
# 公共 API
# ============================================================================

class UsmapData:
    """Usmap 文件解析结果。

    Attributes:
        version: 文件版本号（0-4）
        name_table: 名称查找表
        enums: 枚举映射（枚举名 → {值 → 成员名}）
        schemas: 结构体映射（类名 → UsmapSchema）
    """
    version: int = 0
    name_table: List[str] = field(default_factory=list)
    enums: Dict[str, Dict[int, str]] = field(default_factory=dict)
    schemas: Dict[str, UsmapSchema] = field(default_factory=dict)

    def __init__(
        self,
        source: Union[str, bytes, BinaryIO, None] = None,
        budget: "ResourceBudget | None" = None,
        **kwargs: object,
    ):
        # 允许无参数构造（测试用）
        if source is None:
            for k, v in kwargs.items():
                setattr(self, k, v)
            return

        # 从文件路径加载
        if isinstance(source, str):
            path: str = source
            lower = path.lower()
            if lower.endswith(".jmap") or lower.endswith(".jmap.gz"):
                self._load_jmap(path, budget=budget)
                return
            if not lower.endswith(".usmap"):
                raise ParseError(f"不支持的映射文件类型: {path}")
            with open(path, "rb") as fh:
                data = fh.read()
            if lower.endswith(".gz"):
                if budget is not None:
                    budget.reserve(os.path.getsize(path), "usmap_gzip_decompress")
                data = gzip.decompress(data)
        elif isinstance(source, bytes):
            data = source
        else:
            data = source.read()

        result = _parse_usmap_data(data, budget=budget)
        self.version = result.version
        self.name_table = result.name_table
        self.enums = result.enums
        self.schemas = result.schemas

    def _load_jmap(self, path: str, budget: "ResourceBudget | None" = None) -> None:
        """加载 .jmap/.jmap.gz JSON 映射文件。"""
        with open(path, "rb") as fh:
            data = fh.read()
        if path.lower().endswith(".gz"):
            if budget is not None:
                budget.reserve(os.path.getsize(path), "usmap_jmap_gzip_decompress")
            data = gzip.decompress(data)
        root = json.loads(data.decode("utf-8"))
        self.name_table = []
        self.enums = {}
        self.schemas = {}
        for full_name, obj in root.get("objects", {}).items():
            if not isinstance(obj, dict):
                continue
            short_name = full_name.split(".")[-1]
            obj_type = obj.get("type")
            if obj_type == "Enum":
                values: Dict[int, str] = {}
                for item in obj.get("names", []):
                    if isinstance(item, list) and len(item) >= 2:
                        values[int(item[1])] = str(item[0])
                self.enums[short_name] = values
            elif obj_type in {"Class", "ScriptStruct"}:
                properties: Dict[int, UsmapProperty] = {}
                idx = 0
                for prop in obj.get("properties", []):
                    if not isinstance(prop, dict):
                        continue
                    inner_src = prop.get("container") or prop.get("inner") or prop.get("key_prop")
                    value_src = prop.get("value_prop")
                    type_name = str(prop.get("type") or "Unknown")
                    inner = None
                    value = None
                    if isinstance(inner_src, dict):
                        inner = _jmap_prop_type(inner_src)
                    if isinstance(value_src, dict):
                        value = _jmap_prop_type(value_src)
                    array_dim = int(prop.get("array_dim") or 1)
                    p = UsmapProperty(
                        index=idx,
                        name=str(prop.get("name") or ""),
                        type_name=type_name,
                        struct_type=(prop.get("struct") or "").split(".")[-1] or None,
                        inner_type=inner,
                        value_type=value,
                        enum_name=(prop.get("enum") or "").split(".")[-1] or None,
                        array_dim=array_dim,
                    )
                    properties[idx] = p
                    idx += 1
                self.schemas[short_name] = UsmapSchema(
                    name=short_name,
                    super_type=(obj.get("super_struct") or "").split(".")[-1] or None,
                    serializable_count=len(properties),
                    property_count=len(properties),
                    properties=properties,
                )

    def get_schema(self, name: Optional[str]) -> Optional[UsmapSchema]:
        """按名称获取 schema，支持短名和全限定名。"""
        if not name:
            return None
        short = name.split(".")[-1]
        return self.schemas.get(short) or self.schemas.get(name)

    def find_property(self, struct_name: str, prop_name: str) -> Optional[UsmapProperty]:
        """在结构体及其父类链中查找属性。"""
        seen: set = set()
        current = self.get_schema(struct_name)
        while current is not None and current.name not in seen:
            seen.add(current.name)
            for prop in current.properties.values():
                if prop.name.lower() == prop_name.lower():
                    return prop
            current = self.get_schema(current.super_type)
        return None


def _jmap_prop_type(prop: Dict[str, object], depth: int = 0) -> UsmapProperty:
    """从 jmap 属性 dict 构建 UsmapProperty（递归）。"""
    _MAX_JMAP_RECURSION = 64
    if depth > _MAX_JMAP_RECURSION:
        raise ValueError(f"jmap 属性递归深度超过限制 ({_MAX_JMAP_RECURSION})")

    type_name = str(prop.get("type") or "Unknown")
    inner_src = prop.get("container") or prop.get("inner") or prop.get("key_prop")
    value_src = prop.get("value_prop")
    inner = _jmap_prop_type(inner_src, depth + 1) if isinstance(inner_src, dict) else None
    value = _jmap_prop_type(value_src, depth + 1) if isinstance(value_src, dict) else None
    return UsmapProperty(
        index=0,
        name="",
        type_name=type_name,
        struct_type=(prop.get("struct") or "").split(".")[-1] or None,
        inner_type=inner,
        value_type=value,
        enum_name=(prop.get("enum") or "").split(".")[-1] or None,
    )


def parse_usmap(source: Union[str, bytes, BinaryIO],
                budget: "ResourceBudget | None" = None) -> UsmapData:
    """解析 .usmap 或 .jmap 文件。

    Args:
        source: 文件路径、bytes 数据或可读二进制流
        budget: 可选资源预算

    Returns:
        UsmapData 解析结果

    Raises:
        ParseError: 文件格式错误或不支持的版本
    """
    return UsmapData(source, budget=budget)
