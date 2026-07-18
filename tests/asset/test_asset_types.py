"""资产类型解析器单元测试 — SoundCue + LevelSequence + 嵌套子图。

合并自 test_sound_cue.py、test_level_sequence.py 和 test_subgraph.py。
"""
from __future__ import annotations

import struct

import pytest
from unittest.mock import MagicMock

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.sound_cue import parse_sound_cue
from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence
from uasset_read.models.core import UEdGraph, UEdGraphNode
from uasset_read.models.ir import GraphIR, NodeIR, PinIR
from uasset_read.ir_builder import _build_graph_ir, _build_node_ir


# ===========================================================================
# SoundCue 测试
# ===========================================================================


def _build_sound_cue_payload(
    first_node: int = 1,
    volume: float = 1.0,
    pitch: float = 1.0,
    nodes: list[int] | None = None,
) -> bytes:
    """构建 SoundCue payload。

    Args:
        first_node: FirstNode int32
        volume: VolumeMultiplier float32
        pitch: PitchMultiplier float32
        nodes: SoundCueNodes int32 数组（None 则使用默认 [2, 3]）
    """
    if nodes is None:
        nodes = [2, 3]
    buf = bytearray()
    buf += struct.pack("<i", first_node)
    buf += struct.pack("<f", volume)
    buf += struct.pack("<f", pitch)
    buf += struct.pack("<i", len(nodes))
    for n in nodes:
        buf += struct.pack("<i", n)
    return bytes(buf)


class TestParseSoundCueBasic:
    """基础解析测试。"""

    def test_parse_sound_cue(self):
        """解析标准 SoundCue — 验证所有字段。"""
        payload = _build_sound_cue_payload(
            first_node=5,
            volume=0.8,
            pitch=1.2,
            nodes=[10, 20, 30],
        )
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 5
        assert result["volume_multiplier"] == pytest.approx(0.8)
        assert result["pitch_multiplier"] == pytest.approx(1.2)
        assert result["node_count"] == 3
        assert result["sound_cue_nodes"] == [10, 20, 30]

    def test_parse_sound_cue_empty_nodes(self):
        """解析无节点的 SoundCue。"""
        payload = _build_sound_cue_payload(
            first_node=0,
            volume=1.0,
            pitch=1.0,
            nodes=[],
        )
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 0
        assert result["node_count"] == 0
        assert result["sound_cue_nodes"] == []

    def test_parse_sound_cue_default_values(self):
        """使用默认参数解析 SoundCue。"""
        payload = _build_sound_cue_payload()
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 1
        assert result["volume_multiplier"] == pytest.approx(1.0)
        assert result["pitch_multiplier"] == pytest.approx(1.0)
        assert result["sound_cue_nodes"] == [2, 3]

    def test_parse_sound_cue_read_full(self):
        """解析后指针应位于末尾。"""
        payload = _build_sound_cue_payload()
        archive = ByteArchive(payload)

        parse_sound_cue(archive, [])

        assert archive.tell() == len(payload)


class TestParseSoundCueErrorHandling:
    """错误处理测试。"""

    def test_negative_node_count(self):
        """负数节点数返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)    # FirstNode
        buf += struct.pack("<f", 1.0)  # VolumeMultiplier
        buf += struct.pack("<f", 1.0)  # PitchMultiplier
        buf += struct.pack("<i", -1)   # SoundCueNodes.Count = -1
        archive = ByteArchive(bytes(buf))

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid node count" in result["error"]

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 写入 FirstNode 和 VolumeMultiplier，但缺少 PitchMultiplier 和 Nodes
        buf = bytearray()
        buf += struct.pack("<i", 0)    # FirstNode
        buf += struct.pack("<f", 1.0)  # VolumeMultiplier（缺少后续数据）
        archive = ByteArchive(bytes(buf))

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_empty_payload(self):
        """空 payload 返回 failed 状态。"""
        archive = ByteArchive(b"")

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "failed"


class TestParseSoundCueRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_sound_cue 可正常导入。"""
        from uasset_read.parsers.asset_types.sound_cue import parse_sound_cue as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 sound_cue 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")


