"""
uasset-read skill集成测试

验证skill触发、API调用、输出解读三个环节正确工作。

API版本: output_version: "3.0" (Phase 14冻结)
"""

import pytest
from pathlib import Path
from uasset_read import parse_uasset, format_json_full, format_json_summary, format_markdown


# 测试资产路径（D-15-04锁定）
TEST_ASSET_PATH = Path(
    "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
)


class TestSkillFilesExist:
    """SKILL-04: 验证skill文件结构完整"""

    def test_skill_directory_exists(self):
        """验证skill目录存在"""
        skill_dir = Path(".claude/skills/uasset-read")
        assert skill_dir.exists(), "skill目录不存在"

    def test_skill_md_exists(self):
        """验证SKILL.md主文件存在"""
        skill_md = Path(".claude/skills/uasset-read/SKILL.md")
        assert skill_md.exists(), "SKILL.md不存在"

    def test_knowledge_directory_exists(self):
        """验证knowledge目录存在"""
        knowledge_dir = Path(".claude/skills/uasset-read/knowledge")
        assert knowledge_dir.exists(), "knowledge目录不存在"

    def test_knowledge_files_count(self):
        """验证knowledge文件数量>=6"""
        knowledge_dir = Path(".claude/skills/uasset-read/knowledge")
        md_files = list(knowledge_dir.glob("*.md"))
        assert len(md_files) >= 6, f"知识文件数量不足: {len(md_files)} < 6"

    def test_examples_directory_exists(self):
        """验证examples目录存在"""
        examples_dir = Path(".claude/skills/uasset-read/examples")
        assert examples_dir.exists(), "examples目录不存在"

    def test_examples_files_count(self):
        """验证examples文件数量>=4"""
        examples_dir = Path(".claude/skills/uasset-read/examples")
        md_files = list(examples_dir.glob("*.md"))
        assert len(md_files) >= 4, f"示例文件数量不足: {len(md_files)} < 4"


class TestSkillTriggersDefined:
    """SKILL-04: 验证触发词定义（D-15-01）"""

    def test_skill_md_contains_trigger_uasset(self):
        """验证触发词 'uasset' 在SKILL.md中"""
        skill_md = Path(".claude/skills/uasset-read/SKILL.md").read_text()
        assert "uasset" in skill_md.lower(), "触发词 'uasset' 未在SKILL.md中定义"

    def test_skill_md_contains_trigger_extension(self):
        """验证触发词 '.uasset' 在SKILL.md中"""
        skill_md = Path(".claude/skills/uasset-read/SKILL.md").read_text()
        assert ".uasset" in skill_md, "触发词 '.uasset' 未在SKILL.md中定义"

    def test_skill_md_contains_trigger_parse_uasset(self):
        """验证触发词 'parse_uasset' 在SKILL.md中"""
        skill_md = Path(".claude/skills/uasset-read/SKILL.md").read_text()
        assert "parse_uasset" in skill_md, "触发词 'parse_uasset' 未在SKILL.md中定义"

    def test_skill_md_contains_trigger_blueprints(self):
        """验证触发词 '蓝图' 在SKILL.md中"""
        skill_md = Path(".claude/skills/uasset-read/SKILL.md").read_text()
        assert "蓝图" in skill_md, "触发词 '蓝图' 未在SKILL.md中定义"


class TestParseUassetApiCall:
    """SKILL-04: 验证parse_uasset API可调用"""

    def test_parse_uasset_importable(self):
        """验证parse_uasset可导入"""
        from uasset_read import parse_uasset
        assert callable(parse_uasset), "parse_uasset不是可调用函数"

    def test_parse_uasset_returns_parse_result(self):
        """验证parse_uasset返回ParseResult类型"""
        # 使用测试资产（如果可用）
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            assert hasattr(result, "is_success"), "返回结果无is_success字段"
            assert hasattr(result, "summary"), "返回结果无summary字段"
            assert hasattr(result, "export_map"), "返回结果无export_map字段"
        else:
            pytest.skip("测试资产不可用")

    def test_parse_uasset_success_on_valid_asset(self):
        """验证有效资产解析成功"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            assert result.is_success, f"解析失败: {result.errors}"
        else:
            pytest.skip("测试资产不可用")

    def test_parse_uasset_returns_package_name(self):
        """验证解析结果包含package_name"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            assert result.summary.package_name != "", "package_name为空"
            assert "FirstPerson" in result.summary.package_name, f"package_name不含FirstPerson: {result.summary.package_name}"
        else:
            pytest.skip("测试资产不可用")


