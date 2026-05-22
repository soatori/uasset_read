"""N2C — Node-to-Code 中间格式模块。

节点处理器架构：将 UEdGraphNode 转换为语义化的 N2CNodeDefinition，
再通过 Processor 模式分发到具体处理器。
"""
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.id_mapper import N2CIdMapper
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor
from uasset_read.n2c.processor_registry import N2CProcessorRegistry
from uasset_read.n2c.schema import N2CStruct, N2CGraph, N2CNode, N2CPin
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry
from uasset_read.n2c.validation import N2C_JSON_SCHEMA, validate_n2c_json
from uasset_read.n2c.serializer import to_n2c_json, from_n2c_json, _estimate_token_count
from uasset_read.n2c.flow_extractor import extract_chains, extract_data_flow_map

__all__ = [
    "N2CNodeDefinition",
    "N2CNodeProcessor",
    "N2CProcessorRegistry",
    "N2CNodeType",
    "N2CNodeTypeRegistry",  # Phase 68 新增
    # Phase 70 新增
    "N2CStruct",
    "N2CGraph",
    "N2CNode",
    "N2CPin",
    "N2CIdMapper",
    "N2C_JSON_SCHEMA",
    "validate_n2c_json",
    "to_n2c_json",
    "from_n2c_json",
    "extract_chains",
    "extract_data_flow_map",
    "_estimate_token_count",
]
