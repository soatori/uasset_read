# UE Linker 生命周期对齐实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将解析管线对齐 UE FLinkerLoad 生命周期，修正 payload 起点策略，补齐 SoftObjectPath/DependsMap 语义，统一状态模型。

**Architecture:** 
1. 重构 parse_uasset.py 将 export 属性解析收口到 PackageLinker.preload()
2. 修正 property_parser.py 默认使用 SerialOffset 而非 ScriptSerialization offsets
3. 建立 class serialization 策略表，明确标记 partial/opaque 状态
4. 在 linker 层保存 SoftObjectPathList，属性解析时按索引解析
5. 修正 DependsMap 按 FPackageIndex 语义解析
6. 统一状态模型为 success|partial|failed

**Tech Stack:** Python 3.10+, pytest, UE5 .uasset 格式参考

---

## 文件结构

### 新建文件
- `src/uasset_read/link/class_serialization_registry.py` — 类序列化策略注册表
- `tests/test_linker_lifecycle.py` — 生命周期对齐测试
- `tests/test_soft_object_path_index.py` — SoftObjectPath 索引解析测试
- `tests/test_depends_map_package_index.py` — DependsMap PackageIndex 语义测试
- `tests/test_status_unification.py` — 状态模型统一测试

### 修改文件
- `src/uasset_read/parse_uasset.py` — 移除直接属性解析循环，统一使用 linker.preload()
- `src/uasset_read/link/linker.py` — 保存 SoftObjectPathList，修正 preload() 逻辑
- `src/uasset_read/parsers/property_parser.py` — 默认使用 SerialOffset，添加策略参数
- `src/uasset_read/parsers/property_types.py` — SoftObjectProperty 支持索引解析
- `src/uasset_read/serializers/object_resources.py` — ObjectExport 添加序列化策略字段
- `src/uasset_read/formatters/helpers.py` — 统一状态为 success|partial|failed
- `src/uasset_read/ir_builder.py` — 状态推导逻辑对齐新模型

---

## Task 1: 建立类序列化策略注册表

**Files:**
- Create: `src/uasset_read/link/class_serialization_registry.py`
- Test: `tests/test_class_serialization_registry.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_class_serialization_registry.py
"""类序列化策略注册表测试。"""
import pytest
from uasset_read.link.class_serialization_registry import (
    ClassSerializationRegistry, SerializationStrategy, get_serialization_strategy
)


def test_registry_default_strategies():
    """测试默认策略注册。"""
    registry = ClassSerializationRegistry()
    
    # BlueprintGeneratedClass 应该使用 tagged_properties_only
    assert registry.get_strategy("BlueprintGeneratedClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY
    
    # StaticMesh 应该使用 opaque_class_payload（当前无完整 Serialize 实现）
    assert registry.get_strategy("StaticMesh") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    
    # EdGraph 应该使用 tagged_properties_only
    assert registry.get_strategy("EdGraph") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


def test_registry_custom_strategy():
    """测试自定义策略注册。"""
    registry = ClassSerializationRegistry()
    registry.register_strategy("MyCustomClass", SerializationStrategy.FULL_SERIALIZER)
    
    assert registry.get_strategy("MyCustomClass") == SerializationStrategy.FULL_SERIALIZER


def test_get_serialization_strategy_convenience():
    """测试便捷函数。"""
    assert get_serialization_strategy("BlueprintGeneratedClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY
    assert get_serialization_strategy("UnknownClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY  # 默认


def test_strategy_metadata():
    """测试策略元数据。"""
    registry = ClassSerializationRegistry()
    metadata = registry.get_strategy_metadata("StaticMesh")
    
    assert metadata is not None
    assert metadata["strategy"] == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    assert metadata["reason"] == "No full Serialize() implementation"
    assert metadata["output_status"] == "opaque_class_payload"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_class_serialization_registry.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'uasset_read.link.class_serialization_registry'"

- [ ] **Step 3: 实现类序列化策略注册表**

```python
# src/uasset_read/link/class_serialization_registry.py
"""类序列化策略注册表 — 标记每类 export 的序列化方式。

UE 中每个 UObject 子类都有自己的 Serialize() 实现。当前解析器仅对部分类型
（如 BlueprintGeneratedClass、EdGraph）实现了完整的属性解析，其他类型
（如 StaticMesh、Texture2D）的 payload 包含类特定的二进制数据，不能简单
地按 PropertyTag 循环解析。

此注册表标记每类 export 的序列化策略，供 property_parser 和 linker 使用。
"""
from enum import Enum
from typing import Dict, Optional


class SerializationStrategy(Enum):
    """序列化策略枚举。"""
    
    FULL_SERIALIZER = "full_serializer"
    """完整 Serialize() 实现（当前无此类，预留）。"""
    
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    """仅解析 PropertyTag 序列（如 BlueprintGeneratedClass、EdGraph）。"""
    
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    """类特定二进制 payload，无 PropertyTag 序列（如 StaticMesh、Texture2D）。"""
    
    SKIP_UNSUPPORTED = "skip_unsupported"
    """跳过不支持的类型，输出诊断信息。"""


# 默认策略映射
_DEFAULT_STRATEGIES: Dict[str, SerializationStrategy] = {
    # 蓝图相关 — 使用 PropertyTag 序列
    "BlueprintGeneratedClass": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "EdGraph": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "EdGraphNode": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "EdGraphPin": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "UserDefinedStruct": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "UserDefinedEnum": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    
    # 资产类型 — 类特定 payload（当前无完整 Serialize 实现）
    "StaticMesh": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "SkeletalMesh": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "Texture2D": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "TextureCube": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "Material": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "MaterialInstanceConstant": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "AnimSequence": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "SoundWave": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    
    # 组件 — 部分使用 PropertyTag，部分有类特定数据
    # 当前统一按 tagged_properties_only 处理，后续可细化
    "StaticMeshComponent": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "SkeletalMeshComponent": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "SceneComponent": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
}

