"""BlueprintVariable var_type 字段填充测试（Issue #172）。"""

import pytest


class TestVariableVarType:
    """验证 BlueprintVariable.var_type 不为 None。"""

    def test_variable_has_var_type(self):
        """变量应包含 var_type 类型信息"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(
            "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset",
            tolerant=True,
        )
        assert result.is_success, f"解析失败: {result.errors}"
        blueprint = result.blueprint
        assert blueprint is not None, "蓝图数据不应为 None"
        assert len(blueprint.variables) > 0, "蓝图变量列表不应为空"

        none_vars = [v for v in blueprint.variables if v.var_type is None]
        assert not none_vars, (
            f"以下变量的 var_type 为 None: {[v.var_name for v in none_vars]}"
        )

        for var in blueprint.variables:
            assert var.var_type is not None, f"变量 {var.var_name} 的 var_type 为 None"
            # var_type 的 pin_category 不应为空
            assert var.var_type.pin_category, (
                f"变量 {var.var_name} 的 var_type.pin_category 为空"
            )