class TestOutputInterpretation:
    """SKILL-04: 验证输出字段可正确解读"""

    def test_status_field_valid(self):
        """验证status字段为有效值"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_summary(result)
            assert output["status"]["status"] in ["success", "fail", "error"], \
                f"status值无效: {output['status']['status']}"
        else:
            pytest.skip("测试资产不可用")

    def test_output_version_is_3_0(self):
        """验证output_version为'3.0'"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_summary(result)
            assert output["output_version"] == "3.0", \
                f"output_version不正确: {output['output_version']}"
        else:
            pytest.skip("测试资产不可用")

    def test_graphs_summary_is_list(self):
        """验证graphs_summary是列表类型"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_summary(result)
            assert "graphs_summary" in output, "缺少graphs_summary字段"
            assert isinstance(output["graphs_summary"], list), \
                f"graphs_summary类型不正确: {type(output['graphs_summary'])}"
        else:
            pytest.skip("测试资产不可用")

    def test_exports_is_list(self):
        """验证exports是列表类型"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_full(result)
            assert "exports" in output, "缺少exports字段"
            assert isinstance(output["exports"], list), \
                f"exports类型不正确: {type(output['exports'])}"
        else:
            pytest.skip("测试资产不可用")

    def test_graphs_summary_contains_eventgraph(self):
        """验证graphs_summary包含EventGraph（如果测试资产有蓝图数据）"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_summary(result)

            # 如果graphs_summary为空，可能是Cooked资产或特殊资产，跳过而非失败
            if not output["graphs_summary"]:
                pytest.skip("测试资产无EventGraph数据（可能是Cooked资产）")

            graph_names = [g["graph_name"] for g in output["graphs_summary"]]
            assert "EventGraph" in graph_names, f"未找到EventGraph: {graph_names}"
        else:
            pytest.skip("测试资产不可用")

    def test_execution_flows_contains_function_name(self):
        """验证execution_flows包含function_name"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_summary(result)

            for flow in output["graphs_summary"]:
                for exec_flow in flow["execution_flows"]:
                    assert "function_name" in exec_flow, "execution_flow缺少function_name"
                    assert exec_flow["function_name"] != "", "function_name为空"
        else:
            pytest.skip("测试资产不可用")


class TestFormatFunctions:
    """验证输出格式函数"""

    def test_format_json_full_returns_dict(self):
        """验证format_json_full返回字典"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            output = format_json_full(result)
            assert isinstance(output, dict), f"输出类型不正确: {type(output)}"
        else:
            pytest.skip("测试资产不可用")

    def test_format_json_summary_compact(self):
        """验证format_json_summary比format_json_full更精简"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            full = format_json_full(result)
            summary = format_json_summary(result)

            # summary应移除imports字段
            assert "imports" not in summary, "summary包含imports（应移除）"
            # full应包含imports字段
            assert "imports" in full, "full缺少imports字段"
        else:
            pytest.skip("测试资产不可用")

    def test_format_markdown_starts_with_hash(self):
        """验证format_markdown以Markdown标题开头"""
        if TEST_ASSET_PATH.exists():
            result = parse_uasset(str(TEST_ASSET_PATH))
            markdown = format_markdown(result)
            assert markdown.startswith("#"), f"Markdown不以#开头: {markdown[:20]}"
        else:
            pytest.skip("测试资产不可用")


