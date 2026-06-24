"""JSON 渲染器输出测试。"""
from __future__ import annotations

import json
import pytest

from uasset_read.core import parse_single

SAMPLE_TEXTURE = "E:/Develop/lib/Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_New_D.uasset"


class TestJSONRendererExports:
    """验证 JSON 渲染器对不同资产类型 exports 的输出。"""

    def test_json_renderer_includes_non_blueprint_exports(self):
        """非蓝图资产应输出所有 exports"""
        output = json.loads(parse_single(SAMPLE_TEXTURE))
        assert len(output.get("exports", [])) > 0, "非蓝图资产应有 exports"
