"""Pytest-discoverable fixtures (plan File Map).

Fixture definitions do not live only in ``tests.fixtures``: tests import
ordinary helpers from there, while pytest injects the named fixtures below
automatically. Fixtures that need models introduced by later tasks import
lazily inside their bodies so this conftest stays importable from Task 1 on.
"""

import pytest

from tests.fixtures import make_property_input, parse_sample, sample_path
from uasset_read.models.document import PackageDocument


@pytest.fixture
def stackobot_document() -> PackageDocument:
    # manifest: export_count=31, b_is_asset_count=2, legacy, UE4=864
    return parse_sample("StackOBot_BP_Drone.uasset", depth="decode")


@pytest.fixture
def ue58_blueprint_document() -> PackageDocument:
    # manifest: export_count=24, UE4=522, UE5=1018
    return parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")


@pytest.fixture
def stackobot_source():
    from uasset_read.sources import CompositeSource

    return CompositeSource.from_package(sample_path("StackOBot_BP_Drone.uasset"))


@pytest.fixture
def ue58_source():
    from uasset_read.sources import CompositeSource

    return CompositeSource.from_package(sample_path("MyProject_UE58_TestBlueprint.uasset"))


@pytest.fixture
def stackobot_material() -> PackageDocument:
    # manifest: export_count=42; design gate 3 expects 39 material expressions
    return parse_sample("StackOBot_M_BotBase.uasset", depth="decode")


@pytest.fixture
def cooked_material() -> PackageDocument:
    # cooked/editor-stripped material; expected capability limited/unavailable
    return parse_sample("TestMaterial.uasset", depth="decode")


@pytest.fixture
def tagged_fixture():
    return make_property_input("TestBlueprint.uasset")


@pytest.fixture
def fake_source(tmp_path):
    from uasset_read.sources import CompositeSource

    main = tmp_path / "A.uasset"
    sidecar = tmp_path / "A.uexp"
    main.write_bytes(b"\x00\x01")
    sidecar.write_bytes(b"\x02\x03\x04")
    return CompositeSource.from_package(main)


@pytest.fixture
def package_document(stackobot_document) -> PackageDocument:
    return stackobot_document


@pytest.fixture
def document(package_document) -> PackageDocument:
    return package_document


@pytest.fixture
def object_record(stackobot_document):
    return stackobot_document.objects[0]


@pytest.fixture
def unknown_object_record(object_record):
    from dataclasses import replace

    return replace(object_record, class_name="UnknownClass", roles=[])


@pytest.fixture
def package_context(stackobot_document):
    return stackobot_document.package


@pytest.fixture
def function_analysis_ir():
    """Small typed fixture for operand projection; sample fixtures stay dicts."""
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import ControlFlowGraph
    from uasset_read.models.analysis import FunctionAnalysis

    instruction = BytecodeInstruction(
        statement_index=0,
        statement_ordinal=0,
        logical_end=4,
        serialized_start=0,
        serialized_end=8,
        opcode="EX_VirtualFunction",
        operands={"parameters": [{"name": "Value", "value": 1}]},
        expression={"parameters": [{"name": "Value", "value": 1}]},
        reads=[],
        writes=[],
        call_target="Synthetic.Call",
        jump_target_statement_index=None,
        jump_kind="none",
        source_node_id=None,
    )
    return FunctionAnalysis(
        object_id="export:9",
        owner_object_id="export:0",
        name="Synthetic",
        function_name="Synthetic",
        script_source_range=None,
        expression_count=1,
        entrypoint=None,
        instructions=[instruction],
        cfg=ControlFlowGraph(blocks=[], edges=[], entry=0, metadata={}),
        reads=set(),
        writes=set(),
        calls=["Synthetic.Call"],
        bytecode_status="parsed",
        diagnostics=[],
    )


@pytest.fixture
def stackobot_semantic(stackobot_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    return BlueprintCorrelation().build(stackobot_document)


@pytest.fixture
def ue58_semantic(ue58_blueprint_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    return BlueprintCorrelation().build(ue58_blueprint_document)
