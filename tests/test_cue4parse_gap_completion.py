import gzip
import json
import struct
import zlib
from io import BytesIO
from pathlib import Path

import pytest

from uasset_read.archive import FArchive
from uasset_read.constants import (
    CPF_BlueprintCallable,
    CPF_Net,
    CPF_NoClear,
    PKG_UnversionedProperties,
    PROP_TAG_HAS_BINARY_OR_NATIVE,
    PROP_TAG_SKIPPED_SERIALIZE,
)
from uasset_read.mappings import JmapParser, PropertyInfo, PropertyType, StructMapping, TypeMappings, UsmapParser
from uasset_read.models.properties import MapValue, PropertyTag, SetValue, SoftObjectPathValue
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.iostore.structures import FIoChunkId, FIoStoreTocCompressedBlockEntry
from uasset_read.objects.exports.material import UMaterialInstance
from uasset_read.objects.exports.mesh import UStaticMesh
from uasset_read.objects.exports.texture import UTexture2D
from uasset_read.serializers.graph import read_fmember_reference, read_pin_reference
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.pak.decompress import decompress_block, normalize_compression_method
from uasset_read.parsers.property_parser import parse_properties_from_export, parse_property_value
from uasset_read.parsers.property_types import (
    parse_asset_object_property,
    parse_lazy_object_property,
    parse_soft_object_property,
)
from uasset_read.serializers.property_tags import read_property_tag

pytestmark = pytest.mark.auxiliary


def _archive(tmp_path: Path, data: bytes) -> FArchive:
    path = tmp_path / "data.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=False)


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<II", index, number)


def _type_node(index: int, inner_count: int) -> bytes:
    return _fname(index) + struct.pack("<i", inner_count)


def test_recursive_property_type_name_and_binary_flags(tmp_path):
    name_map = ["MyMap", "MapProperty", "NameProperty", "ArrayProperty", "IntProperty"]
    value = b"abcd"
    data = (
        _fname(0)
        + _type_node(1, 2)
        + _type_node(2, 0)
        + _type_node(3, 1)
        + _type_node(4, 0)
        + struct.pack("<iB", len(value), PROP_TAG_HAS_BINARY_OR_NATIVE)
        + value
    )
    ar = _archive(tmp_path, data)
    # 使用 UE5 版本 >= 1012 的 mock summary 以触发新格式解析
    from unittest.mock import Mock
    mock_summary = Mock()
    mock_summary.file_version_ue5 = 1012
    tag = read_property_tag(ar, name_map, summary=mock_summary)

    assert tag.type == "MapProperty"
    assert tag.key_type == "NameProperty"
    assert tag.value_type == "ArrayProperty"
    assert tag.type_name.children[1].children[0].name == "IntProperty"
    assert tag.serialize_type == "BinaryOrNative"

    parsed = parse_property_value(tag, ar, name_map, [], None)
    assert parsed["kind"] == "binary_or_native_property"
    assert parsed["raw_data"] == value


def test_skipped_property_reads_bounded_raw(tmp_path):
    tag = PropertyTag(name="Skipped", type="IntProperty", size=3, flags=PROP_TAG_SKIPPED_SERIALIZE)
    tag.serialize_type = "Skipped"
    ar = _archive(tmp_path, b"xyz")
    parsed = parse_property_value(tag, ar, [], [], None)
    assert parsed == {
        "kind": "skipped_property",
        "type": "IntProperty",
        "size": 3,
        "raw_data": b"xyz",
    }


def test_jmap_and_jmap_gz_minimal_parse(tmp_path):
    payload = {
        "objects": {
            "/Script/Game.EColor": {"type": "Enum", "names": [["Red", 1]]},
            "/Script/Game.MyStruct": {
                "type": "ScriptStruct",
                "properties": [
                    {
                        "name": "Items",
                        "type": "ArrayProperty",
                        "inner": {"type": "StructProperty", "struct": "/Script/Game.Inner"},
                    }
                ],
            },
        }
    }
    data = json.dumps(payload).encode("utf-8")
    jmap = JmapParser(data).mappings
    assert jmap.enums["EColor"][1] == "Red"
    assert jmap.types["MyStruct"].property_by_name("Items").mapping_type.inner_type.struct_type == "Inner"

    path = tmp_path / "mapping.jmap.gz"
    path.write_bytes(gzip.compress(data))
    gz = JmapParser(str(path)).mappings
    assert "MyStruct" in gz.types


