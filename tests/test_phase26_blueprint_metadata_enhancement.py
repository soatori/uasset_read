"""
Phase 26: 蓝图元数据增强测试

测试 BlueprintVariable 类的增强功能：
- 属性标志解析
- 元数据提取（EditCondition、Category、MetaClass）
- 可见性标志
"""
import pytest
from uasset_read import (
    BlueprintVariable,
    FArchive,
    read_blueprint_variable,
    PackageFileSummary,
    CPF_EditAnywhere,
    CPF_EditInstanceOnly,
    CPF_BlueprintReadWrite,
    CPF_BlueprintReadOnly,
    CPF_Transient,
    CPF_SaveGame,
    CPF_ExposeOnSpawn,
)


class TestPhase26BlueprintVariableEnhancements:
    """测试 Phase 26 BlueprintVariable 增强功能"""

    def test_blueprint_variable_has_phase26_fields(self):
        """BlueprintVariable 必须包含 Phase 26 新增字段 (per 26-01)"""
        var = BlueprintVariable(
            var_name="TestVar",
            var_type=None,
            category="TestCategory",
            property_flags=0
        )

        # Phase 26: 元数据字段
        assert hasattr(var, 'edit_condition')
        assert hasattr(var, 'meta_class')
        assert hasattr(var, 'edit_category')
        assert hasattr(var, 'edit_widget')
        assert hasattr(var, 'meta_data')

        # Phase 26: 可见性标志
        assert hasattr(var, 'is_edit_anywhere')
        assert hasattr(var, 'is_edit_instance_only')
        assert hasattr(var, 'is_visible_anywhere')
        assert hasattr(var, 'is_blueprint_read_only')

        # Phase 26: 完整标志位
        assert hasattr(var, 'is_blueprint_readable')
        assert hasattr(var, 'is_blueprint_writable')
        assert hasattr(var, 'is_transient')
        assert hasattr(var, 'is_duplicate_transient')
        assert hasattr(var, 'is_save_game')
        assert hasattr(var, 'is_no_clear')
        assert hasattr(var, 'is_reference_only')
        assert hasattr(var, 'is_blueprint_assignable')
        assert hasattr(var, 'is_blueprint_callable')
        assert hasattr(var, 'is_rep_notify')
        assert hasattr(var, 'is_interp')
        assert hasattr(var, 'is_expose_on_spawn')
        assert hasattr(var, 'is_net')
        assert hasattr(var, 'is_replicated')
        assert hasattr(var, 'is_non_pi_ed_duplicate_transient')

    def test_parse_property_flags_returns_correct_flags(self):
        """_parse_property_flags 必须正确解析属性标志 (per 26-01)"""
        archive = FArchive.__new__(FArchive)
        archive._byte_swapping = False

        # 测试 EditAnywhere 标志
        flags = archive._parse_property_flags(CPF_EditAnywhere)
        assert flags['is_edit_anywhere'] == True
        assert flags['is_edit_instance_only'] == False

        # 测试 EditInstanceOnly 标志
        flags = archive._parse_property_flags(CPF_EditInstanceOnly)
        assert flags['is_edit_instance_only'] == True
        assert flags['is_edit_anywhere'] == False

        # 测试 BlueprintReadWrite 标志
        flags = archive._parse_property_flags(CPF_BlueprintReadWrite)
        assert flags['is_blueprint_readable'] == True
        assert flags['is_blueprint_writable'] == True

        # 测试 BlueprintReadOnly 标志
        flags = archive._parse_property_flags(CPF_BlueprintReadOnly)
        assert flags['is_blueprint_read_only'] == True
        assert flags['is_blueprint_readable'] == False

        # 测试 Transient 标志
        flags = archive._parse_property_flags(CPF_Transient)
        assert flags['is_transient'] == True

        # 测试 SaveGame 标志
        flags = archive._parse_property_flags(CPF_SaveGame)
        assert flags['is_save_game'] == True

        # 测试 ExposeOnSpawn 标志
        flags = archive._parse_property_flags(CPF_ExposeOnSpawn)
        assert flags['is_expose_on_spawn'] == True

    def test_parse_property_flags_combined_flags(self):
        """_parse_property_flags 必须正确解析组合标志 (per 26-01)"""
        archive = FArchive.__new__(FArchive)
        archive._byte_swapping = False

        # 测试组合标志
        combined_flags = CPF_EditAnywhere | CPF_BlueprintReadWrite | CPF_Transient
        flags = archive._parse_property_flags(combined_flags)

        assert flags['is_edit_anywhere'] == True
        assert flags['is_blueprint_readable'] == True
        assert flags['is_blueprint_writable'] == True
        assert flags['is_transient'] == True

    def test_meta_data_initialized_as_dict(self):
        """meta_data 字段必须初始化为空字典 (per 26-01)"""
        var = BlueprintVariable(
            var_name="TestVar",
            var_type=None,
            category="TestCategory",
            property_flags=0
        )

        assert var.meta_data == {}

    def test_blueprint_variable_can_set_phase26_fields(self):
        """BlueprintVariable 必须可以设置 Phase 26 字段 (per 26-01)"""
        var = BlueprintVariable(
            var_name="TestVar",
            var_type=None,
            category="TestCategory",
            property_flags=0,
            edit_condition="MyVar > 0",
            meta_class="UObject",
            is_edit_anywhere=True,
            is_transient=True,
            is_save_game=True
        )

        assert var.edit_condition == "MyVar > 0"
        assert var.meta_class == "UObject"
        assert var.is_edit_anywhere == True
        assert var.is_transient == True
        assert var.is_save_game == True

    def test_metadata_field_stores_meta_data(self):
        """metadata 字段必须存储元数据 (per 26-01)"""
        var = BlueprintVariable(
            var_name="TestVar",
            var_type=None,
            category="TestCategory",
            property_flags=0,
            metadata={
                "EditCondition": "MyVar > 0",
                "Category": "Test",
                "MetaClass": "UObject"
            }
        )

        assert var.metadata["EditCondition"] == "MyVar > 0"
        assert var.metadata["Category"] == "Test"
        assert var.metadata["MetaClass"] == "UObject"

    def test_all_phase26_boolean_flags_default_to_false(self):
        """所有 Phase 26 布尔标志必须默认为 False (per 26-01)"""
        var = BlueprintVariable(
            var_name="TestVar",
            var_type=None,
            category="TestCategory",
            property_flags=0
        )

        # 可见性标志
        assert var.is_edit_anywhere == False
        assert var.is_edit_instance_only == False
        assert var.is_visible_anywhere == False
        assert var.is_blueprint_read_only == False

        # 完整标志位
        assert var.is_blueprint_readable == False
        assert var.is_blueprint_writable == False
        assert var.is_transient == False
        assert var.is_duplicate_transient == False
        assert var.is_save_game == False
        assert var.is_no_clear == False
        assert var.is_reference_only == False
        assert var.is_blueprint_assignable == False
        assert var.is_blueprint_callable == False
        assert var.is_rep_notify == False
        assert var.is_interp == False
        assert var.is_expose_on_spawn == False
        assert var.is_net == False
        assert var.is_replicated == False
        assert var.is_non_pi_ed_duplicate_transient == False