"""utils.py 单元测试"""

from uasset_read.core.utils import safe_str, safe_int, normalize_hex_guid


# --- safe_str ---

def test_safe_str_none():
    assert safe_str(None) == ""


def test_safe_str_default_override():
    assert safe_str(None, "N/A") == "N/A"


def test_safe_str_int():
    assert safe_str(42) == "42"


def test_safe_str_str():
    assert safe_str("hello") == "hello"


def test_safe_str_bool():
    assert safe_str(True) == "True"


def test_safe_str_float():
    assert safe_str(3.14) == "3.14"


# --- safe_int ---

def test_safe_int_none():
    assert safe_int(None) == 0


def test_safe_int_default_override():
    assert safe_int(None, -1) == -1


def test_safe_int_int():
    assert safe_int(42) == 42


def test_safe_int_str_valid():
    assert safe_int("123") == 123


def test_safe_int_str_invalid():
    assert safe_int("abc") == 0


def test_safe_int_str_invalid_with_default():
    assert safe_int("xyz", -99) == -99


def test_safe_int_bool_returns_default():
    """bool is subclass of int in Python, but the isinstance guard only allows int/str."""
    # Note: bool is a subclass of int, so isinstance(True, int) is True.
    # This means safe_int(True) returns 1 (True).
    assert safe_int(True) == 1


def test_safe_int_float_returns_default():
    assert safe_int(3.14) == 0


def test_safe_int_list_returns_default():
    assert safe_int([1, 2]) == 0


def test_safe_int_negative_str():
    assert safe_int("-5") == -5


def test_safe_int_empty_str():
    assert safe_int("") == 0


# --- normalize_hex_guid ---

def test_normalize_hex_guid_none():
    assert normalize_hex_guid(None) is None


def test_normalize_hex_guid_empty():
    result = normalize_hex_guid("")
    assert result == ""


def test_normalize_hex_guid_with_dashes():
    assert normalize_hex_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_without_dashes():
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_lowercase():
    assert normalize_hex_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_already_normalized():
    assert normalize_hex_guid("a1b2c3d4e5f67890abcdef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_mixed_case():
    """测试混合大小写 GUID 归一化为小写"""
    assert normalize_hex_guid("A1b2C3d4-E5f6-7890-aBcD-eF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_all_uppercase_no_dashes():
    """测试全大写无连字符 GUID 归一化为小写"""
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"