def test_usmap_minimal_parse():
    names = [b"MyStruct", b"MyProp"]
    payload = struct.pack("<I", len(names))
    for name in names:
        payload += struct.pack("<H", len(name)) + name
    payload += struct.pack("<I", 0)  # enums
    payload += struct.pack("<I", 1)  # structs
    payload += struct.pack("<i", 0)  # struct name
    payload += struct.pack("<i", -1)  # super
    payload += struct.pack("<HH", 1, 1)
    payload += struct.pack("<HBiB", 0, 1, 1, 2)  # index, array_dim, name, IntProperty
    data = (
        struct.pack("<HB", 0x30C4, 4)
        + b"\x00"  # no versioning
        + b"\x00"  # no compression
        + struct.pack("<II", len(payload), len(payload))
        + payload
    )

    mappings = UsmapParser(data).mappings
    assert mappings.types["MyStruct"].property_by_name("MyProp").mapping_type.type == "IntProperty"


def test_borderlands4_custom_properties(tmp_path):
    class Summary:
        _game = "Borderlands4"

    name_map = ["Def", "CustomProperty_FD"]
    tag = PropertyTag(
        name="DefPtr",
        type="CustomProperty_FD",
        size=12,
        type_parts=[("CustomProperty_FD", 0)],
    )
    ar = _archive(tmp_path, _fname(0) + struct.pack("<i", 42))
    parsed = parse_property_value(tag, ar, name_map, [], Summary())
    assert parsed == {"kind": "GbxDefPtrProperty", "name": "Def", "struct": 42}


def test_soft_object_outputs_are_normalized(tmp_path):
    ar = _archive(tmp_path, struct.pack("<i", 6) + b"/Game\x00" + struct.pack("<i", 4) + b"Sub\x00")
    soft = parse_soft_object_property(PropertyTag("Soft", "SoftObjectProperty", 14), ar, [])
    assert isinstance(soft, SoftObjectPathValue)
    assert soft.asset_path == "/Game"

    ar = _archive(tmp_path, struct.pack("<i", 6) + b"/Game\x00")
    asset = parse_asset_object_property(PropertyTag("Asset", "AssetObjectProperty", 10), ar)
    assert isinstance(asset, SoftObjectPathValue)
    assert asset.raw_kind == "AssetObjectProperty"

    ar = _archive(tmp_path, bytes(range(16)))
    lazy = parse_lazy_object_property(PropertyTag("Lazy", "LazyObjectProperty", 16), ar)
    assert isinstance(lazy, SoftObjectPathValue)
    assert lazy.guid == bytes(range(16)).hex()


def test_cpf_values_are_ue5_standard():
    assert CPF_Net == 0x0000000000000800
    assert CPF_NoClear == 0x0000000000200000
    assert CPF_BlueprintCallable == 0x0000000004000000


def test_common_decompression_supports_aliases_and_wrapped_zlib():
    payload = b"hello unreal"
    compressed = zlib.compress(payload)

    assert normalize_compression_method("zstandard") == "Zstd"
    assert decompress_block(compressed, len(payload), "zlib") == payload
    assert decompress_block(gzip.compress(payload), len(payload), "gzip") == payload

    try:
        decompress_block(b"not oodle", 10, "Oodle")
    except NotImplementedError as exc:
        assert "Oodle" in str(exc)
    else:
        raise AssertionError("Oodle should fail clearly when no optional backend exists")