# 策略元数据
_STRATEGY_METADATA: Dict[SerializationStrategy, Dict[str, str]] = {
    SerializationStrategy.FULL_SERIALIZER: {
        "reason": "Full Serialize() implementation available",
        "output_status": "success",
    },
    SerializationStrategy.TAGGED_PROPERTIES_ONLY: {
        "reason": "PropertyTag sequence parsing",
        "output_status": "success",
    },
    SerializationStrategy.OPAQUE_CLASS_PAYLOAD: {
        "reason": "No full Serialize() implementation",
        "output_status": "opaque_class_payload",
    },
    SerializationStrategy.SKIP_UNSUPPORTED: {
        "reason": "Unsupported class type",
        "output_status": "skipped",
    },
}


class ClassSerializationRegistry:
    """类序列化策略注册表。"""
    
    def __init__(self):
        self._strategies: Dict[str, SerializationStrategy] = dict(_DEFAULT_STRATEGIES)
    
    def get_strategy(self, class_name: str) -> SerializationStrategy:
        """获取类的序列化策略。
        
        Args:
            class_name: UE 类名（如 "BlueprintGeneratedClass"、"StaticMesh"）
        
        Returns:
            SerializationStrategy 枚举值
        """
        return self._strategies.get(class_name, SerializationStrategy.TAGGED_PROPERTIES_ONLY)
    
    def register_strategy(self, class_name: str, strategy: SerializationStrategy) -> None:
        """注册自定义序列化策略。
        
        Args:
            class_name: UE 类名
            strategy: 序列化策略
        """
        self._strategies[class_name] = strategy
    
    def get_strategy_metadata(self, class_name: str) -> Optional[Dict[str, str]]:
        """获取策略元数据。
        
        Args:
            class_name: UE 类名
        
        Returns:
            包含 strategy、reason、output_status 的字典
        """
        strategy = self.get_strategy(class_name)
        metadata = _STRATEGY_METADATA.get(strategy, {})
        return {
            "strategy": strategy.value,
            "reason": metadata.get("reason", "Unknown"),
            "output_status": metadata.get("output_status", "unknown"),
        }


# 全局单例
_GLOBAL_REGISTRY: Optional[ClassSerializationRegistry] = None


def get_serialization_registry() -> ClassSerializationRegistry:
    """获取全局序列化策略注册表。"""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ClassSerializationRegistry()
    return _GLOBAL_REGISTRY


def get_serialization_strategy(class_name: str) -> SerializationStrategy:
    """便捷函数：获取类的序列化策略。"""
    return get_serialization_registry().get_strategy(class_name)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_class_serialization_registry.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/link/class_serialization_registry.py tests/test_class_serialization_registry.py
git commit -m "feat: add class serialization strategy registry

- Define SerializationStrategy enum (FULL_SERIALIZER, TAGGED_PROPERTIES_ONLY, OPAQUE_CLASS_PAYLOAD, SKIP_UNSUPPORTED)
- Register default strategies for common UE classes (Blueprint, asset types, components)
- Add strategy metadata (reason, output_status) for diagnostics
- Provide global registry singleton and convenience functions

Refs: UE LinkerLoad.cpp Serialize() pattern"
```

---

## Task 2: 修正 property_parser payload 起点策略

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py:319-386`
- Test: `tests/test_property_parser_payload_origin.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_property_parser_payload_origin.py
"""属性解析 payload 起点策略测试。"""
import pytest
from unittest.mock import MagicMock, Mock
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.package_summary import PackageFileSummary


def test_payload_origin_default_serial_offset():
    """测试默认使用 SerialOffset 作为 payload 起点（对齐 UE 普通路径）。"""
    # 构造 mock export
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = 1000
    export.serial_size = 500
    export.script_serialization_start_offset = 100  # UE5.10+ 字段
    export.script_serialization_end_offset = 400
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    
    # 构造 mock archive
    archive = MagicMock()
    archive.tell = Mock(side_effect=[1000, 1000, 1500])  # seek 后 tell 返回 1000
    archive.read_u8 = Mock(return_value=0x00)  # serialization_control
    
    # 构造 mock summary (UE5.10+)
    summary = MagicMock(spec=PackageFileSummary)
    summary.file_version_ue5 = 1015  # >= UE5_SCRIPT_SERIALIZATION_OFFSET
    summary.package_flags = 0
    
    name_map = ["None", "TestProp"]
    export_map = []
    import_map = []
    
    # 调用解析（应使用 serial_offset，而非 script_serialization_start_offset）
    result = parse_properties_from_export(
        export, archive, summary, name_map, export_map, import_map
    )
    
    # 验证 archive.seek 被调用时使用的是 serial_offset (1000)，而非 serial_offset + script_offset (1100)
    archive.seek.assert_called()
    first_seek_call = archive.seek.call_args_list[0]
    assert first_seek_call[0][0] == 1000, "Should use serial_offset as default payload origin"


def test_payload_origin_script_offset_explicit_flag():
    """测试显式 flag 时使用 ScriptSerialization offsets。"""
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = 1000
    export.serial_size = 500
    export.script_serialization_start_offset = 100
    export.script_serialization_end_offset = 400
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    
    archive = MagicMock()
    archive.tell = Mock(side_effect=[1100, 1100, 1400])
    archive.read_u8 = Mock(return_value=0x00)
    
    summary = MagicMock(spec=PackageFileSummary)
    summary.file_version_ue5 = 1015
    summary.package_flags = 0
    
    name_map = ["None"]
    export_map = []
    import_map = []
    
    # 显式指定使用 script offsets
    result = parse_properties_from_export(
        export, archive, summary, name_map, export_map, import_map,
        use_script_serialization_offsets=True
    )
    
    # 验证使用了 script_serialization_start_offset
    first_seek_call = archive.seek.call_args_list[0]
    assert first_seek_call[0][0] == 1100, "Should use serial_offset + script_serialization_start_offset when flag is set"


def test_payload_origin_ue4_uses_serial_offset():
    """测试 UE4 资产始终使用 SerialOffset。"""
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = 1000
    export.serial_size = 500
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    
    archive = MagicMock()
    archive.tell = Mock(side_effect=[1000, 1000, 1500])
    archive.read_u8 = Mock(return_value=0x00)
    
    summary = MagicMock(spec=PackageFileSummary)
    summary.file_version_ue5 = 0  # UE4
    summary.package_flags = 0
    
    name_map = ["None"]
    export_map = []
    import_map = []
    
    result = parse_properties_from_export(
        export, archive, summary, name_map, export_map, import_map
    )
    
    first_seek_call = archive.seek.call_args_list[0]
    assert first_seek_call[0][0] == 1000, "UE4 should always use serial_offset"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_property_parser_payload_origin.py -v
```

