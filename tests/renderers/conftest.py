"""渲染器测试共享 fixtures。"""

import pytest
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    GraphIR,
    NodeIR,
    PinIR,
)


@pytest.fixture
def make_pin_ir():
    """创建 PinIR 的工厂 fixture。"""
    def _make(
        pin_name: str = "TestPin",
        pin_type: str = "bool",
        linked_to: list[str] | None = None,
        direction: str = "output",
        default_value: str | None = None,
    ) -> PinIR:
        return PinIR(
            pin_name=pin_name,
            pin_type=pin_type,
            linked_to=linked_to or [],
            direction=direction,
            default_value=default_value,
        )

    return _make


@pytest.fixture
def make_node_ir():
    """创建 NodeIR 的工厂 fixture。"""
    def _make(
        node_name: str = "TestNode",
        node_class: str = "K2Node_Event",
        pins: list[PinIR] | None = None,
        node_comment: str | None = None,
        execution_flow: list[dict] | None = None,
    ) -> NodeIR:
        return NodeIR(
            node_guid="00000000000000000000000000000001",
            node_class=node_class,
            node_comment=node_comment,
            pins=pins or [],
            execution_flow=execution_flow or [],
        )

    return _make


@pytest.fixture
def make_graph_ir():
    """创建 GraphIR 的工厂 fixture。"""
    def _make(
        name: str = "TestGraph",
        nodes: list[NodeIR] | None = None,
        graph_class: str = "EdGraph",
        graph_type: str | None = None,
        execution_chains: list[list[str]] | None = None,
    ) -> GraphIR:
        return GraphIR(
            graph_guid="00000000000000000000000000000002",
            graph_name=name,
            graph_class=graph_class,
            nodes=nodes or [],
            execution_chains=execution_chains or [],
            graph_type=graph_type,
        )

    return _make


@pytest.fixture
def make_export_ir():
    """创建 ExportIR 的工厂 fixture。"""
    def _make(
        index: int = 0,
        object_name: str = "TestExport",
        class_name: str = "BlueprintGeneratedClass",
        properties: list | None = None,
        graphs: list[GraphIR] | None = None,
        serial_size: int = 1024,
        parse_status: str = "success",
    ) -> ExportIR:
        return ExportIR(
            index=index,
            object_name=object_name,
            object_class=class_name,
            serial_size=serial_size,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=properties or [],
            graphs=graphs or [],
            bulk_data=None,
            parse_status=parse_status,
        )

    return _make


@pytest.fixture
def make_package_ir():
    """创建最小 PackageIR 的工厂 fixture。"""
    def _make(
        name: str = "TestPackage",
        class_name: str = "BlueprintGeneratedClass",
        exports: list[ExportIR] | None = None,
        variables: list | None = None,
        graphs: list[GraphIR] | None = None,
    ) -> PackageIR:
        header = PackageHeaderIR(
            package_name=name,
            package_class=class_name,
            package_flags=0,
            total_export_count=len(exports or []),
            total_import_count=0,
            ue_version="5.4",
        )

        return PackageIR(
            header=header,
            name_map=(),
            imports=[],
            exports=exports or [],
            linker=None,
            variables=variables or [],
            function_graphs=[],
            status="success",
        )

    return _make
