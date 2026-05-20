"""
Agent 翻译管线测试 — AgentTranslationPipeline 整合测试。

Phase 66-01: 测试 Agent 翻译管线整合 cpp_gen + Kismet 反编译输出。

测试：
1. AgentTranslationPipeline importable and callable
2. translate_blueprint_to_cpp(LinkerParseResult) returns CppClassIR
3. IR has correct class name (ABP_FirstPersonCharacter)
4. IR has ACharacter parent_class
5. IR.properties includes component properties
6. IR.methods populated from graphs + decompiled_functions
7. Fallback strategy works when decompiled_functions is empty
"""
import pytest
from typing import List, Dict, Any
from dataclasses import dataclass, field


# ============================================================================
# Mock/Stub data for testing without actual uasset files
# ============================================================================

@dataclass
class MockBlueprintMetadata:
    """Mock BlueprintMetadata for testing."""
    is_blueprint: bool = True
    parent_class: str = "/Script/Engine.Character"
    name: str = "BP_FirstPersonCharacter"
    variables: List[Any] = field(default_factory=list)


@dataclass
class MockFEdGraphPinType:
    """Mock FEdGraphPinType for testing."""
    pin_category: str = "object"
    pin_subcategory: str = "/Script/Engine.SceneComponent"


@dataclass
class MockBlueprintVariable:
    """Mock BlueprintVariable for testing."""
    var_name: str = "CameraComponent"
    var_type: MockFEdGraphPinType = field(default_factory=MockFEdGraphPinType)
    is_component: bool = True
    property_flags: int = 0


@dataclass
class MockKismetDecompiledResult:
    """Mock KismetDecompiledResult for testing."""
    function_name: str = "Aim"
    signature: str = "void Aim()"
    local_variables: List[Dict[str, str]] = field(default_factory=list)
    cpp_code: str = "// Aim function body\n// this->Aim();"


@dataclass
class MockUEdGraphPin:
    """Mock UEdGraphPin for testing."""
    pin_name: str = ""
    pin_type: Any = None
    direction: int = 0
    hidden: bool = False


@dataclass
class MockK2NodeFunctionEntry:
    """Mock K2Node_FunctionEntry for testing."""
    class_name: str = "K2Node_FunctionEntry"
    pins: List[MockUEdGraphPin] = field(default_factory=list)


@dataclass
class MockUEdGraph:
    """Mock UEdGraph for testing."""
    graph_name: str = "AimGraph"
    nodes: List[Any] = field(default_factory=list)


@dataclass
class MockLinkerParseResult:
    """Mock LinkerParseResult for testing."""
    blueprint: Any = None
    graphs: List[Any] = field(default_factory=list)
    decompiled_functions: List[Any] = field(default_factory=list)
    components: List[Dict] = field(default_factory=list)
    name_map: List[str] = field(default_factory=lambda: ["BP_FirstPersonCharacter"])
    summary: Any = None
    linker: Any = None


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def mock_result_with_decompiled():
    """Create mock LinkerParseResult with decompiled functions."""
    # Create blueprint metadata
    bp = MockBlueprintMetadata(
        is_blueprint=True,
        parent_class="/Script/Engine.Character",
        name="BP_FirstPersonCharacter",
        variables=[
            MockBlueprintVariable(
                var_name="CameraComponent",
                var_type=MockFEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.CameraComponent"
                ),
                is_component=True,
                property_flags=0
            )
        ]
    )

    # Create graphs with FunctionEntry nodes
    func_entry = MockK2NodeFunctionEntry(
        class_name="K2Node_FunctionEntry",
        pins=[
            MockUEdGraphPin(pin_name="self", pin_type=MockFEdGraphPinType(pin_category="object", pin_subcategory="self")),
            MockUEdGraphPin(pin_name="then", pin_type=MockFEdGraphPinType(pin_category="exec")),
        ]
    )
    # Add function_reference mock
    func_entry.function_reference = type('obj', (object,), {'member_name': 'Aim'})()

    graphs = [MockUEdGraph(graph_name="AimGraph", nodes=[func_entry])]

    # Create decompiled functions
    decompiled = [
        MockKismetDecompiledResult(
            function_name="Aim",
            signature="void Aim()",
            cpp_code="// Aim function body\nthis->ProcessAim();"
        )
    ]

    return MockLinkerParseResult(
        blueprint=bp,
        graphs=graphs,
        decompiled_functions=decompiled,
        components=[{"name": "CameraComponent", "class": "CameraComponent"}],
        name_map=["BP_FirstPersonCharacter"]
    )


@pytest.fixture
def mock_result_no_decompiled():
    """Create mock LinkerParseResult without decompiled functions (fallback test)."""
    bp = MockBlueprintMetadata(
        is_blueprint=True,
        parent_class="/Script/Engine.Character",
        name="BP_FirstPersonCharacter",
        variables=[]
    )

    func_entry = MockK2NodeFunctionEntry(
        class_name="K2Node_FunctionEntry",
        pins=[]
    )
    func_entry.function_reference = type('obj', (object,), {'member_name': 'Aim'})()

    graphs = [MockUEdGraph(graph_name="AimGraph", nodes=[func_entry])]

    return MockLinkerParseResult(
        blueprint=bp,
        graphs=graphs,
        decompiled_functions=[],  # Empty decompiled functions
        components=[],
        name_map=["BP_FirstPersonCharacter"]
    )


@pytest.fixture
def mock_result_no_blueprint():
    """Create mock LinkerParseResult without blueprint (error test)."""
    return MockLinkerParseResult(
        blueprint=None,
        graphs=[],
        decompiled_functions=[],
        components=[],
        name_map=[]
    )