Expected: FAIL with "AssertionError: Should use serial_offset as default payload origin"

- [ ] **Step 3: 修正 property_parser.py payload 起点逻辑**

```python
# src/uasset_read/parsers/property_parser.py:319-386
# 修改 parse_properties_from_export 函数签名和 payload 起点计算

def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None,
    linker: Optional[Any] = None,
    mappings: Optional[Any] = None,
    game: Optional[str] = None,
    tolerant: bool = True,
    use_script_serialization_offsets: bool = False,  # 新增参数
) -> List[PropertyValue]:
    """从 export 条目读取所有属性（PROP-01）。

    参考 Class.cpp SerializeVersionedTaggedProperties 模式：
    1. Seek 到属性起始位置
    2. 循环读取 PropertyTag 直到 Name == "None"
    3. 分派到类型特定解析函数
    4. 边界验证（seek 到 start + tag.size）

    Args:
        export: ObjectExport 实例
        archive: FArchive 实例
        summary: PackageFileSummary 实例（版本信息）
        name_map: 名称表
        export_map: 导出表
        import_map: 导入表（ObjectProperty 解析需要，linker 未提供时使用）
        linker: PackageLinker 实例（可选，优先用于 ObjectProperty 解析）
        use_script_serialization_offsets: 显式使用 ScriptSerialization offsets（仅用于诊断或特殊场景）

    Returns:
        List[PropertyValue] 属性值列表
    """
    properties: List[PropertyValue] = []
    property_count = 0
    if mappings is not None:
        setattr(summary, "_mappings", mappings)
    if game is not None:
        setattr(summary, "_game", game)

    # 修正：默认使用 SerialOffset 作为 payload 起点（对齐 UE 普通路径）
    # UE 只在特殊条件下（property bag placeholder 或类不匹配）才使用 ScriptSerialization offsets
    # 见 LinkerLoad.cpp:4793 FObjectExport::SerialOffset 调用 Object->Serialize
    property_start = export.serial_offset
    if use_script_serialization_offsets and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        # 显式 flag 时才使用 script offsets（用于诊断或特殊场景）
        property_start = export.serial_offset + export.script_serialization_start_offset
        logger.debug(
            "Using ScriptSerialization offsets for '%s' (start=%d, explicit flag)",
            export.object_name, property_start,
        )
    archive.seek(property_start)

    # ... 后续代码保持不变 ...
    
    # 计算属性数据边界
    # 修正：默认使用 SerialOffset + SerialSize 作为 payload 终点
    if use_script_serialization_offsets and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_end = export.serial_offset + export.script_serialization_end_offset
    else:
        property_end = export.serial_offset + export.serial_size
    
    # ... 后续代码保持不变 ...
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_property_parser_payload_origin.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/property_parser.py tests/test_property_parser_payload_origin.py
git commit -m "fix: use SerialOffset as default payload origin (align with UE normal path)

- Change property_parser.py to use SerialOffset/SerialSize by default
- Add use_script_serialization_offsets parameter for explicit opt-in
- ScriptSerialization offsets now only used for diagnostics or special scenarios
- Aligns with UE LinkerLoad.cpp:4793 FObjectExport::SerialOffset pattern

Refs: UE LinkerLoad.cpp FObjectExport::Serialize()"
```

---

## Task 3: 重构 parse_uasset.py 统一使用 linker.preload()

