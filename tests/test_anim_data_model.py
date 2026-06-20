"""UAnimDataModel 解析器测试。"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_parse_anim_data_model_returns_dict():
    """验证 parse_anim_data_model 返回正确的字典结构。"""
    from uasset_read.parsers.asset_types.anim_data_model import parse_anim_data_model

    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    archive.read.return_value = b"\x00" * 256

    result = parse_anim_data_model(archive, [])

    assert isinstance(result, dict)
    assert "parse_status" in result
    assert result["parse_status"] == "partial_metadata"
    assert "raw_offset" in result
    assert "sample_size" in result


def test_anim_data_model_handler_registered():
    """验证 AnimationDataModel handler 已注册到 registry。"""
    from uasset_read.parsers.class_registry import get_class_registry

    registry = get_class_registry()
    handler = registry.find_handler("AnimationDataModel")
    assert handler is not None
    assert handler.handler_name == "AnimDataModelHandler"


def test_anim_data_model_not_skipped():
    """验证 AnimationDataModel 不再被 tolerant skip。"""
    from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

    export = MagicMock()
    export.object_name = "AM_MM_Rifle_DryFire"

    # class_name 参数传入 "AnimationDataModel"
    result = should_skip_export_for_tolerant_parsing(export, class_name="AnimationDataModel")
    assert result is False
