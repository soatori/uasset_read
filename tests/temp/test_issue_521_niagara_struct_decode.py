"""B1 struct decode tests for NiagaraVariable, NiagaraGraphScriptUsageInfo,
VersionedNiagaraScriptData.

These tests assert that the parser decodes named fields from each struct type.
Currently they FAIL because the structs appear as opaque; Tasks 2-3 will make
them pass.
"""
import json
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from uasset_read import parse_single

SAMPLE = Path(__file__).resolve().parents[2] / "tests/samples/NM_BPSystemEvent.uasset"
SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

# Exact struct_type strings from probe (Step 1).
# NiagaraVariable: parser recognizes name, parse_status=opaque.
# NiagaraGraphScriptUsageInfo: parser falls back to "UnknownStruct" (opaque).
# VersionedNiagaraScriptData: parser falls back to "UnknownStruct" (opaque).
# Tests use the correct C++ names so they guide the Task 2-3 implementation.
STRUCT_TYPE_NAMES = {
    "NiagaraVariable": "NiagaraVariable",
    "NiagaraGraphScriptUsageInfo": "NiagaraGraphScriptUsageInfo",
    "VersionedNiagaraScriptData": "VersionedNiagaraScriptData",
}


def _parse_fixture():
    return json.loads(parse_single(str(SAMPLE), format="json", tolerant=True, log_enabled=False))


def _find_struct_values(data, target_struct_type):
    """Recursively find all StructValue dicts with the given struct_type."""
    results = []
    if isinstance(data, dict):
        if data.get("struct_type") == target_struct_type:
            results.append(data)
        for v in data.values():
            results.extend(_find_struct_values(v, target_struct_type))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_struct_values(item, target_struct_type))
    return results


class TestNiagaraVariableDecode:
    """NiagaraVariable: FName Name + tagged FNiagaraTypeDefinition + data blob.
    Source: NiagaraModule.cpp:1732 (custom Serialize).
    B0a evidence: 111-114 bytes per instance, 12 total in fixture.
    """

    def test_sha256(self):
        assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SHA256

    def test_niagara_variable_has_decoded_name(self):
        """After decode, NiagaraVariable must expose 'Name' as a string."""
        data = _parse_fixture()
        nv_type = STRUCT_TYPE_NAMES["NiagaraVariable"]
        values = _find_struct_values(data, nv_type)
        assert len(values) >= 12, f"Expected >= 12 NiagaraVariable values, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"NiagaraVariable parse_status={v.get('parse_status')}, expected 'success'"
            )
            fields = v.get("fields", {})
            assert "Name" in fields, f"NiagaraVariable missing 'Name' field; fields={list(fields.keys())}"
            # Name should be a non-empty string (FName)
            name_val = fields["Name"]
            assert isinstance(name_val, str) and len(name_val) > 0, f"Name={name_val!r}"

    def test_niagara_variable_has_type_definition(self):
        """After decode, NiagaraVariable must expose TypeDefinition fields."""
        data = _parse_fixture()
        nv_type = STRUCT_TYPE_NAMES["NiagaraVariable"]
        values = _find_struct_values(data, nv_type)
        for v in values:
            fields = v.get("fields", {})
            # TypeDefinition may be nested or flattened depending on decode approach
            # Accept either a 'TypeDefinition' dict or flattened fields like 'UnderlyingType'
            has_typedef = "TypeDefinition" in fields or "UnderlyingType" in fields
            assert has_typedef, (
                f"NiagaraVariable missing TypeDefinition; fields={list(fields.keys())}"
            )


class TestNiagaraGraphScriptUsageInfoDecode:
    """NiagaraGraphScriptUsageInfo: tagged property stream.
    Source: NiagaraGraph.h:87/:571.
    B0a evidence: 544/544 bytes consumed, fields: BaseId(Guid), UsageType(Enum),
    UsageId(Guid), CompileHash, CompileHashFromGraph, Traversal(Array<Object>).
    """

    def test_has_decoded_fields(self):
        """After decode, NiagaraGraphScriptUsageInfo must expose named fields."""
        data = _parse_fixture()
        gui_type = STRUCT_TYPE_NAMES["NiagaraGraphScriptUsageInfo"]
        values = _find_struct_values(data, gui_type)
        assert len(values) >= 1, f"Expected >= 1 NiagaraGraphScriptUsageInfo, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"NiagaraGraphScriptUsageInfo parse_status={v.get('parse_status')}"
            )
            fields = v.get("fields", {})
            # Expect at least BaseId and UsageType from the tagged stream
            assert "BaseId" in fields or "UsageType" in fields, (
                f"Missing expected fields; fields={list(fields.keys())}"
            )


class TestVersionedNiagaraScriptDataDecode:
    """VersionedNiagaraScriptData: tagged property stream.
    Source: NiagaraScript.h:619/:873.
    B0a evidence: 2038/2038 bytes consumed.
    """

    def test_has_decoded_fields(self):
        """After decode, VersionedNiagaraScriptData must expose named fields."""
        data = _parse_fixture()
        vsd_type = STRUCT_TYPE_NAMES["VersionedNiagaraScriptData"]
        values = _find_struct_values(data, vsd_type)
        assert len(values) >= 1, f"Expected >= 1 VersionedNiagaraScriptData, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"VersionedNiagaraScriptData parse_status={v.get('parse_status')}"
            )
            fields = v.get("fields", {})
            # Expect at least Version and Category from the tagged stream
            has_key_field = "Version" in fields or "Category" in fields or "ModuleUsageBitmask" in fields
            assert has_key_field, (
                f"Missing expected fields; fields={list(fields.keys())}"
            )
