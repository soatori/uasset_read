"""Phase 44 tests — UEdGraphPin linked_to_objects with mock linker.

Uses real FArchive via BytesIO-backed temp files to ensure byte consumption
matches the production parser exactly.
"""

import io
import os
import struct
import tempfile
import pytest

from uasset_read.serializers.graph import (
    read_pin_reference, read_pin_array, read_ue_graph_pin,
)
from uasset_read.serializers.object_resources import (
    PackageIndex, ObjectImport, ObjectExport,
)
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.archive import FArchive


class _BytesIOArchive:
    """FArchive-compatible reader backed by BytesIO.

    Mirrors FArchive's exact byte consumption:
    - read_bool = uint32 (4 bytes)
    - read_name = u32 index + u32 number (8 bytes)
    - read_fstring = i32 length + data
    - read_bytes = raw bytes
    - read_u8/read_i32 etc = standard struct unpacks
    """

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self.file_size = len(data)
        self._tolerant = True

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int):
        self._buf.seek(pos)

    def read_u8(self) -> int:
        return struct.unpack('<B', self._buf.read(1))[0]

    def read_u32(self) -> int:
        return struct.unpack('<I', self._buf.read(4))[0]

    def read_i32(self) -> int:
        return struct.unpack('<i', self._buf.read(4))[0]

    def read_i64(self) -> int:
        return struct.unpack('<q', self._buf.read(8))[0]

    def read_bytes(self, n: int) -> bytes:
        return self._buf.read(n)

    def read_fstring(self) -> str:
        length = struct.unpack('<i', self._buf.read(4))[0]
        if length == 0:
            return ""
        if length < 0:
            data = self._buf.read(-length * 2)
            return data.decode('utf-16', errors='replace').rstrip('\x00')
        data = self._buf.read(length)
        return data.decode('utf-8', errors='replace').rstrip('\x00')

    def read_bool(self) -> bool:
        return struct.unpack('<I', self._buf.read(4))[0] != 0

    def read_bool_1byte(self) -> bool:
        return struct.unpack('<B', self._buf.read(1))[0] != 0

    def read_name(self, name_map: list) -> str:
        """FName: u32 index + u32 number."""
        index = struct.unpack('<I', self._buf.read(4))[0]
        number = struct.unpack('<I', self._buf.read(4))[0]
        if 0 <= index < len(name_map):
            base = name_map[index]
            if number > 0:
                return f"{base}_{number}"
            return base
        return "None"