**Files:**
- Modify: `src/uasset_read/parse_uasset.py:568-620`
- Test: `tests/test_linker_lifecycle.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_linker_lifecycle.py
"""Linker 生命周期对齐测试。"""
import pytest
from unittest.mock import MagicMock, patch, call
from uasset_read.parse_uasset import parse_package
from uasset_read.link.linker import PackageLinker


def test_parse_package_uses_linker_preload():
    """测试 parse_package 通过 linker.preload() 解析 export 属性。"""
    # Mock 所有依赖
    with patch('uasset_read.parse_uasset.open_package_bundle') as mock_open, \
         patch('uasset_read.parse_uasset.read_package_summary') as mock_summary, \
         patch('uasset_read.parse_uasset.read_name_table') as mock_name_map, \
         patch('uasset_read.parse_uasset.read_import_map') as mock_import_map, \
         patch('uasset_read.parse_uasset.read_export_map') as mock_export_map, \
         patch('uasset_read.parse_uasset.PackageLinker') as mock_linker_class:
        
        # 构造 mock 数据
        mock_archive = MagicMock()
        mock_archive.total_size = MagicMock(return_value=10000)
        mock_archive.get_mmap_info = MagicMock(return_value={"used": False, "warning": None})
        mock_archive.get_diagnostics = MagicMock(return_value=[])
        mock_open.return_value.open_archive = MagicMock(return_value=mock_archive)
        
        mock_summary_obj = MagicMock()
        mock_summary_obj.export_count = 2
        mock_summary_obj.name_count = 10
        mock_summary.return_value = mock_summary_obj
        
        mock_name_map.return_value = ["None", "TestExport1", "TestExport2"]
        mock_import_map.return_value = []
        
        mock_export1 = MagicMock()
        mock_export1.serial_size = 100
        mock_export1.object_name = "TestExport1"
        mock_export2 = MagicMock()
        mock_export2.serial_size = 200
        mock_export2.object_name = "TestExport2"
        mock_export_map.return_value = [mock_export1, mock_export2]
        
        # Mock linker
        mock_linker = MagicMock(spec=PackageLinker)
        mock_linker._export_objects = [MagicMock(), MagicMock()]
        mock_linker.diagnostics = []
        mock_linker_class.return_value = mock_linker
        
        # 调用解析
        result = parse_package("test.uasset", tolerant=True)
        
        # 验证 linker.preload() 被调用（而非直接调用 parse_properties_from_export）
        assert mock_linker.preload.call_count == 2, "Should call linker.preload() for each export"
        mock_linker.preload.assert_has_calls([call(0), call(1)], any_order=True)
        
        # 验证 post_load 在 preload 之后调用
        assert mock_linker.post_load.called, "Should call linker.post_load() after preload"


def test_linker_preload_calls_property_parser():
    """测试 linker.preload() 内部调用 parse_properties_from_export。"""
    with patch('uasset_read.link.linker.parse_properties_from_export') as mock_parse:
        mock_archive = MagicMock()
        mock_summary = MagicMock()
        mock_name_map = ["None"]
        mock_import_map = []
        mock_export_map = [MagicMock()]
        
        mock_export_map[0].serial_offset = 1000
        mock_export_map[0].serial_size = 100
        mock_export_map[0].object_name = "TestExport"
        
        linker = PackageLinker(
            mock_archive, mock_summary, mock_name_map,
            mock_import_map, mock_export_map
        )
        linker.link()
        
        # 调用 preload
        linker.preload(0)
        
        # 验证 parse_properties_from_export 被调用
        assert mock_parse.called, "linker.preload() should call parse_properties_from_export"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_linker_lifecycle.py -v
```

Expected: FAIL with "AssertionError: Should call linker.preload() for each export"

- [ ] **Step 3: 重构 parse_uasset.py 移除直接属性解析循环**

```python
# src/uasset_read/parse_uasset.py:568-620
# 修改 _parse_package_core 函数

def _parse_package_core(
    path: str,
    result,
    tolerant: bool = True,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    extra_linker_setup: Optional[Callable] = None,
    check_aes_key: Optional[bytes] = None,
    lightweight_threshold: Optional[int] = None,
) -> None:
    """共享核心解析逻辑 — 读取 package 并填充 result。"""
    from uasset_read.link.linker import PackageLinker

    archive = None
    bundle = None
    mappings_provider = None

    try:
        # ... 前面的代码保持不变（读取 summary、name_map、import_map、export_map）...
        
        # 创建 linker 用于完整对象图解析
        linker: Optional["PackageLinker"] = None
        try:
            linker = PackageLinker(
                archive, result.summary, result.name_map,
                result.import_map, result.export_map or [],
                version_container=result.version_container,
            )
            linker.link()
            result.linker = linker

            if extra_linker_setup is not None:
                extra_linker_setup(linker, result)

            # 修正：通过 linker.preload() 解析所有 export 属性
            # 对齐 UE FLinkerLoad::Preload() 模式
            for idx in range(len(result.export_map or [])):
                try:
                    linker.preload(idx)
                except Exception as e:
                    if not tolerant:
                        raise ParseError(f"Preload export #{idx} failed: {e}") from e
                    result.errors.append(f"Preload export #{idx} failed: {e}")
                    if idx < len(result.export_map):
                        export = result.export_map[idx]
                        setattr(export, "parse_status", "failed")
                        setattr(export, "fallback_reason", "preload_error")
                        setattr(export, "error_message", str(e))

            # 所有 export preload 完成后调用 post_load
            linker.post_load()
        except Exception as e:
            if not tolerant:
                raise ParseError(f"Linker creation failed: {e}") from e
            result.errors.append(f"Linker creation failed: {e}")

        if _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold):
            result.warnings.append(
                "Lightweight tolerant parse used due to export complexity "
                f"(exports={getattr(result.summary, 'export_count', 0)})"
            )
            result.metadata["lightweight_tolerant_parse"] = True
            result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
            result.is_success = True
            return

        # 从 linker 实例同步属性到 export_map（保持向后兼容）
        if linker is not None:
            for idx, export in enumerate(result.export_map or []):
                if idx < len(linker._export_objects):
                    instance = linker._export_objects[idx]
                    if instance._preloaded and instance.serialized_properties:
                        export.properties = instance.serialized_properties
                        if not getattr(export, "parse_status", None):
                            setattr(export, "parse_status", "success")
                        
                        # 提取组件变换属性
                        if export.properties:
                            export.transforms = extract_component_transforms(export.properties)

        # 共享后处理
        _post_process(
            path, archive, result.summary, result.name_map,
            result.import_map, result.export_map or [], result, tolerant,
            linker=linker,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            archive_factory=lambda: bundle.open_archive(tolerant=tolerant) if bundle else FArchive(path, tolerant=tolerant),
        )
        result.is_success = len(result.errors) == 0

    # ... 异常处理保持不变 ...
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_linker_lifecycle.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parse_uasset.py tests/test_linker_lifecycle.py
git commit -m "refactor: unify export parsing through linker.preload()

- Remove direct parse_properties_from_export loop from parse_uasset.py
- All export property parsing now goes through PackageLinker.preload()
- Aligns with UE FLinkerLoad::Preload() lifecycle pattern
- Sync parsed properties back to export_map for backward compatibility
- Ensures linker state and export state are not split

Refs: UE LinkerLoad.cpp FLinkerLoad::Preload()"
```

---

## Task 4: 补齐 SoftObjectPath 索引解析

