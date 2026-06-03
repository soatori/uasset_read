"""IR（中间表示）数据结构 — PackageIR 层级模型。

IR 是解析结果的统一数据源，渲染器只接收 PackageIR，不访问 ParseResult。
所有 GUID（Node/Pin）统一为 32 位小写 hex。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageHeaderIR:
    """包头部精简摘要。"""
    package_name: str
    package_class: str
    package_flags: int
    total_export_count: int
    total_import_count: int
    ue_version: str


@dataclass
class PinIR:
    """单个 Pin 的 IR 表示。"""
    pin_name: str
    pin_type: str
    pin_type_value: str | None
    linked_to: list[str]
    direction: str
    default_value: str | None


@dataclass
class NodeIR:
    """单个节点的 IR 表示。"""
    node_guid: str
    node_class: str
    node_comment: str | None
    pins: list[PinIR]
    execution_flow: list[dict]


@dataclass
class GraphIR:
    """单个图的 IR 表示。"""
    graph_guid: str
    graph_name: str
    graph_class: str
    nodes: list[NodeIR]
    execution_chains: list[list[str]]


@dataclass
class PropertyIR:
    """单个属性的 IR 表示。"""
    name: str
    type: str
    value: Any
    array_index: int
    guid: str | None


@dataclass
class ExportIR:
    """单个导出对象的 IR 表示。"""
    index: int
    object_name: str
    object_class: str
    serial_size: int
    outer_index_resolved: str | None
    super_index_resolved: str | None
    parent_class: str | None
    properties: list[PropertyIR]
    graphs: list[GraphIR]
    bulk_data: dict | None


@dataclass
class LinkerSummaryIR:
    """包链接摘要。"""
    has_linker: bool
    import_paths: list[str]
    export_paths: list[str]


@dataclass
class PackageIR:
    """顶层 IR 结构。"""
    header: PackageHeaderIR
    name_map: list[str]
    imports: list[dict]
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
