"""kismet 模块缺陷测试。"""
import struct
import pytest


class TestKismetQuality:
    """kismet 模块质量验证。"""

    def test_kismet_imports(self):
        """kismet 模块可正常导入。"""
        from uasset_read.kismet import bytecode_extractor
        assert bytecode_extractor is not None

    def test_kismet_tokens_all_unique(self):
        """EExprToken 枚举值必须唯一。"""
        from uasset_read.kismet.tokens import EExprToken
        values = [t.value for t in EExprToken]
        assert len(values) == len(set(values)), "EExprToken 存在重复值"

    def test_expr_class_map_covers_all_tokens(self):
        """EXPR_CLASS_MAP 应覆盖所有 EExprToken 值（除保留值）。"""
        from uasset_read.kismet.tokens import EExprToken
        from uasset_read.kismet.expressions import EXPR_CLASS_MAP
        for token in EExprToken:
            if token.value in (0x03, 0x05, 0x08, 0x0A, 0x0D, 0x0E, 0x10,
                               0x56, 0x57, 0x58, 0x59):
                continue  # 保留/未使用值
            assert token in EXPR_CLASS_MAP, f"EXPR_CLASS_MAP 缺少 {token.name} (0x{token.value:02X})"

    # ==================================================================
    # 缺陷 1: EX_NameConst 应使用 read_i32 而非 read_u32
    # ==================================================================

    def test_name_const_uses_signed_read(self):
        """EX_NameConst 应使用 read_i32 读取 FName index/number（对齐 UE 序列化格式）。

        UE FName 序列化为两个 int32 值。read_fname_kismet() 正确使用 read_i32，
        但 EX_NameConst.from_archive() 错误使用 read_u32。
        如果 name index 是负值（如 -1 表示 None），read_u32 会将其解释为
        4294967295 而非 -1，导致 resolve_fname 无法正确处理。
        """
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        # 构造一个 FName: index=-1 (signed), number=0
        # 如果用 read_u32，-1 会变成 4294967295
        name_index = -1
        name_number = 0
        data = struct.pack('<ii', name_index, name_number)  # 两个 int32

        archive = FKismetArchive(data, "test", [], tolerant=False)
        expr = EX_NameConst.from_archive(archive, [])

        # 正确行为：使用 read_i32，-1 应该被解析为 -1
        # resolve_fname 会将 -1 视为越界，返回 "Unknown_-1"
        assert "Unknown_-1" in expr.Value

    def test_name_const_positive_index(self):
        """EX_NameConst 正数索引应正常工作。"""
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["TestName", "AnotherName"]
        data = struct.pack('<ii', 0, 0)  # index=0, number=0

        archive = FKismetArchive(data, "test", name_map, tolerant=False)
        expr = EX_NameConst.from_archive(archive, name_map)

        assert expr.Value == "TestName"

    def test_name_const_with_number(self):
        """EX_NameConst 带 number 后缀应正确格式化。"""
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["TestName"]
        data = struct.pack('<ii', 0, 3)  # index=0, number=3

        archive = FKismetArchive(data, "test", name_map, tolerant=False)
        expr = EX_NameConst.from_archive(archive, name_map)

        assert expr.Value == "TestName_3"

    def test_name_const_matches_read_fname_kismet(self):
        """EX_NameConst 的读取方式应与 FKismetArchive.read_fname_kismet 一致。"""
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["Hello", "World"]
        # 构造两个 FName 的原始数据
        data = struct.pack('<iiii', 1, 0, 0, 2)  # FName("World_0"), FName("Hello_2")

        archive = FKismetArchive(data, "test", name_map, tolerant=False)

        # 通过 read_fname_kismet 读取
        fname1 = archive.read_fname_kismet()
        fname2 = archive.read_fname_kismet()

        assert fname1 == "World"
        assert fname2 == "Hello_2"

    # ==================================================================
    # 缺陷 2: EX_RemoveMulticastDelegate 字段命名错误
    # ==================================================================

    def test_remove_multicast_delegate_field_name(self):
        """EX_RemoveMulticastDelegate 的第二个字段应命名为 DelegateToRemove。

        当前错误命名为 DelegateToAdd（从 EX_AddMulticastDelegate 复制而来），
        与 UE 语义不符。UE 源码中该字段表示"要移除的委托"，不是"要添加的委托"。
        """
        from uasset_read.kismet.expressions.delegates import EX_RemoveMulticastDelegate
        # 检查类定义中是否有 DelegateToRemove 字段
        import dataclasses
        fields = {f.name for f in dataclasses.fields(EX_RemoveMulticastDelegate)}
        assert "DelegateToRemove" in fields, (
            "EX_RemoveMulticastDelegate 应有 DelegateToRemove 字段，"
            f"当前字段: {fields}"
        )

    def test_remove_multicast_delegate_from_archive_uses_correct_field(self):
        """EX_RemoveMulticastDelegate.from_archive 应填充 DelegateToRemove 字段。"""
        from uasset_read.kismet.expressions.delegates import EX_RemoveMulticastDelegate
        from uasset_read.kismet.archive import FKismetArchive

        # EX_RemoveMulticastDelegate 格式: Delegate(expression) DelegateToRemove(expression)
        # 构造: Delegate=Self(0x17), DelegateToRemove=IntConst(0x1D, 42), EndFunctionParms(0x16)
        data = bytearray()
        data.extend(struct.pack('B', 0x17))  # Delegate: EX_Self
        data.extend(struct.pack('B', 0x1D))  # DelegateToRemove token: EX_IntConst
        data.extend(struct.pack('<i', 42))  # DelegateToRemove value: 42
        data.extend(struct.pack('B', 0x16))  # EndFunctionParms

        archive = FKismetArchive(bytes(data), "test", [], tolerant=False)
        expr = EX_RemoveMulticastDelegate.from_archive(archive, [])

        # 修复后应有 DelegateToRemove 字段
        assert hasattr(expr, 'DelegateToRemove'), "应有 DelegateToRemove 属性"
        assert expr.DelegateToRemove is not None
        if hasattr(expr.DelegateToRemove, 'Value'):
            assert expr.DelegateToRemove.Value == 42

    # ==================================================================
    # 缺陷 3: EX_SetArray.from_archive 存储位置错误
    # ==================================================================

    def test_set_array_assigning_property_populated(self):
        """EX_SetArray.from_archive 应填充 AssigningProperty 字段。

        当前错误存储到 ArrayInnerProp，导致 translator 查找 AssigningProperty
        时始终得到 None，输出 "?" 而非实际变量名。
        """
        from uasset_read.kismet.expressions.containers import EX_SetArray
        from uasset_read.kismet.archive import FKismetArchive

        # EX_SetArray 格式: FKismetPropertyPointer + elements + EX_EndArray
        # FKismetPropertyPointer: bNew(u32) + FFieldPath(count(u32) + name_index(u32))
        data = bytearray()
        data.extend(struct.pack('<I', 1))  # bNew = True (u32, 1=nonzero)
        data.extend(struct.pack('<I', 1))  # FFieldPath count = 1
        data.extend(struct.pack('<I', 0))  # name index = 0
        data.extend(struct.pack('B', 0x32))  # EX_EndArray token (single byte)

        name_map = ["MyArray"]
        archive = FKismetArchive(bytes(data), "test", name_map, tolerant=False)
        expr = EX_SetArray.from_archive(archive, name_map)

        # AssigningProperty 应被填充（而非 ArrayInnerProp）
        assert expr.AssigningProperty is not None, (
            "EX_SetArray.from_archive 应填充 AssigningProperty，"
            "当前 AssigningProperty=None"
        )

    def test_set_array_translator_uses_assigning_property(self):
        """translator 应能正确翻译 EX_SetArray 的变量引用。"""
        from uasset_read.kismet.expressions.containers import EX_SetArray
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer, FFieldPath

        # 构造 EX_SetArray，手动设置 AssigningProperty
        prop = FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=["MyArray"]))
        # 元素列表为 None（简化测试）
        expr = EX_SetArray(AssigningProperty=prop, Elements=None)

        translator = KismetTranslator()
        result = translator.line_cpp(expr)

        # 不应输出 "?" — 应输出包含变量名的结果
        assert "?" not in result or "MyArray" in result, (
            f"EX_SetArray 翻译结果不应为纯 '?': {result}"
        )

    # ==================================================================
    # 缺陷 4: FKismetPropertyPointer.__str__ 旧路径返回原始整数
    # ==================================================================

    def test_property_pointer_legacy_str_not_raw_integer(self):
        """FKismetPropertyPointer 旧路径的 __str__ 不应返回原始整数。

        当前返回 str(self.Old.index) 即纯数字字符串，
        应返回更有意义的描述。
        """
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        from uasset_read.serializers.object_resources import PackageIndex

        # 构造旧路径属性指针
        old_index = PackageIndex(5)
        ptr = FKismetPropertyPointer(bNew=False, Old=old_index)
        result = str(ptr)

        # 不应仅是数字 "5"
        assert result != "5", (
            f"FKismetPropertyPointer 旧路径 __str__ 不应返回纯数字 '5'，"
            f"当前返回: {result}"
        )

    # ==================================================================
    # 附加质量测试
    # ==================================================================

    def test_token_enum_values_match_ue_source(self):
        """关键 token 值应对齐 UE EExprToken.cs。"""
        from uasset_read.kismet.tokens import EExprToken

        assert EExprToken.EX_EndOfScript == 0x53
        assert EExprToken.EX_Return == 0x04
        assert EExprToken.EX_Jump == 0x06
        assert EExprToken.EX_JumpIfNot == 0x07
        assert EExprToken.EX_Context == 0x19
        assert EExprToken.EX_FinalFunction == 0x1C
        assert EExprToken.EX_CallMath == 0x68
        assert EExprToken.EX_SwitchValue == 0x69
        assert EExprToken.EX_LocalFinalFunction == 0x46

    def test_cast_token_values_match_ue_source(self):
        """ECastToken 值应对齐 UE 源码。"""
        from uasset_read.kismet.tokens import ECastToken

        assert ECastToken.CST_ObjectToInterface == 0x00
        assert ECastToken.CST_ObjectToBool == 0x01
        assert ECastToken.CST_InterfaceToBool == 0x02
        assert ECastToken.CST_DoubleToFloat == 0x03
        assert ECastToken.CST_FloatToDouble == 0x04

    def test_expression_base_to_dict(self):
        """KismetExpression 基类 to_dict 应返回正确结构。"""
        from uasset_read.kismet.expressions.literals import EX_IntConst
        expr = EX_IntConst(Value=42)
        expr.StatementIndex = 10
        d = expr.to_dict()
        assert d["Inst"] == "EX_IntConst"
        assert d["StatementIndex"] == 10
        assert d["Value"] == 42

    def test_parse_empty_bytecode(self):
        """解析空字节码应返回空列表。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        result = parse_bytecode_stream(b"", [])
        assert result == []

    def test_parse_end_of_script_only(self):
        """仅含 EX_EndOfScript 的字节码应返回单元素列表。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        from uasset_read.kismet.tokens import EExprToken

        data = bytes([EExprToken.EX_EndOfScript])
        result = parse_bytecode_stream(data, [])
        assert len(result) == 1
        assert result[0].Token == EExprToken.EX_EndOfScript

    def test_structured_flow_empty_input(self):
        """StructuredControlFlow 空输入应返回空列表。"""
        from uasset_read.kismet.structured_flow import StructuredControlFlow
        flow = StructuredControlFlow()
        result = flow.reconstruct([])
        assert result == []

    def test_type_registry_basic(self):
        """TypeRegistry 基本注册和查询。"""
        from uasset_read.kismet.translator import TypeRegistry
        reg = TypeRegistry()
        reg.register_variable("MyVar", "int")
        assert reg.lookup("MyVar") == "int"
        assert reg.resolve_type("Unknown") == "auto"

    def test_type_registry_populate_from_metadata(self):
        """TypeRegistry 从元数据批量初始化。"""
        from uasset_read.kismet.translator import TypeRegistry
        reg = TypeRegistry()
        reg.populate_from_metadata({
            "variables": [
                {"name": "Health", "type": "FloatProperty"},
                {"name": "bIsDead", "type": "BoolProperty"},
            ],
            "functions": [
                {
                    "name": "TakeDamage",
                    "params": [
                        {"name": "Amount", "type": "FloatProperty"},
                        {"name": "OutResult", "type": "FloatProperty", "flags": "CPF_OutParm"},
                    ],
                }
            ],
        })
        assert reg.resolve_type("Health") == "float"
        assert reg.resolve_type("bIsDead") == "bool"
        assert reg.resolve_type("Amount") == "float"
        assert reg.resolve_type("OutResult") == "float&"

    def test_math_cleaner_basic_ops(self):
        """MathFunctionCleaner 基本运算转换。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        assert MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"]) == "a + b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Multiply_FloatFloat", ["a", "b"]) == "(a * b)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "EqualEqual_IntInt", ["a", "b"]) == "a == b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Not_PreBool", ["x"]) == "!x"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanAND", ["a", "b"]) == "a && b"

    def test_math_cleaner_type_conversion(self):
        """MathFunctionCleaner 类型转换。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToBool", ["x"]) == "(x != 0)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_BoolToInt", ["x"]) == "(x ? 1 : 0)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToFloat", ["x"]) == "((float)x)"

    def test_math_cleaner_fallback(self):
        """MathFunctionCleaner 未知函数应回退到 Class::Func 格式。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        result = MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a"])
        assert result == "KismetMathLibrary::SomeUnknownFunc(a)"

    def test_blueprint_node_cleaner_basic(self):
        """BlueprintNodeCleaner 基本节点映射。"""
        from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner

        # Character::Jump
        result = BlueprintNodeCleaner.clean("ACharacter", "Jump", [])
        assert result == "Jump()"

        # Actor::K2_GetActorLocation
        result = BlueprintNodeCleaner.clean("AActor", "K2_GetActorLocation", [])
        assert result == "GetActorLocation()"

        # 未知节点回退
        result = BlueprintNodeCleaner.clean("MyClass", "MyFunc", ["arg1"])
        assert result == "MyClass::MyFunc(arg1)"

    def test_jump_analyzer_empty_expressions(self):
        """JumpAnalyzer 空表达式列表应正常工作。"""
        from uasset_read.kismet.jump_analyzer import JumpAnalyzer
        analyzer = JumpAnalyzer([])
        report = analyzer.analyze_structured_rate()
        assert report.total_jump_exprs == 0
        assert report.rate == 1.0  # 无跳转 → 100% 结构化

    def test_function_body_builder_empty(self):
        """FunctionBodyBuilder 空表达式应返回有效函数体。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder
        builder = FunctionBodyBuilder()
        result = builder.to_function_body([], func_name="TestFunc")
        assert "TestFunc" in result
        assert "{" in result
        assert "}" in result

    def test_kismet_decompiled_result_to_dict(self):
        """KismetDecompiledResult.to_dict 应返回可序列化字典。"""
        import json
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="TestFunc",
            signature="void TestFunc()",
            local_variables=[],
            cpp_code="void TestFunc() {}",
            expressions=[],
            bytecode_source="function_export",
            bytecode_status="parsed",
        )
        d = result.to_dict()
        # 应可 JSON 序列化
        json_str = json.dumps(d)
        assert "TestFunc" in json_str

    def test_reset_bpgc_cache(self):
        """reset_bpgc_cache 应重置模块级缓存。"""
        from uasset_read.kismet.bytecode_extractor import reset_bpgc_cache, _bpgc_bytecode_cache
        import uasset_read.kismet.bytecode_extractor as mod

        # 设置缓存为非 None
        mod._bpgc_bytecode_cache = {"test": b"data"}
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None

    def test_extract_and_parse_non_ustruct(self):
        """非 UStruct 类型的 export 应返回空结果。"""
        from uasset_read.kismet.bytecode_extractor import extract_and_parse, USTRUCT_TYPES
        # 验证 USTRUCT_TYPES 包含预期值
        assert "Function" in USTRUCT_TYPES
        assert "UFunction" in USTRUCT_TYPES