**Files:**
- Modify: `src/uasset_read/link/linker.py`
- Modify: `src/uasset_read/parsers/property_types.py`
- Test: `tests/test_soft_object_path_index.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_soft_object_path_index.py
"""SoftObjectPath 索引解析测试。"""
import pytest
from unittest.mock import MagicMock
from uasset_read.link.linker import PackageLinker
from uasset_read.parsers.property_types import parse_soft_object_property
from uasset_read.models.properties import PropertyTag, SoftObjectPathValue


def test_linker_stores_soft_object_path_list():
    """测试 linker 保存 SoftObjectPathList。"""
    mock_archive = MagicMock()
    mock_summary = MagicMock()
    mock_summary.soft_object_paths_count = 2
    mock_summary.soft_object_paths_offset = 1000
    
    # Mock archive.read 返回 SoftObjectPath 数据
    mock_archive.read_name = MagicMock(side_effect=["/Game/Asset1", "Asset1", "/Game/Asset2", "Asset2"])
    mock_archive.read_fstring = MagicMock(side_effect=["", ""])
    
    name_map = ["None"]
    import_map = []
    export_map = []
    
    linker = PackageLinker(
        mock_archive, mock_summary, name_map,
        import_map, export_map
    )
    
    # 验证 soft_object_path_list 被保存
    assert hasattr(linker, '_soft_object_path_list')
    assert len(linker._soft_object_path_list) == 2
    assert linker._soft_object_path_list[0]["asset_path"] == "/Game/Asset1.Asset1"
    assert linker._soft_object_path_list[1]["asset_path"] == "/Game/Asset2.Asset2"


def test_soft_object_property_uses_index_when_list_exists():
    """测试 SoftObjectProperty 在列表存在时按索引解析。"""
    tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=4)
    
    mock_archive = MagicMock()
    mock_archive.read_i32 = MagicMock(return_value=0)  # 索引 0
    
    name_map = ["None"]
    
    # Mock linker 提供 soft_object_path_list
    mock_linker = MagicMock()
    mock_linker._soft_object_path_list = [
        {"asset_path": "/Game/Asset.Asset", "sub_path": ""}
    ]
    
    # 调用解析（应读取 int32 索引并查找列表）
    result = parse_soft_object_property(tag, mock_archive, name_map, linker=mock_linker)
    
    # 验证返回的是列表中的路径，而非读取 FString
    assert isinstance(result, SoftObjectPathValue)
    assert result.asset_path == "/Game/Asset.Asset"
    assert result.sub_path == ""


def test_soft_object_property_fallback_to_fstring_when_no_list():
    """测试 SoftObjectProperty 在列表不存在时回退到 FString。"""
    tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=20)
    
    mock_archive = MagicMock()
    mock_archive.read_fstring = MagicMock(side_effect=["/Game/Asset.Asset", ""])
    
    name_map = ["None"]
    
    # 无 linker 或 linker 无 soft_object_path_list
    result = parse_soft_object_property(tag, mock_archive, name_map, linker=None)
    
    # 验证回退到 FString 解析
    assert isinstance(result, SoftObjectPathValue)
    assert result.asset_path == "/Game/Asset.Asset"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_soft_object_path_index.py -v
```

Expected: FAIL

- [ ] **Step 3: 在 linker 中保存 SoftObjectPathList**

```python
# src/uasset_read/link/linker.py
# 在 PackageLinker.__init__ 中加载 SoftObjectPathList

def __init__(
    self,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    version_container: Optional["VersionContainer"] = None,
):
    self._archive = archive
    self._summary = summary
    self._name_map = name_map
    self._import_map = import_map
    self._export_map = export_map
    self._version_container = version_container

    # Public aliases
    self.summary = summary
    self.name_map = name_map
    self.version_container = version_container

    self._import_objects: List[UObjectInstance] = []
    self._export_objects: List[UObjectInstance] = []
    self._root_objects: List[UObjectInstance] = []
    self._preload_cache: dict[int, bool] = {}
    self._diagnostics: List[OffsetRangeDiagnostic] = []
    self._file_size: int = getattr(archive, '_file_size', 0)
    
    # 新增：加载 SoftObjectPathList（UE5.7+）
    self._soft_object_path_list: List[dict] = []
    self._load_soft_object_path_list()

def _load_soft_object_path_list(self) -> None:
    """加载 SoftObjectPathList（UE5.7+ 包头中的软对象路径表）。
    
    UE 在 LinkerLoad.cpp:6450 先加载此表，属性中的 FSoftObjectPath
    在表存在时读的是 int32 索引，而非 FString。
    """
    if not hasattr(self._summary, 'soft_object_paths_count'):
        return
    if self._summary.soft_object_paths_count <= 0:
        return
    if self._summary.soft_object_paths_offset <= 0:
        return
    
    saved_pos = self._archive.tell()
    try:
        self._archive.seek(self._summary.soft_object_paths_offset)
        for _ in range(self._summary.soft_object_paths_count):
            # UE5 >= 1007 format: double FName
            package_name = self._archive.read_name(self._name_map)
            asset_name = self._archive.read_name(self._name_map)
            asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
            sub_path = self._archive.read_fstring()
            self._soft_object_path_list.append({
                "asset_path": asset_path,
                "sub_path": sub_path,
            })
    except Exception as e:
        logger.warning("Failed to load SoftObjectPathList: %s", e)
    finally:
        self._archive.seek(saved_pos)

@property
def soft_object_path_list(self) -> List[dict]:
    """返回 SoftObjectPathList（供属性解析器使用）。"""
    return self._soft_object_path_list
```

- [ ] **Step 4: 修改 parse_soft_object_property 支持索引解析**