def test_usmap_array_dim_indexes_are_absolute():
    names = [b"MyStruct", b"MyProp"]
    payload = struct.pack("<I", len(names))
    for name in names:
        payload += struct.pack("<H", len(name)) + name
    payload += struct.pack("<I", 0)
    payload += struct.pack("<I", 1)
    payload += struct.pack("<i", 0)
    payload += struct.pack("<i", -1)
    payload += struct.pack("<HH", 2, 1)
    payload += struct.pack("<HBiB", 5, 2, 1, 2)
    data = (
        struct.pack("<HB", 0x30C4, 4)
        + b"\x00"
        + b"\x00"
        + struct.pack("<II", len(payload), len(payload))
        + payload
    )

    props = UsmapParser(data).mappings.types["MyStruct"].properties

    assert sorted(props) == [5, 6]
    assert props[6].index == 6


def test_asset_metadata_deserializers_populate_structured_fields():
    tex = UTexture2D()
    tex.properties = {
        "PlatformData": {
            "SizeX": 128,
            "SizeY": 64,
            "PixelFormat": "PF_DXT1",
            "Mips": [{"SizeX": 128, "SizeY": 64, "DataSize": 512}],
        }
    }
    tex.deserialize(None, 0, 0)
    assert tex.size_x == 128
    assert tex.mip_levels[0]["data_size"] == 512

    mat = UMaterialInstance()
    mat.properties = {
        "Parent": "/Game/M",
        "ScalarParameterValues": [
            {"ParameterInfo": {"Name": "Roughness"}, "ParameterValue": 0.5}
        ],
    }
    mat.deserialize(None, 0, 0)
    assert mat.parent == "/Game/M"
    assert mat.scalar_parameters == {"Roughness": 0.5}

    mesh = UStaticMesh()
    mesh.properties = {
        "LightMapResolution": 64,
        "RenderData": {"LODResources": [{"Sections": [{"MaterialIndex": 0}], "NumVertices": 3}]},
    }
    mesh.deserialize(None, 0, 0)
    assert mesh.lightmap_resolution == 64
    assert mesh.render_data["lod_count"] == 1
    assert mesh.lod_groups[0]["section_count"] == 1


