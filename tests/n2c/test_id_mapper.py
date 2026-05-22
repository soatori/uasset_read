"""N2CIdMapper tests — GUID ↔ 短 ID 双向映射。"""
import pytest

from uasset_read.n2c.id_mapper import N2CIdMapper


class TestN2CIdMapperRegister:
    """N2CIdMapper.register() tests."""

    def test_first_registration(self):
        mapper = N2CIdMapper()
        assert mapper.register("GUID-A") == "N1"

    def test_second_registration(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        assert mapper.register("GUID-B") == "N2"

    def test_idempotent_registration(self):
        mapper = N2CIdMapper()
        result1 = mapper.register("GUID-A")
        result2 = mapper.register("GUID-A")
        assert result1 == result2 == "N1"

    def test_registration_does_not_overwrite(self):
        """T-70-01: 重复 GUID 不允许覆盖已有映射。"""
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        mapper.register("GUID-B")
        # Re-registering GUID-A should still return N1, not N3
        assert mapper.register("GUID-A") == "N1"
        assert mapper.register("GUID-B") == "N2"


class TestN2CIdMapperToShort:
    """N2CIdMapper.to_short() tests."""

    def test_registered_guid(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        assert mapper.to_short("GUID-A") == "N1"

    def test_unregistered_guid(self):
        mapper = N2CIdMapper()
        assert mapper.to_short("UNKNOWN") is None

    def test_multiple_guids(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        mapper.register("GUID-B")
        mapper.register("GUID-C")
        assert mapper.to_short("GUID-A") == "N1"
        assert mapper.to_short("GUID-B") == "N2"
        assert mapper.to_short("GUID-C") == "N3"


class TestN2CIdMapperToGuid:
    """N2CIdMapper.to_guid() tests."""

    def test_registered_short_id(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        assert mapper.to_guid("N1") == "GUID-A"

    def test_unregistered_short_id(self):
        mapper = N2CIdMapper()
        assert mapper.to_guid("N99") is None

    def test_bidirectional_consistency(self):
        mapper = N2CIdMapper()
        guid = "SOME-GUID-12345"
        short = mapper.register(guid)
        assert mapper.to_guid(short) == guid
        assert mapper.to_short(guid) == short


class TestN2CIdMapperReset:
    """N2CIdMapper.reset() tests."""

    def test_reset_clears_mappings(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        mapper.register("GUID-B")
        mapper.reset()
        assert mapper.to_short("GUID-A") is None
        assert mapper.to_guid("N1") is None
        assert mapper.to_guid("N2") is None

    def test_reset_allows_re_registration(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        mapper.reset()
        # After reset, GUID-A should get N1 again
        assert mapper.register("GUID-A") == "N1"

    def test_reset_counter(self):
        mapper = N2CIdMapper()
        mapper.register("GUID-A")
        mapper.register("GUID-B")
        mapper.reset()
        # After reset, counter should start from 0 again
        mapper.register("GUID-C")
        assert mapper.register("GUID-D") == "N2"