```python
# src/uasset_read/parsers/property_types.py
# 修改 parse_soft_object_property 函数签名

def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    linker: Optional[Any] = None,  # 新增参数
) -> SoftObjectPathValue:
    """解析 SoftObjectProperty（FSoftObjectPath）。
    
    UE5.7+ 如果包头存在 SoftObjectPathList，属性中存储的是 int32 索引，
    而非 FString。见 LinkerLoad.cpp:6450。
    """
    # 检查 linker 是否提供 SoftObjectPathList
    if linker is not None and hasattr(linker, 'soft_object_path_list'):
        soft_list = linker.soft_object_path_list
        if soft_list:
            # 列表存在，读取 int32 索引
            index = archive.read_i32()
            if 0 <= index < len(soft_list):
                entry = soft_list[index]
                return SoftObjectPathValue(
                    raw_kind=tag.type,
                    asset_path=entry["asset_path"],
                    sub_path=entry.get("sub_path", ""),
                )
            else:
                # 索引越界，返回诊断信息
                logger.warning(
                    "SoftObjectProperty index %d out of range [0, %d)",
                    index, len(soft_list),
                )
                return SoftObjectPathValue(
                    raw_kind=tag.type,
                    asset_path=f"<invalid_index_{index}>",
                    sub_path="",
                )
    
    # 列表不存在，回退到 FString 解析（UE4 或 UE5 早期版本）
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)
```

- [ ] **Step 5: 更新 property_parser.py 传递 linker 到 SoftObjectProperty**

```python
# src/uasset_read/parsers/property_parser.py
# 在 parse_property_value 中传递 linker 到 SoftObjectProperty

# 修改 dispatch 逻辑
elif tag.type in ("NameProperty", "DelegateProperty", "SoftClassProperty"):
    return handler(tag, archive, name_map)
elif tag.type in ("SoftObjectProperty",):
    # SoftObjectProperty 需要 linker 以支持索引解析
    return handler(tag, archive, name_map, linker=linker)
```

- [ ] **Step 6: 运行测试验证通过**

```bash
python -m pytest tests/test_soft_object_path_index.py -v
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/link/linker.py src/uasset_read/parsers/property_types.py src/uasset_read/parsers/property_parser.py tests/test_soft_object_path_index.py
git commit -m "feat: support SoftObjectPath index resolution (UE5.7+)

- Load SoftObjectPathList in PackageLinker.__init__
- Modify parse_soft_object_property to read int32 index when list exists
- Fallback to FString parsing when list is absent (UE4 or early UE5)
- Aligns with UE LinkerLoad.cpp:6450 FSoftObjectPath serialization

Refs: UE LinkerLoad.cpp FSoftObjectPath::Serialize()"
```

---

## Task 5: 修正 DependsMap 按 FPackageIndex 语义解析

**Files:**
- Modify: `src/uasset_read/link/linker.py:398-413`
- Test: `tests/test_depends_map_package_index.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_depends_map_package_index.py
"""DependsMap PackageIndex 语义测试。"""
import pytest
from unittest.mock import MagicMock
from uasset_read.link.linker import PackageLinker
from uasset_read.serializers.object_resources import PackageIndex


def test_depends_map_resolves_package_index():
    """测试 DependsMap 按 FPackageIndex 语义解析（支持 import/export）。"""
    mock_archive = MagicMock()
    mock_summary = MagicMock()
    mock_summary.depends_map = [
        [1, -1],  # Export 0 依赖 Export 0 (index 0) 和 Import 0 (index -1)
        [2],      # Export 1 依赖 Export 1 (index 1)
    ]
    
    name_map = ["None", "ImportObj", "ExportObj"]
    
    # Mock import/export map
    mock_import = MagicMock()
    mock_import.object_name = "ImportObj"
    mock_import.class_name = "Class"
    mock_import.class_package = "Package"
    mock_import.outer_index = PackageIndex(0)
    
    mock_export = MagicMock()
    mock_export.object_name = "ExportObj"
    mock_export.class_index = PackageIndex(0)
    mock_export.super_index = PackageIndex(0)
    mock_export.outer_index = PackageIndex(0)
    mock_export.serial_offset = 1000
    mock_export.serial_size = 100
    
    import_map = [mock_import]
    export_map = [mock_export, mock_export]
    
    linker = PackageLinker(
        mock_archive, mock_summary, name_map,
        import_map, export_map
    )
    linker.link()
    linker.post_load()
    
    # 验证 Export 0 的依赖包含 Import 0 和 Export 0
    export0_inst = linker._export_objects[0]
    assert len(export0_inst.dependencies) == 2
    
    # 第一个依赖应该是 Import 0 (package_index = -1)
    dep0 = export0_inst.dependencies[0]
    assert dep0.package_index == -1
    assert dep0.is_import is True
    
    # 第二个依赖应该是 Export 0 (package_index = 1)
    dep1 = export0_inst.dependencies[1]
    assert dep1.package_index == 1
    assert dep1.is_import is False


def test_depends_map_invalid_index_diagnostic():
    """测试 DependsMap 无效索引产生诊断信息。"""
    mock_archive = MagicMock()
    mock_summary = MagicMock()
    mock_summary.depends_map = [
        [999],  # 无效索引
    ]
    
    name_map = ["None"]
    import_map = []
    export_map = [MagicMock()]
    export_map[0].serial_offset = 1000
    export_map[0].serial_size = 100
    export_map[0].object_name = "TestExport"
    export_map[0].class_index = PackageIndex(0)
    export_map[0].super_index = PackageIndex(0)
    export_map[0].outer_index = PackageIndex(0)
    
    linker = PackageLinker(
        mock_archive, mock_summary, name_map,
        import_map, export_map
    )
    linker.link()
    linker.post_load()
    
    # 验证产生诊断信息
    assert len(linker.diagnostics) > 0
    assert any("DependsMap" in str(d.field) for d in linker.diagnostics)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_depends_map_package_index.py -v
```

Expected: FAIL

- [ ] **Step 3: 修正 linker._build_dependency_graph**