def test_iostore_directory_index_parses_path_to_chunk():
    def fstring(text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        return struct.pack("<i", len(data)) + data

    invalid = 0xFFFFFFFF
    mount = fstring("../../../Game")
    dirs = struct.pack("<i", 1) + struct.pack("<IIII", invalid, invalid, invalid, 0)
    files = struct.pack("<i", 1) + struct.pack("<III", 0, invalid, 0)
    strings = struct.pack("<i", 1) + fstring("A.uasset")

    reader = IoStoreReader("unused.utoc")
    reader._directory_index_buffer = mount + dirs + files + strings
    reader._chunk_ids = [FIoChunkId(b"123456789012")]

    reader._parse_directory_index()

    assert reader.list_files() == ["Game/A.uasset"]
    assert reader._directory_index["Game/A.uasset"].bytes == b"123456789012"

    reader._chunk_offsets = [type("Offset", (), {"offset": 0, "length": 4})()]
    reader._ucas_files = [BytesIO(b"data")]
    reader._header = type("Header", (), {"partition_size": 0, "is_encrypted": False})()
    assert reader.extract_path("A") == b"data"
    assert reader.extract_path("/game/a.uasset") == b"data"
    assert reader.extract_path("missing.uasset") is None


def test_iostore_compressed_chunk_and_missing_key_paths():
    payload = b"compressed payload"
    compressed = zlib.compress(payload)
    reader = IoStoreReader("unused.utoc")
    reader._ucas_files = [BytesIO(compressed)]
    reader._header = type("Header", (), {"partition_size": 0, "is_encrypted": False})()
    reader._compression_block_size = len(payload)
    reader._compression_methods = ["None", "Zlib"]
    reader._compression_blocks = [
        FIoStoreTocCompressedBlockEntry(0, len(compressed), len(payload), 1)
    ]

    assert reader._read_data(0, len(payload)) == payload

    reader._header = type("Header", (), {"partition_size": 0, "is_encrypted": True})()
    reader._aes_key = None
    try:
        reader._read_data(0, len(payload))
    except ValueError as exc:
        assert "AES key" in str(exc)
    else:
        raise AssertionError("encrypted IoStore read without key should fail")


def test_iostore_cross_block_compressed_read():
    first = b"abcdefgh"
    second = b"ijklmnop"
    first_compressed = zlib.compress(first)
    second_compressed = zlib.compress(second)
    reader = IoStoreReader("unused.utoc")
    reader._ucas_files = [BytesIO(first_compressed + second_compressed)]
    reader._header = type("Header", (), {"partition_size": 0, "is_encrypted": False})()
    reader._compression_block_size = 8
    reader._compression_methods = ["None", "Zlib"]
    reader._compression_blocks = [
        FIoStoreTocCompressedBlockEntry(0, len(first_compressed), len(first), 1),
        FIoStoreTocCompressedBlockEntry(len(first_compressed), len(second_compressed), len(second), 1),
    ]

    assert reader._read_data(3, 10) == b"defghijklm"


def test_iostore_uncompressed_partition_spanning_read():
    reader = IoStoreReader("unused.utoc")
    reader._ucas_files = [BytesIO(b"abcd"), BytesIO(b"efgh")]
    reader._header = type("Header", (), {"partition_size": 4, "is_encrypted": False})()

    assert reader._read_data(2, 5) == b"cdefg"


def test_iostore_oodle_block_fails_clearly():
    reader = IoStoreReader("unused.utoc")
    reader._ucas_files = [BytesIO(b"oodle bytes")]
    reader._header = type("Header", (), {"partition_size": 0, "is_encrypted": False})()
    reader._compression_block_size = 16
    reader._compression_methods = ["None", "Oodle"]
    reader._compression_blocks = [
        FIoStoreTocCompressedBlockEntry(0, 10, 16, 1)
    ]

    try:
        reader._read_data(0, 4)
    except NotImplementedError as exc:
        assert "Oodle" in str(exc)
    else:
        raise AssertionError("Oodle IoStore block should fail clearly")


def test_blueprint_reference_binary_helpers(tmp_path):
    ar = _archive(tmp_path, struct.pack("<i", 1))
    assert read_pin_reference(ar, [], [], []) is None
    assert ar.tell() == 4

    pin_guid = bytes(range(16))
    pin_data = struct.pack("<ii", 0, 0) + pin_guid
    ar = _archive(tmp_path, pin_data)

    pin_ref = read_pin_reference(ar, [], [], [])

    assert pin_ref["pin_guid"] == "000102030405060708090A0B0C0D0E0F"

    name_map = ["Func"]
    member_guid = bytes(range(16, 32))
    member_data = (
        struct.pack("<i", 0)
        + struct.pack("<i", 0)
        + _fname(0)
        + member_guid
        + struct.pack("<II", 1, 0)
    )
    ar = _archive(tmp_path, member_data)

    ref = read_fmember_reference(ar, name_map, [], [])

    assert ref.member_name == "Func"
    assert ref.member_guid == "10111213-1415-1617-1819-1a1b1c1d1e1f"
    assert ref.b_self_context is True


def test_mapping_driven_unversioned_property_loop_with_super_and_tail(tmp_path):
    class Summary:
        file_version_ue5 = 0
        package_flags = PKG_UnversionedProperties

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        template_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="MyStruct",
        object_flags=0,
        serial_size=16,
        serial_offset=0,
    )
    mappings = TypeMappings(types={
        "BaseStruct": StructMapping(
            name="BaseStruct",
            properties={
                0: PropertyInfo(0, "BaseCount", PropertyType("IntProperty")),
            },
            property_count=1,
        ),
        "MyStruct": StructMapping(
            name="MyStruct",
            super_type="BaseStruct",
            properties={
                0: PropertyInfo(0, "Count", PropertyType("IntProperty")),
                1: PropertyInfo(1, "Weight", PropertyType("FloatProperty")),
            },
            property_count=2,
        )
    })
    ar = _archive(tmp_path, struct.pack("<iif", 3, 7, 1.5) + b"tail")

    props = parse_properties_from_export(export, ar, Summary(), [], [], mappings=mappings)

    assert [(p.name, p.type, p.value) for p in props[:3]] == [
        ("BaseCount", "IntProperty", 3),
        ("Count", "IntProperty", 7),
        ("Weight", "FloatProperty", 1.5),
    ]
    assert props[3].name == "_unversioned_tail"
    assert props[3].value["parse_status"] == "opaque"


