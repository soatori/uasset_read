"""JSONRenderer 单元测试。"""

import json
from io import StringIO

import pytest

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions


@pytest.fixture
def renderer():
    return JSONRenderer()


class TestJSONRendererBasic:
    """基础渲染功能测试。"""

    def test_render_returns_valid_json(self, renderer, make_package_ir):
        """render 返回有效 JSON 字符串。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())

        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_render_includes_header(self, renderer, make_package_ir):
        """JSON 包含 header 字段（通过 summary）。"""
        ir = make_package_ir(name="MyPackage")
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "summary" in parsed
        assert parsed["summary"]["package_name"] == "MyPackage"

    def test_render_empty_exports(self, renderer, make_package_ir):
        """无 export 时 exports 为空列表。"""
        ir = make_package_ir(exports=[])
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert parsed["exports"] == []

    def test_render_with_export(self, renderer, make_package_ir, make_export_ir):
        """包含 export 时正确序列化。"""
        export = make_export_ir(object_name="TestFunc")
        ir = make_package_ir(exports=[export])
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert len(parsed["exports"]) == 1
        assert parsed["exports"][0]["object_name"] == "TestFunc"

    def test_render_includes_status(self, renderer, make_package_ir):
        """JSON 包含 status 字段。"""
        ir = make_package_ir()
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "status" in parsed
        assert parsed["status"]["status"] == "success"

    def test_render_summary_fields(self, renderer, make_package_ir):
        """summary 包含预期的元数据字段。"""
        ir = make_package_ir(name="TestPkg")
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        summary = parsed["summary"]
        assert summary["package_name"] == "TestPkg"
        assert summary["package_flags_decoded"] is not None
        assert isinstance(summary["total_export_count"], int)
        assert isinstance(summary["total_import_count"], int)

    def test_render_multiple_exports(self, renderer, make_package_ir, make_export_ir):
        """多个 export 按顺序序列化。"""
        e1 = make_export_ir(object_name="Alpha")
        e2 = make_export_ir(object_name="Beta")
        ir = make_package_ir(exports=[e1, e2])
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert len(parsed["exports"]) == 2
        assert parsed["exports"][0]["object_name"] == "Alpha"
        assert parsed["exports"][1]["object_name"] == "Beta"


class TestJSONRendererOptions:
    """渲染选项测试。"""

    def test_indent_option(self, renderer, make_package_ir):
        """indent 选项控制 JSON 缩进。"""
        ir = make_package_ir()

        compact = renderer.render(ir, RenderOptions(indent=None))
        indented = renderer.render(ir, RenderOptions(indent=2))

        # 紧凑模式无多余空白
        assert "\n  " not in compact
        # 缩进模式有换行
        assert "\n" in indented

    def test_include_schema_option(self, renderer, make_package_ir):
        """include_schema=True 时添加 $schema 字段。"""
        ir = make_package_ir()

        with_schema = renderer.render(ir, RenderOptions(include_schema=True))
        without_schema = renderer.render(ir, RenderOptions(include_schema=False))

        assert '"$schema"' in with_schema
        assert '"$schema"' not in without_schema


class TestJSONRendererEdgeCases:
    """边界情况测试。"""

    def test_render_with_none_fields(self, renderer, make_package_ir):
        """处理 None 字段不崩溃。"""
        ir = make_package_ir()

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        # 验证可以正常解析
        assert "summary" in parsed

    def test_render_to_writer(self, renderer, make_package_ir):
        """render_to 写入 StringIO。"""
        ir = make_package_ir()
        writer = StringIO()

        renderer.render_to(ir, writer, RenderOptions())

        output = writer.getvalue()
        parsed = json.loads(output)
        assert "summary" in parsed

    def test_render_to_matches_render(self, renderer, make_package_ir, make_export_ir):
        """render_to 与 render 输出内容一致。"""
        export = make_export_ir(object_name="MatchTest")
        ir = make_package_ir(exports=[export])

        render_result = json.loads(renderer.render(ir, RenderOptions(indent=None)))
        writer = StringIO()
        renderer.render_to(ir, writer, RenderOptions(indent=None))
        render_to_result = json.loads(writer.getvalue())

        assert render_result == render_to_result

    def test_render_to_none_options_uses_defaults(self, renderer, make_package_ir):
        """render_to 传入 None 时使用默认 RenderOptions。"""
        ir = make_package_ir()
        writer = StringIO()

        renderer.render_to(ir, writer, options=None)

        output = writer.getvalue()
        parsed = json.loads(output)
        assert "summary" in parsed

    def test_render_with_empty_package_name(self, renderer, make_package_ir):
        """空包名正常渲染。"""
        ir = make_package_ir(name="")
        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert parsed["summary"]["package_name"] == ""

    def test_render_format_name(self, renderer):
        """format_name 属性返回 json。"""
        assert renderer.format_name == "json"


class TestJSONRendererGraphs:
    """图渲染测试。"""

    def test_render_with_graph(self, renderer, make_package_ir, make_export_ir,
                               make_graph_ir, make_node_ir, make_pin_ir):
        """包含图的 export 正确序列化。"""
        pin = make_pin_ir(pin_name="ExecPin", pin_type="exec", direction="output")
        node = make_node_ir(pins=[pin])
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert len(parsed["exports"]) == 1
        export_data = parsed["exports"][0]
        assert "graphs" in export_data
        assert len(export_data["graphs"]) == 1

    def test_render_graph_structure(self, renderer, make_package_ir, make_export_ir,
                                    make_graph_ir, make_node_ir, make_pin_ir):
        """图结构包含 graph_name、graph_guid、nodes。"""
        pin = make_pin_ir()
        node = make_node_ir(pins=[pin])
        graph = make_graph_ir(name="MyGraph", nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        graph_data = parsed["exports"][0]["graphs"][0]
        assert graph_data["graph_name"] == "MyGraph"
        assert graph_data["graph_guid"] == "00000000000000000000000000000002"
        assert len(graph_data["nodes"]) == 1

    def test_render_node_pins(self, renderer, make_package_ir, make_export_ir,
                              make_graph_ir, make_node_ir, make_pin_ir):
        """节点的 pin 包含所有结构化类型字段。"""
        pin = make_pin_ir(
            pin_name="ReturnValue",
            pin_type="bool",
            direction="output",
            default_value="True",
        )
        node = make_node_ir(pins=[pin])
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        pin_data = parsed["exports"][0]["graphs"][0]["nodes"][0]["pins"][0]
        assert pin_data["pin_name"] == "ReturnValue"
        assert pin_data["pin_type"] == "bool"
        assert pin_data["direction"] == "output"
        assert pin_data["default_value"] == "True"
        # 结构化类型字段默认值
        assert "pin_category" in pin_data
        assert "container_type" in pin_data

    def test_render_node_with_macro_expansion(self, renderer, make_package_ir,
                                               make_export_ir, make_graph_ir,
                                               make_node_ir):
        """节点包含 macro_expansion 字段时正确序列化。"""
        node = make_node_ir()
        node.macro_expansion = {"macro_name": "TestMacro"}
        graph = make_graph_ir(nodes=[node])
        export = make_export_ir(graphs=[graph])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        node_data = parsed["exports"][0]["graphs"][0]["nodes"][0]
        assert node_data["macro_expansion"]["macro_name"] == "TestMacro"


class TestJSONRendererVariables:
    """变量渲染测试。"""

    def test_render_with_variables(self, renderer, make_package_ir):
        """变量正确序列化。"""
        from uasset_read.models.ir import VariableIR

        var = VariableIR(name="MyVar", type="int", default_value="0", kind="instance")
        ir = make_package_ir(variables=[var])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "variables" in parsed
        assert len(parsed["variables"]) == 1
        assert parsed["variables"][0]["name"] == "MyVar"

    def test_render_editor_variable_filtered(self, renderer, make_package_ir):
        """编辑器内部变量在 standard 模式下被过滤。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="UbergraphPages", type="Array<int>", default_value="[]", kind="instance"),
            VariableIR(name="UserVar", type="bool", default_value="False", kind="instance"),
        ]
        ir = make_package_ir(variables=vars_)

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "variables" in parsed
        assert len(parsed["variables"]) == 1
        assert parsed["variables"][0]["name"] == "UserVar"

    def test_render_all_editor_variables_hidden(self, renderer, make_package_ir):
        """全是编辑器变量时不输出 variables 字段。"""
        from uasset_read.models.ir import VariableIR

        vars_ = [
            VariableIR(name="FunctionGraphs", type="Array<int>", default_value="[]", kind="instance"),
            VariableIR(name="CategorySorting", type="Array<str>", default_value="[]", kind="instance"),
        ]
        ir = make_package_ir(variables=vars_)

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "variables" not in parsed