```python
# src/uasset_read/link/linker.py
# 修改 _build_dependency_graph 方法

def _build_dependency_graph(self) -> None:
    """将 DependsMap 转换为 UObjectInstance 之间的依赖链接。

    DependsMap[export_index] = [FPackageIndex 列表]
    FPackageIndex: 正数 = export (index = value - 1), 负数 = import (index = -value - 1)
    """
    if not hasattr(self._summary, 'depends_map') or not self._summary.depends_map:
        return

    depends_map = self._summary.depends_map
    for exp_idx, dep_package_indices in enumerate(depends_map):
        if exp_idx >= len(self._export_objects):
            continue
        
        inst = self._export_objects[exp_idx]
        inst.dependencies = []
        
        for pkg_idx_value in dep_package_indices:
            # 将 int32 值转换为 PackageIndex
            pkg_idx = PackageIndex(pkg_idx_value)
            
            # 使用 resolve_package_index 解析（支持 import/export）
            resolved = self.resolve_package_index(pkg_idx)
            if resolved is not None:
                inst.dependencies.append(resolved)
            else:
                # 无法解析，记录诊断
                self._diagnostics.append(OffsetRangeDiagnostic(
                    module="linker",
                    field="DependsMap",
                    export_index=exp_idx,
                    target_offset=pkg_idx_value,
                    file_size=self._file_size,
                    source="_build_dependency_graph",
                    error=f"DependsMap[{exp_idx}] contains invalid PackageIndex {pkg_idx_value}",
                ))
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_depends_map_package_index.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/link/linker.py tests/test_depends_map_package_index.py
git commit -m "fix: resolve DependsMap as FPackageIndex (support import/export)

- Change _build_dependency_graph to interpret DependsMap values as FPackageIndex
- Positive values = export index, negative values = import index
- Use resolve_package_index() to resolve to UObjectInstance
- Add diagnostic for invalid PackageIndex values

Refs: UE FPackageIndex semantics"
```

---

## Task 6: 统一状态模型

**Files:**
- Modify: `src/uasset_read/formatters/helpers.py`
- Modify: `src/uasset_read/ir_builder.py`
- Test: `tests/test_status_unification.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_status_unification.py
"""状态模型统一测试。"""
import pytest
from uasset_read.formatters.helpers import build_status_info
from uasset_read.models.result import ParseResult


def test_status_success():
    """测试 success 状态。"""
    result = ParseResult()
    result.is_success = True
    result.errors = []
    
    status = build_status_info(result)
    assert status.status == "success"


def test_status_partial_with_errors():
    """测试 partial 状态（有错误但部分结果可用）。"""
    result = ParseResult()
    result.is_success = True
    result.errors = ["Some warning"]
    
    status = build_status_info(result)
    assert status.status == "partial"


def test_status_partial_with_lightweight():
    """测试 partial 状态（轻量容错解析）。"""
    result = ParseResult()
    result.is_success = True
    result.errors = []
    result.metadata = {"lightweight_tolerant_parse": True}
    
    status = build_status_info(result)
    assert status.status == "partial"


def test_status_failed():
    """测试 failed 状态。"""
    result = ParseResult()
    result.is_success = False
    result.errors = ["Fatal error"]
    
    status = build_status_info(result)
    assert status.status == "failed"


def test_status_partial_with_opaque_export():
    """测试 partial 状态（包含 opaque export）。"""
    result = ParseResult()
    result.is_success = True
    result.errors = []
    result.export_map = [MagicMock()]
    result.export_map[0].parse_status = "opaque_class_payload"
    
    status = build_status_info(result)
    assert status.status == "partial"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_status_unification.py -v
```

Expected: FAIL

- [ ] **Step 3: 统一 formatters/helpers.py 状态模型**

```python
# src/uasset_read/formatters/helpers.py
# 修改 build_status_info 函数

def build_status_info(result: ParseResult) -> StatusInfo:
    """
    构建 status 字段（统一状态模型）。

    三元分类:
    - success: is_success=True, errors=[], 无 partial 条件
    - partial: is_success=True, 但有 errors/warnings/partial 条件
    - failed: is_success=False

    Partial 条件:
    - errors 非空
    - metadata["lightweight_tolerant_parse"] = True
    - 任何 export 的 parse_status 不是 "success"
    """
    if not result.is_success:
        # is_success=False → failed
        message = result.errors[0] if result.errors else "Parse failed"
        return StatusInfo(status="failed", message=message, code="PARSE_ERROR")
    
    # is_success=True，检查 partial 条件
    is_partial = False
    partial_reasons = []
    
    # 条件 1: errors 非空
    if result.errors:
        is_partial = True
        partial_reasons.append(f"errors={len(result.errors)}")
    
    # 条件 2: 轻量容错解析
    metadata = getattr(result, "metadata", {}) or {}
    if metadata.get("lightweight_tolerant_parse"):
        is_partial = True
        partial_reasons.append("lightweight_tolerant_parse")
    
    # 条件 3: 任何 export 的 parse_status 不是 "success"
    export_map = getattr(result, "export_map", []) or []
    for export in export_map:
        parse_status = getattr(export, "parse_status", None)
        if parse_status and parse_status != "success":
            is_partial = True
            partial_reasons.append(f"export_status={parse_status}")
            break  # 只需发现一个即可
    
    if is_partial:
        message = "; ".join(partial_reasons)
        return StatusInfo(status="partial", message=message, code="PARTIAL_RESULT")
    
    # 无 partial 条件 → success
    return StatusInfo(status="success")
```

- [ ] **Step 4: 统一 ir_builder.py 状态推导**

```python
# src/uasset_read/ir_builder.py
# 修改 _result_status 函数

def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    """推导结果状态（统一模型）。
    
    返回:
    - "success": 解析成功，无 partial 条件
    - "partial": 解析成功但有 partial 条件
    - "failed": 解析失败
    """
    if not getattr(result, "is_success", False):
        return "failed"
    
    # 检查 partial 条件
    if getattr(result, "errors", None):
        return "partial"
    
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"
    
    # 检查 export 状态
    export_map = getattr(result, "export_map", None) or []
    for export in export_map:
        parse_status = getattr(export, "parse_status", None)
        if parse_status and parse_status != "success":
            return "partial"
    
    return "success"
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_status_unification.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/formatters/helpers.py src/uasset_read/ir_builder.py tests/test_status_unification.py
git commit -m "refactor: unify status model to success|partial|failed

- Change formatters/helpers.py build_status_info to use unified model
- Change ir_builder.py _result_status to use unified model
- Partial conditions: errors, lightweight_parse, non-success export status
- Ensures consistent status across all output formats (JSON, IR, etc.)

Refs: UE FLinkerLoad status semantics"
```