def test_mapping_driven_unversioned_container_properties(tmp_path):
    class Summary:
        file_version_ue5 = 0
        package_flags = PKG_UnversionedProperties

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        template_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="ContainerStruct",
        object_flags=0,
        serial_size=24,
        serial_offset=0,
    )
    mappings = TypeMappings(types={
        "ContainerStruct": StructMapping(
            name="ContainerStruct",
            properties={
                0: PropertyInfo(
                    0,
                    "Numbers",
                    PropertyType("ArrayProperty", inner_type=PropertyType("IntProperty")),
                ),
                1: PropertyInfo(
                    1,
                    "Lookup",
                    PropertyType(
                        "MapProperty",
                        inner_type=PropertyType("IntProperty"),
                        value_type=PropertyType("FloatProperty"),
                    ),
                ),
            },
            property_count=2,
        )
    })
    ar = _archive(
        tmp_path,
        struct.pack("<iii", 2, 11, 12)
        + struct.pack("<iiif", 0, 1, 7, 2.5),  # num_keys_to_remove=0, num_entries=1, key=7, value=2.5
    )

    props = parse_properties_from_export(export, ar, Summary(), [], [], mappings=mappings)

    assert props[0].name == "Numbers"
    assert props[0].value == [11, 12]
    assert props[1].name == "Lookup"
    assert isinstance(props[1].value, MapValue)
    assert props[1].value.entries == [{"key": 7, "value": 2.5}]


def test_mapping_driven_unversioned_set_and_optional(tmp_path):
    class Summary:
        file_version_ue5 = 0
        package_flags = PKG_UnversionedProperties

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        template_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="ContainerStruct",
        object_flags=0,
        serial_size=17,
        serial_offset=0,
    )
    mappings = TypeMappings(types={
        "ContainerStruct": StructMapping(
            name="ContainerStruct",
            properties={
                0: PropertyInfo(
                    0,
                    "Names",
                    PropertyType("SetProperty", inner_type=PropertyType("IntProperty")),
                ),
                1: PropertyInfo(
                    1,
                    "MaybeWeight",
                    PropertyType("OptionalProperty", inner_type=PropertyType("FloatProperty")),
                ),
            },
            property_count=2,
        )
    })
    ar = _archive(tmp_path, struct.pack("<iiiiIf", 0, 2, 4, 8, 1, 9.25))  # num_elements_to_remove=0, num_elements=2, elements=[4, 8], OptionalProperty: has_value=1, value=9.25

    props = parse_properties_from_export(export, ar, Summary(), [], [], mappings=mappings)

    assert isinstance(props[0].value, SetValue)
    assert props[0].value.elements == [4, 8]
    assert props[1].value == {"has_value": True, "value": 9.25}


