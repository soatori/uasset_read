"""结构体类型常量和 schema 定义。

包含：
- _EXPECTED_STRUCT_SIZES: 固定布局结构体的预期字节大小
- _LWC_TYPE_MAP: LWC（Large World Coordinates）类型映射
- _TAGGED_FALLBACK_STRUCTS: 需要 tagged fallback 解析的结构体名称
- _TAGGED_FALLBACK_STRUCT_SCHEMAS: tagged fallback 结构体的字段 schema
"""
from __future__ import annotations


# Expected byte sizes for fixed-layout structs (used for fast-path validation)
EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 28,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
    "TopLevelAssetPath": 16,
    # 时间/帧类型
    "Timespan": 8,           # int64
    "DateTime": 8,           # uint64
    "FrameNumber": 4,        # int32
    # 整数向量类型
    "IntVector2": 8,         # 2 * int32
    "Int32Vector2": 8,       # 别名
    "IntVector4": 16,        # 4 * int32
    "UintVector": 12,        # 3 * uint32
    "UintVector2": 8,        # 2 * uint32
    "Uint32Point": 8,        # 别名
    "UintVector4": 16,       # 4 * uint32
    # 64 位整数向量类型
    "Int64Vector2": 16,      # 2 * int64
    "Int64Point": 16,        # 别名
    "Int64Vector": 24,       # 3 * int64
    "Int64Vector4": 32,      # 4 * int64
    "UInt64Vector2": 16,     # 2 * uint64
    "UInt64Point": 16,       # 别名
    "UInt64Vector": 24,      # 3 * uint64
    "UInt64Vector4": 32,     # 4 * uint64
    # 别名类型
    "DeprecateSlateVector2D": 16,  # 别名 Vector2D
    "VectorDouble": 24,            # Wuthering Waves 别名 Vector3d
    "Int32Point": 8,               # 别名 IntPoint
    # UE5 LWC 数学类型
    "Vector2f": 8,           # 2 * float32
    "Vector3f": 12,          # 3 * float32
    "Vector3d": 24,          # 3 * float64
    "Vector4f": 16,          # 4 * float32
    "Vector4d": 32,          # 4 * float64
    "Rotator3f": 12,         # 3 * float32
    "Rotator3d": 24,         # 3 * float64
    "Quat4f": 16,            # 4 * float32
    "Quat4d": 32,            # 4 * float64
    "Plane4f": 16,           # 4 * float32
    "Plane4d": 32,           # 4 * float64
    "Sphere3f": 16,          # 4 * float32
    "Sphere3d": 32,          # 4 * float64
    "Box2f": 16,             # 2 * Vector2f(8)
    "Box3f": 24,             # 2 * Vector3f(12)
    "Matrix44f": 64,         # 4 * Plane4f(16)
    "Transform3f": 48,       # Quat4f(16) + Vector3f(12) + Vector3f(4) + padding
    # 动画/混合空间高频结构体（报告补充）
    "FrameRate": 8,          # float Numerator + int32 Denominator（紧凑格式）
                             # 部分资产使用 tagged 格式（size=37），通过 tagged fallback 解析
    "AnimNotifyTrack": 8,    # 紧凑格式大小
                             # 部分资产使用 tagged 格式（size=0），通过 tagged fallback 解析
    "GuidProperty": 16,      # FGuid 标准大小
}


# LWC（Large World Coordinates）类型映射
LWC_TYPE_MAP: dict[str, tuple[int, int]] = {
    "Vector":        (12, 24),   # FVector3f → FVector3d
    "Rotator":       (12, 24),   # FRotator3f → FRotator3d
    "Vector2D":      (8, 16),    # FVector2f → FVector2d
    "Vector4":       (16, 32),   # FVector4f → FVector4d
    "Quat":          (16, 32),   # FQuat4f → FQuat4d
    "Plane":         (16, 32),   # FPlane4f → FPlane4d
    "Sphere":        (16, 32),   # FSphere3f → FSphere3d
    "Box":           (28, 56),   # 2 * FVector + bool (float → double)
    "BoxSphereBounds": (28, 56), # 3 * FVector + float (float → double)
    "Matrix":        (64, 128),  # 4 * FPlane (float → double)
    "TwoVectors":    (24, 48),   # 2 * FVector (float → double)
    "Transform":     (48, 96),   # FQuat(16/32) + FVector(12/24) + FVector(12/24) + padding(8/16)
}

# LWC 双精度类型名 → 对应的基础类型名
LWC_DOUBLE_TYPE_TO_BASE: dict[str, str] = {
    "Vector3d":    "Vector",
    "Vector4d":    "Vector4",
    "Rotator3d":   "Rotator",
    "Quat4d":      "Quat",
    "Plane4d":     "Plane",
    "Sphere3d":    "Sphere",
}

