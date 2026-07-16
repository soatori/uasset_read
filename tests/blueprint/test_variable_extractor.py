"""variable_extractor.py 单元测试"""

from uasset_read.constants import CPF_Edit, CPF_EditConst
from uasset_read.blueprint.variable_extractor import _map_property_flags


class TestMapPropertyFlags:
    """_map_property_flags 对 CPF_Edit / CPF_EditConst 的处理。"""

    def test_edit_only_sets_is_edit_instance_only(self):
        """仅设 CPF_Edit 时 is_edit_instance_only 为 True。"""
        flags = CPF_Edit
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is True
        assert result["is_edit_instance_only"] is True

    def test_edit_and_editconst_clears_is_edit_instance_only(self):
        """CPF_Edit | CPF_EditConst 时 is_edit_instance_only 为 False。"""
        flags = CPF_Edit | CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is True
        assert result["is_edit_instance_only"] is False

    def test_no_edit_flags(self):
        """无 CPF_Edit 标志时两个 edit 字段均为 False。"""
        flags = 0
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is False
        assert result["is_edit_instance_only"] is False

    def test_editconst_alone(self):
        """仅有 CPF_EditConst（无 CPF_Edit）时两个 edit 字段均为 False。"""
        flags = CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is False
        assert result["is_edit_instance_only"] is False

    def test_other_flags_not_affected(self):
        """其他标志不受影响。"""
        flags = CPF_Edit | CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_blueprint_readable"] is False
        assert result["is_transient"] is False
