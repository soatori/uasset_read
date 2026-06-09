"""
核心数据模型 — UE 蓝图图容器、节点、引脚、蓝图元数据及 ParseResult。

通过扁平导出（D-03），调用者使用 from uasset_read.models import UEdGraph 等。
"""

from .core import (
    FEdGraphPinType,
    UEdGraphPin,
    UEdGraphNode,
    UEdGraph,
    FMemberReference,
)
from .node_types import (
    K2NodeCallFunction,
    K2NodeEvent,
    K2NodeKnot,
    EdGraphNodeComment,
    K2NodeEnhancedInputAction,
    K2NodeFunctionEntry,
)
from .result import (
    ParseResult,
    StatusInfo,
)
from .blueprint import (
    BlueprintMetadata,
    BlueprintVariable,
    BlueprintFunction,
    BlueprintEvent,
    FunctionParameter,
    MulticastDelegate,
)
from .properties import (
    PropertyTag,
    PropertyTypeName,
    PropertyValue,
    SoftObjectPathValue,
    AdvancedPropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
)
from .transforms import (
    VectorValue,
    RotatorValue,
    ScaleValue,
    format_transform_value,
)
from .ir import (
    PackageHeaderIR,
    PinIR,
    NodeIR,
    GraphIR,
    PropertyIR,
    ExportIR,
    ExportRawIR,
    LinkerSummaryIR,
    PackageIR,
)
from .fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)
from .diagnostics import (
    OffsetRangeDiagnostic,
)

__all__ = [
    # 核心模型（core.py）
    "FEdGraphPinType",
    "UEdGraphPin",
    "UEdGraphNode",
    "UEdGraph",
    "FMemberReference",
    # 节点类型（node_types.py）
    "K2NodeCallFunction",
    "K2NodeEvent",
    "K2NodeKnot",
    "EdGraphNodeComment",
    "K2NodeEnhancedInputAction",
    "K2NodeFunctionEntry",
    # 结果（result.py）
    "ParseResult",
    "StatusInfo",
    # 蓝图元数据（blueprint.py）
    "BlueprintMetadata",
    "BlueprintVariable",
    "BlueprintFunction",
    "BlueprintEvent",
    "FunctionParameter",
    "MulticastDelegate",
    # 属性数据模型
    "PropertyTag",
    "PropertyTypeName",
    "PropertyValue",
    "SoftObjectPathValue",
    "AdvancedPropertyValue",
    "StructValue",
    "MapValue",
    "SetValue",
    "EnumValue",
    "TextValue",
    "DelegateValue",
    # 变换数据类
    "VectorValue",
    "RotatorValue",
    "ScaleValue",
    "format_transform_value",
    # IR 中间表示（ir.py）
    "PackageHeaderIR",
    "PinIR",
    "NodeIR",
    "GraphIR",
    "PropertyIR",
    "ExportIR",
    "ExportRawIR",
    "LinkerSummaryIR",
    "PackageIR",
    # Fallback 模型
    "PropertyFallback",
    "StructFallback",
    "GenericUObject",
    "ExportParseStatus",
    "FallbackReason",
    # 诊断模型
    "OffsetRangeDiagnostic",
]
