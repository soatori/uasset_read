"""GatherableTextData 本地化数据 IR 结构测试。

参照 UE 源码 GatherableTextData.h:
- FGatherableTextData: NamespaceName, SourceData, SourceSiteContexts
- FTextSourceSiteContext: KeyName, SiteDescription, IsEditorOnly, IsOptional
"""

from __future__ import annotations

from uasset_read.models.ir import GatherableTextDataIR, SourceSiteContextIR


class TestSourceSiteContextIR:
    """测试 SourceSiteContextIR 数据结构。"""

    def test_basic_construction(self) -> None:
        """基本构造与字段访问。"""
        ctx = SourceSiteContextIR(
            key_name="UI.Button.OK",
            site_description="OK button text",
            is_editor_only=False,
            is_optional=False,
        )
        assert ctx.key_name == "UI.Button.OK"
        assert ctx.site_description == "OK button text"
        assert ctx.is_editor_only is False
        assert ctx.is_optional is False

    def test_editor_only_context(self) -> None:
        """编辑器专用上下文。"""
        ctx = SourceSiteContextIR(
            key_name="Editor.Tooltip",
            site_description="Tooltip for editor widget",
            is_editor_only=True,
            is_optional=True,
        )
        assert ctx.is_editor_only is True
        assert ctx.is_optional is True

    def test_equality(self) -> None:
        """相等性判断。"""
        ctx1 = SourceSiteContextIR("K", "D", False, False)
        ctx2 = SourceSiteContextIR("K", "D", False, False)
        assert ctx1 == ctx2

    def test_inequality(self) -> None:
        """不等性判断。"""
        ctx1 = SourceSiteContextIR("K1", "D", False, False)
        ctx2 = SourceSiteContextIR("K2", "D", False, False)
        assert ctx1 != ctx2


class TestGatherableTextDataIR:
    """测试 GatherableTextDataIR 数据结构。"""

    def test_basic_construction(self) -> None:
        """基本构造与字段访问。"""
        ir = GatherableTextDataIR(
            namespace_name="Game",
            source_string="Hello World",
            source_site_contexts=[],
        )
        assert ir.namespace_name == "Game"
        assert ir.source_string == "Hello World"
        assert ir.source_site_contexts == []

    def test_with_contexts(self) -> None:
        """包含多个上下文。"""
        ctx1 = SourceSiteContextIR("Key1", "Site1", False, False)
        ctx2 = SourceSiteContextIR("Key2", "Site2", True, True)
        ir = GatherableTextDataIR(
            namespace_name="MyGame.UI",
            source_string="Submit",
            source_site_contexts=[ctx1, ctx2],
        )
        assert len(ir.source_site_contexts) == 2
        assert ir.source_site_contexts[0].key_name == "Key1"
        assert ir.source_site_contexts[1].is_editor_only is True

    def test_empty_namespace(self) -> None:
        """空命名空间。"""
        ir = GatherableTextDataIR(
            namespace_name="",
            source_string="Some text",
            source_site_contexts=[],
        )
        assert ir.namespace_name == ""
        assert ir.source_string == "Some text"

    def test_equality(self) -> None:
        """相等性判断。"""
        ir1 = GatherableTextDataIR("NS", "Text", [])
        ir2 = GatherableTextDataIR("NS", "Text", [])
        assert ir1 == ir2

    def test_inequality(self) -> None:
        """不等性判断。"""
        ir1 = GatherableTextDataIR("NS1", "Text", [])
        ir2 = GatherableTextDataIR("NS2", "Text", [])
        assert ir1 != ir2

    def test_multiple_contexts_equality(self) -> None:
        """含上下文的相等性判断。"""
        ctx = SourceSiteContextIR("K", "D", False, False)
        ir1 = GatherableTextDataIR("NS", "Text", [ctx])
        ir2 = GatherableTextDataIR("NS", "Text", [ctx])
        assert ir1 == ir2