# LWC 单精度类型名 → 对应的基础类型名
LWC_FLOAT_TYPE_TO_BASE: dict[str, str] = {
    "Vector3f":    "Vector",
    "Vector4f":    "Vector4",
    "Rotator3f":   "Rotator",
    "Quat4f":      "Quat",
    "Plane4f":     "Plane",
    "Sphere3f":    "Sphere",
    "Vector2f":    "Vector2D",
}


# Tagged fallback structs and schemas
TAGGED_FALLBACK_STRUCTS: set[str] = {
    "MemberReference",
    "SimpleMemberReference",
    # Blueprint 变量描述 struct（ArrayProperty 内层，size=0 时仍需 tagged 解析）
    "FBPVariableDescription",
    "BPVariableDescription",
    "EdGraphPinType",
    "FEdGraphPinType",
    "BPVariableDescriptionHelper",
    # Blueprint 相关 struct
    "ImplementedInterfaces",
    "LastEditedDocuments",
    "CategorySorting",
    # AnimSequence 结构体（部分资产使用 tagged 格式）
    "FrameRate",         # 部分资产 tag.size=37，使用 tagged PropertyTag 格式
    "AnimNotifyTrack",   # 部分资产 tag.size=0，使用 tagged PropertyTag 格式
    # 编辑器结构体
    "FEditorElement",    # 蓝图编辑器组合框选项（DisplayName/Value/bIsDefault）
    "EditorElement",
    # 材质参数结构体（材质实例资产使用 tagged 格式）
    "ScalarParameterValue",
    "FScalarParameterValue",
    "FMaterialParameterInfo",
    # 动画混合空间结构体（部分资产使用 tagged 格式）
    "BlendSample",          # FBlendSample — BlendSpace 采样点（SampleValue/Time/RateScale/bIsValid）
    "FBlendSample",
}
"""需要 tagged fallback 解析的结构体名称集合。"""

TAGGED_FALLBACK_STRUCT_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "MemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    "SimpleMemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    # 新增 UE5.5 结构体
    "NewVariables": [
        ("VarName", "NameProperty"),
        ("VarGuid", "GuidProperty"),
        ("VarType", "StructProperty"),  # FEdGraphPinType
    ],
    "ImplementedInterfaces": [
        ("InterfaceName", "NameProperty"),
        ("InterfaceGuid", "GuidProperty"),
    ],
    "LastEditedDocuments": [
        ("DocumentName", "NameProperty"),
    ],
    "CategorySorting": [
        ("CategoryName", "NameProperty"),
    ],
    # AnimSequence 结构体 tagged fallback schemas
    "FrameRate": [
        ("Numerator", "FloatProperty"),
        ("Denominator", "IntProperty"),
    ],
    "AnimNotifyTrack": [
        ("TrackIndex", "Int64Property"),
        ("TrackName", "NameProperty"),
    ],
    # 编辑器结构体
    "FEditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    "EditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    # 材质参数结构体 tagged fallback schemas
    "FMaterialParameterInfo": [
        ("ParameterName", "NameProperty"),
        ("Index", "IntProperty"),
        ("bOverride", "BoolProperty"),
    ],
    "ScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),   # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    "FScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),   # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    # 动画混合空间结构体 tagged fallback schemas
    "BlendSample": [
        ("SampleValue", "StructProperty"),   # FVector — 混合空间采样点坐标
        ("Time", "FloatProperty"),            # float — 动画时间值
        ("RateScale", "IntProperty"),         # int32 — 播放速率缩放
        ("bIsValid", "BoolProperty"),         # bool — 采样点是否有效
    ],
    "FBlendSample": [
        ("SampleValue", "StructProperty"),   # FVector — 混合空间采样点坐标
        ("Time", "FloatProperty"),            # float — 动画时间值
        ("RateScale", "IntProperty"),         # int32 — 播放速率缩放
        ("bIsValid", "BoolProperty"),         # bool — 采样点是否有效
    ],
}


# 向后兼容别名
_EXPECTED_STRUCT_SIZES = EXPECTED_STRUCT_SIZES
_LWC_TYPE_MAP = LWC_TYPE_MAP
_LWC_DOUBLE_TYPE_TO_BASE = LWC_DOUBLE_TYPE_TO_BASE
_LWC_FLOAT_TYPE_TO_BASE = LWC_FLOAT_TYPE_TO_BASE
_TAGGED_FALLBACK_STRUCTS = TAGGED_FALLBACK_STRUCTS
_TAGGED_FALLBACK_STRUCT_SCHEMAS = TAGGED_FALLBACK_STRUCT_SCHEMAS