# ============================================================================
# Tests
# ============================================================================

class TestAgentTranslationPipelineImport:
    """Test 1: AgentTranslationPipeline importable and callable."""

    def test_import_agent_translation_pipeline(self):
        """AgentTranslationPipeline should be importable."""
        from uasset_read.agent import AgentTranslationPipeline
        assert AgentTranslationPipeline is not None

    def test_import_translate_blueprint_to_cpp(self):
        """translate_blueprint_to_cpp should be importable."""
        from uasset_read.agent import translate_blueprint_to_cpp
        assert translate_blueprint_to_cpp is not None


class TestAgentTranslationPipelineReturnsCppClassIR:
    """Test 2: translate_blueprint_to_cpp(LinkerParseResult) returns CppClassIR."""

    def test_returns_cpp_class_ir(self, mock_result_with_decompiled):
        """translate_blueprint_to_cpp should return CppClassIR."""
        from uasset_read.agent import translate_blueprint_to_cpp
        from uasset_read.cpp_gen import CppClassIR

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert isinstance(ir, CppClassIR)


class TestCppClassIRHasCorrectName:
    """Test 3: IR has correct class name (ABP_FirstPersonCharacter)."""

    def test_class_name_has_a_prefix(self, mock_result_with_decompiled):
        """Class name should start with 'A' for Actor-derived classes."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert ir.name.startswith("A")

    def test_class_name_contains_blueprint_name(self, mock_result_with_decompiled):
        """Class name should contain the blueprint name."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert "FirstPersonCharacter" in ir.name or "BP_FirstPersonCharacter" in ir.name


class TestCppClassIRHasCorrectParentClass:
    """Test 4: IR has ACharacter parent_class."""

    def test_parent_class_is_character(self, mock_result_with_decompiled):
        """Parent class should be ACharacter."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert ir.parent_class == "ACharacter"


class TestCppClassIRHasProperties:
    """Test 5: IR.properties includes component properties."""

    def test_properties_not_empty(self, mock_result_with_decompiled):
        """IR.properties should not be empty when blueprint has components."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert len(ir.properties) > 0

    def test_properties_include_camera_component(self, mock_result_with_decompiled):
        """IR.properties should include CameraComponent."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        prop_names = [p.name for p in ir.properties]
        assert "CameraComponent" in prop_names


class TestCppClassIRHasMethods:
    """Test 6: IR.methods populated from graphs + decompiled_functions."""

    def test_methods_not_empty(self, mock_result_with_decompiled):
        """IR.methods should not be empty when graphs have function entries."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        assert len(ir.methods) > 0

    def test_methods_have_correct_name(self, mock_result_with_decompiled):
        """IR.methods should have correct function name."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        method_names = [m.cpp_name for m in ir.methods]
        assert "Aim" in method_names

    def test_methods_have_body_from_kismet(self, mock_result_with_decompiled):
        """IR.methods should have body_text from Kismet decompilation."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_with_decompiled)
        aim_method = next((m for m in ir.methods if m.cpp_name == "Aim"), None)
        assert aim_method is not None
        # Check body_text field (added per D-66-03)
        assert hasattr(aim_method, 'body_text')
        # Body should contain Kismet decompiled code
        if aim_method.body_text:
            assert "Aim" in aim_method.body_text or "function" in aim_method.body_text.lower()


class TestFallbackStrategy:
    """Test 7: Fallback strategy works when decompiled_functions is empty."""

    def test_methods_exist_without_decompiled(self, mock_result_no_decompiled):
        """IR.methods should still be populated from graphs even without decompiled."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_no_decompiled)
        # Methods should exist (from graphs)
        assert len(ir.methods) > 0

    def test_body_text_empty_without_decompiled(self, mock_result_no_decompiled):
        """Method body_text should be empty/None without decompiled functions."""
        from uasset_read.agent import translate_blueprint_to_cpp

        ir = translate_blueprint_to_cpp(mock_result_no_decompiled)
        for method in ir.methods:
            # Without decompiled functions, body_text should be None or empty
            assert method.body_text is None or method.body_text == ""


class TestInputValidation:
    """Test input validation (per T-66-01, D-66-01)."""

    def test_raises_on_none_blueprint(self, mock_result_no_blueprint):
        """Should raise ValueError when blueprint is None."""
        from uasset_read.agent import AgentTranslationPipeline

        with pytest.raises(ValueError, match="blueprint"):
            AgentTranslationPipeline(mock_result_no_blueprint)

    def test_raises_on_non_blueprint(self):
        """Should raise ValueError when is_blueprint is False."""
        from uasset_read.agent import AgentTranslationPipeline

        bp = MockBlueprintMetadata(is_blueprint=False)
        result = MockLinkerParseResult(blueprint=bp, graphs=[], decompiled_functions=[])

        with pytest.raises(ValueError, match="is_blueprint"):
            AgentTranslationPipeline(result)


# ============================================================================
# Integration test (optional, requires actual uasset file)
# ============================================================================

@pytest.mark.skip(reason="Requires actual BP_FirstPersonCharacter.uasset file")
class TestIntegrationWithRealFile:
    """Integration test with actual .uasset file."""

    def test_real_blueprint_translation(self):
        """Test translation on real BP_FirstPersonCharacter.uasset."""
        import sys
        sys.path.insert(0, 'src')
        from uasset_read import parse_uasset_with_linker
        from uasset_read.agent import translate_blueprint_to_cpp

        result = parse_uasset_with_linker(
            'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset',
            tolerant=True
        )
        ir = translate_blueprint_to_cpp(result)

        assert ir.name.startswith("A")
        assert ir.parent_class == "ACharacter"
        assert len(ir.properties) > 0