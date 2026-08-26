"""Skeleton 语义输出测试 — 验证层级安全、容错和 JSON 合约。"""

from __future__ import annotations

import json

import pytest

from uasset_read.parsers.asset_types.skeleton import _validate_hierarchy
from uasset_read.semantic.render import render_semantic_json
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _make_header(**kwargs) -> PackageHeaderIR:
    defaults = dict(
        package_name="/Game/Test/Skeleton",
        package_class="Skeleton",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.3",
    )
    defaults.update(kwargs)
    return PackageHeaderIR(**defaults)


def _make_skeleton_export(asset_type_data: dict | None = None, **kwargs) -> ExportIR:
    defaults = dict(
        index=0,
        object_name="Skeleton",
        object_class="Skeleton",
        serial_size=1024,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
        asset_type_data=asset_type_data,
    )
    defaults.update(kwargs)
    return ExportIR(**defaults)


def _make_ir(exports: list[ExportIR] | None = None) -> PackageIR:
    return PackageIR(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=exports or [],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
    )


def _make_ref_skeleton(names: list[str], parents: list[int]) -> dict:
    """构造 reference_skeleton 字典。"""
    return {
        "names": names,
        "parents": parents,
        "bone_count": len(names),
        "transforms": [],
        "pose_count": len(names),
        "name_to_index": {},
    }


def _render_json(ir: PackageIR) -> dict:
    semantic_ir = build_semantic_ir(ir)
    output = render_semantic_json(semantic_ir)
    return json.loads(output)


# ---------------------------------------------------------------------------
# 层级验证测试
# ---------------------------------------------------------------------------


class TestHierarchyValidation:
    """验证 _validate_hierarchy 函数的检测能力。"""

    def test_valid_hierarchy(self):
        """所有 parent 在范围内且无环 → 空诊断列表。"""
        ref = _make_ref_skeleton(
            names=["root", "child1", "child2"],
            parents=[-1, 0, 0],
        )
        result = _validate_hierarchy(ref)
        assert result == []

    def test_single_root(self):
        """单根骨骼 → 无 MULTIPLE_ROOTS 诊断。"""
        ref = _make_ref_skeleton(
            names=["root", "child"],
            parents=[-1, 0],
        )
        result = _validate_hierarchy(ref)
        assert not any(d["code"] == "SKELETON_MULTIPLE_ROOTS" for d in result)

    def test_multiple_roots(self):
        """多根骨骼 → MULTIPLE_ROOTS 诊断。"""
        ref = _make_ref_skeleton(
            names=["root1", "root2", "child"],
            parents=[-1, -1, 0],
        )
        result = _validate_hierarchy(ref)
        diag = next(d for d in result if d["code"] == "SKELETON_MULTIPLE_ROOTS")
        assert diag["count"] == 2
        assert len(diag["examples"]) == 2

    def test_invalid_parent_out_of_range_high(self):
        """parent_index >= bone_count → INVALID_PARENT_INDEX。"""
        ref = _make_ref_skeleton(
            names=["root", "child1", "child2"],
            parents=[-1, 5, 0],
        )
        result = _validate_hierarchy(ref)
        diag = next(d for d in result if d["code"] == "SKELETON_INVALID_PARENT_INDEX")
        assert diag["count"] == 1
        assert diag["examples"][0] == {"bone_index": 1, "parent_index": 5}

    def test_invalid_parent_negative_two(self):
        """parent_index = -2（低于 INDEX_NONE）→ INVALID_PARENT_INDEX。"""
        ref = _make_ref_skeleton(
            names=["root", "child"],
            parents=[-1, -2],
        )
        result = _validate_hierarchy(ref)
        diag = next(d for d in result if d["code"] == "SKELETON_INVALID_PARENT_INDEX")
        assert diag["count"] == 1

    def test_invalid_parent_aggregation(self):
        """多个无效 parent 聚合计数 + 限制 examples 为 5。"""
        parents = [-1] + [999] * 20
        names = ["root"] + [f"bone_{i}" for i in range(20)]
        ref = _make_ref_skeleton(names=names, parents=parents)
        result = _validate_hierarchy(ref)
        diag = next(d for d in result if d["code"] == "SKELETON_INVALID_PARENT_INDEX")
        assert diag["count"] == 20
        assert len(diag["examples"]) == 5

    def test_cycle_detection(self):
        """A→B→A 环 → HIERARCHY_CYCLE。"""
        ref = _make_ref_skeleton(
            names=["A", "B", "C"],
            parents=[1, 2, 1],  # A→B, B→C, C→A (cycle)
        )
        result = _validate_hierarchy(ref)
        diag = next(d for d in result if d["code"] == "SKELETON_HIERARCHY_CYCLE")
        assert diag["count"] >= 1
        assert len(diag["examples"]) >= 1

    def test_no_cycle_detection_when_invalid_parents(self):
        """有 invalid parent 时跳过环检测（避免误报）。"""
        ref = _make_ref_skeleton(
            names=["A", "B"],
            parents=[999, 999],
        )
        result = _validate_hierarchy(ref)
        assert any(d["code"] == "SKELETON_INVALID_PARENT_INDEX" for d in result)
        assert not any(d["code"] == "SKELETON_HIERARCHY_CYCLE" for d in result)

    def test_empty_skeleton(self):
        """空骨骼列表 → 无诊断。"""
        ref = _make_ref_skeleton(names=[], parents=[])
        result = _validate_hierarchy(ref)
        assert result == []

    def test_single_bone_root(self):
        """单根骨骼（无子骨骼）→ 无诊断。"""
        ref = _make_ref_skeleton(names=["root"], parents=[-1])
        result = _validate_hierarchy(ref)
        assert result == []