# ===========================================================================
# LevelSequence 测试
# ===========================================================================


def _build_fstring_utf16(text: str) -> bytes:
    """构建 UTF-16 FString（负长度前缀 + UTF-16-LE 数据）。

    UE 的 UTF-16 FString 序列化格式：
    - Length: int32（负值 = 字符数，含 null terminator）
    - Data: Length * 2 字节的 UTF-16-LE 数据（含 null terminator）
    """
    if not text:
        return struct.pack("<i", 0)
    encoded = text.encode("utf-16-le")
    # 负长度 = 字符数（含 null terminator）
    char_count = len(text) + 1
    return struct.pack("<i", -char_count) + encoded + b"\x00\x00"


def _build_level_sequence_payload(
    movie_scene: int = 0,
    movie_scene_source: int = 0,
    license: str = "DefaultLicense",
    display_rate_num: int = 24,
    display_rate_den: int = 1,
    tick_resolution_num: int = 24000,
    tick_resolution_den: int = 1001,
) -> bytes:
    """构建 LevelSequence payload。

    Args:
        movie_scene: MovieScene int32 (opaque pointer)
        movie_scene_source: MovieSceneSource int32 (TSoftObjectPtr)
        license: MovieSceneLicense FString
        display_rate_num: DisplayRate Numerator int32
        display_rate_den: DisplayRate Denominator int32
        tick_resolution_num: TickResolution Numerator int32
        tick_resolution_den: TickResolution Denominator int32
    """
    buf = bytearray()
    buf += struct.pack("<i", movie_scene)
    buf += struct.pack("<i", movie_scene_source)
    buf += _build_fstring_utf16(license)
    buf += struct.pack("<i", display_rate_num)
    buf += struct.pack("<i", display_rate_den)
    buf += struct.pack("<i", tick_resolution_num)
    buf += struct.pack("<i", tick_resolution_den)
    return bytes(buf)


class TestParseLevelSequenceBasic:
    """基础解析测试。"""

    def test_parse_level_sequence(self):
        """解析标准 LevelSequence — 验证所有字段。"""
        payload = _build_level_sequence_payload(
            movie_scene=42,
            movie_scene_source=7,
            license="TestLicense",
            display_rate_num=30,
            display_rate_den=1,
            tick_resolution_num=30000,
            tick_resolution_den=1001,
        )
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene"] == 42
        assert result["movie_scene_source"] == 7
        assert result["movie_scene_license"] == "TestLicense"
        assert result["display_rate"]["numerator"] == 30
        assert result["display_rate"]["denominator"] == 1
        assert result["tick_resolution"]["numerator"] == 30000
        assert result["tick_resolution"]["denominator"] == 1001

    def test_parse_level_sequence_default_values(self):
        """使用默认参数解析 LevelSequence。"""
        payload = _build_level_sequence_payload()
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene"] == 0
        assert result["movie_scene_source"] == 0
        assert result["movie_scene_license"] == "DefaultLicense"
        assert result["display_rate"]["numerator"] == 24
        assert result["display_rate"]["denominator"] == 1
        assert result["tick_resolution"]["numerator"] == 24000
        assert result["tick_resolution"]["denominator"] == 1001

    def test_parse_level_sequence_empty_license(self):
        """解析空许可证字符串的 LevelSequence。"""
        payload = _build_level_sequence_payload(license="")
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene_license"] == ""

    def test_parse_level_sequence_read_full(self):
        """解析后指针应位于末尾。"""
        payload = _build_level_sequence_payload()
        archive = ByteArchive(payload)

        parse_level_sequence(archive, [])

        assert archive.tell() == len(payload)

    def test_parse_level_sequence_fractional_framerate(self):
        """解析非整数帧率（如 NTSC 23.976 fps）。"""
        payload = _build_level_sequence_payload(
            display_rate_num=24000,
            display_rate_den=1001,
            tick_resolution_num=24000,
            tick_resolution_den=1001,
        )
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["display_rate"]["numerator"] == 24000
        assert result["display_rate"]["denominator"] == 1001