class TestJSONRendererProperties:
    """属性渲染测试。"""

    def test_render_export_with_properties(self, renderer, make_package_ir, make_export_ir):
        """export 包含属性时正确序列化。"""
        from uasset_read.models.ir import PropertyIR

        prop = PropertyIR(name="Health", type="float", value=100.0, array_index=0, guid=None)
        export = make_export_ir(properties=[prop])
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        assert "properties" in parsed["exports"][0]
        props = parsed["exports"][0]["properties"]
        assert len(props) == 1
        assert props[0]["name"] == "Health"
        assert props[0]["value"] == 100.0

    def test_render_editor_property_filtered(self, renderer, make_package_ir, make_export_ir):
        """编辑器布局属性在 standard 模式下被过滤。"""
        from uasset_read.models.ir import PropertyIR

        props = [
            PropertyIR(name="NodePosX", type="int", value=100, array_index=0, guid=None),
            PropertyIR(name="GameProp", type="int", value=42, array_index=0, guid=None),
        ]
        export = make_export_ir(properties=props)
        ir = make_package_ir(exports=[export])

        result = renderer.render(ir, RenderOptions())
        parsed = json.loads(result)

        # 只有 GameProp 应该通过过滤
        assert "properties" in parsed["exports"][0]
        filtered = [p for p in parsed["exports"][0]["properties"] if p["name"] == "GameProp"]
        assert len(filtered) == 1
        assert "NodePosX" not in [p["name"] for p in parsed["exports"][0]["properties"]]
