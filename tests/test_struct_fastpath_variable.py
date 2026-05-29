"""测试变长类型 Struct fast-path"""
import pytest


def test_variable_length_types_not_in_fastpath():
    """确认变长类型不在 fast-path 中"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    # 这些类型是变长的，不应在 fast-path 中
    variable_types = [
        "SoftObjectPath",
        "StringAssetReference",
        "StringClassReference",
        "SoftClassPath",
        "GameplayTagContainer",
        "PerPlatformBool",
        "PerPlatformFloat",
        "PerPlatformInt",
        "PerPlatformFrameRate",
        "PerPlatformFString",
        "PerQualityLevelInt",
        "PerQualityLevelFloat",
        "ExpressionInput",
        "MaterialAttributesInput",
        "ColorMaterialInput",
        "ScalarMaterialInput",
        "VectorMaterialInput",
        "Vector2MaterialInput",
        "RichCurveKey",
        "SimpleCurveKey",
        "NameCurveKey",
        "CompressedRichCurve",
        "RawAnimSequenceTrack",
        "AnimationAttributeIdentifier",
        "AttributeCurve",
        "MovieSceneFrameRange",
        "MovieSceneSegment",
        "MovieSceneFloatChannel",
        "MovieSceneDoubleChannel",
        "MovieSceneSubSequenceTree",
        "MovieSceneTrackFieldData",
        "MovieSceneSubSectionFieldData",
        "SectionEvaluationDataTree",
        "MovieSceneEvalTemplatePtr",
        "MovieSceneEvaluationFieldEntityTree",
        "MovieSceneEventParameters",
        "MovieSceneTrackImplementationPtr",
        "MovieSceneSequenceInstanceDataPtr",
        "MovieSceneTimeWarpVariant",
        "NiagaraVariable",
        "NiagaraVariableBase",
        "NiagaraVariableWithOffset",
        "NiagaraDataInterfaceGPUParamInfo",
        "NiagaraDataChannelVariable",
        "ClothLODDataCommon",
        "ClothLODData",
        "ClothTetherData",
        "InstancedStruct",
        "InstancedStructContainer",
        "InstancedPropertyBag",
        "InstancedOverridablePropertyBag",
        "WorldConditionQueryDefinition",
        "UniversalObjectLocatorFragment",
        "UniqueNetIdRepl",
        "Spline",
        "TypedParameter",
        "EdGraphPinType",
        "NavAgentSelector",
        "SmartName",
        "MaterialOverrideNanite",
        "MaterialLayersFunctionsTree",
        "LevelSequenceObjectReferenceMap",
        "MidiEvent",
        "PCGPoint",
        "PCGDataPtrWrapper",
        "PCGPointArray",
        "SkeletalMeshSamplingLODBuiltData",
        "SkeletalMeshSamplingRegionBuiltData",
    ]

    for type_name in variable_types:
        assert _EXPECTED_STRUCT_SIZES.get(type_name) is None, f"{type_name} should not be in fast-path"


def test_all_fastpath_types_have_valid_sizes():
    """验证所有 fast-path 类型都有有效的大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    for type_name, size in _EXPECTED_STRUCT_SIZES.items():
        assert isinstance(size, int), f"{type_name} size should be int, got {type(size)}"
        assert size > 0, f"{type_name} size should be positive, got {size}"


def test_fastpath_types_count():
    """验证 fast-path 类型数量"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    # 应该有 40+ 种 fast-path 类型
    assert len(_EXPECTED_STRUCT_SIZES) >= 40, f"Expected at least 40 fast-path types, got {len(_EXPECTED_STRUCT_SIZES)}"