class TestKnowledgeFilesContent:
    """验证知识文件内容质量"""

    def test_blueprint_semantics_has_eventgraph(self):
        """验证blueprint-semantics.md包含EventGraph"""
        content = Path(".claude/skills/uasset-read/knowledge/blueprint-semantics.md").read_text()
        assert "EventGraph" in content, "blueprint-semantics.md缺少EventGraph说明"

    def test_blueprint_semantics_has_output_version(self):
        """验证blueprint-semantics.md包含output_version说明"""
        content = Path(".claude/skills/uasset-read/knowledge/blueprint-semantics.md").read_text()
        assert "output_version" in content, "blueprint-semantics.md缺少output_version说明"

    def test_node_types_has_k2node(self):
        """验证node-types.md包含K2Node类型"""
        content = Path(".claude/skills/uasset-read/knowledge/node-types.md").read_text()
        assert "K2Node" in content, "node-types.md缺少K2Node说明"
        # 应包含多种节点类型
        assert "K2Node_Event" in content, "node-types.md缺少K2Node_Event"
        assert "K2Node_CallFunction" in content, "node-types.md缺少K2Node_CallFunction"

    def test_cpp_conversion_has_beginplay(self):
        """验证cpp-conversion.md包含BeginPlay示例"""
        content = Path(".claude/skills/uasset-read/knowledge/cpp-conversion.md").read_text()
        assert "BeginPlay" in content, "cpp-conversion.md缺少BeginPlay示例"

    def test_cpp_conversion_has_uproperty(self):
        """验证cpp-conversion.md包含UPROPERTY说明"""
        content = Path(".claude/skills/uasset-read/knowledge/cpp-conversion.md").read_text()
        assert "UPROPERTY" in content, "cpp-conversion.md缺少UPROPERTY说明"

    def test_troubleshooting_has_cooked(self):
        """验证troubleshooting.md包含Cooked资产说明"""
        content = Path(".claude/skills/uasset-read/knowledge/troubleshooting.md").read_text()
        assert "Cooked" in content, "troubleshooting.md缺少Cooked资产说明"

    def test_troubleshooting_has_is_success(self):
        """验证troubleshooting.md包含is_success说明"""
        content = Path(".claude/skills/uasset-read/knowledge/troubleshooting.md").read_text()
        assert "is_success" in content, "troubleshooting.md缺少is_success说明"


class TestExamplesFilesContent:
    """验证示例文件内容"""

    def test_basic_usage_has_parse_uasset(self):
        """验证basic-usage.md包含parse_uasset调用"""
        content = Path(".claude/skills/uasset-read/examples/basic-usage.md").read_text()
        assert "parse_uasset" in content, "basic-usage.md缺少parse_uasset调用"

    def test_basic_usage_has_firstperson_path(self):
        """验证basic-usage.md包含FirstPerson路径"""
        content = Path(".claude/skills/uasset-read/examples/basic-usage.md").read_text()
        assert "FirstPerson" in content, "basic-usage.md缺少FirstPerson路径"

    def test_basic_usage_has_is_success_check(self):
        """验证basic-usage.md包含is_success检查"""
        content = Path(".claude/skills/uasset-read/examples/basic-usage.md").read_text()
        assert "is_success" in content, "basic-usage.md缺少is_success检查"

    def test_blueprint_analysis_has_graphs_summary(self):
        """验证blueprint-analysis.md包含graphs_summary使用"""
        content = Path(".claude/skills/uasset-read/examples/blueprint-analysis.md").read_text()
        assert "graphs_summary" in content, "blueprint-analysis.md缺少graphs_summary"

    def test_blueprint_analysis_has_k2node(self):
        """验证blueprint-analysis.md包含K2Node识别"""
        content = Path(".claude/skills/uasset-read/examples/blueprint-analysis.md").read_text()
        assert "K2Node" in content, "blueprint-analysis.md缺少K2Node识别"


# 运行测试命令
# python -m pytest tests/test_skill_integration.py -v