def test_mapping_driven_unversioned_header_fragments_and_zero_mask(tmp_path):
    class Summary:
        file_version_ue5 = 0
        package_flags = PKG_UnversionedProperties

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        template_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="HeaderStruct",
        object_flags=0,
        serial_size=18,
        serial_offset=0,
    )
    mappings = TypeMappings(types={
        "HeaderStruct": StructMapping(
            name="HeaderStruct",
            properties={
                0: PropertyInfo(0, "A", PropertyType("IntProperty")),
                1: PropertyInfo(1, "Skipped", PropertyType("IntProperty")),
                2: PropertyInfo(2, "ZeroFloat", PropertyType("FloatProperty")),
                3: PropertyInfo(3, "B", PropertyType("IntProperty")),
            },
            property_count=4,
        )
    })
    fragment0 = (0 | (0 << 7) | (1 << 8))
    fragment1 = (1 | (1 << 7) | (2 << 8))
    terminator = 0
    data = (
        struct.pack("<HHHI", fragment0, fragment1, terminator, 0b01)
        + struct.pack("<ii", 11, 22)
    )
    ar = _archive(tmp_path, data)

    props = parse_properties_from_export(export, ar, Summary(), [], [], mappings=mappings)

    assert [(p.name, p.value) for p in props] == [
        ("A", 11),
        ("ZeroFloat", 0.0),
        ("B", 22),
    ]


def test_mapping_driven_unversioned_zero_value_at_payload_end(tmp_path):
    class Summary:
        file_version_ue5 = 0
        package_flags = PKG_UnversionedProperties

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        template_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="ZeroStruct",
        object_flags=0,
        serial_size=8,
        serial_offset=0,
    )
    mappings = TypeMappings(types={
        "ZeroStruct": StructMapping(
            name="ZeroStruct",
            properties={0: PropertyInfo(0, "Enabled", PropertyType("BoolProperty"))},
            property_count=1,
        )
    })
    fragment = (0 | (1 << 7) | (1 << 8))
    data = struct.pack("<HHI", fragment, 0, 0b1)
    ar = _archive(tmp_path, data)

    props = parse_properties_from_export(export, ar, Summary(), [], [], mappings=mappings)

    assert [(p.name, p.value) for p in props] == [("Enabled", False)]


def test_jmap_nested_type_names_and_array_dim_are_stable():
    payload = {
        "objects": {
            "/Script/Game.Parent": {
                "type": "Class",
                "properties": [{"name": "Inherited", "type": "IntProperty"}],
            },
            "/Script/Game.Child": {
                "type": "Class",
                "super_struct": "/Script/Game.Parent",
                "properties": [
                    {
                        "name": "Choices",
                        "type": "OptionalProperty",
                        "inner": {"type": "SetProperty", "inner": {"type": "NameProperty"}},
                        "array_dim": 2,
                    },
                    {
                        "name": "Scores",
                        "type": "MapProperty",
                        "key_prop": {"type": "NameProperty"},
                        "value_prop": {"type": "EnumProperty", "enum": "/Script/Game.EColor"},
                    },
                ],
            },
        }
    }

    mappings = JmapParser(json.dumps(payload).encode("utf-8")).mappings
    child = mappings.types["Child"]

    assert sorted(child.properties) == [0, 1, 2]
    assert mappings.property_by_name("Child", "Inherited").name == "Inherited"
    assert child.properties[0].mapping_type.type == "OptionalProperty"
    assert child.properties[0].mapping_type.inner_type.type == "SetProperty"
    assert child.properties[2].mapping_type.value_type.enum_name == "EColor"


def test_asset_deserializers_record_opaque_offsets():
    tex = UTexture2D()
    tex.deserialize(None, 123, 45)

    assert tex.parse_status == "opaque"
    assert tex.raw_offset == 123
    assert tex.raw_size == 45


def test_minimal_static_mesh_payload_metadata(tmp_path):
    from uasset_read.parsers.asset_types.static_mesh import parse_static_mesh

    data = b"\x00" * 256
    ar = _archive(tmp_path, data)

    parsed = parse_static_mesh(ar, [])

    assert parsed["parse_status"] == "partial_metadata"
    assert "raw_offset" in parsed
    assert "sample_size" in parsed


def test_minimal_texture2d_payload_metadata(tmp_path):
    from uasset_read.parsers.asset_types.texture2d import parse_texture2d

    data = b"\x00" * 256
    ar = _archive(tmp_path, data)

    parsed = parse_texture2d(ar, [])

    assert parsed["parse_status"] == "partial_metadata"
    assert "raw_offset" in parsed
    assert "sample_size" in parsed