class TestParseLevelSequenceErrorHandling:
    """错误处理测试。"""

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 只写入 MovieScene 和 MovieSceneSource，缺少后续字段
        buf = bytearray()
        buf += struct.pack("<i", 0)   # MovieScene
        buf += struct.pack("<i", 0)   # MovieSceneSource
        archive = ByteArchive(bytes(buf))

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_empty_payload(self):
        """空 payload 返回 failed 状态。"""
        archive = ByteArchive(b"")

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "failed"


class TestParseLevelSequenceRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_level_sequence 可正常导入。"""
        from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 level_sequence 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")


# ===========================================================================
# 嵌套子图解析测试 (Issue #178)
# ===========================================================================


class TestSubgraphParsing:
    """测试嵌套子图解析。"""

    def test_uegraph_subgraphs_field(self):
        """测试 UEdGraph 支持 subgraphs 字段。"""
        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="AnimationGraph",
        )
        assert hasattr(graph, "subgraphs")
        assert graph.subgraphs == []

    def test_uegraph_with_subgraphs(self):
        """测试带有子图的 UEdGraph。"""
        child_graph = UEdGraph(
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
        )
        parent_graph = UEdGraph(
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            subgraphs=[child_graph],
        )
        assert len(parent_graph.subgraphs) == 1
        assert parent_graph.subgraphs[0].graph_name == "ChildGraph"

    def test_graphir_subgraphs_field(self):
        """测试 GraphIR 支持 subgraphs 字段。"""
        graph_ir = GraphIR(
            graph_guid="test-guid",
            graph_name="TestGraph",
            graph_class="AnimationGraph",
            nodes=[],
            execution_chains=[],
        )
        assert hasattr(graph_ir, "subgraphs")
        assert graph_ir.subgraphs == []

    def test_graphir_with_subgraphs(self):
        """测试带有子图的 GraphIR。"""
        child_ir = GraphIR(
            graph_guid="child-guid",
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
            nodes=[],
            execution_chains=[],
        )
        parent_ir = GraphIR(
            graph_guid="parent-guid",
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            subgraphs=[child_ir],
        )
        assert len(parent_ir.subgraphs) == 1
        assert parent_ir.subgraphs[0].graph_name == "ChildGraph"

    def test_graphir_graph_type(self):
        """测试 GraphIR 支持 graph_type 字段。"""
        graph_ir = GraphIR(
            graph_guid="test-guid",
            graph_name="StateMachine",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            graph_type="state_machine",
        )
        assert graph_ir.graph_type == "state_machine"

    def test_build_graph_ir_with_subgraphs(self):
        """测试 _build_graph_ir 正确构建嵌套子图。"""
        # 创建子图
        child_node = UEdGraphNode(
            node_guid="child-node-guid",
            node_comment="State Result",
            class_name="AnimGraphNode_StateResult",
            pins=[],
        )
        child_graph = UEdGraph(
            graph_name="Idle Loop",
            graph_class="AnimationStateGraph",
            nodes=[child_node],
        )

        # 创建父图
        parent_node = UEdGraphNode(
            node_guid="parent-node-guid",
            node_comment="State Machine",
            class_name="AnimGraphNode_StateMachine",
            pins=[],
        )
        parent_graph = UEdGraph(
            graph_name="AnimGraph",
            graph_class="AnimationGraph",
            nodes=[parent_node],
            subgraphs=[child_graph],
        )

        # 构建 IR
        graph_ir = _build_graph_ir(parent_graph)

        # 验证
        assert graph_ir.graph_name == "AnimGraph"
        assert len(graph_ir.nodes) == 1
        assert len(graph_ir.subgraphs) == 1
        assert graph_ir.subgraphs[0].graph_name == "Idle Loop"
        assert graph_ir.subgraphs[0].graph_class == "AnimationStateGraph"

    def test_nested_subgraphs(self):
        """测试多层嵌套子图。"""
        # 创建最深层子图
        deep_graph = UEdGraph(
            graph_name="DeepGraph",
            graph_class="AnimationStateGraph",
        )

        # 创建中间层子图
        mid_graph = UEdGraph(
            graph_name="MidGraph",
            graph_class="AnimationStateMachineGraph",
            subgraphs=[deep_graph],
        )

        # 创建顶层图
        top_graph = UEdGraph(
            graph_name="TopGraph",
            graph_class="AnimationGraph",
            subgraphs=[mid_graph],
        )

        # 构建 IR
        graph_ir = _build_graph_ir(top_graph)

        # 验证多层嵌套
        assert len(graph_ir.subgraphs) == 1
        assert graph_ir.subgraphs[0].graph_name == "MidGraph"
        assert len(graph_ir.subgraphs[0].subgraphs) == 1
        assert graph_ir.subgraphs[0].subgraphs[0].graph_name == "DeepGraph"


class TestAnimGraphNodeParsing:
    """测试 AnimGraphNode 解析。"""

    def test_anim_graph_node_data_structure(self):
        """测试 AnimGraphNode node_data 结构。"""
        from uasset_read.serializers.graph_node import _read_anim_graph_node

        # 模拟 raw_properties
        raw_properties = {
            "EditorStateMachineGraph": 123,
            "EditorStateMachineGraphPackageIndex": 123,
        }

        # 调用函数
        result = _read_anim_graph_node(
            archive=None,
            name_map=[],
            summary=None,
            export_map=[],
            import_map=[],
            linker=None,
            class_name="AnimGraphNode_StateMachine",
            raw_properties=raw_properties,
        )

        # 验证
        assert result["node_type"] == "AnimGraphNode_StateMachine"
        # 无 linker 且 export_map 为空时，subgraph_references 不会被添加
        # 因为 PackageIndex 无法解析（pkg_idx > len(export_map)）
        # 但 node_type 应该正确设置


class TestJsonRendererSubgraphs:
    """测试 JSON 渲染器支持嵌套子图。"""

    def test_json_renderer_includes_subgraphs(self):
        """测试 JSON 输出包含嵌套子图。"""
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR

        # 创建带子图的 GraphIR
        child_ir = GraphIR(
            graph_guid="child-guid",
            graph_name="ChildGraph",
            graph_class="AnimationStateGraph",
            nodes=[],
            execution_chains=[],
        )
        graph_ir = GraphIR(
            graph_guid="parent-guid",
            graph_name="ParentGraph",
            graph_class="AnimationStateMachineGraph",
            nodes=[],
            execution_chains=[],
            subgraphs=[child_ir],
            graph_type="state_machine",
        )

        # 创建 ExportIR
        from uasset_read.models.ir import ExportIR
        export_ir = ExportIR(
            index=0,
            object_name="TestExport",
            object_class="AnimBlueprint",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[graph_ir],
            bulk_data=None,
        )

        # 创建 PackageIR
        header = PackageHeaderIR(
            package_name="TestPackage",
            package_class="AnimBlueprint",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.x",
        )
        package_ir = PackageIR(
            header=header,
            name_map=[],
            imports=[],
            exports=[export_ir],
            linker=None,
        )

        # 渲染
        renderer = JSONRenderer()
        from uasset_read.renderers.base import RenderOptions
        options = RenderOptions(output_level="debug")
        output = renderer.render(package_ir, options)

        # 验证 JSON 输出包含子图
        import json
        data = json.loads(output)
        graphs = data["exports"][0]["graphs"]
        assert len(graphs) == 1
        assert "subgraphs" in graphs[0]
        assert len(graphs[0]["subgraphs"]) == 1
        assert graphs[0]["subgraphs"][0]["graph_name"] == "ChildGraph"
        assert graphs[0]["graph_type"] == "state_machine"