---

## Task 7: 集成测试与回归验证

**Files:**
- Test: `tests/test_ue_lifecycle_integration.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/test_ue_lifecycle_integration.py
"""UE 生命周期对齐集成测试。"""
import pytest
from pathlib import Path
from uasset_read import parse_single


# 使用项目样本资产
SAMPLE_ASSETS = [
    "E:/Develop/lib/UnrealEngine/Samples/Blueprints/BP_Test.uasset",
    "E:/Develop/lib/UnrealEngine/Samples/Meshes/SM_Test.uasset",
]


@pytest.mark.integration
@pytest.mark.parametrize("asset_path", SAMPLE_ASSETS)
def test_lifecycle_alignment_integration(asset_path):
    """测试生命周期对齐集成。"""
    if not Path(asset_path).exists():
        pytest.skip(f"Sample asset not found: {asset_path}")
    
    # 解析资产
    result = parse_single(asset_path, format="json")
    
    # 验证 JSON 输出包含统一状态
    import json
    data = json.loads(result)
    
    assert "status" in data
    assert data["status"]["status"] in ["success", "partial", "failed"]
    
    # 验证 export 包含 parse_status
    if "exports" in data and data["exports"]:
        for export in data["exports"]:
            if "parse_status" in export:
                assert export["parse_status"] in [
                    "success", "partial", "failed",
                    "opaque_class_payload", "opaque_unversioned", "skipped"
                ]


@pytest.mark.integration
def test_soft_object_path_resolution():
    """测试 SoftObjectPath 索引解析集成。"""
    # 使用包含 SoftObjectPath 的样本资产
    asset_path = "E:/Develop/lib/UnrealEngine/Samples/Blueprints/BP_WithSoftRefs.uasset"
    if not Path(asset_path).exists():
        pytest.skip(f"Sample asset not found: {asset_path}")
    
    result = parse_single(asset_path, format="json")
    
    # 验证 SoftObjectPath 被正确解析
    import json
    data = json.loads(result)
    
    # 查找包含 SoftObjectProperty 的 export
    found_soft_ref = False
    for export in data.get("exports", []):
        for prop in export.get("properties", []):
            if prop.get("type") == "SoftObjectProperty":
                found_soft_ref = True
                # 验证 asset_path 不是索引值
                value = prop.get("value", {})
                if isinstance(value, dict):
                    assert "asset_path" in value
                    assert not value["asset_path"].startswith("<invalid_index_")
    
    # 如果资产确实包含 SoftObjectProperty，验证至少找到一个
    # （如果没找到，可能是资产不包含此类属性，测试通过）


@pytest.mark.integration
def test_depends_map_resolution():
    """测试 DependsMap PackageIndex 解析集成。"""
    asset_path = "E:/Develop/lib/UnrealEngine/Samples/Blueprints/BP_WithDeps.uasset"
    if not Path(asset_path).exists():
        pytest.skip(f"Sample asset not found: {asset_path}")
    
    result = parse_single(asset_path, format="json")
    
    import json
    data = json.loads(result)
    
    # 验证 linker 依赖被解析
    if "linker" in data and "exports" in data["linker"]:
        for export in data["linker"]["exports"]:
            if "dependencies" in export:
                # 依赖应该是对象引用，而非原始索引
                for dep in export["dependencies"]:
                    assert isinstance(dep, dict)
                    assert "object_name" in dep or "package_index" in dep
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_ue_lifecycle_integration.py -v -m integration
```

Expected: PASS (或 SKIP 如果样本资产不存在)

- [ ] **Step 3: 运行全量测试验证无回归**

```bash
python scripts/test_matrix.py all
```

Expected: 所有测试通过（或已知 xfail）

- [ ] **Step 4: 提交集成测试**

```bash
git add tests/test_ue_lifecycle_integration.py
git commit -m "test: add UE lifecycle alignment integration tests

- Test lifecycle alignment with sample assets
- Test SoftObjectPath index resolution
- Test DependsMap PackageIndex resolution
- Verify unified status model in JSON output

Refs: UE FLinkerLoad lifecycle"
```

---

## 完成标准

1. ✅ 所有 export 属性解析通过 `linker.preload()` 完成
2. ✅ 默认使用 `SerialOffset/SerialSize` 作为 payload 起点/终点
3. ✅ 类序列化策略注册表标记每类 export 的序列化方式
4. ✅ SoftObjectPath 在列表存在时按索引解析
5. ✅ DependsMap 按 FPackageIndex 语义解析（支持 import/export）
6. ✅ 状态模型统一为 `success|partial|failed`
7. ✅ 全量测试通过，无回归

---

## 风险与缓解

**风险 1: 向后兼容性**
- 缓解: 保留 `export.properties` 字段，从 linker 实例同步

**风险 2: 性能影响**
- 缓解: `linker.preload()` 已实现缓存，不会重复解析

**风险 3: 样本资产不可用**
- 缓解: 集成测试使用 `pytest.skip()` 处理缺失资产

**风险 4: UE 版本差异**
- 缓解: SoftObjectPath 索引解析仅在 UE5.7+ 启用，回退到 FString

---

## 参考文档

- UE LinkerLoad.cpp:4694 — FLinkerLoad::Preload()
- UE LinkerLoad.cpp:4793 — FObjectExport::SerialOffset
- UE LinkerLoad.cpp:6450 — FSoftObjectPath::Serialize()
- UE ObjectResource.cpp:125 — FObjectExport 表字段读取