def _make_export_map(*names):
    """Create ObjectExport list with given object names."""
    result = []
    for i, name in enumerate(names):
        result.append(ObjectExport(
            class_index=PackageIndex(-1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name=name,
            object_flags=0,
            serial_size=100,
            serial_offset=i * 100,
        ))
    return result


def _make_import_map(*names):
    """Create ObjectImport list with given object names."""
    result = []
    for name in names:
        result.append(ObjectImport(
            class_package="TestPkg",
            class_name="TestClass",
            outer_index=PackageIndex(0),
            object_name=name,
        ))
    return result


def _make_mock_linker():
    """Mock linker with resolve_package_index returning UObjectInstance."""
    linker = type("MockLinker", (), {})()
    obj1 = UObjectInstance(
        package_index=1, object_name="NodeA", object_class="K2Node_Event",
        class_package="/Script/Test", outer_index=None, is_import=False,
        outer=None, linker=linker,
    )
    obj2 = UObjectInstance(
        package_index=2, object_name="NodeB", object_class="K2Node_CallFunction",
        class_package="/Script/Test", outer_index=None, is_import=False,
        outer=None, linker=linker,
    )
    import_obj = UObjectInstance(
        package_index=-1, object_name="ImportA", object_class="ExternalClass",
        class_package="/Script/Core", outer_index=None, is_import=True,
        outer=None, linker=linker,
    )

    def resolve(pkg_idx):
        if pkg_idx.index == 1:
            return obj1
        elif pkg_idx.index == 2:
            return obj2
        elif pkg_idx.index == -1:
            return import_obj
        return None

    linker.resolve_package_index = resolve
    return linker


def _make_mock_summary():
    summary = type("MockSummary", (), {})()
    summary.file_version_ue4 = 522
    summary.file_version_ue5 = 1
    summary.legacy_file_version = 0
    summary.get_custom_version = lambda guid, default: 9999
    return summary


def _write_pin_reference(buf, owning_node_index: int, pin_guid: bytes = None):
    """Write a pin reference: b_null(4) + owning_node_index(4) + guid(16)."""
    if pin_guid is None:
        pin_guid = b'\xAB' * 16
    buf.write(struct.pack('<i', 0))  # b_null_ptr = 0 (not null)
    buf.write(struct.pack('<i', owning_node_index))
    buf.write(pin_guid)


def _write_null_pin_reference(buf):
    """Write a null pin reference: b_null(4) + owning(4) + guid(16)."""
    buf.write(struct.pack('<i', 1))  # b_null_ptr != 0
    buf.write(struct.pack('<i', 0))
    buf.write(b'\x00' * 16)


def _write_pin_array(buf, entries: list):
    """Write a pin array: count(4) + entries.
    entries: list of owning_node_index ints, or empty list.
    """
    buf.write(struct.pack('<i', len(entries)))
    for idx in entries:
        if idx == 0:
            _write_null_pin_reference(buf)
        else:
            _write_pin_reference(buf, idx)


def _write_ue5_inline_pin_ref(buf, owning_node_index: int, pin_guid: bytes = None, is_null: bool = False):
    """Write UE5 inline pin ref: b_null(4) + owning(4) + guid(16)."""
    if pin_guid is None:
        pin_guid = b'\xCC' * 16
    buf.write(struct.pack('<i', 1 if is_null else 0))
    buf.write(struct.pack('<i', owning_node_index))
    buf.write(pin_guid)


def _write_ftext_none(buf):
    """Write FText with history_type=None: flags(4) + history(1) + b_culture(4)."""
    buf.write(struct.pack('<i', 0))       # flags
    buf.write(struct.pack('<B', 0xff))    # history_type = None
    buf.write(struct.pack('<I', 0))       # b_has_culture_invariant_string


def _build_minimal_ue5_pin(linked_to_indices=None, sub_pin_indices=None,
                           parent_owning=None, ref_owning=None):
    """Build a minimal valid UE5 pin binary.

    Returns bytes that read_ue_graph_pin can fully parse.
    linked_to_indices: list of int (owning_node_index for each linked pin)
    sub_pin_indices: list of int
    parent_owning: int or 0 (for null parent)
    ref_owning: int or 0
    """
    if linked_to_indices is None:
        linked_to_indices = []
    if sub_pin_indices is None:
        sub_pin_indices = []

    buf = io.BytesIO()

    # 1. OwningNode
    buf.write(struct.pack('<i', 5))
    # 2. PinId (16 bytes)
    buf.write(b'\xAA' * 16)
    # 3. PinName (FName: index + number)
    buf.write(struct.pack('<I', 0))  # name index
    buf.write(struct.pack('<I', 0))  # instance number
    # 4. PinFriendlyName (FText, history=None)
    _write_ftext_none(buf)
    # 5. SourceIndex
    buf.write(struct.pack('<i', 0))
    # 6. PinToolTip (empty FString)
    buf.write(struct.pack('<i', 0))
    # 7. Direction
    buf.write(struct.pack('<B', 0))

    # 8. PinType — full UE5 serialization
    # pin_category (FName)
    buf.write(struct.pack('<I', 0))
    buf.write(struct.pack('<I', 0))
    # pin_subcategory (FName)
    buf.write(struct.pack('<I', 0))
    buf.write(struct.pack('<I', 0))
    # pin_subcategory_object (i32)
    buf.write(struct.pack('<i', 0))
    # container_type (u8)
    buf.write(struct.pack('<B', 0))
    # is_reference (bool=1 byte)
    buf.write(struct.pack('<B', 0))
    # is_weak_pointer (bool=1 byte)
    buf.write(struct.pack('<B', 0))
    # MemberReference
    buf.write(struct.pack('<i', 0))  # member_parent
    buf.write(struct.pack('<I', 0))  # member_name index
    buf.write(struct.pack('<I', 0))  # member_name number
    buf.write(b'\x00' * 16)          # member_guid
    # is_const (bool=1 byte)
    buf.write(struct.pack('<B', 0))
    # is_uobject_wrapper (bool=1 byte)
    buf.write(struct.pack('<B', 0))
    # b_serialize_as_single_precision_float (bool=1 byte)
    buf.write(struct.pack('<B', 0))

    # 9. DefaultValue (empty FString)
    buf.write(struct.pack('<i', 0))
    # 10. AutogeneratedDefaultValue (empty FString)
    buf.write(struct.pack('<i', 0))
    # 11. DefaultObject (i32)
    buf.write(struct.pack('<i', 0))
    # 12. DefaultTextValue (FText, history=None)
    _write_ftext_none(buf)

    # 13. LinkedTo array
    _write_pin_array(buf, linked_to_indices)
    # 14. SubPins array
    _write_pin_array(buf, sub_pin_indices)
    # 15. ParentPin (UE5 inline: 24 bytes)
    if parent_owning:
        _write_ue5_inline_pin_ref(buf, parent_owning)
    else:
        _write_ue5_inline_pin_ref(buf, 0, is_null=True)
    # 16. ReferencePassThrough (UE5 inline: 24 bytes)
    if ref_owning:
        _write_ue5_inline_pin_ref(buf, ref_owning)
    else:
        _write_ue5_inline_pin_ref(buf, 0, is_null=True)
    # 17. PersistentGuid (16 bytes)
    buf.write(b'\xFF' * 16)
    # 18. BitField (u32)
    buf.write(struct.pack('<I', 0))

    return buf.getvalue()


class TestPinReferenceWithLinker:
    """UAT #3: read_pin_reference adds owning_node_object when linker provided."""

    def test_linker_populates_owning_node_object_export(self):
        """Export index (owning_node_index=1) → UObjectInstance resolved."""
        data = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\xAB' * 16
        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()

        result = read_pin_reference(archive, [], [], [], linker)

        assert result is not None
        assert "owning_node_object" in result
        assert result["owning_node_object"].object_name == "NodeA"

    def test_linker_populates_owning_node_object_import(self):
        """Import index (owning_node_index=-1) → UObjectInstance resolved."""
        data = struct.pack('<i', 0) + struct.pack('<i', -1) + b'\xCD' * 16
        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()

        result = read_pin_reference(archive, [], [], [], linker)

        assert result is not None
        assert "owning_node_object" in result
        assert result["owning_node_object"] is not None

    def test_null_pin_no_object(self):
        """Null pin (b_null != 0) → returns None."""
        data = struct.pack('<i', 1)
        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()

        result = read_pin_reference(archive, [], [], [], linker)
        assert result is None

    def test_zero_index_no_object_key(self):
        """Zero owning_node_index → no owning_node_object key added."""
        data = struct.pack('<i', 0) + struct.pack('<i', 0) + b'\x00' * 16
        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()

        result = read_pin_reference(archive, [], [], [], linker)
        assert result is not None
        assert "owning_node_object" not in result

    def test_no_linker_no_object_key(self):
        """No linker → no owning_node_object key even with valid index."""
        data = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\xAB' * 16
        archive = _BytesIOArchive(data)

        result = read_pin_reference(archive, [], [], [], None)
        assert result is not None
        assert "owning_node_object" not in result


class TestPinArrayWithLinker:
    """UAT #3 (extended): read_pin_array passes linker through."""

    def test_array_with_two_entries(self):
        """Array count=2, each entry resolved to UObjectInstance."""
        buf = io.BytesIO()
        buf.write(struct.pack('<i', 2))  # count
        buf.write(struct.pack('<i', 0))  # b_null
        buf.write(struct.pack('<i', 1))  # owning_node_index
        buf.write(b'\x11' * 16)           # pin_guid
        buf.write(struct.pack('<i', 0))  # b_null
        buf.write(struct.pack('<i', 2))  # owning_node_index
        buf.write(b'\x22' * 16)           # pin_guid

        archive = _BytesIOArchive(buf.getvalue())
        linker = _make_mock_linker()

        result = read_pin_array(archive, [], [], [], linker)

        assert len(result) == 2
        assert result[0]["owning_node_object"].object_name == "NodeA"
        assert result[1]["owning_node_object"].object_name == "NodeB"


class TestGraphPinObjectsFields:
    """UAT #4: read_ue_graph_pin populates *objects fields."""

    def test_linked_to_objects_populated(self):
        """When linker provided, linked_to_objects parallel to linked_to_raw."""
        # linked_to has 1 entry pointing to export index 1 (= NodeA)
        # sub_pins has 1 entry pointing to export index 2 (= NodeB)
        data = _build_minimal_ue5_pin(
            linked_to_indices=[1],
            sub_pin_indices=[2],
        )

        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA", "NodeB")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker)

        # Verify linked_to_raw
        assert len(pin.linked_to_raw) == 1
        assert pin.linked_to_raw[0]["owning_node"] == "NodeA"

        # Verify linked_to_objects — parallel array
        assert len(pin.linked_to_objects) == 1
        assert pin.linked_to_objects[0].object_name == "NodeA"

        # Verify sub_pins
        assert len(pin.sub_pins) == 1
        assert pin.sub_pins[0]["owning_node"] == "NodeB"
        assert len(pin.sub_pins_objects) == 1
        assert pin.sub_pins_objects[0].object_name == "NodeB"

        # Verify null parent_pin and ref_pass_through
        assert pin.parent_pin_object is None
        assert pin.ref_pass_through_object is None

    def test_parent_pin_object_populated(self):
        """UE5 parent_pin with non-null owning_node_index → parent_pin_object set."""
        data = _build_minimal_ue5_pin(parent_owning=1)

        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker)

        assert pin.parent_pin_object is not None
        assert pin.parent_pin_object.object_name == "NodeA"

    def test_ref_pass_through_object_populated(self):
        """UE5 ref_pass_through with non-null owning_node_index resolved."""
        data = _build_minimal_ue5_pin(ref_owning=2)

        archive = _BytesIOArchive(data)
        linker = _make_mock_linker()
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA", "NodeB")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker)

        assert pin.ref_pass_through_object is not None
        assert pin.ref_pass_through_object.object_name == "NodeB"

    def test_null_entries_store_none(self):
        """Null pin references → corresponding *objects field entry is None."""
        # linked_to with 1 entry + 1 null entry
        buf = io.BytesIO()
        buf.write(struct.pack('<i', 2))  # count = 2
        _write_pin_reference(buf, 1, b'\x11' * 16)   # valid → NodeA
        _write_null_pin_reference(buf)                 # null → None
        # sub_pins empty, parent null, ref null
        buf.write(struct.pack('<i', 0))  # sub_pins count=0
        _write_ue5_inline_pin_ref(buf, 0, is_null=True)   # parent null
        _write_ue5_inline_pin_ref(buf, 0, is_null=True)   # ref null
        # persistent_guid + bitfield
        buf.write(b'\xFF' * 16)
        buf.write(struct.pack('<I', 0))

        # Prepend the fixed header before linked_to
        header = _build_minimal_ue5_pin()
        # Find linked_to position in header and replace from there
        header_data = _build_minimal_ue5_pin(linked_to_indices=[])
        # Actually, let's build the full thing from scratch
        full_buf = io.BytesIO()
        full_buf.write(struct.pack('<i', 5))      # owning_node_index
        full_buf.write(b'\xAA' * 16)               # pin_id
        full_buf.write(struct.pack('<I', 0))       # pin_name index
        full_buf.write(struct.pack('<I', 0))       # pin_name number
        # FText none
        full_buf.write(struct.pack('<i', 0))
        full_buf.write(struct.pack('<B', 0xff))
        full_buf.write(struct.pack('<I', 0))
        # SourceIndex
        full_buf.write(struct.pack('<i', 0))
        # PinToolTip empty
        full_buf.write(struct.pack('<i', 0))
        # Direction
        full_buf.write(struct.pack('<B', 0))
        # PinType — 1-byte bools for UE5
        full_buf.write(struct.pack('<I', 0))  # pin_category index
        full_buf.write(struct.pack('<I', 0))  # pin_category number
        full_buf.write(struct.pack('<I', 0))  # pin_subcategory index
        full_buf.write(struct.pack('<I', 0))  # pin_subcategory number
        full_buf.write(struct.pack('<i', 0))  # pin_subcategory_object
        full_buf.write(struct.pack('<B', 0))  # container_type
        full_buf.write(struct.pack('<B', 0))  # is_reference (1-byte)
        full_buf.write(struct.pack('<B', 0))  # is_weak_pointer (1-byte)
        full_buf.write(struct.pack('<i', 0))  # member_parent
        full_buf.write(struct.pack('<I', 0))  # member_name index
        full_buf.write(struct.pack('<I', 0))  # member_name number
        full_buf.write(b'\x00' * 16)          # member_guid
        full_buf.write(struct.pack('<B', 0))  # is_const (1-byte)
        full_buf.write(struct.pack('<B', 0))  # is_uobject_wrapper (1-byte)
        full_buf.write(struct.pack('<B', 0))  # b_serialize_as_single_precision_float (1-byte)
        # DefaultValue strings
        full_buf.write(struct.pack('<i', 0))
        full_buf.write(struct.pack('<i', 0))
        # DefaultObject
        full_buf.write(struct.pack('<i', 0))
        # DefaultTextValue
        full_buf.write(struct.pack('<i', 0))
        full_buf.write(struct.pack('<B', 0xff))
        full_buf.write(struct.pack('<I', 0))
        # linked_to array (2 entries: valid + null)
        full_buf.write(struct.pack('<i', 2))  # count
        _write_pin_reference(full_buf, 1, b'\x11' * 16)
        _write_null_pin_reference(full_buf)
        # sub_pins empty
        full_buf.write(struct.pack('<i', 0))
        # parent_pin null
        _write_ue5_inline_pin_ref(full_buf, 0, is_null=True)
        # ref_pass_through null
        _write_ue5_inline_pin_ref(full_buf, 0, is_null=True)
        # persistent_guid + bitfield
        full_buf.write(b'\xFF' * 16)
        full_buf.write(struct.pack('<I', 0))

        archive = _BytesIOArchive(full_buf.getvalue())
        linker = _make_mock_linker()
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker)

        assert len(pin.linked_to_raw) == 1  # null entry filtered out by read_pin_array
        assert len(pin.linked_to_objects) == 1
        assert pin.linked_to_objects[0].object_name == "NodeA"