# ---------------------------------------------------------------------------
# JSON 渲染测试
# ---------------------------------------------------------------------------


class TestSkeletonJSONRendering:
    """验证 skeleton 块在 JSON 输出中的正确渲染。"""

    def test_skeleton_block_present(self):
        """有 skeleton asset_type_data 时，JSON 输出包含 skeleton 键。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=["root", "child"],
                parents=[-1, 0],
            ),
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        assert "skeleton" in data

    def test_bone_count_matches_bones(self):
        """bone_count 与 bones 数组长度一致。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=["root", "child1", "child2"],
                parents=[-1, 0, 0],
            ),
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        sk = data["skeleton"]
        assert sk["bone_count"] == 3
        assert len(sk["bones"]) == 3

    def test_bone_names_and_parents(self):
        """bones 列表包含正确的 name 和 parent_index。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=["root", "spine", "head"],
                parents=[-1, 0, 1],
            ),
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        bones = data["skeleton"]["bones"]
        assert bones[0] == {"name": "root", "parent_index": -1}
        assert bones[1] == {"name": "spine", "parent_index": 0}
        assert bones[2] == {"name": "head", "parent_index": 1}

    def test_invalid_hierarchy_renders_diagnostics(self):
        """无效层级时，skeleton 块包含 hierarchy_diagnostics。"""
        ad = {
            "parse_status": "partial",
            "reference_skeleton": _make_ref_skeleton(
                names=["root", "bad"],
                parents=[-1, 999],
            ),
            "valid_hierarchy": False,
            "hierarchy_diagnostics": [
                {
                    "code": "SKELETON_INVALID_PARENT_INDEX",
                    "count": 1,
                    "examples": [{"bone_index": 1, "parent_index": 999}],
                }
            ],
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        sk = data["skeleton"]
        assert sk["valid_hierarchy"] is False
        assert len(sk["hierarchy_diagnostics"]) == 1
        assert sk["hierarchy_diagnostics"][0]["code"] == "SKELETON_INVALID_PARENT_INDEX"

    def test_partial_status_rendered(self):
        """parse_status 非 success 时在 skeleton 块中渲染。"""
        ad = {
            "parse_status": "partial",
            "reference_skeleton": _make_ref_skeleton(
                names=["root"],
                parents=[-1],
            ),
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        assert data["skeleton"]["parse_status"] == "partial"

    def test_guid_rendered(self):
        """guid 字段正确渲染。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=["root"],
                parents=[-1],
            ),
            "guid": "00000000-00009100-00000C00-69687400",
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        assert data["skeleton"]["skeleton_summary"]["guid"] == "00000000-00009100-00000C00-69687400"

    def test_no_skeleton_block_without_data(self):
        """无 skeleton asset_type_data 时，JSON 输出不含 skeleton 键。"""
        export = _make_skeleton_export(asset_type_data=None)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        assert "skeleton" not in data

    def test_empty_bones(self):
        """bone_count=0 时 bones 为空列表。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=[],
                parents=[],
            ),
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        sk = data["skeleton"]
        assert sk["bone_count"] == 0
        assert "bones" not in sk  # empty list is omitted from output

    def test_retarget_sources_metadata(self):
        """retarget_sources 只渲染元数据（不含 transforms 数组）。"""
        ad = {
            "parse_status": "success",
            "reference_skeleton": _make_ref_skeleton(
                names=["root"],
                parents=[-1],
            ),
            "retarget_sources": [
                {
                    "name": "default",
                    "pose_name": "default",
                    "source_mesh": "/Game/Mesh/SK_Mannequin",
                    "transforms": [{"translation": {}, "rotation": {}, "scale": {}}],
                    "transform_count": 1,
                }
            ],
            "valid_hierarchy": True,
        }
        export = _make_skeleton_export(asset_type_data=ad)
        ir = _make_ir(exports=[export])
        data = _render_json(ir)
        sources = data["skeleton"]["retarget_sources"]
        assert len(sources) == 1
        assert sources[0]["name"] == "default"
        assert sources[0]["pose_name"] == "default"
        assert sources[0]["source_mesh"] == "/Game/Mesh/SK_Mannequin"
        assert "transforms" not in sources[0]  # transforms array is not rendered


# ---------------------------------------------------------------------------
# CiciToon 容错集成测试
# ---------------------------------------------------------------------------


class TestCiciToonTolerant:
    """CiciToon_SK_Mannequin.uasset 容错 JSON 输出测试。"""

    SAMPLE_PATH = "tests/samples/CiciToon_SK_Mannequin.uasset"

    @pytest.mark.skipif(
        not __import__("os").path.exists(
            __import__("pathlib").Path(__file__).parent / "samples" / "CiciToon_SK_Mannequin.uasset"
        ),
        reason="sample not available",
    )
    def test_tolerant_json_no_exception(self):
        """CiciToon 在 tolerant 模式下不抛异常，返回合法 JSON。"""
        from uasset_read.core import parse_single

        output = parse_single(self.SAMPLE_PATH, format="json", tolerant=True)
        data = json.loads(output)
        assert "skeleton" in data

    @pytest.mark.skipif(
        not __import__("os").path.exists(
            __import__("pathlib").Path(__file__).parent / "samples" / "CiciToon_SK_Mannequin.uasset"
        ),
        reason="sample not available",
    )
    def test_bone_count_matches_bones(self):
        """bone_count 与 emitted bones 数量一致。"""
        from uasset_read.core import parse_single

        output = parse_single(self.SAMPLE_PATH, format="json", tolerant=True)
        data = json.loads(output)
        sk = data["skeleton"]
        assert sk["bone_count"] == len(sk["bones"])

    @pytest.mark.skipif(
        not __import__("os").path.exists(
            __import__("pathlib").Path(__file__).parent / "samples" / "CiciToon_SK_Mannequin.uasset"
        ),
        reason="sample not available",
    )
    def test_invalid_hierarchy_has_aggregated_diagnostics(self):
        """无效层级产生 aggregated diagnostics 而非逐条展开。"""
        from uasset_read.core import parse_single

        output = parse_single(self.SAMPLE_PATH, format="json", tolerant=True)
        data = json.loads(output)
        sk = data["skeleton"]
        assert sk.get("valid_hierarchy") is False
        diag = sk.get("hierarchy_diagnostics", [])
        # 至少有一条 INVALID_PARENT_INDEX 诊断
        parent_diag = [d for d in diag if d["code"] == "SKELETON_INVALID_PARENT_INDEX"]
        assert len(parent_diag) == 1
        # count 应 > 0，examples 应 <= 5
        assert parent_diag[0]["count"] > 0
        assert len(parent_diag[0]["examples"]) <= 5

    @pytest.mark.skipif(
        not __import__("os").path.exists(
            __import__("pathlib").Path(__file__).parent / "samples" / "CiciToon_SK_Mannequin.uasset"
        ),
        reason="sample not available",
    )
    def test_partial_status(self):
        """CiciToon skeleton 有层级错误时 parse_status 为 partial。"""
        from uasset_read.core import parse_single

        output = parse_single(self.SAMPLE_PATH, format="json", tolerant=True)
        data = json.loads(output)
        sk = data["skeleton"]
        assert sk.get("parse_status") == "partial"
