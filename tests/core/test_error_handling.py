import pytest
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.exceptions import ParseError


class MockResult:
    def __init__(self):
        self.errors = []


def test_tolerant_parse_no_error():
    result = MockResult()
    with tolerant_parse(result, "test"):
        pass
    assert result.errors == []


def test_tolerant_parse_with_error():
    result = MockResult()
    with pytest.raises(ParseError):
        with tolerant_parse(result, "test"):
            raise ParseError("test error")
    assert len(result.errors) == 1
    assert "test error" in result.errors[0]
