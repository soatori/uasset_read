"""UMaterialInstance 参数提取增强测试"""
import pytest
from unittest.mock import MagicMock


class TestCollectParametersEnhanced:
    def test_collect_parameters_extracts_association(self):
        """_collect_parameters 应提取 Association 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "BaseColor", "Association": 0, "Index": -1},
            "ParameterValue": [1.0, 0.0, 0.0, 1.0],
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert "BaseColor" in result
        assert result["BaseColor"]["association"] == 0
        assert result["BaseColor"]["index"] == -1

    def test_collect_parameters_extracts_index(self):
        """_collect_parameters 应提取 Index 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "LayerMask", "Association": 1, "Index": 2},
            "ParameterValue": 0.5,
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert result["LayerMask"]["index"] == 2

    def test_collect_parameters_preserves_value(self):
        """_collect_parameters 应保留原有 value 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "Roughness"},
            "ParameterValue": 0.3,
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert result["Roughness"]["value"] == 0.3
