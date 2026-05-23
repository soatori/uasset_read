"""MathFunctionCleaner tests — Kismet library function beautification."""
from uasset_read.kismet.translator import MathFunctionCleaner


class TestMathArithmetic:
    """Test arithmetic function cleaning."""

    def test_add_int_int(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"]) == "a + b"

    def test_subtract(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Subtract_FloatFloat", ["a", "b"]) == "a - b"

    def test_multiply(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Multiply_FloatFloat", ["a", "b"]) == "(a * b)"

    def test_divide(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Divide_FloatFloat", ["a", "b"]) == "(a / b)"

    def test_percent(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Percent_IntInt", ["a", "b"]) == "(a % b)"

    def test_negate(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Negate_Float", ["a"]) == "-a"


class TestMathComparison:
    """Test comparison function cleaning."""

    def test_equal(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "EqualEqual_IntInt", ["a", "b"]) == "a == b"

    def test_not_equal(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "NotEqual_IntInt", ["a", "b"]) == "(a !== b)"

    def test_less(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Less_IntInt", ["a", "b"]) == "(a < b)"

    def test_less_equal(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "LessEqual_IntInt", ["a", "b"]) == "(a <= b)"

    def test_greater(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Greater_IntInt", ["a", "b"]) == "(a > b)"

    def test_greater_equal(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "GreaterEqual_IntInt", ["a", "b"]) == "(a >= b)"


class TestMathBoolean:
    """Test boolean function cleaning."""

    def test_boolean_and(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanAND", ["a", "b"]) == "a && b"

    def test_boolean_or(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanOR", ["a", "b"]) == "(a || b)"

    def test_boolean_nand(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanNAND", ["a", "b"]) == "!(a && b)"

    def test_boolean_nor(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanNOR", ["a", "b"]) == "!(a || b)"

    def test_boolean_xor(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanXOR", ["a", "b"]) == "a ^ b"

    def test_not_pre_bool(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Not_PreBool", ["a"]) == "!a"


class TestMathConversions:
    """Test type conversion cleaning."""

    def test_int_to_bool(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToBool", ["a"]) == "(a != 0)"

    def test_bool_to_int(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_BoolToInt", ["a"]) == "(a ? 1 : 0)"

    def test_bool_to_float(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_BoolToFloat", ["a"]) == "(a ? 1.0f : 0.0f)"

    def test_float_to_int(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_FloatToInt", ["a"]) == "((int32)a)"

    def test_int_to_float(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToFloat", ["a"]) == "((float)a)"


class TestMathSelect:
    """Test Select (ternary) cleaning."""

    def test_select(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Select_bool", ["a", "b", "cond"]) == "(cond ? a : b)"


class TestMathBreakers:
    """Test Break* functions (multi-line assignments)."""

    def test_break_vector(self):
        result = MathFunctionCleaner.clean("KismetMathLibrary", "BreakVector", ["v", "X", "Y", "Z"])
        assert "X = v.X" in result
        assert "Y = v.Y" in result
        assert "Z = v.Z" in result

    def test_break_rotator(self):
        result = MathFunctionCleaner.clean("KismetMathLibrary", "BreakRotator", ["r", "Roll", "Pitch", "Yaw"])
        assert "Roll = r.Roll" in result
        assert "Pitch = r.Pitch" in result
        assert "Yaw = r.Yaw" in result

    def test_break_transform(self):
        result = MathFunctionCleaner.clean("KismetMathLibrary", "BreakTransform", ["t", "loc", "rot", "scale"])
        assert "loc = t.Location" in result
        assert "rot = t.Rotation" in result
        assert "scale = t.Scale" in result


class TestMathConstructors:
    """Test Make* constructor cleaning."""

    def test_make_vector(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "MakeVector", ["x", "y", "z"]) == "FVector(x, y, z)"

    def test_make_rotator(self):
        assert MathFunctionCleaner.clean("KismetMathLibrary", "MakeRotator", ["p", "y", "r"]) == "FRotator(p, y, r)"

    def test_make_transform(self):
        result = MathFunctionCleaner.clean("KismetMathLibrary", "MakeTransform", ["loc", "rot", "scale"])
        assert result == "FTransform(loc, rot, scale)"


class TestMathFallback:
    """Test fallback for unmatched functions."""

    def test_unmatched_math(self):
        result = MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a", "b"])
        assert result == "KismetMathLibrary::SomeUnknownFunc(a, b)"


class TestStringLibrary:
    """Test KismetStringLibrary cleaning."""

    def test_concat_str_str(self):
        assert MathFunctionCleaner.clean("KismetStringLibrary", "Concat_StrStr", ["a", "b"]) == "a += b"

    def test_string_equal(self):
        assert MathFunctionCleaner.clean("KismetStringLibrary", "EqualEqual_StrStr", ["a", "b"]) == "a == b"

    def test_len(self):
        assert MathFunctionCleaner.clean("KismetStringLibrary", "Len", ["str"]) == "str.Length"

    def test_conv_bool_to_string(self):
        assert MathFunctionCleaner.clean("KismetStringLibrary", "Conv_BoolToString", ["a"]) == 'a ? "true" : "false"'


class TestArrayLibrary:
    """Test KismetArrayLibrary cleaning."""

    def test_array_length(self):
        assert MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Length", ["arr"]) == "arr.Length"

    def test_array_add(self):
        assert MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Add", ["arr", "item"]) == "arr.Add(item)"

    def test_array_contains(self):
        assert MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Contains", ["arr", "item"]) == "arr.Contains(item)"

    def test_array_clear(self):
        assert MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Clear", ["arr"]) == "arr.Clear()"


class TestMapLibrary:
    """Test BlueprintMapLibrary cleaning."""

    def test_map_length(self):
        assert MathFunctionCleaner.clean("BlueprintMapLibrary", "Map_Length", ["m"]) == "m.Length"

    def test_map_get(self):
        assert MathFunctionCleaner.clean("BlueprintMapLibrary", "Map_Get", ["m", "k", "v"]) == "v = m[k]"

    def test_map_contains(self):
        assert MathFunctionCleaner.clean("BlueprintMapLibrary", "Map_Contains", ["m", "k"]) == "m.Contains(k)"


class TestSetLibrary:
    """Test BlueprintSetLibrary cleaning."""

    def test_set_add(self):
        assert MathFunctionCleaner.clean("BlueprintSetLibrary", "Set_AddItems", ["s", "item"]) == "s.Add(item)"

    def test_set_clear(self):
        assert MathFunctionCleaner.clean("BlueprintSetLibrary", "Set_Clear", ["s"]) == "s.Clear()"

    def test_set_is_empty(self):
        assert MathFunctionCleaner.clean("BlueprintSetLibrary", "Set_IsEmpty", ["s"]) == "s.Length == 0"