class TestBackwardCompatibility:
    """UAT #5: No linker → all *objects fields at default values."""

    def test_no_linker_empty_objects(self):
        """When linker=None, linked_to_objects etc are None-filled (parallel array)."""
        data = _build_minimal_ue5_pin(linked_to_indices=[1])

        archive = _BytesIOArchive(data)
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker=None)

        assert len(pin.linked_to_raw) == 1
        # linked_to_objects is same length as linked_to_raw, filled with None
        # (parallel array — index alignment, not empty)
        assert pin.linked_to_objects == [None]
        assert pin.sub_pins_objects == []
        assert pin.parent_pin_object is None
        assert pin.ref_pass_through_object is None

    def test_no_linker_raw_data_intact(self):
        """Without linker, linked_to_raw still contains correct dict data."""
        data = _build_minimal_ue5_pin(linked_to_indices=[1])

        archive = _BytesIOArchive(data)
        summary = _make_mock_summary()
        exports = _make_export_map("NodeA")
        imports = _make_import_map()

        pin = read_ue_graph_pin(archive, [], summary, exports, imports, linker=None)

        assert pin.linked_to_raw[0]["owning_node"] == "NodeA"
        assert len(pin.linked_to_raw[0]["pin_guid"]) == 32  # hex string


class TestCallChainLinkerPassing:
    """UAT #6: Verify call chain passes linker parameter."""

    def test_read_ue_graph_node_accepts_linker(self):
        from uasset_read.serializers.graph import read_ue_graph_node
        import inspect
        sig = inspect.signature(read_ue_graph_node)
        assert "linker" in sig.parameters

    def test_read_ue_graph_accepts_linker(self):
        from uasset_read.serializers.graph import read_ue_graph
        import inspect
        sig = inspect.signature(read_ue_graph)
        assert "linker" in sig.parameters

    def test_read_pin_array_passes_linker(self):
        from uasset_read.serializers.graph import read_pin_array
        import inspect
        sig = inspect.signature(read_pin_array)
        assert "linker" in sig.parameters

    def test_create_node_from_archive_accepts_linker(self):
        from uasset_read.serializers.graph import create_node_from_archive
        import inspect
        sig = inspect.signature(create_node_from_archive)
        assert "linker" in sig.parameters
